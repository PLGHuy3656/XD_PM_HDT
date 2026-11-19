"""Thread-safe runtime state store for canonical AI V1 objects with Redis runtime/cache & PostgreSQL backing (CP5.2 / CP8.2 / CP8.4).

Stores:
- Latest `DetectionResult` per cameraId in ephemeral memory (for live frame / WebSocket)
  plus compact bounded detection summary in Redis `ai:latest:{cameraId}`
- Latest `CountUpdate` per cameraId in Redis `ai:latest:{cameraId}` (recoverable from PostgreSQL `ai_db.ai_count_updates` on Redis miss)
- Recent `AIEvent` records (durable in PostgreSQL `ai_db.ai_events` + bounded memory ring buffer)
- Live `CameraRuntimeStatus` per cameraId in Redis `ai:runtime:{cameraId}` (never reconstructed from PostgreSQL after Redis flush)

Also implements `RuntimeEventSink` so it can be attached directly to `CameraPipeline`
or `AIRuntimeManager`.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import logging
import threading
from typing import Any, Deque, Dict, List, Optional

from app.config import settings
from app.redis_client import (
    AI_LATEST_KEY_PREFIX,
    AI_RUNTIME_KEY_PREFIX,
    ai_latest_key,
    ai_runtime_key,
    get_redis_client,
)
from app.repositories.ai_event_repository import AIEventRepository
from app.repositories.count_update_repository import CountUpdateRepository
from app.runtime.sink import BaseRuntimeSink
from app.schemas.canonical import (
    AIEvent,
    CameraRuntimeStatus,
    CountUpdate,
    DetectionResult,
)

logger = logging.getLogger("ai_service.runtime.state_store")


class InMemoryAIRuntimeStateStore(BaseRuntimeSink):
    """Thread-safe runtime state store for AI runtime state with Redis runtime/cache and PostgreSQL backing (CP8.2 / CP8.4).

    Persistence Policy (CP8.0 / CP8.2 / CP8.4):
    - DetectionResult (per-frame): EPHEMERAL in memory only (NEVER persisted to PostgreSQL;
      only a compact bounded summary is merged atomically into `ai:latest:{cameraId}`, never frame history).
    - CameraRuntimeStatus: LIVE RUNTIME STATE in Redis `ai:runtime:{cameraId}` (reconstructed
      only from new active camera runtime observations after Redis flush, never from PostgreSQL).
    - CountUpdate: DURABLE in PostgreSQL `ai_db.ai_count_updates` when count_repository is attached,
      plus latest cached atomically in Redis `ai:latest:{cameraId}` (recoverable from PostgreSQL on Redis miss).
    - AIEvent: DURABLE in PostgreSQL `ai_db.ai_events` when event_repository is attached,
      plus recent bounded ring buffer in memory.
    """

    _ATOMIC_AI_LATEST_MERGE_LUA = """
    local key = KEYS[1]
    local mode = ARGV[1]
    local camera_id = ARGV[2]
    local farm_id = ARGV[3]
    local zone_id = ARGV[4]
    local sub_json = ARGV[5]
    local new_ts = tonumber(ARGV[6])
    local new_frame_id = tonumber(ARGV[7])
    local iso_ts = ARGV[8]
    local ttl = tonumber(ARGV[9])

    local doc = {
        cameraId = camera_id,
        farmId = cjson.null,
        zoneId = cjson.null,
        latestCount = cjson.null,
        countVersionTsUs = 0,
        countFrameId = -1,
        latestDetectionSummary = cjson.null,
        detectionVersionTsUs = 0,
        detectionFrameId = -1,
        lastFrameAt = cjson.null,
        updatedAt = iso_ts,
        versionTsUs = new_ts
    }

    local raw = redis.call('GET', key)
    if raw then
        local ok, cur = pcall(cjson.decode, raw)
        if ok and type(cur) == 'table' and cur['cameraId'] == camera_id then
            doc = cur
            if doc['countVersionTsUs'] == nil or doc['countVersionTsUs'] == cjson.null then
                doc['countVersionTsUs'] = 0
            end
            if doc['countFrameId'] == nil or doc['countFrameId'] == cjson.null then
                doc['countFrameId'] = -1
            end
            if doc['detectionVersionTsUs'] == nil or doc['detectionVersionTsUs'] == cjson.null then
                doc['detectionVersionTsUs'] = 0
            end
            if doc['detectionFrameId'] == nil or doc['detectionFrameId'] == cjson.null then
                doc['detectionFrameId'] = -1
            end
            if doc['versionTsUs'] == nil or doc['versionTsUs'] == cjson.null then
                doc['versionTsUs'] = 0
            end
        end
    end

    if farm_id ~= '' then
        doc['farmId'] = farm_id
    elseif doc['farmId'] == nil then
        doc['farmId'] = cjson.null
    end

    if zone_id ~= '' then
        doc['zoneId'] = zone_id
    elseif doc['zoneId'] == nil then
        doc['zoneId'] = cjson.null
    end

    local sub_obj = cjson.decode(sub_json)
    local applied = 0

    if mode == 'count' then
        local cur_c_ts = tonumber(doc['countVersionTsUs']) or 0
        local cur_c_fid = tonumber(doc['countFrameId']) or -1
        if new_ts > cur_c_ts or (new_ts == cur_c_ts and new_frame_id >= cur_c_fid) then
            doc['latestCount'] = sub_obj
            doc['countVersionTsUs'] = new_ts
            doc['countFrameId'] = new_frame_id
            applied = 1
        end
    elseif mode == 'detection' then
        local cur_d_ts = tonumber(doc['detectionVersionTsUs']) or 0
        local cur_d_fid = tonumber(doc['detectionFrameId']) or -1
        if new_ts > cur_d_ts or (new_ts == cur_d_ts and new_frame_id >= cur_d_fid) then
            doc['latestDetectionSummary'] = sub_obj
            doc['detectionVersionTsUs'] = new_ts
            doc['detectionFrameId'] = new_frame_id
            doc['lastFrameAt'] = iso_ts
            applied = 1
        end
    end

    local final_c_ts = tonumber(doc['countVersionTsUs']) or 0
    local final_d_ts = tonumber(doc['detectionVersionTsUs']) or 0
    if doc['lastFrameAt'] == nil or doc['lastFrameAt'] == cjson.null then
        doc['lastFrameAt'] = iso_ts
    end

    local prev_ver = tonumber(doc['versionTsUs']) or 0
    if new_ts >= prev_ver and applied == 1 then
        doc['versionTsUs'] = new_ts
        doc['updatedAt'] = iso_ts
    elseif prev_ver == 0 then
        doc['versionTsUs'] = math.max(final_c_ts, final_d_ts, new_ts)
        doc['updatedAt'] = iso_ts
    end

    redis.call('SET', key, cjson.encode(doc), 'EX', ttl)
    return applied
    """

    def __init__(
        self,
        max_events: int = 500,
        max_count_history: int = 100,
        count_repository: Optional[CountUpdateRepository] = None,
        event_repository: Optional[AIEventRepository] = None,
        redis_client: Any = None,
        redis_url: Optional[str] = None,
        redis_enabled: Optional[bool] = None,
        latest_ttl_seconds: Optional[int] = None,
        runtime_ttl_seconds: Optional[int] = None,
    ) -> None:
        if max_events <= 0:
            raise ValueError("max_events must be > 0")
        if max_count_history <= 0:
            raise ValueError("max_count_history must be > 0")
        self._max_events = max_events
        self._max_count_history = max_count_history
        self._count_repository = count_repository
        self._event_repository = event_repository
        self._redis_client = redis_client
        self._redis_url = redis_url or settings.ai_redis_url
        self._redis_enabled = (
            settings.ai_redis_enabled if redis_enabled is None else bool(redis_enabled)
        )
        self._latest_ttl_seconds = max(
            1,
            int(
                latest_ttl_seconds
                if latest_ttl_seconds is not None
                else settings.ai_latest_ttl_seconds
            ),
        )
        self._runtime_ttl_seconds = max(
            1,
            int(
                runtime_ttl_seconds
                if runtime_ttl_seconds is not None
                else settings.ai_runtime_ttl_seconds
            ),
        )
        self._lock = threading.RLock()
        self._latest_detections: Dict[str, DetectionResult] = {}
        self._latest_counts: Dict[str, CountUpdate] = {}
        self._count_history: Dict[str, Deque[CountUpdate]] = {}
        self._latest_statuses: Dict[str, CameraRuntimeStatus] = {}
        self._status_templates: Dict[str, CameraRuntimeStatus] = {}
        self._recent_events: Deque[AIEvent] = deque()
        self._events_by_id: Dict[str, AIEvent] = {}
        self.count_persistence_failures: int = 0
        self.event_persistence_failures: int = 0

    @property
    def redis_enabled(self) -> bool:
        return self._redis_enabled

    def _get_redis(self) -> Any:
        if self._redis_client is None:
            self._redis_client = get_redis_client(self._redis_url)
        return self._redis_client

    # ------------------------------------------------------------------
    # Timestamp & Redis serialization helpers (CP8.4)
    # ------------------------------------------------------------------
    @staticmethod
    def _iso_to_epoch_us(iso_str: str) -> int:
        raw = iso_str.strip()
        candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return int(dt.timestamp() * 1_000_000)

    @classmethod
    def _serialize_runtime_status(cls, status: CameraRuntimeStatus) -> tuple[str, int]:
        version_ts_us = cls._iso_to_epoch_us(status.updatedAt)
        payload = status.model_dump(by_alias=True)
        payload["lastError"] = status.errorMessage or status.errorCode
        payload["versionTsUs"] = version_ts_us
        return json.dumps(payload, separators=(",", ":")), version_ts_us

    @staticmethod
    def _deserialize_runtime_status(raw: str) -> CameraRuntimeStatus:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Runtime status Redis payload must be a JSON object")
        last_error = data.pop("lastError", None)
        data.pop("versionTsUs", None)
        if last_error and not data.get("errorMessage"):
            data["errorMessage"] = str(last_error)
        return CameraRuntimeStatus.model_validate(data)

    def _atomic_merge_latest_count(self, update: CountUpdate) -> bool:
        if not self._redis_enabled:
            return False
        key = ai_latest_key(update.cameraId)
        try:
            ts_us = self._iso_to_epoch_us(update.recordedAt)
            count_json = json.dumps(update.model_dump(by_alias=True), separators=(",", ":"))
            res = self._get_redis().eval(
                self._ATOMIC_AI_LATEST_MERGE_LUA,
                1,
                key,
                "count",
                update.cameraId,
                update.farmId or "",
                update.zoneId or "",
                count_json,
                str(ts_us),
                str(int(update.frameId)),
                update.recordedAt,
                str(self._latest_ttl_seconds),
            )
            return bool(res)
        except Exception as exc:
            logger.warning(
                "[AI REDIS LATEST WRITE WARNING] Failed to merge count into %s: %s",
                key,
                exc,
            )
            return False

    def _atomic_merge_latest_detection(self, result: DetectionResult) -> bool:
        if not self._redis_enabled:
            return False
        key = ai_latest_key(result.cameraId)
        try:
            ts_us = self._iso_to_epoch_us(result.capturedAt)
            compact_summary = {
                "frameId": result.frameId,
                "capturedAt": result.capturedAt,
                "detectionCount": len(result.detections),
                "frame": result.frame.model_dump(by_alias=True),
            }
            summary_json = json.dumps(compact_summary, separators=(",", ":"))
            res = self._get_redis().eval(
                self._ATOMIC_AI_LATEST_MERGE_LUA,
                1,
                key,
                "detection",
                result.cameraId,
                result.farmId or "",
                result.zoneId or "",
                summary_json,
                str(ts_us),
                str(int(result.frameId)),
                result.capturedAt,
                str(self._latest_ttl_seconds),
            )
            return bool(res)
        except Exception as exc:
            logger.warning(
                "[AI REDIS LATEST WRITE WARNING] Failed to merge detection summary into %s: %s",
                key,
                exc,
            )
            return False

    def _write_runtime_status_in_redis(self, status: CameraRuntimeStatus) -> bool:
        if not self._redis_enabled:
            return False
        key = ai_runtime_key(status.cameraId)
        try:
            serialized, _ = self._serialize_runtime_status(status)
            self._get_redis().set(key, serialized, ex=self._runtime_ttl_seconds)
            return True
        except Exception as exc:
            logger.warning(
                "[AI REDIS RUNTIME WRITE WARNING] Failed to write %s: %s",
                key,
                exc,
            )
            return False

    # ------------------------------------------------------------------
    # RuntimeEventSink implementation
    # ------------------------------------------------------------------
    def on_detection(self, result: DetectionResult) -> None:
        self.record_detection(result)

    def on_count(self, update: CountUpdate) -> None:
        self.record_count(update)

    def on_event(self, event: AIEvent) -> None:
        self.record_event(event)

    def on_status(self, status: CameraRuntimeStatus) -> None:
        self.record_status(status)

    # ------------------------------------------------------------------
    # Explicit write methods
    # ------------------------------------------------------------------
    def record_detection(self, result: DetectionResult) -> None:
        """Records per-frame DetectionResult in ephemeral memory (never persisted to PostgreSQL)
        and atomically merges a compact bounded summary into `ai:latest:{cameraId}`.
        """
        new_ts_us = self._iso_to_epoch_us(result.capturedAt)
        with self._lock:
            existing_det = self._latest_detections.get(result.cameraId)
            if existing_det is None:
                self._latest_detections[result.cameraId] = result
            else:
                cur_ts_us = self._iso_to_epoch_us(existing_det.capturedAt)
                if new_ts_us > cur_ts_us or (
                    new_ts_us == cur_ts_us and result.frameId >= existing_det.frameId
                ):
                    self._latest_detections[result.cameraId] = result
            template = self._status_templates.get(result.cameraId)

        if self._redis_enabled:
            self._atomic_merge_latest_detection(result)

            # If live runtime status key was flushed/expired while camera pipeline is actively
            # emitting frames, reconstruct `ai:runtime:{cameraId}` from this new live observation.
            try:
                rt_key = ai_runtime_key(result.cameraId)
                if not self._get_redis().exists(rt_key):
                    reconstructed = CameraRuntimeStatus(
                        cameraId=result.cameraId,
                        farmId=result.farmId or (template.farmId if template else None),
                        zoneId=result.zoneId or (template.zoneId if template else None),
                        status="ONLINE",
                        sourceConnected=True,
                        inferenceStatus="RUNNING",
                        fps=template.fps if template else 0.0,
                        width=result.frame.width,
                        height=result.frame.height,
                        modelVersion=template.modelVersion if template else "yolo26n-best",
                        trackerType=template.trackerType if template else "bytetrack",
                        processedFrames=max(1, result.frameId + 1),
                        lastFrameAt=result.capturedAt,
                        updatedAt=result.capturedAt,
                        errorCode=None,
                        errorMessage=None,
                    )
                    self._write_runtime_status_in_redis(reconstructed)
            except Exception:
                pass

    def record_count(self, update: CountUpdate) -> bool:
        """Persists CountUpdate to PostgreSQL (if configured) before atomically updating Redis `ai:latest:{cameraId}`.

        Returns True on success, False if durable persistence failed.
        """
        if self._count_repository is not None:
            try:
                self._count_repository.save(update)
            except Exception as exc:
                with self._lock:
                    self.count_persistence_failures += 1
                logger.error(
                    "[AI COUNT PERSISTENCE FAILED] Failed to persist CountUpdate for camera='%s' frame=%d: %s",
                    update.cameraId,
                    update.frameId,
                    exc,
                )
                return False

        with self._lock:
            history = self._count_history.get(update.cameraId)
            if history is None:
                history = deque(maxlen=self._max_count_history)
                self._count_history[update.cameraId] = history
            history.append(update)

        if self._redis_enabled:
            self._atomic_merge_latest_count(update)
        else:
            new_ts_us = self._iso_to_epoch_us(update.recordedAt)
            with self._lock:
                cur = self._latest_counts.get(update.cameraId)
                if cur is None:
                    self._latest_counts[update.cameraId] = update
                else:
                    cur_ts_us = self._iso_to_epoch_us(cur.recordedAt)
                    if new_ts_us > cur_ts_us or (
                        new_ts_us == cur_ts_us and update.frameId >= cur.frameId
                    ):
                        self._latest_counts[update.cameraId] = update
        return True

    def record_event(self, event: AIEvent) -> bool:
        """Persists AIEvent to PostgreSQL (if configured) before recording in runtime state.

        Returns True on success, False if durable persistence failed.
        """
        if self._event_repository is not None:
            try:
                self._event_repository.save(event)
            except Exception as exc:
                with self._lock:
                    self.event_persistence_failures += 1
                logger.error(
                    "[AI EVENT PERSISTENCE FAILED] Failed to persist AIEvent eventId='%s' camera='%s': %s",
                    event.eventId,
                    event.cameraId,
                    exc,
                )
                return False

        with self._lock:
            if event.eventId in self._events_by_id:
                return True
            if len(self._recent_events) >= self._max_events:
                evicted = self._recent_events.popleft()
                self._events_by_id.pop(evicted.eventId, None)
            self._recent_events.append(event)
            self._events_by_id[event.eventId] = event
        return True

    def record_status(self, status: CameraRuntimeStatus) -> None:
        """Records live CameraRuntimeStatus in Redis `ai:runtime:{cameraId}` (CP8.4)."""
        with self._lock:
            self._status_templates[status.cameraId] = status
            self._latest_statuses[status.cameraId] = status

        if self._redis_enabled:
            self._write_runtime_status_in_redis(status)

    # ------------------------------------------------------------------
    # Read / query methods
    # ------------------------------------------------------------------
    def get_latest_detection(self, camera_id: str) -> Optional[DetectionResult]:
        with self._lock:
            return self._latest_detections.get(camera_id)

    def get_latest_summary(self, camera_id: str) -> Optional[dict[str, Any]]:
        """Returns the bounded `ai:latest:{cameraId}` summary dict from Redis if valid."""
        if not self._redis_enabled:
            return None
        key = ai_latest_key(camera_id)
        try:
            raw = self._get_redis().get(key)
        except Exception as exc:
            logger.warning(
                "[AI REDIS LATEST READ WARNING] Failed to read %s: %s",
                key,
                exc,
            )
            return None
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or not data.get("cameraId"):
                raise ValueError("Invalid ai:latest summary object")
            return data
        except Exception as parse_exc:
            logger.warning(
                "[AI REDIS LATEST CORRUPT] Malformed JSON at %s (%s); evicting",
                key,
                parse_exc,
            )
            try:
                self._get_redis().delete(key)
            except Exception:
                pass
            return None

    def get_latest_count(self, camera_id: str) -> Optional[CountUpdate]:
        """Returns latest CountUpdate from Redis `ai:latest:{cameraId}`, falling back to PostgreSQL on miss/corrupt."""
        if self._redis_enabled:
            key = ai_latest_key(camera_id)
            try:
                raw = self._get_redis().get(key)
            except Exception as redis_exc:
                logger.warning(
                    "[AI REDIS LATEST READ WARNING] Failed to read %s (%s); falling back to PostgreSQL",
                    key,
                    redis_exc,
                )
                raw = None

            if raw is not None:
                try:
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        raise ValueError("ai:latest Redis value must be a JSON object")
                    if "latestCount" in data:
                        if data["latestCount"] is not None:
                            return CountUpdate.model_validate(data["latestCount"])
                    elif "entryCount" in data:
                        return CountUpdate.model_validate(data)
                    else:
                        raise ValueError("ai:latest Redis value missing latestCount field")
                except Exception as parse_exc:
                    logger.warning(
                        "[AI REDIS LATEST CORRUPT] Malformed JSON at %s (%s); evicting and falling back to PostgreSQL",
                        key,
                        parse_exc,
                    )
                    try:
                        self._get_redis().delete(key)
                    except Exception:
                        pass
        else:
            with self._lock:
                cached = self._latest_counts.get(camera_id)
            if cached is not None:
                return cached

        if self._count_repository is not None:
            try:
                persisted = self._count_repository.get_latest_by_camera(camera_id)
                if persisted is not None:
                    if self._redis_enabled:
                        self._atomic_merge_latest_count(persisted)
                    else:
                        with self._lock:
                            self._latest_counts[camera_id] = persisted
                return persisted
            except Exception as exc:
                logger.warning(
                    "[AI COUNT QUERY WARNING] Failed to query latest CountUpdate for camera='%s': %s",
                    camera_id,
                    exc,
                )
        return None

    def list_count_updates(
        self,
        camera_id: str,
        limit: int = 100,
        start_time: Optional[datetime | str] = None,
        end_time: Optional[datetime | str] = None,
    ) -> List[CountUpdate]:
        if self._count_repository is not None:
            try:
                if start_time is not None and end_time is not None:
                    return self._count_repository.list_by_time_range(
                        camera_id=camera_id,
                        start_time=start_time,
                        end_time=end_time,
                        limit=limit,
                    )
                return self._count_repository.list_by_camera(camera_id=camera_id, limit=limit)
            except Exception as exc:
                logger.warning(
                    "[AI COUNT QUERY WARNING] Failed to list CountUpdate history for camera='%s': %s",
                    camera_id,
                    exc,
                )
        latest = self.get_latest_count(camera_id)
        return [latest] if latest is not None else []

    def get_count_history(self, camera_id: str, limit: int = 20) -> List[CountUpdate]:
        """Return recent CountUpdate items for a camera ordered newest-first."""
        if limit <= 0:
            raise ValueError("limit must be > 0")
        with self._lock:
            history = self._count_history.get(camera_id)
            if history:
                return list(reversed(history))[:limit]
        return self.list_count_updates(camera_id=camera_id, limit=limit)

    def get_camera_status(self, camera_id: str) -> Optional[CameraRuntimeStatus]:
        """Returns live CameraRuntimeStatus from Redis `ai:runtime:{cameraId}`.

        Follows CP8.4 Runtime Reconstruction Rule:
        After Redis flush/restart, camera runtime status is NOT rebuilt from historical
        PostgreSQL rows; it returns None until new active camera runtime observations arrive.
        """
        if self._redis_enabled:
            key = ai_runtime_key(camera_id)
            try:
                raw = self._get_redis().get(key)
            except Exception as redis_exc:
                logger.warning(
                    "[AI REDIS RUNTIME READ WARNING] Failed to read %s (%s); returning conservative absent status",
                    key,
                    redis_exc,
                )
                return None

            if raw is None:
                return None

            try:
                return self._deserialize_runtime_status(raw)
            except Exception as parse_exc:
                logger.warning(
                    "[AI REDIS RUNTIME CORRUPT] Malformed JSON at %s (%s); evicting and returning absent status",
                    key,
                    parse_exc,
                )
                try:
                    self._get_redis().delete(key)
                except Exception:
                    pass
                return None

        with self._lock:
            return self._latest_statuses.get(camera_id)

    def list_camera_statuses(self) -> List[CameraRuntimeStatus]:
        if self._redis_enabled:
            try:
                client = self._get_redis()
                keys = sorted(client.keys(f"{AI_RUNTIME_KEY_PREFIX}*"))
            except Exception as redis_exc:
                logger.warning(
                    "[AI REDIS RUNTIME LIST WARNING] Failed to list %s* (%s); returning empty status list",
                    AI_RUNTIME_KEY_PREFIX,
                    redis_exc,
                )
                return []

            statuses_by_id: Dict[str, CameraRuntimeStatus] = {}
            for key in keys:
                try:
                    raw = client.get(key)
                except Exception as read_exc:
                    logger.warning(
                        "[AI REDIS RUNTIME READ WARNING] Failed to read %s: %s",
                        key,
                        read_exc,
                    )
                    continue
                if raw is None:
                    continue
                try:
                    status_obj = self._deserialize_runtime_status(raw)
                    statuses_by_id[status_obj.cameraId] = status_obj
                except Exception as parse_exc:
                    logger.warning(
                        "[AI REDIS RUNTIME CORRUPT] Malformed JSON at %s (%s); evicting",
                        key,
                        parse_exc,
                    )
                    try:
                        client.delete(key)
                    except Exception:
                        pass
            return [statuses_by_id[k] for k in sorted(statuses_by_id.keys())]

        with self._lock:
            return [self._latest_statuses[k] for k in sorted(self._latest_statuses.keys())]

    def list_events(
        self,
        camera_id: Optional[str] = None,
        limit: int = 100,
        farm_id: Optional[str] = None,
        start_time: Optional[datetime | str] = None,
        end_time: Optional[datetime | str] = None,
    ) -> List[AIEvent]:
        """Return recent AIEvent records ordered newest-first."""
        if limit <= 0:
            raise ValueError("limit must be > 0")
        if self._event_repository is not None:
            try:
                if start_time is not None and end_time is not None:
                    return self._event_repository.list_by_time_range(
                        start_time=start_time,
                        end_time=end_time,
                        camera_id=camera_id,
                        limit=limit,
                    )
                return self._event_repository.list_recent(
                    camera_id=camera_id,
                    farm_id=farm_id,
                    limit=limit,
                )
            except Exception as exc:
                logger.warning(
                    "[AI EVENT QUERY WARNING] Failed to list AIEvent history: %s",
                    exc,
                )
        with self._lock:
            items = list(reversed(self._recent_events))
            if camera_id is not None:
                items = [e for e in items if e.cameraId == camera_id]
            if farm_id is not None:
                items = [e for e in items if e.farmId == farm_id]
            return items[:limit]

    def get_event(self, event_id: str) -> Optional[AIEvent]:
        if self._event_repository is not None:
            try:
                persisted = self._event_repository.get(event_id)
                if persisted is not None:
                    return persisted
            except Exception as exc:
                logger.warning(
                    "[AI EVENT QUERY WARNING] Failed to query AIEvent eventId='%s': %s",
                    event_id,
                    exc,
                )
        with self._lock:
            return self._events_by_id.get(event_id)

    def clear_redis_state(self, camera_id: Optional[str] = None) -> None:
        """Clears Redis runtime/cache keys (`ai:latest:*` and `ai:runtime:*`)."""
        if not self._redis_enabled:
            return
        try:
            client = self._get_redis()
            if camera_id is not None:
                client.delete(ai_latest_key(camera_id), ai_runtime_key(camera_id))
            else:
                latest_keys = client.keys(f"{AI_LATEST_KEY_PREFIX}*")
                runtime_keys = client.keys(f"{AI_RUNTIME_KEY_PREFIX}*")
                all_keys = [*latest_keys, *runtime_keys]
                if all_keys:
                    client.delete(*all_keys)
        except Exception as exc:
            logger.warning(
                "[AI REDIS CLEAR WARNING] Failed to clear AI Redis keys: %s",
                exc,
            )

    def clear(self) -> None:
        with self._lock:
            self._latest_detections.clear()
            self._latest_counts.clear()
            self._count_history.clear()
            self._latest_statuses.clear()
            self._status_templates.clear()
            self._recent_events.clear()
            self._events_by_id.clear()
            self.count_persistence_failures = 0
            self.event_persistence_failures = 0
        self.clear_redis_state()
        if self._count_repository is not None:
            try:
                self._count_repository.clear()
            except Exception:
                pass
        if self._event_repository is not None:
            try:
                self._event_repository.clear()
            except Exception:
                pass


__all__ = ["InMemoryAIRuntimeStateStore"]
