"""RabbitMQ topic exchange producer sink for AI outputs (AI-FR-008, AI-FR-009, AI-NFR-002, AI-NFR-006).

Traffic Segregation Rules:
- `AIEvent` (`PREDATOR_DETECTED`) -> Priority 0, routing key `ai.predator.detected` (consumed by Notification Queue).
- `CountUpdate` -> Priority 10, routing key `ai.count.updated` when `publish_counts=True` (consumed by Persistence/Analytics Queue).
- `CameraRuntimeStatus` -> Priority 20, routing key `ai.camera.status` only when `publish_status=True` (default False).
- `DetectionResult` -> Strict NO-OP (kept on AI REST API & WebSocket only).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import json
import logging
import os
import queue
import threading
import time
from typing import Any, Callable, Dict, Optional

try:
    import pika  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - optional at import time for offline environments
    pika = None  # type: ignore[assignment]

from app.runtime.camera_pipeline import CameraPipeline
from app.runtime.sink import BaseRuntimeSink
from app.schemas.canonical import (
    AIEvent,
    CameraRuntimeStatus,
    CountUpdate,
    DetectionResult,
)

log = logging.getLogger("swiftletcare.ai.rabbitmq_sink")

DEFAULT_ROUTING_KEYS: Dict[str, str] = {
    "predator_detected": "ai.predator.detected",
    "count_updated": "ai.count.updated",
    "camera_status": "ai.camera.status",
}

PublishFn = Callable[[str, str, Dict[str, Any], Dict[str, Any]], None]


def _parse_bool_env(raw: Optional[str], default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes")


@dataclass(order=True)
class _RMQQueueItem:
    priority: int
    timestamp: float
    seq: int
    routing_key: str = field(compare=False)
    payload: Dict[str, Any] = field(compare=False)
    headers: Dict[str, Any] = field(compare=False)


class RabbitMQRuntimeSink(BaseRuntimeSink):
    """Non-blocking RabbitMQ producer sink publishing canonical AI events & counts to a topic exchange."""

    def __init__(
        self,
        url: str = "amqp://guest:guest@localhost:5672/%2F",
        exchange: str = "swiftletcare.ai",
        exchange_type: str = "topic",
        durable: bool = True,
        routing_keys: Optional[Dict[str, str]] = None,
        enabled: bool = True,
        publish_counts: bool = True,
        publish_status: bool = False,
        max_retries: int = 2,
        max_queue_size: int = 200,
        publish_fn: Optional[PublishFn] = None,
    ) -> None:
        self.url = str(url).strip() or "amqp://guest:guest@localhost:5672/%2F"
        self.exchange = str(exchange).strip() or "swiftletcare.ai"
        self.exchange_type = str(exchange_type).strip() or "topic"
        self.durable = bool(durable)
        self.routing_keys = {**DEFAULT_ROUTING_KEYS, **(routing_keys or {})}
        self.enabled = bool(enabled)
        self.publish_counts = bool(publish_counts)
        self.publish_status = bool(publish_status)
        self.max_retries = max(0, int(max_retries))
        self._publish_fn = publish_fn

        self._queue: queue.PriorityQueue[_RMQQueueItem] = queue.PriorityQueue(maxsize=max_queue_size)
        self._seq_counter = 0
        self._stop_event = threading.Event()
        self._closed = False
        self._in_flight = False

        self._connection: Any = None
        self._channel: Any = None
        self._exchange_declared = False

        self._worker_thread: Optional[threading.Thread] = None
        if self.enabled:
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="RabbitMQRuntimeSinkWorker",
                daemon=True,
            )
            self._worker_thread.start()

    @classmethod
    def from_config(
        cls,
        cfg: Dict[str, Any],
        publish_fn: Optional[PublishFn] = None,
    ) -> "RabbitMQRuntimeSink":
        """Construct RabbitMQRuntimeSink reading from `rabbitmq:` config with environment overrides."""
        rmq_cfg = dict(cfg.get("rabbitmq", {}))

        enabled = _parse_bool_env(
            os.getenv("AI_RABBITMQ_ENABLED"),
            bool(rmq_cfg.get("enabled", False)),
        )
        url = str(
            os.getenv("AI_RABBITMQ_URL")
            or rmq_cfg.get("url")
            or "amqp://guest:guest@localhost:5672/%2F"
        )
        exchange = str(
            os.getenv("AI_RABBITMQ_EXCHANGE")
            or rmq_cfg.get("exchange")
            or "swiftletcare.ai"
        )
        exchange_type = str(rmq_cfg.get("exchange_type", "topic"))
        durable = bool(rmq_cfg.get("durable", True))
        max_retries = int(rmq_cfg.get("max_retries", 2))

        rk_raw = rmq_cfg.get("routing_keys") or {}
        routing_keys = {k: str(v) for k, v in rk_raw.items()}

        publish_counts = _parse_bool_env(
            os.getenv("AI_RABBITMQ_PUBLISH_COUNTS"),
            bool(rmq_cfg.get("publish_counts", True)),
        )
        publish_status = _parse_bool_env(
            os.getenv("AI_RABBITMQ_PUBLISH_STATUS"),
            bool(rmq_cfg.get("publish_status", False)),
        )

        return cls(
            url=url,
            exchange=exchange,
            exchange_type=exchange_type,
            durable=durable,
            routing_keys=routing_keys,
            enabled=enabled,
            publish_counts=publish_counts,
            publish_status=publish_status,
            max_retries=max_retries,
            publish_fn=publish_fn,
        )

    def _enqueue(
        self,
        priority: int,
        routing_key: str,
        payload: Dict[str, Any],
        headers: Dict[str, Any],
    ) -> None:
        """Enqueue message with priority eviction protection for priority=0 AIEvent."""
        if not self.enabled or self._closed:
            return

        item = _RMQQueueItem(
            priority=priority,
            timestamp=time.time(),
            seq=self._seq_counter,
            routing_key=routing_key,
            payload=payload,
            headers=headers,
        )
        self._seq_counter += 1

        try:
            self._queue.put_nowait(item)
        except queue.Full:
            if priority == 0:  # Urgent AIEvent (PREDATOR_DETECTED) evicts lower priority count/status
                with self._queue.mutex:
                    worst_idx = -1
                    worst_prio = -1
                    for idx, q_item in enumerate(self._queue.queue):
                        if q_item.priority > worst_prio:
                            worst_prio = q_item.priority
                            worst_idx = idx
                    if worst_idx >= 0 and worst_prio > 0:
                        del self._queue.queue[worst_idx]
                        heapq.heapify(self._queue.queue)
                        heapq.heappush(self._queue.queue, item)
                        self._queue.not_empty.notify()
                        return
            log.warning("RabbitMQRuntimeSink queue is full; dropping message for %s", routing_key)

    def on_event(self, event: AIEvent) -> None:
        """Publish immediate predator detection event with priority 0 and key `ai.predator.detected`."""
        payload = event.to_dict()
        payload["snapshot"] = CameraPipeline.normalize_snapshot_ref(event.snapshot)
        routing_key = self.routing_keys.get(
            "predator_detected",
            DEFAULT_ROUTING_KEYS["predator_detected"],
        )
        headers = {
            "eventType": str(event.eventType),
            "cameraId": str(event.cameraId),
        }
        self._enqueue(priority=0, routing_key=routing_key, payload=payload, headers=headers)

    def on_count(self, update: CountUpdate) -> None:
        """Publish periodic count update with priority 10 and key `ai.count.updated` if enabled."""
        if not self.publish_counts:
            return
        routing_key = self.routing_keys.get(
            "count_updated",
            DEFAULT_ROUTING_KEYS["count_updated"],
        )
        headers = {
            "eventType": "COUNT_UPDATED",
            "cameraId": str(update.cameraId),
        }
        self._enqueue(priority=10, routing_key=routing_key, payload=update.to_dict(), headers=headers)

    def on_status(self, status: CameraRuntimeStatus) -> None:
        """Publish camera runtime status only when `publish_status=True` (default False)."""
        if not self.publish_status:
            return
        routing_key = self.routing_keys.get(
            "camera_status",
            DEFAULT_ROUTING_KEYS["camera_status"],
        )
        headers = {
            "eventType": "CAMERA_STATUS",
            "cameraId": str(status.cameraId),
        }
        self._enqueue(priority=20, routing_key=routing_key, payload=status.to_dict(), headers=headers)

    def on_detection(self, result: DetectionResult) -> None:
        """NO-OP: Frame-level detections stay on AI REST/WebSocket only (AI-NFR-006)."""
        pass

    def _worker_loop(self) -> None:
        """Daemon worker loop draining PriorityQueue and publishing to RabbitMQ."""
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            self._in_flight = True
            try:
                self._publish_with_retry(item)
            finally:
                self._in_flight = False
                self._queue.task_done()

    def _ensure_amqp_channel(self) -> Any:
        """Ensure an active pika BlockingConnection and declared topic exchange."""
        if pika is None:
            raise RuntimeError("pika package is required for AMQP connection")

        if (
            self._connection is not None
            and getattr(self._connection, "is_open", False)
            and self._channel is not None
            and getattr(self._channel, "is_open", False)
        ):
            if not self._exchange_declared:
                self._channel.exchange_declare(
                    exchange=self.exchange,
                    exchange_type=self.exchange_type,
                    durable=self.durable,
                )
                self._exchange_declared = True
            return self._channel

        self._close_amqp_connection()
        params = pika.URLParameters(self.url)
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()
        self._channel.exchange_declare(
            exchange=self.exchange,
            exchange_type=self.exchange_type,
            durable=self.durable,
        )
        self._exchange_declared = True
        return self._channel

    def _close_amqp_connection(self) -> None:
        """Safely close open AMQP channel and connection."""
        self._exchange_declared = False
        if self._channel is not None:
            try:
                if getattr(self._channel, "is_open", False):
                    self._channel.close()
            except Exception:
                pass
            self._channel = None
        if self._connection is not None:
            try:
                if getattr(self._connection, "is_open", False):
                    self._connection.close()
            except Exception:
                pass
            self._connection = None

    def _publish_once(self, item: _RMQQueueItem) -> None:
        """Perform a single publish call via custom `publish_fn` or `pika`."""
        props_dict: Dict[str, Any] = {
            "content_type": "application/json",
            "delivery_mode": 2,
            "headers": dict(item.headers),
        }
        if self._publish_fn is not None:
            self._publish_fn(self.exchange, item.routing_key, item.payload, props_dict)
            return

        channel = self._ensure_amqp_channel()
        body = json.dumps(item.payload).encode("utf-8")
        properties = pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,
            headers=dict(item.headers),
        )
        channel.basic_publish(
            exchange=self.exchange,
            routing_key=item.routing_key,
            body=body,
            properties=properties,
        )

    def _publish_with_retry(self, item: _RMQQueueItem) -> None:
        """Publish item to exchange with exponential backoff retries; never raises."""
        max_attempts = 1 + self.max_retries
        attempts = 0

        while attempts < max_attempts and not self._stop_event.is_set():
            attempts += 1
            try:
                self._publish_once(item)
                return
            except Exception as exc:
                if self._publish_fn is None:
                    self._close_amqp_connection()
                log.warning(
                    "RabbitMQRuntimeSink publish to %s (%s) failed: %s (attempt %d/%d)",
                    self.exchange,
                    item.routing_key,
                    exc,
                    attempts,
                    max_attempts,
                )

            if attempts < max_attempts and not self._stop_event.is_set():
                delay = 0.05 * (2 ** (attempts - 1))
                self._stop_event.wait(delay)

    def flush(self, timeout: float = 2.0) -> None:
        """Wait up to `timeout` seconds for queued messages to be published."""
        t0 = time.time()
        while not self._queue.empty() or self._in_flight:
            if time.time() - t0 >= timeout:
                break
            time.sleep(0.01)

    def close(self) -> None:
        """Flush pending messages and cleanly shut down worker thread and AMQP connection."""
        if self._closed:
            return
        self._closed = True
        self.flush(timeout=1.0)
        self._stop_event.set()
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        self._close_amqp_connection()


__all__ = ["DEFAULT_ROUTING_KEYS", "RabbitMQRuntimeSink"]
