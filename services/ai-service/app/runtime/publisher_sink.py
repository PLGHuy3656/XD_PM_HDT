"""Runtime sink that adapts canonical AI events to DomainEvents and publishes to RabbitMQ (CP7.3)."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.domain_events.constants import (
    CANONICAL_EVENT_VERSION,
    EVENT_AI_PREDATOR_DETECTED,
    PRODUCER_AI_SERVICE,
    SUPPORTED_PREDATOR_CLASSES,
)
from app.domain_events.envelope import DomainEvent
from app.domain_events.models import BBoxPayload, PredatorDetectedPayload
from app.ports.domain_event_publisher import DomainEventPublisher
from app.ports.metadata_resolver import (
    CameraMetadataResolver,
    default_camera_metadata_resolver,
)
from app.repositories.ai_event_repository import (
    AIEventRepository,
    default_ai_event_repository,
)
from app.runtime.sink import BaseRuntimeSink
from app.schemas.canonical import (
    AIEvent,
    CameraRuntimeStatus,
    CountUpdate,
    DetectionResult,
)

logger = logging.getLogger("ai_service.runtime.publisher_sink")


class DomainEventPublisherRuntimeSink(BaseRuntimeSink):
    """Runtime event sink bridging AI pipeline domain events to the DomainEventPublisher port.

    Strict Invariants:
    1. ONLY `ai.predator.detected` is published to RabbitMQ.
    2. Explicitly NEVER publishes count updates (`ai.count.*`), line crossings,
       entry/exit events, raw detections, bounding boxes, or CameraRuntimeStatus.
    3. Supported predator classes are strictly rat and snake.
    4. Enriches camera events with farmId and zoneId via CameraMetadataResolver.
       If metadata is unresolved, safe failure policy is applied: log diagnostic and
       suppress publication. NEVER fabricates fake business IDs (FARM-01/ZONE-01).
    5. PredatorMonitor in the AI pipeline is the sole authority for domain cooldown
       and debounce. This sink does not silently re-filter or swallow valid AI events.
    6. Sanitizes snapshot references to prevent leaking internal filesystem paths.
    """

    def __init__(
        self,
        publisher: DomainEventPublisher,
        metadata_resolver: Optional[CameraMetadataResolver] = None,
        default_frame_width: int = 1920,
        default_frame_height: int = 1080,
        event_repository: Optional[AIEventRepository] = None,
    ) -> None:
        self.publisher = publisher
        self.metadata_resolver = metadata_resolver or default_camera_metadata_resolver
        self.default_frame_width = int(default_frame_width)
        self.default_frame_height = int(default_frame_height)
        self.event_repository: Optional[AIEventRepository] = (
            event_repository if event_repository is not None else default_ai_event_repository
        )

        # Cache camera dimensions observed from detections or runtime status
        self._camera_dims: Dict[str, Tuple[int, int]] = {}

    def on_status(self, status: CameraRuntimeStatus) -> None:
        """Records frame resolution from camera status; NEVER publishes to RabbitMQ."""
        if status.width and status.height:
            self._camera_dims[status.cameraId] = (status.width, status.height)

    def on_detection(self, result: DetectionResult) -> None:
        """Records frame resolution from detection result; NEVER publishes to RabbitMQ."""
        if result.frame and result.frame.width > 0 and result.frame.height > 0:
            self._camera_dims[result.cameraId] = (result.frame.width, result.frame.height)

    def on_count(self, update: CountUpdate) -> None:
        """Strict NO-OP: Count updates are explicitly NOT bound to notification flow."""
        pass

    def on_event(self, event: AIEvent) -> None:
        """Processes AIEvent and publishes ai.predator.detected when criteria match."""
        # Invariant 1: Only PREDATOR_DETECTED events
        if event.eventType != "PREDATOR_DETECTED":
            logger.debug(
                "[PUBLISHER SINK] Discarded non-predator AIEvent type '%s'",
                event.eventType,
            )
            return

        # Invariant 2: Only supported predator classes (rat, snake)
        pred_cls = str(event.cls).lower().strip()
        if pred_cls not in SUPPORTED_PREDATOR_CLASSES:
            logger.warning(
                "[PUBLISHER SINK] Discarded unsupported predator class '%s' for camera '%s'",
                pred_cls,
                event.cameraId,
            )
            return

        # Invariant 3: Resolve farmId and zoneId without fabricating fake IDs
        raw_farm_id = event.farmId.strip() if event.farmId and event.farmId.strip() else None
        raw_zone_id = event.zoneId.strip() if event.zoneId and event.zoneId.strip() else None

        farm_id = raw_farm_id or self.metadata_resolver.resolve_farm_id(event.cameraId)
        zone_id = raw_zone_id or self.metadata_resolver.resolve_zone_id(event.cameraId)

        if not farm_id or not zone_id:
            logger.error(
                "[PUBLISHER SINK] Dropped predator event for camera '%s': unresolved farmId/zoneId metadata. "
                "Safe failure policy applied: refusing to fabricate fake IDs or publish incorrectly scoped alert.",
                event.cameraId,
            )
            return

        # Step 4 (CP8.2): Persist AIEvent durably before RabbitMQ publication.
        # Avoid publishing or reporting durable success if DB persistence fails.
        if self.event_repository is not None:
            try:
                enriched_event = event.model_copy(
                    update={"farmId": farm_id, "zoneId": zone_id}
                )
                self.event_repository.save(enriched_event)
            except Exception as exc:
                logger.error(
                    "[PUBLISHER SINK] Durable persistence failed for AIEvent '%s' camera='%s': %s. "
                    "Suppressing RabbitMQ publication to avoid reporting unpersisted event.",
                    event.eventId,
                    event.cameraId,
                    exc,
                )
                return

        # Invariant 4: Derive pixel bbox (x, y, width, height)
        x1 = round(event.bbox.x1, 1)
        y1 = round(event.bbox.y1, 1)
        width = round(max(0.0, event.bbox.x2 - event.bbox.x1), 1)
        height = round(max(0.0, event.bbox.y2 - event.bbox.y1), 1)
        bbox = BBoxPayload(x=x1, y=y1, width=width, height=height)

        # Invariant 5: Sanitize snapshot reference (filename only, no local private paths)
        snapshot_ref: Optional[str] = None
        if event.snapshot:
            snapshot_ref = Path(event.snapshot).name

        # Determine frame dimensions
        frame_w, frame_h = self._camera_dims.get(
            event.cameraId,
            (self.default_frame_width, self.default_frame_height),
        )

        # Build payload
        payload = PredatorDetectedPayload(
            farmId=farm_id,
            zoneId=zone_id,
            cameraId=event.cameraId,
            predatorClass=pred_cls,  # type: ignore[arg-type]
            confidence=round(event.confidence, 4),
            snapshotRef=snapshot_ref,
            frameWidth=frame_w,
            frameHeight=frame_h,
            bbox=bbox,
        )

        # Build canonical DomainEvent envelope
        domain_event = DomainEvent(
            eventId=str(uuid.uuid4()),
            eventType=EVENT_AI_PREDATOR_DETECTED,
            eventVersion=CANONICAL_EVENT_VERSION,
            occurredAt=event.detectedAt,
            producer=PRODUCER_AI_SERVICE,
            correlationId=None,
            payload=payload.to_dict(),
        )

        # Publish
        self.publisher.publish_nowait(domain_event)
        logger.info(
            "[PUBLISHER SINK] Dispatched '%s' eventId='%s' camera='%s' class='%s' farm='%s' zone='%s'",
            domain_event.event_type,
            domain_event.event_id,
            event.cameraId,
            pred_cls,
            farm_id,
            zone_id,
        )


__all__ = ["DomainEventPublisherRuntimeSink"]
