"""RabbitMQ consumer adapter implementing bounded retry, DLQ, and durable idempotency (CP7.5)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import aio_pika
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustChannel

from app.infrastructure.rabbitmq.config import RabbitMQSettings, RedisSettings
from app.infrastructure.rabbitmq.connection import RabbitMQConnectionManager
from app.infrastructure.rabbitmq.envelope import CanonicalEnvelope, PermanentEnvelopeError
from app.infrastructure.rabbitmq.inbox import EventInbox, InboxResult, NullEventInbox
from app.infrastructure.rabbitmq.idempotency import (
    ClaimStatus,
    IdempotencyStore,
    InMemoryIdempotencyStore,
    RedisIdempotencyStore,
    default_idempotency_store,
)
from app.infrastructure.rabbitmq.mapper import EventMapper
from app.services.notification_service import NotificationService

logger = logging.getLogger("notification_service.infrastructure.rabbitmq.consumer")


class RabbitMQAlertConsumer:
    """Infrastructure consumer adapter for notification.alert-events.v1 queue.

    CP7.5 Reliability Guarantees:
    1. Bounded Retry: Bounded retry attempts (RABBITMQ_MAX_RETRIES, default 3) with delayed retry
       via notification.alert-events.v1.retry (TTL ~ 5000ms). Eliminates infinite hot requeue loops.
    2. Dead Letter Queue: Permanent errors and retry-exhausted messages route cleanly to
       notification.alert-events.v1.dlq via swiftlet.notification.dlx.
    3. Publish-then-ACK Safety: When republishing to retry queue or DLX, the original message is
       acknowledged strictly after broker publisher confirm succeeds.
    4. Durable Idempotency: Redis-backed atomic claim ('SET NX EX') prevents duplicate processing
       across process restarts and concurrent consumer replicas.
    5. Monitoring-Ready Logging: Structured metric logs exposing eventId, eventType, producer,
       routingKey, retryCount, and result ('processed' | 'duplicate' | 'retry_scheduled' | 'dead_lettered' | 'invalid').
    """

    def __init__(
        self,
        service: NotificationService,
        connection_manager: Optional[RabbitMQConnectionManager] = None,
        idempotency_store: Optional[IdempotencyStore] = None,
        settings: Optional[RabbitMQSettings] = None,
        redis_settings: Optional[RedisSettings] = None,
        inbox: Optional[EventInbox] = None,
    ) -> None:
        self.service = service
        # Durable inbox (PostgreSQL processed_events) committed with the event's effects (CP8.5).
        self.inbox: EventInbox = inbox or NullEventInbox()
        self.settings = settings or RabbitMQSettings.from_env()
        self.redis_settings = redis_settings or RedisSettings.from_env()
        self.connection_manager = connection_manager or RabbitMQConnectionManager(self.settings)
        self.idempotency_store = idempotency_store or default_idempotency_store
        self.mapper = EventMapper(service=self.service)

        self._consumer_tag: Optional[str] = None
        self._is_running = False
        self._lock = asyncio.Lock()

        # Operational metrics
        self.received_count: int = 0
        self.processed_count: int = 0
        self.duplicate_count: int = 0
        self.retry_scheduled_count: int = 0
        self.dead_lettered_count: int = 0
        self.rejected_count: int = 0
        self.failed_count: int = 0
        self.deferred_count: int = 0
        self._consecutive_publish_failures: int = 0

    @property
    def is_running(self) -> bool:
        return self._is_running and self.connection_manager.is_connected

    async def start(self) -> None:
        """Starts consuming messages from the notification queue."""
        async with self._lock:
            if self._is_running:
                return

            await self.connection_manager.connect()
            queue = await self.connection_manager.get_queue()

            self._consumer_tag = await queue.consume(self._handle_message, no_ack=False)
            self._is_running = True
            logger.info(
                "[NOTIFICATION RABBITMQ CONSUMER STARTED] Consuming queue '%s' (tag=%s, max_retries=%d, prefetch=%d)",
                self.settings.queue_name,
                self._consumer_tag,
                self.settings.max_retries,
                self.settings.prefetch_count,
            )

    async def stop(self) -> None:
        """Stops consumption and cancels consumer tag gracefully."""
        async with self._lock:
            if not self._is_running:
                return

            self._is_running = False
            if self._consumer_tag and self.connection_manager.is_connected:
                try:
                    queue = await self.connection_manager.get_queue()
                    await queue.cancel(self._consumer_tag)
                except Exception as exc:
                    logger.debug("[NOTIFICATION RABBITMQ CONSUMER] Cancel error: %s", exc)
                self._consumer_tag = None

            await self.connection_manager.close()
            logger.info("[NOTIFICATION RABBITMQ CONSUMER STOPPED]")

    # -------------------------------------------------------------------------
    # Idempotency Helpers (Sync / Async Dispatch)
    # -------------------------------------------------------------------------

    async def _try_claim(self, event_id: str) -> bool:
        """Attempts to acquire atomic lease on event_id."""
        if isinstance(self.idempotency_store, RedisIdempotencyStore):
            return await self.idempotency_store.try_claim_async(
                event_id,
                claim_ttl=self.redis_settings.processing_claim_ttl_seconds,
            )
        return self.idempotency_store.try_claim(event_id)

    async def _claim(self, event_id: str) -> ClaimStatus:
        """Claims event_id and reports CLAIMED / DONE / IN_PROGRESS (CP8.5).

        Raises when the idempotency store is unavailable.
        """
        if isinstance(self.idempotency_store, RedisIdempotencyStore):
            return await self.idempotency_store.claim_async(
                event_id,
                claim_ttl=self.redis_settings.processing_claim_ttl_seconds,
            )
        return self.idempotency_store.claim(event_id)

    async def _mark_done(self, event_id: str) -> None:
        """Transitions state to DONE with long-term retention."""
        if isinstance(self.idempotency_store, RedisIdempotencyStore):
            await self.idempotency_store.mark_done_async(
                event_id,
                ttl_seconds=self.redis_settings.idempotency_ttl_seconds,
            )
        else:
            self.idempotency_store.mark_done(event_id)

    async def _release_claim(self, event_id: str) -> None:
        """Releases lease upon temporary failure so delayed retries can proceed."""
        if isinstance(self.idempotency_store, RedisIdempotencyStore):
            await self.idempotency_store.release_claim_async(event_id)
        else:
            self.idempotency_store.release_claim(event_id)

    # -------------------------------------------------------------------------
    # Publish-Then-ACK Safety Helpers (CP7.5 Section 9)
    # -------------------------------------------------------------------------

    async def _publish_to_exchange(
        self,
        exchange_name: str,
        routing_key: str,
        body: bytes,
        headers: Dict[str, Any],
        content_type: str = "application/json",
    ) -> None:
        """Publishes a persistent message with broker publisher confirm."""
        channel: AbstractRobustChannel = await self.connection_manager.get_channel()
        exchange = await channel.get_exchange(exchange_name)
        msg = aio_pika.Message(
            body=body,
            content_type=content_type,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers=headers,
            type=routing_key,
        )
        await exchange.publish(msg, routing_key=routing_key)

    async def _nack_with_backoff(self, message: AbstractIncomingMessage, event_id: str) -> None:
        """Requeues a message after an exponential, capped delay (CP8.5).

        Used only when the broker cannot accept a deferral/retry publish, so the
        message is never ACKed without a confirmed copy and never hot-requeued.
        """
        self._consecutive_publish_failures += 1
        delay_ms = min(
            self.settings.nack_backoff_max_ms,
            self.settings.nack_backoff_base_ms * (2 ** min(self._consecutive_publish_failures - 1, 16)),
        )
        logger.warning(
            "[RABBITMQ CONSUMER NACK BACKOFF] eventId='%s' requeue in %dms (consecutive failures=%d)",
            event_id,
            delay_ms,
            self._consecutive_publish_failures,
        )
        await asyncio.sleep(delay_ms / 1000.0)
        try:
            await message.nack(requeue=True)
        except Exception as exc:
            logger.error("[RABBITMQ CONSUMER] nack after backoff failed for eventId='%s': %s", event_id, exc)

    async def _defer(
        self,
        message: AbstractIncomingMessage,
        raw_headers: Dict[str, Any],
        routing_key: str,
        event_id: str,
        event_type: str,
        producer: str,
        retry_count: int,
        reason: str,
    ) -> None:
        """Re-schedules an event whose processing is not confirmed (CP8.5).

        The event is re-published through the existing retry exchange/queue (delayed
        by its TTL) and the original is ACKed only after the broker confirmed the
        copy. Deferrals are counted in x-defer-count and do not consume the
        processing-failure budget in x-retry-count. After max_defers the event is
        dead-lettered with x-dead-letter-reason='defer_exhausted'.
        """
        defer_count = int(raw_headers.get("x-defer-count", 0))
        headers = dict(raw_headers)
        headers["x-original-routing-key"] = raw_headers.get("x-original-routing-key", routing_key)
        headers["x-defer-reason"] = reason

        if defer_count >= self.settings.max_defers:
            headers["x-defer-count"] = defer_count
            headers["x-dead-letter-reason"] = "defer_exhausted"
            target_exchange, target_rk, result = self.settings.dlx_exchange, self.settings.dlq_routing_key, "dead_lettered"
        else:
            headers["x-defer-count"] = defer_count + 1
            target_exchange, target_rk, result = self.settings.retry_exchange, self.settings.retry_routing_key, "deferred"

        logger.info(
            "[RABBITMQ_METRIC] eventId='%s' eventType='%s' producer='%s' routingKey='%s' "
            "retryCount=%d deferCount=%d result='%s' reason='%s'",
            event_id,
            event_type,
            producer,
            routing_key,
            retry_count,
            headers["x-defer-count"],
            result,
            reason,
        )
        try:
            await self._publish_to_exchange(
                exchange_name=target_exchange,
                routing_key=target_rk,
                body=message.body,
                headers=headers,
            )
        except Exception as pub_err:
            logger.critical(
                "[RABBITMQ CONSUMER DEFER PUBLISH FAILED] eventId='%s': %s. Not ACKing original message.",
                event_id,
                pub_err,
            )
            await self._nack_with_backoff(message, event_id)
            return

        self._consecutive_publish_failures = 0
        if result == "dead_lettered":
            self.dead_lettered_count += 1
        else:
            self.deferred_count += 1
        try:
            await message.ack()
        except Exception as ack_exc:
            logger.error("[RABBITMQ CONSUMER] ACK after defer failed for eventId='%s': %s", event_id, ack_exc)

    # -------------------------------------------------------------------------
    # Main Message Pipeline
    # -------------------------------------------------------------------------

    async def _handle_message(self, message: AbstractIncomingMessage) -> None:
        """Message handler executing validate -> idempotency -> map -> process -> ACK/retry/DLQ."""
        self.received_count += 1
        routing_key = getattr(message, "routing_key", "")
        raw_headers = dict(getattr(message, "headers", None) or {})
        retry_count = int(raw_headers.get("x-retry-count", 0))

        # 1. Parse and validate canonical envelope
        try:
            envelope = CanonicalEnvelope.parse_raw_json(message.body)
        except PermanentEnvelopeError as exc:
            self.rejected_count += 1
            logger.error(
                "[RABBITMQ CONSUMER REJECT] Permanent message error (routingKey='%s'): %s. "
                "Rejecting message with requeue=False (routes to DLQ via x-dead-letter-exchange).",
                routing_key,
                exc,
            )
            logger.info(
                "[RABBITMQ_METRIC] eventId='UNKNOWN' eventType='UNKNOWN' producer='UNKNOWN' "
                "routingKey='%s' retryCount=%d result='invalid' reason='%s'",
                routing_key,
                retry_count,
                str(exc),
            )
            # Permanent failure: reject without requeueing (routes to DLQ via broker x-dead-letter-exchange)
            try:
                await message.reject(requeue=False)
            except Exception as rej_exc:
                logger.error("[RABBITMQ CONSUMER] Reject ACK error: %s", rej_exc)
            return
        except Exception as exc:
            self.rejected_count += 1
            logger.error(
                "[RABBITMQ CONSUMER REJECT] Unexpected parse error: %s. Rejecting with requeue=False (routes to DLQ).",
                exc,
            )
            logger.info(
                "[RABBITMQ_METRIC] eventId='UNKNOWN' eventType='UNKNOWN' producer='UNKNOWN' "
                "routingKey='%s' retryCount=%d result='invalid' reason='%s'",
                routing_key,
                retry_count,
                str(exc),
            )
            try:
                await message.reject(requeue=False)
            except Exception:
                pass
            return

        event_id = envelope.event_id
        event_type = envelope.event_type
        producer = envelope.producer

        logger.info(
            "[RABBITMQ CONSUMER RECEIVED] eventId='%s' eventType='%s' producer='%s' routingKey='%s' retryCount=%d",
            event_id,
            event_type,
            producer,
            routing_key,
            retry_count,
        )

        # 2. Check message idempotency and acquire atomic claim.
        #    Only a DONE state may be ACKed as duplicate. A PROCESSING lease held by another
        #    (possibly crashed) delivery, or an unavailable store, means the event is not
        #    confirmed processed: defer it through the retry queue instead of ACKing (CP8.5).
        try:
            claim_status = await self._claim(event_id)
        except Exception as claim_err:
            logger.error("[RABBITMQ CONSUMER] Idempotency store failure for eventId='%s': %s", event_id, claim_err)
            await self._defer(
                message, raw_headers, routing_key, event_id, event_type, producer, retry_count,
                reason="idempotency_store_unavailable",
            )
            return

        if claim_status == ClaimStatus.IN_PROGRESS:
            logger.warning(
                "[RABBITMQ CONSUMER IN PROGRESS] eventId='%s' lease held by another delivery; deferring (not ACKing as duplicate).",
                event_id,
            )
            await self._defer(
                message, raw_headers, routing_key, event_id, event_type, producer, retry_count,
                reason="claim_in_progress",
            )
            return

        if claim_status == ClaimStatus.DONE:
            self.duplicate_count += 1
            logger.info(
                "[RABBITMQ CONSUMER DUPLICATE] eventId='%s' already processed (DONE). Discarding side-effects and ACKing.",
                event_id,
            )
            logger.info(
                "[RABBITMQ_METRIC] eventId='%s' eventType='%s' producer='%s' routingKey='%s' "
                "retryCount=%d result='duplicate' reason='already_done'",
                event_id,
                event_type,
                producer,
                routing_key,
                retry_count,
            )
            try:
                await message.ack()
            except Exception as ack_exc:
                logger.error("[RABBITMQ CONSUMER] Duplicate ACK error: %s", ack_exc)
            return

        # 3. Map and process through application service inside the durable inbox:
        #    the processed_events marker and all notification_db changes commit together.
        try:
            inbox_result = self.inbox.process_once(
                event_id,
                event_type,
                producer,
                lambda: self.mapper.process_envelope(envelope),
            )
        except PermanentEnvelopeError as exc:
            self.rejected_count += 1
            logger.error(
                "[RABBITMQ CONSUMER PAYLOAD REJECT] eventId='%s' permanent error: %s. Rejecting with requeue=False (routes to DLQ).",
                event_id,
                exc,
            )
            logger.info(
                "[RABBITMQ_METRIC] eventId='%s' eventType='%s' producer='%s' routingKey='%s' "
                "retryCount=%d result='invalid' reason='%s'",
                event_id,
                event_type,
                producer,
                routing_key,
                retry_count,
                str(exc),
            )
            await self._release_claim(event_id)
            try:
                await message.reject(requeue=False)
            except Exception:
                pass
            return
        except Exception as exc:
            self.failed_count += 1
            logger.error(
                "[RABBITMQ CONSUMER PROCESSING FAILED] eventId='%s' error: %s. Evaluating bounded retry.",
                event_id,
                exc,
                exc_info=True,
            )

            # Bounded Retry Evaluation (CP7.5 Sections 5, 6, 8, 9)
            if retry_count < self.settings.max_retries:
                next_retries = retry_count + 1
                self.retry_scheduled_count += 1
                logger.warning(
                    "[RABBITMQ CONSUMER RETRY] eventId='%s' attempt %d/%d failed. Routing to retry exchange '%s' (TTL=%dms).",
                    event_id,
                    next_retries,
                    self.settings.max_retries,
                    self.settings.retry_exchange,
                    self.settings.retry_ttl_ms,
                )
                logger.info(
                    "[RABBITMQ_METRIC] eventId='%s' eventType='%s' producer='%s' routingKey='%s' "
                    "retryCount=%d result='retry_scheduled' reason='%s'",
                    event_id,
                    event_type,
                    producer,
                    routing_key,
                    next_retries,
                    str(exc),
                )

                # Release claim so retry delivery can re-acquire lease
                await self._release_claim(event_id)

                retry_headers = dict(raw_headers)
                retry_headers["x-retry-count"] = next_retries
                retry_headers["x-original-routing-key"] = routing_key
                retry_headers["x-error-message"] = str(exc)

                try:
                    # 1. Publish to retry exchange with publisher confirm
                    await self._publish_to_exchange(
                        exchange_name=self.settings.retry_exchange,
                        routing_key=self.settings.retry_routing_key,
                        body=message.body,
                        headers=retry_headers,
                    )
                    # 2. Only after publisher confirm, ACK original message (Publish-then-ACK safety)
                    await message.ack()
                    self._consecutive_publish_failures = 0
                except Exception as pub_err:
                    logger.critical(
                        "[RABBITMQ CONSUMER RETRY PUBLISH FAILED] eventId='%s': %s. Not ACKing original message.",
                        event_id,
                        pub_err,
                    )
                    # Return the message to the queue after a bounded backoff instead of leaving it
                    # unacknowledged on the channel (CP8.5).
                    await self._nack_with_backoff(message, event_id)
                return
            else:
                # Retry Exhausted -> Route to DLQ (CP7.5 Section 8, 9)
                self.dead_lettered_count += 1
                logger.error(
                    "[RABBITMQ CONSUMER EXHAUSTED] eventId='%s' exceeded max retries (%d/%d). Routing to DLX '%s'.",
                    event_id,
                    retry_count,
                    self.settings.max_retries,
                    self.settings.dlx_exchange,
                )
                logger.info(
                    "[RABBITMQ_METRIC] eventId='%s' eventType='%s' producer='%s' routingKey='%s' "
                    "retryCount=%d result='dead_lettered' reason='retry_exhausted'",
                    event_id,
                    event_type,
                    producer,
                    routing_key,
                    retry_count,
                )

                dlq_headers = dict(raw_headers)
                dlq_headers["x-retry-count"] = retry_count
                dlq_headers["x-dead-letter-reason"] = "retry_exhausted"
                dlq_headers["x-original-routing-key"] = routing_key
                dlq_headers["x-error-message"] = str(exc)

                try:
                    # Publish to DLX with publisher confirm
                    await self._publish_to_exchange(
                        exchange_name=self.settings.dlx_exchange,
                        routing_key=self.settings.dlq_routing_key,
                        body=message.body,
                        headers=dlq_headers,
                    )
                    # Acknowledge original message once safely in DLQ
                    await message.ack()
                except Exception as dlq_err:
                    logger.critical(
                        "[RABBITMQ CONSUMER DLQ PUBLISH FAILED] eventId='%s': %s. Falling back to reject requeue=False.",
                        event_id,
                        dlq_err,
                    )
                    try:
                        await message.reject(requeue=False)
                    except Exception:
                        pass
                return

        if inbox_result == InboxResult.ALREADY_PROCESSED:
            # Effects were committed by an earlier delivery whose Redis DONE was lost
            # (crash before mark_done, or Redis data loss). Restore DONE and discard.
            self.duplicate_count += 1
            try:
                await self._mark_done(event_id)
            except Exception as store_err:
                logger.error("[RABBITMQ CONSUMER] Failed to restore DONE for eventId='%s': %s", event_id, store_err)
            logger.info(
                "[RABBITMQ_METRIC] eventId='%s' eventType='%s' producer='%s' routingKey='%s' "
                "retryCount=%d result='duplicate' reason='already_processed_durable'",
                event_id,
                event_type,
                producer,
                routing_key,
                retry_count,
            )
            try:
                await message.ack()
            except Exception as ack_exc:
                logger.error("[RABBITMQ CONSUMER] Duplicate ACK error: %s", ack_exc)
            return

        # 4. Mark DONE & ACK only after successful application processing
        try:
            await self._mark_done(event_id)
        except Exception as store_err:
            logger.error("[RABBITMQ CONSUMER] Failed to mark eventId='%s' DONE: %s", event_id, store_err)

        try:
            await message.ack()
            self.processed_count += 1
            logger.info(
                "[RABBITMQ CONSUMER ACK] eventId='%s' processed and acknowledged successfully.",
                event_id,
            )
            logger.info(
                "[RABBITMQ_METRIC] eventId='%s' eventType='%s' producer='%s' routingKey='%s' "
                "retryCount=%d result='processed' reason='success'",
                event_id,
                event_type,
                producer,
                routing_key,
                retry_count,
            )
        except Exception as ack_exc:
            logger.error("[RABBITMQ CONSUMER] ACK error for eventId='%s': %s", event_id, ack_exc)


__all__ = ["RabbitMQAlertConsumer"]
