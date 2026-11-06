"""Minimal self-contained MQTT v3.1.1 broker for local E2E demonstrations.

Supports:
- CONNECT / CONNACK (including Last Will & Testament - LWT)
- PUBLISH / PUBACK (QoS 0 & QoS 1, retained messages)
- SUBSCRIBE / SUBACK (with '+' and '#' wildcard topic matching)
- PINGREQ / PINGRESP
- DISCONNECT (suppresses LWT; abrupt disconnect triggers LWT broadcast)
- Defensive rejection of malformed or non-MQTT (e.g. HTTP/browser) connections

Usage:
    python demo/local_broker.py --host 127.0.0.1 --port 1883
"""

import argparse
import asyncio
import logging
import os
import struct
from dataclasses import dataclass, field

logger = logging.getLogger("demo.broker")

MAX_PACKET_SIZE = 65536  # 64 KiB cap for demo broker packets


class MalformedMQTTPacketError(ValueError):
    """Raised when an incoming TCP stream sends non-MQTT or truncated packet data."""


def topic_matches_filter(topic: str, topic_filter: str) -> bool:
    """Evaluates MQTT v3.1.1 topic filter matching ('+' and '#')."""
    t_parts = topic.split("/")
    f_parts = topic_filter.split("/")

    for i, f_part in enumerate(f_parts):
        if f_part == "#":
            return True
        if i >= len(t_parts):
            return False
        if f_part != "+" and f_part != t_parts[i]:
            return False

    return len(t_parts) == len(f_parts)


def encode_remaining_length(length: int) -> bytes:
    out = bytearray()
    while True:
        encoded_byte = length % 128
        length //= 128
        if length > 0:
            encoded_byte |= 0x80
        out.append(encoded_byte)
        if length == 0:
            break
    return bytes(out)


async def read_remaining_length(reader: asyncio.StreamReader) -> int:
    multiplier = 1
    value = 0
    while True:
        byte_data = await reader.readexactly(1)
        encoded_byte = byte_data[0]
        value += (encoded_byte & 127) * multiplier
        if (encoded_byte & 128) == 0:
            break
        multiplier *= 128
        if multiplier > 128 * 128 * 128:
            raise MalformedMQTTPacketError("Malformed MQTT Remaining Length header")
    if value > MAX_PACKET_SIZE:
        raise MalformedMQTTPacketError(
            f"Packet remaining length {value} exceeds demo limit ({MAX_PACKET_SIZE} bytes)"
        )
    return value


def unpack_u16(buf: bytes, offset: int, field_name: str = "uint16") -> tuple[int, int]:
    """Safely unpacks a big-endian uint16 from buf at offset with bounds checking."""
    if offset < 0 or offset + 2 > len(buf):
        raise MalformedMQTTPacketError(
            f"Truncated packet reading {field_name} at offset {offset} (buffer len={len(buf)})"
        )
    val = struct.unpack_from(">H", buf, offset)[0]
    return val, offset + 2


def read_utf8_string(buf: bytes, offset: int, field_name: str = "string") -> tuple[str, int]:
    """Safely reads a length-prefixed UTF-8 string with strict bounds validation."""
    str_len, offset = unpack_u16(buf, offset, f"{field_name} length")
    if offset + str_len > len(buf):
        raise MalformedMQTTPacketError(
            f"Truncated {field_name}: declared {str_len} bytes at offset {offset}, "
            f"but buffer only has {len(buf) - offset} bytes remaining"
        )
    try:
        val = buf[offset : offset + str_len].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MalformedMQTTPacketError(f"Invalid UTF-8 in {field_name}: {exc}") from exc
    return val, offset + str_len


def read_bytes_field(buf: bytes, offset: int, field_name: str = "bytes") -> tuple[bytes, int]:
    """Safely reads a length-prefixed binary field with strict bounds validation."""
    field_len, offset = unpack_u16(buf, offset, f"{field_name} length")
    if offset + field_len > len(buf):
        raise MalformedMQTTPacketError(
            f"Truncated {field_name}: declared {field_len} bytes at offset {offset}, "
            f"but buffer only has {len(buf) - offset} bytes remaining"
        )
    val = buf[offset : offset + field_len]
    return val, offset + field_len


def build_publish_packet(
    topic: str,
    payload: bytes,
    qos: int = 0,
    retain: bool = False,
    packet_id: int = 1,
) -> bytes:
    flags = (qos << 1) | (0x01 if retain else 0x00)
    header_byte = 0x30 | flags

    topic_bytes = topic.encode("utf-8")
    var_header = bytearray(struct.pack(">H", len(topic_bytes)) + topic_bytes)
    if qos > 0:
        var_header.extend(struct.pack(">H", packet_id))

    body = bytes(var_header) + payload
    return bytes([header_byte]) + encode_remaining_length(len(body)) + body


@dataclass
class ClientSession:
    client_id: str
    writer: asyncio.StreamWriter
    subscriptions: dict[str, int] = field(default_factory=dict)
    will_topic: str | None = None
    will_payload: bytes = b""
    will_qos: int = 0
    will_retain: bool = False
    clean_disconnect: bool = False


