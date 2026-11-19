"""HTTP backend event sink actively pushing AI outputs to backend services (AI-FR-008, AI-FR-009, AI-NFR-002, AI-NFR-006)."""
from __future__ import annotations

import heapq
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx

from app.runtime.camera_pipeline import CameraPipeline
from app.runtime.sink import BaseRuntimeSink
from app.schemas.canonical import (
    AIEvent,
    CameraRuntimeStatus,
    CountUpdate,
    DetectionResult,
)

log = logging.getLogger("swiftletcare.ai.backend_sink")

DEFAULT_PATHS = {
    "events": "/api/ai/events",
    "counts": "/api/ai/counts",
    "status": "/api/ai/status",
}


@dataclass(order=True)
class _QueueItem:
    priority: int
    timestamp: float
    seq: int
    path: str = field(compare=False)
    payload: Dict[str, Any] = field(compare=False)
    retries_left: int = field(compare=False, default=2)


class HttpBackendSink(BaseRuntimeSink):
    """Transport-specific sink pushing canonical AI outputs to an HTTP backend via non-blocking worker."""

    def __init__(
        self,
        base_url: str = "http://localhost:3000",
        paths: Optional[Dict[str, str]] = None,
        enabled: bool = True,
        timeout_s: float = 3.0,
        max_retries: int = 2,
        api_key: str = "",
        client: Optional[httpx.Client] = None,
        max_queue_size: int = 200,
    ) -> None:
        self.base_url = str(base_url).rstrip("/")
        self.paths = {**DEFAULT_PATHS, **(paths or {})}
        self.enabled = bool(enabled)
        self.timeout_s = max(0.1, float(timeout_s))
        self.max_retries = max(0, int(max_retries))
        self.api_key = str(api_key).strip()

        self._queue: queue.PriorityQueue[_QueueItem] = queue.PriorityQueue(maxsize=max_queue_size)
        self._seq_counter = 0
        self._stop_event = threading.Event()
        self._closed = False
        self._in_flight = False

        if client is not None:
            self._client = client
            self._own_client = False
        else:
            self._client = httpx.Client(timeout=self.timeout_s)
            self._own_client = True

        self._worker_thread: Optional[threading.Thread] = None
        if self.enabled:
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="HttpBackendSinkWorker",
                daemon=True,
            )
            self._worker_thread.start()

    @classmethod
    def from_config(
        cls,
        cfg: Dict[str, Any],
        client: Optional[httpx.Client] = None,
    ) -> "HttpBackendSink":
        """Construct HttpBackendSink reading from backend: or publisher.http: with env overrides."""
        backend_cfg = dict(cfg.get("backend", {}))
        pub_cfg = dict(cfg.get("publisher", {}))
        pub_type = str(pub_cfg.get("type", "jsonl")).lower()
        pub_http = dict(pub_cfg.get("http", {}))

        # 1. Resolve enabled flag
        env_enabled = os.getenv("AI_BACKEND_ENABLED")
        if env_enabled is not None:
            enabled = env_enabled.lower() in ("1", "true", "yes")
        else:
            enabled = bool(backend_cfg.get("enabled", False) or pub_type in ("http", "multi"))

        # 2. Resolve base_url
        env_base_url = os.getenv("AI_BACKEND_BASE_URL")
        if env_base_url:
            base_url = env_base_url
        else:
            base_url = str(
                backend_cfg.get("base_url")
                or pub_http.get("base_url")
                or "http://localhost:3000"
            )

        # 3. Resolve paths
        paths_raw = backend_cfg.get("paths") or pub_http.get("paths") or {}
        paths = {k: str(v) for k, v in paths_raw.items()}

        # 4. Resolve timeout and retries
        timeout_s = float(backend_cfg.get("timeout_s") or pub_http.get("timeout_s", 3.0))
        max_retries = int(backend_cfg.get("max_retries") or pub_http.get("max_retries", 2))

        # 5. Resolve api_key
        env_api_key = os.getenv("AI_BACKEND_API_KEY")
        api_key = env_api_key or str(backend_cfg.get("api_key") or pub_http.get("api_key", ""))

        return cls(
            base_url=base_url,
            paths=paths,
            enabled=enabled,
            timeout_s=timeout_s,
            max_retries=max_retries,
            api_key=api_key,
            client=client,
        )

    def _enqueue(self, priority: int, path: str, payload: Dict[str, Any]) -> None:
        """Enqueue payload with priority drop protection for high-priority AIEvent."""
        if not self.enabled or self._closed:
            return

        item = _QueueItem(
            priority=priority,
            timestamp=time.time(),
            seq=self._seq_counter,
            path=path,
            payload=payload,
            retries_left=self.max_retries,
        )
        self._seq_counter += 1

        try:
            self._queue.put_nowait(item)
        except queue.Full:
            if priority == 0:  # High priority AIEvent (PREDATOR_DETECTED)
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
            log.warning("HttpBackendSink queue is full; dropping payload for %s", path)

    def on_event(self, event: AIEvent) -> None:
        """Push predator event immediately to backend with priority 0."""
        payload = event.to_dict()
        payload["snapshot"] = CameraPipeline.normalize_snapshot_ref(event.snapshot)
        path = self.paths.get("events", DEFAULT_PATHS["events"])
        self._enqueue(priority=0, path=path, payload=payload)

    def on_count(self, update: CountUpdate) -> None:
        """Push count update to backend with priority 10."""
        path = self.paths.get("counts", DEFAULT_PATHS["counts"])
        self._enqueue(priority=10, path=path, payload=update.to_dict())

    def on_status(self, status: CameraRuntimeStatus) -> None:
        """Push status transition to backend with priority 20."""
        path = self.paths.get("status", DEFAULT_PATHS["status"])
        self._enqueue(priority=20, path=path, payload=status.to_dict())

    def on_detection(self, result: DetectionResult) -> None:
        """NO-OP: Per AI-NFR-006, individual frame detections are NOT sent to backend."""
        pass

    def _worker_loop(self) -> None:
        """Daemon worker loop taking items from PriorityQueue and sending via HTTP."""
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            self._in_flight = True
            try:
                self._send_with_retry(item)
            finally:
                self._in_flight = False
                self._queue.task_done()

    def _send_with_retry(self, item: _QueueItem) -> None:
        """Send item payload to HTTP backend with exponential backoff on retries."""
        url = f"{self.base_url}{item.path}"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"

        max_attempts = 1 + self.max_retries
        attempts = 0

        while attempts < max_attempts and not self._stop_event.is_set():
            attempts += 1
            try:
                resp = self._client.post(url, json=item.payload, headers=headers, timeout=self.timeout_s)
                if resp.status_code < 400:
                    return
                elif resp.status_code >= 500:
                    log.warning(
                        "HttpBackendSink POST %s returned server error %d (attempt %d/%d)",
                        url,
                        resp.status_code,
                        attempts,
                        max_attempts,
                    )
                else:
                    log.warning(
                        "HttpBackendSink POST %s returned 4xx client error %d: %s",
                        url,
                        resp.status_code,
                        resp.text,
                    )
                    return
            except Exception as exc:
                log.warning(
                    "HttpBackendSink POST %s connection failure: %s (attempt %d/%d)",
                    url,
                    exc,
                    attempts,
                    max_attempts,
                )

            if attempts < max_attempts and not self._stop_event.is_set():
                delay = 0.05 * (2 ** (attempts - 1))
                self._stop_event.wait(delay)

    def flush(self, timeout: float = 2.0) -> None:
        """Wait up to `timeout` seconds for queued payloads to be sent."""
        t0 = time.time()
        while not self._queue.empty() or self._in_flight:
            if time.time() - t0 >= timeout:
                break
            time.sleep(0.01)

    def close(self) -> None:
        """Flush pending items and cleanly shut down worker thread and client."""
        if self._closed:
            return
        self._closed = True
        self.flush(timeout=1.0)
        self._stop_event.set()
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        if self._own_client and self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass


__all__ = ["HttpBackendSink"]
