"""Child process for real crash / redelivery tests of the Notification RabbitMQ consumer.

Runs the production RabbitMQAlertConsumer against real RabbitMQ, Redis and
PostgreSQL in its own OS process so the parent test can SIGKILL it at precise
points. Test-only fault injection is applied by monkeypatching inside this
process; production code is not modified for testing.

Usage:
    python consumer_crash_child.py <mode> <redis_key_prefix> <claim_ttl_s> <marker_file> <farm_id>

Modes:
    normal               consume until terminated
    hang_before_process  claim the event, write marker, then block forever (parent kills -9)
    crash_after_commit   process + commit to PostgreSQL, then os._exit before Redis mark_done
    fail_once_after_alert_write  first attempt raises after the alert write (rollback), retry succeeds
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVICE_ROOT))

import redis.asyncio as aioredis  # noqa: E402

from app.dependencies import init_app_state  # noqa: E402
from app.infrastructure.rabbitmq.config import RabbitMQSettings, RedisSettings  # noqa: E402
from app.infrastructure.rabbitmq.connection import RabbitMQConnectionManager  # noqa: E402
from app.infrastructure.rabbitmq.consumer import RabbitMQAlertConsumer  # noqa: E402
from app.infrastructure.rabbitmq.idempotency import RedisIdempotencyStore  # noqa: E402
from app.infrastructure.rabbitmq.inbox import PostgresEventInbox  # noqa: E402
from app.ports.recipient_resolver import RecipientInfo  # noqa: E402
from app.repositories.postgres_alert_repo import PostgreSQLAlertRepository  # noqa: E402
from app.repositories.postgres_notification_repo import PostgreSQLNotificationRepository  # noqa: E402
from app.repositories.postgres_user_device_repo import PostgreSQLUserDeviceRepository  # noqa: E402
from app.services.in_memory_recipient_resolver import InMemoryRecipientResolver  # noqa: E402
from app.services.mock_fcm_provider import MockFCMProvider  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", stream=sys.stdout)


async def main() -> None:
    mode, prefix, claim_ttl, marker, farm_id = sys.argv[1:6]
    claim_ttl_s = int(claim_ttl)
    db_url = os.environ["NOTIFICATION_DATABASE_URL"]

    resolver = InMemoryRecipientResolver()
    resolver.register_recipient(farm_id, RecipientInfo(user_id="user_crash_test", email="crash@test.vn", roles=["FARM_OWNER"]))
    service = init_app_state(
        alert_repo=PostgreSQLAlertRepository(db_url),
        notification_repo=PostgreSQLNotificationRepository(db_url),
        user_device_repo=PostgreSQLUserDeviceRepository(db_url),
        recipient_resolver=resolver,
        fcm_provider=MockFCMProvider(),
    )

    store = RedisIdempotencyStore(
        redis_client=aioredis.Redis(host="127.0.0.1", port=6379, db=0, decode_responses=False),
        idempotency_ttl_seconds=3600,
        processing_claim_ttl_seconds=claim_ttl_s,
        key_prefix=prefix,
    )
    settings = RabbitMQSettings(
        host="127.0.0.1", port=5672, user="swiftlet", password="swiftlet123", vhost="/",
        queue_name="notification.alert-events.v1", prefetch_count=10, enabled=True,
        max_retries=int(os.getenv("RABBITMQ_MAX_RETRIES", "3")),
        retry_ttl_ms=5000,
        max_defers=int(os.getenv("RABBITMQ_MAX_DEFERS", "120")),
    )
    redis_settings = RedisSettings(processing_claim_ttl_seconds=claim_ttl_s, idempotency_ttl_seconds=3600)
    consumer = RabbitMQAlertConsumer(
        service=service,
        connection_manager=RabbitMQConnectionManager(settings=settings),
        idempotency_store=store,
        settings=settings,
        redis_settings=redis_settings,
        inbox=PostgresEventInbox(db_url),
    )

    if mode == "hang_before_process":
        def hang(envelope):  # runs after the claim was acquired
            Path(marker).write_text(envelope.event_id)
            time.sleep(3600)
        consumer.mapper.process_envelope = hang
    elif mode == "fail_once_after_alert_write":
        # First delivery: the alert row is written inside the transaction, then the first
        # notification insert fails -> whole transaction must roll back (no marker, no alert).
        repo = service.notification_repo
        original_save = repo.save
        state = {"failed": False}

        def flaky_save(notification):
            if not state["failed"]:
                state["failed"] = True
                Path(marker).write_text("failed-once")
                raise RuntimeError("injected notification insert failure")
            return original_save(notification)

        repo.save = flaky_save
    elif mode == "crash_after_commit":
        async def crash_mark_done(event_id: str) -> None:
            Path(marker).write_text(event_id)
            os._exit(137)  # PostgreSQL already committed; Redis DONE never written
        consumer._mark_done = crash_mark_done

    await consumer.start()
    print("CHILD_READY", flush=True)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop.set)
    await stop.wait()
    await consumer.stop()


if __name__ == "__main__":
    asyncio.run(main())
