"""Idempotent RabbitMQ topology declarator via Management HTTP API (CP7.1)."""
from __future__ import annotations

import base64
import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from infrastructure.rabbitmq.constants import DEFAULT_RETRY_TTL_MS
from infrastructure.rabbitmq.topology import (
    BindingDefinition,
    ExchangeDefinition,
    QueueDefinition,
    get_v1_topology,
)

log = logging.getLogger("swiftletcare.infrastructure.rabbitmq.declarator")


class RabbitMQDeclarator:
    """Declares and manages RabbitMQ V1 topology idempotently using Management API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        vhost: str = "/",
    ) -> None:
        self.base_url = (base_url or os.getenv("RABBITMQ_MANAGEMENT_URL") or "http://localhost:15672").rstrip("/")
        self.username = username or os.getenv("RABBITMQ_DEFAULT_USER") or "swiftlet"
        self.password = password or os.getenv("RABBITMQ_DEFAULT_PASS") or "swiftlet123"
        self.vhost = vhost
        self._auth_header = "Basic " + base64.b64encode(f"{self.username}:{self.password}".encode()).decode()

    def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}/api/{path.lstrip('/')}"
        headers = {
            "Authorization": self._auth_header,
            "Content-Type": "application/json",
        }
        body_bytes = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                raw = resp.read()
                if raw:
                    return json.loads(raw.decode("utf-8"))
                return None
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"RabbitMQ API error [{err.code}] {err.reason} on {method} {url}: {err_body}") from err

    @property
    def encoded_vhost(self) -> str:
        return urllib.parse.quote(self.vhost, safe="")

    def declare_exchange(self, ex: ExchangeDefinition) -> None:
        path = f"exchanges/{self.encoded_vhost}/{urllib.parse.quote(ex.name, safe='')}"
        payload = {
            "type": ex.type,
            "durable": ex.durable,
            "auto_delete": ex.auto_delete,
            "arguments": ex.arguments,
        }
        self._request("PUT", path, payload)
        log.info("Declared exchange '%s' (type=%s, durable=%s)", ex.name, ex.type, ex.durable)

    def declare_queue(self, q: QueueDefinition) -> None:
        path = f"queues/{self.encoded_vhost}/{urllib.parse.quote(q.name, safe='')}"
        payload = {
            "durable": q.durable,
            "auto_delete": q.auto_delete,
            "arguments": q.arguments,
        }
        self._request("PUT", path, payload)
        log.info("Declared queue '%s' (durable=%s, args=%s)", q.name, q.durable, q.arguments)

    def declare_binding(self, b: BindingDefinition) -> None:
        ex_enc = urllib.parse.quote(b.source_exchange, safe="")
        q_enc = urllib.parse.quote(b.destination_queue, safe="")
        path = f"bindings/{self.encoded_vhost}/e/{ex_enc}/q/{q_enc}"
        payload = {
            "routing_key": b.routing_key,
            "arguments": b.arguments,
        }
        self._request("POST", path, payload)
        log.info("Bound queue '%s' to exchange '%s' (routing_key='%s')", b.destination_queue, b.source_exchange, b.routing_key)

    def apply_topology(self, retry_ttl_ms: int = DEFAULT_RETRY_TTL_MS) -> Dict[str, int]:
        """Apply the entire V1 topology idempotently."""
        topo = get_v1_topology(retry_ttl_ms=retry_ttl_ms)

        for ex in topo["exchanges"]:
            self.declare_exchange(ex)

        for q in topo["queues"]:
            self.declare_queue(q)

        for b in topo["bindings"]:
            self.declare_binding(b)

        return {
            "exchanges": len(topo["exchanges"]),
            "queues": len(topo["queues"]),
            "bindings": len(topo["bindings"]),
        }

    def get_queue_info(self, queue_name: str) -> Dict[str, Any]:
        path = f"queues/{self.encoded_vhost}/{urllib.parse.quote(queue_name, safe='')}"
        return self._request("GET", path)

    def purge_queue(self, queue_name: str) -> None:
        path = f"queues/{self.encoded_vhost}/{urllib.parse.quote(queue_name, safe='')}/contents"
        self._request("DELETE", path)

    def delete_queue(self, queue_name: str) -> None:
        """Deletes a queue completely from RabbitMQ (used for recreation when arguments mutate)."""
        path = f"queues/{self.encoded_vhost}/{urllib.parse.quote(queue_name, safe='')}"
        self._request("DELETE", path)

    def publish_message(
        self,
        exchange: str,
        routing_key: str,
        payload: Dict[str, Any],
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Publish test message via Management API."""
        path = f"exchanges/{self.encoded_vhost}/{urllib.parse.quote(exchange, safe='')}/publish"
        body = {
            "properties": properties or {},
            "routing_key": routing_key,
            "payload": json.dumps(payload),
            "payload_encoding": "string",
        }
        res = self._request("POST", path, body)
        return bool(res and res.get("routed") is True)

    def get_messages(
        self,
        queue_name: str,
        count: int = 1,
        ackmode: str = "ack_requeue_false",  # purge retrieved messages
    ) -> list:
        """Retrieve messages from a queue for inspection."""
        path = f"queues/{self.encoded_vhost}/{urllib.parse.quote(queue_name, safe='')}/get"
        body = {
            "count": count,
            "ackmode": ackmode,
            "encoding": "auto",
        }
        return self._request("POST", path, body) or []

    def wait_for_queue_count(
        self,
        queue_name: str,
        expected_count: int,
        timeout: float = 5.0,
    ) -> int:
        """Poll queue until messages count reaches expected_count or timeout."""
        import time
        start = time.time()
        while time.time() - start < timeout:
            cnt = self.get_queue_info(queue_name).get("messages", 0)
            if cnt == expected_count:
                return cnt
            time.sleep(0.1)
        return self.get_queue_info(queue_name).get("messages", 0)


__all__ = ["RabbitMQDeclarator"]