class LocalMQTTBroker:
    """Lightweight in-process MQTT v3.1.1 broker for local development and demos."""

    def __init__(self, host: str = "127.0.0.1", port: int = 1883):
        self.host = host
        self.port = port
        self.sessions: dict[str, ClientSession] = {}
        self.retained_messages: dict[str, tuple[bytes, int]] = {}
        self._server: asyncio.AbstractServer | None = None
        self._next_packet_id: int = 1

    def _allocate_packet_id(self) -> int:
        pid = self._next_packet_id
        self._next_packet_id = (self._next_packet_id % 65535) + 1
        return pid

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        sockets = self._server.sockets
        if sockets:
            self.port = sockets[0].getsockname()[1]
        logger.info("Local MQTT broker listening on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for session in list(self.sessions.values()):
            try:
                session.writer.close()
            except Exception:
                pass
        self.sessions.clear()
        logger.info("Local MQTT broker stopped")

    async def _broadcast_message(
        self, topic: str, payload: bytes, qos: int, retain: bool
    ) -> None:
        if retain:
            if payload:
                self.retained_messages[topic] = (payload, qos)
            else:
                self.retained_messages.pop(topic, None)

        for session in list(self.sessions.values()):
            matched_qos: int | None = None
            for sub_filter, sub_qos in session.subscriptions.items():
                if topic_matches_filter(topic, sub_filter):
                    matched_qos = (
                        sub_qos
                        if matched_qos is None
                        else max(matched_qos, sub_qos)
                    )
            if matched_qos is not None:
                deliver_qos = min(qos, matched_qos)
                pkt = build_publish_packet(
                    topic=topic,
                    payload=payload,
                    qos=deliver_qos,
                    retain=False,
                    packet_id=self._allocate_packet_id(),
                )
                try:
                    session.writer.write(pkt)
                    await session.writer.drain()
                except Exception:
                    pass

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        session: ClientSession | None = None
        peer = writer.get_extra_info("peername")
        try:
            while True:
                first_byte_data = await reader.readexactly(1)
                first_byte = first_byte_data[0]
                packet_type = (first_byte & 0xF0) >> 4
                flags = first_byte & 0x0F

                # First packet on a new TCP connection MUST be MQTT CONNECT (0x10)
                if session is None and first_byte != 0x10:
                    raise MalformedMQTTPacketError(
                        f"Expected MQTT CONNECT (0x10) as first packet from {peer}, "
                        f"got byte 0x{first_byte:02x} (non-MQTT traffic)"
                    )

                if packet_type not in (1, 3, 4, 8, 10, 12, 14):
                    raise MalformedMQTTPacketError(
                        f"Unsupported or invalid MQTT packet_type={packet_type} (byte=0x{first_byte:02x})"
                    )

                rem_len = await read_remaining_length(reader)
                body = await reader.readexactly(rem_len) if rem_len > 0 else b""

                if packet_type == 1:  # CONNECT
                    if session is not None:
                        raise MalformedMQTTPacketError("Duplicate CONNECT packet on active session")

                    proto_name, offset = read_utf8_string(body, 0, "protocol_name")
                    if proto_name not in ("MQTT", "MQIsdp"):
                        raise MalformedMQTTPacketError(
                            f"Unsupported protocol name '{proto_name}' (expected 'MQTT')"
                        )

                    if offset + 4 > len(body):
                        raise MalformedMQTTPacketError(
                            "Truncated CONNECT variable header (missing level/flags/keepalive)"
                        )
                    _proto_level = body[offset]
                    connect_flags = body[offset + 1]
                    _keep_alive, _ = unpack_u16(body, offset + 2, "keep_alive")
                    offset += 4

                    client_id, offset = read_utf8_string(body, offset, "client_id")
                    if not client_id:
                        client_id = f"anon-{id(writer)}"

                    will_flag = bool(connect_flags & 0x04)
                    will_qos = (connect_flags >> 3) & 0x03
                    if will_qos not in (0, 1, 2):
                        raise MalformedMQTTPacketError(f"Invalid will_qos={will_qos}")
                    will_retain = bool(connect_flags & 0x20)
                    will_topic = None
                    will_payload = b""

                    if will_flag:
                        will_topic, offset = read_utf8_string(body, offset, "will_topic")
                        will_payload, offset = read_bytes_field(body, offset, "will_payload")

                    session = ClientSession(
                        client_id=client_id,
                        writer=writer,
                        will_topic=will_topic,
                        will_payload=will_payload,
                        will_qos=will_qos,
                        will_retain=will_retain,
                    )
                    self.sessions[client_id] = session
                    logger.info("[BROKER] Client connected: %s (LWT=%s)", client_id, will_topic)

                    # Send CONNACK (0x20, len=2, flags=0, rc=0)
                    writer.write(b"\x20\x02\x00\x00")
                    await writer.drain()

                elif packet_type == 3:  # PUBLISH
                    qos = (flags >> 1) & 0x03
                    if qos > 2:
                        raise MalformedMQTTPacketError(f"Invalid PUBLISH QoS={qos}")
                    retain = bool(flags & 0x01)
                    topic, offset = read_utf8_string(body, 0, "publish_topic")
                    if not topic:
                        raise MalformedMQTTPacketError("Empty PUBLISH topic is not allowed")
                    packet_id = 0
                    if qos > 0:
                        packet_id, offset = unpack_u16(body, offset, "packet_id")
                    payload = body[offset:]

                    if qos == 1:
                        # Send PUBACK
                        writer.write(b"\x40\x02" + struct.pack(">H", packet_id))
                        await writer.drain()

                    logger.info(
                        "[BROKER] PUBLISH from %s -> %s (%d bytes, retain=%s)",
                        session.client_id if session else "unknown",
                        topic,
                        len(payload),
                        retain,
                    )
                    await self._broadcast_message(topic, payload, qos, retain)

                elif packet_type == 4:  # PUBACK
                    if len(body) < 2:
                        raise MalformedMQTTPacketError("Truncated PUBACK packet")

                elif packet_type == 8:  # SUBSCRIBE
                    packet_id, offset = unpack_u16(body, 0, "subscribe_packet_id")
                    if offset >= len(body):
                        raise MalformedMQTTPacketError("SUBSCRIBE packet contains no topic filters")
                    granted_qos = bytearray()
                    new_filters: list[tuple[str, int]] = []

                    while offset < len(body):
                        sub_filter, offset = read_utf8_string(body, offset, "topic_filter")
                        if offset >= len(body):
                            raise MalformedMQTTPacketError(
                                "Truncated SUBSCRIBE packet (missing requested QoS byte)"
                            )
                        req_qos = body[offset] & 0x03
                        offset += 1
                        if session:
                            session.subscriptions[sub_filter] = req_qos
                        granted_qos.append(req_qos)
                        new_filters.append((sub_filter, req_qos))
                        logger.info(
                            "[BROKER] SUBSCRIBE %s -> %s (QoS %d)",
                            session.client_id if session else "unknown",
                            sub_filter,
                            req_qos,
                        )

                    # Send SUBACK
                    suback_body = struct.pack(">H", packet_id) + bytes(granted_qos)
                    writer.write(
                        b"\x90" + encode_remaining_length(len(suback_body)) + suback_body
                    )
                    await writer.drain()

                    # Deliver matching retained messages
                    for sub_filter, sub_qos in new_filters:
                        for r_topic, (r_payload, r_qos) in list(self.retained_messages.items()):
                            if topic_matches_filter(r_topic, sub_filter):
                                pkt = build_publish_packet(
                                    topic=r_topic,
                                    payload=r_payload,
                                    qos=min(sub_qos, r_qos),
                                    retain=True,
                                    packet_id=self._allocate_packet_id(),
                                )
                                writer.write(pkt)
                                await writer.drain()

                elif packet_type == 10:  # UNSUBSCRIBE
                    packet_id, _ = unpack_u16(body, 0, "unsubscribe_packet_id")
                    writer.write(b"\xB0\x02" + struct.pack(">H", packet_id))
                    await writer.drain()

                elif packet_type == 12:  # PINGREQ
                    writer.write(b"\xD0\x00")
                    await writer.drain()

                elif packet_type == 14:  # DISCONNECT
                    if session:
                        session.clean_disconnect = True
                        logger.info("[BROKER] Clean DISCONNECT from %s", session.client_id)
                    break

        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        except MalformedMQTTPacketError as exc:
            logger.warning(
                "[BROKER] Rejecting malformed/non-MQTT client (%s): %s",
                session.client_id if session else peer,
                exc,
            )
        except Exception as exc:
            logger.warning(
                "[BROKER] Unexpected client error (%s): %s",
                session.client_id if session else peer,
                exc,
            )
        finally:
            if session:
                if self.sessions.get(session.client_id) is session:
                    del self.sessions[session.client_id]
                if not session.clean_disconnect and session.will_topic:
                    logger.info(
                        "[BROKER] Unclean disconnect for %s; publishing LWT to %s",
                        session.client_id,
                        session.will_topic,
                    )
                    await self._broadcast_message(
                        topic=session.will_topic,
                        payload=session.will_payload,
                        qos=session.will_qos,
                        retain=session.will_retain,
                    )
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


async def _run_forever(host: str, port: int) -> None:
    broker = LocalMQTTBroker(host=host, port=port)
    await broker.start()
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        await broker.stop()


def main() -> None:
    default_host = os.getenv("IOT_DEMO_BROKER_HOST", "127.0.0.1")
    default_port = int(os.getenv("IOT_DEMO_BROKER_PORT", "1883"))

    parser = argparse.ArgumentParser(description="SwiftletCare Local Demo MQTT Broker")
    parser.add_argument(
        "--host",
        default=default_host,
        help="Bind host (default: IOT_DEMO_BROKER_HOST or 127.0.0.1; use 0.0.0.0 for LAN ESP32)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=default_port,
        help="Bind port (default: IOT_DEMO_BROKER_PORT or 1883)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        asyncio.run(_run_forever(args.host, args.port))
    except KeyboardInterrupt:
        print("\n[BROKER] Stopped by user.")


if __name__ == "__main__":
    main()
