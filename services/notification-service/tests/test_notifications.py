import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.delivery import send_fcm
from app.consumer import (
    RETRY_DELAY_MS,
    _build_retry_message,
    _retry_queue_arguments,
    deliver_pending_notifications,
    process_event,
)
from app.main import app
from app.repositories import notification_content
from app.schemas import FcmTokenRequest, PushSubscriptionRequest


class NotificationContentTests(unittest.TestCase):
    def test_assignment_notifies_the_assigned_technician(self):
        content = notification_content(
            "management.technician_assigned",
            {
                "technician_id": "technician-id",
                "farm_name": "Nhà yến A",
            },
            "technician-id",
        )

        self.assertEqual(
            content,
            (
                "Phân công nhà yến mới",
                "Bạn được phân công phụ trách Nhà yến A.",
                "info",
            ),
        )

    def test_failed_command_ack_is_danger_category(self):
        content = notification_content(
            "device.command.acknowledged",
            {
                "status": "FAILED",
                "node_id": "node-01",
                "action": "relay",
            },
            "user-id",
        )

        self.assertEqual(content[2], "danger")
        self.assertIn("node-01", content[1])

    def test_environment_threshold_event_contains_reading_and_location(self):
        content = notification_content(
            "environment.threshold_exceeded",
            {
                "metric": "Nhiệt độ",
                "value": 38,
                "unit": "°C",
                "threshold": 35,
                "farm_name": "Nhà yến A",
                "zone_name": "Khu A",
            },
            "user-id",
        )

        self.assertEqual(content[0], "Thông số môi trường vượt ngưỡng")
        self.assertIn("38°C", content[1])
        self.assertIn("Nhà yến A", content[1])
        self.assertEqual(content[2], "danger")

    def test_device_offline_and_sensor_timeout_are_danger_notifications(self):
        offline = notification_content(
            "device.offline",
            {"node_id": "node-01", "farm_name": "Nhà yến A"},
            "user-id",
        )
        timeout = notification_content(
            "device.sensor.timeout",
            {
                "node_id": "node-01",
                "sensor_name": "DHT22",
                "farm_name": "Nhà yến A",
            },
            "user-id",
        )

        self.assertEqual(offline[2], "danger")
        self.assertIn("node-01", offline[1])
        self.assertEqual(timeout[2], "danger")
        self.assertIn("DHT22", timeout[1])

    def test_ai_threat_and_work_request_events_are_formatted(self):
        threat = notification_content(
            "ai.threat.detected",
            {
                "threat_type": "predator",
                "farm_name": "Nhà yến A",
                "confidence": 0.91,
            },
            "user-id",
        )
        work_request = notification_content(
            "management.work_request.created",
            {"work_request_id": "WR-1", "farm_name": "Nhà yến A"},
            "user-id",
        )

        self.assertEqual(threat[2], "danger")
        self.assertIn("91%", threat[1])
        self.assertEqual(work_request[2], "warning")
        self.assertIn("WR-1", work_request[1])

    def test_push_subscriptions_reject_untrusted_urls(self):
        with self.assertRaises(ValueError):
            PushSubscriptionRequest.model_validate(
                {
                    "endpoint": "https://127.0.0.1/internal",
                    "keys": {"p256dh": "key", "auth": "secret"},
                }
            )

    def test_push_subscriptions_accept_public_push_provider(self):
        subscription = PushSubscriptionRequest.model_validate(
            {
                "endpoint": "https://fcm.googleapis.com/send/test",
                "keys": {"p256dh": "key", "auth": "secret"},
            }
        )

        self.assertEqual(subscription.endpoint.host, "fcm.googleapis.com")


class NotificationDeliveryTests(unittest.TestCase):
    def test_fcm_delivery_uses_registered_user_token(self):
        import firebase_admin

        notification = {
            "id": "40000000-0000-4000-8000-000000000001",
            "event_type": "ai.threat.detected",
            "title": "Threat detected",
            "message": "A threat was detected.",
        }

        with (
            patch(
                "app.delivery.settings.firebase_service_account_path",
                "service-account.json",
            ),
            patch(
                "app.delivery.repositories.get_fcm_tokens",
                return_value=["registered-token"],
            ),
            patch(
                "firebase_admin.get_app",
                side_effect=ValueError("not initialized"),
            ),
            patch("firebase_admin.credentials.Certificate"),
            patch(
                "firebase_admin.initialize_app",
                return_value=object(),
            ),
            patch(
                "firebase_admin.messaging.send",
                return_value="message-id",
            ) as send,
        ):
            delivered = send_fcm(
                notification,
                "20000000-0000-4000-8000-000000000001",
            )

        self.assertTrue(delivered)
        message = send.call_args.args[0]
        self.assertEqual(message.token, "registered-token")
        self.assertEqual(message.notification.title, "Threat detected")


class NotificationConsumerTests(unittest.IsolatedAsyncioTestCase):
    def test_retry_queue_waits_and_preserves_original_event_routing_key(self):
        arguments = _retry_queue_arguments("swiftletcare.notifications")

        self.assertEqual(arguments["x-message-ttl"], RETRY_DELAY_MS)
        self.assertEqual(arguments["x-dead-letter-exchange"], "")
        self.assertEqual(
            arguments["x-dead-letter-routing-key"],
            "swiftletcare.notifications",
        )

    def test_retry_message_preserves_metadata_and_increments_retry_count(self):
        import aio_pika

        message = aio_pika.Message(
            body=b'{"event_type":"management.technician_assigned"}',
            content_type="application/json",
            headers={"x-notification-retry": 1, "trace-id": "trace-1"},
            message_id="event-1",
            correlation_id="correlation-1",
        )

        retry_message = _build_retry_message(message, 1)

        self.assertEqual(retry_message.headers["x-notification-retry"], 2)
        self.assertEqual(retry_message.headers["trace-id"], "trace-1")
        self.assertEqual(retry_message.message_id, "event-1")
        self.assertEqual(retry_message.correlation_id, "correlation-1")
        self.assertIsNone(retry_message.expiration)

    async def test_event_is_persisted_once_per_unique_recipient(self):
        event = {
            "event_id": "10000000-0000-4000-8000-000000000001",
            "event_type": "management.technician_assigned",
            "recipient_user_ids": [
                "20000000-0000-4000-8000-000000000001",
                "20000000-0000-4000-8000-000000000001",
            ],
            "data": {
                "technician_id": "20000000-0000-4000-8000-000000000001",
                "farm_name": "Nhà yến A",
            },
        }
        notification = {"id": "notification-id"}

        with (
            patch(
                "app.consumer.repositories.create_notification",
                return_value=notification,
            ) as create_notification,
            patch(
                "app.consumer.notification_connections.broadcast",
                new_callable=AsyncMock,
            ) as broadcast,
        ):
            await process_event(event)

        create_notification.assert_called_once()
        broadcast.assert_awaited_once_with(
            "20000000-0000-4000-8000-000000000001",
            {"type": "notification", "notification": notification},
        )

    async def test_rejects_event_without_recipient_list(self):
        with self.assertRaises(ValueError):
            await process_event(
                {
                    "event_id": "10000000-0000-4000-8000-000000000001",
                    "event_type": "management.technician_assigned",
                    "data": {},
                }
            )

    async def test_ignores_non_notification_event_types(self):
        with patch(
            "app.consumer.repositories.create_notification"
        ) as create_notification:
            await process_event(
                {
                    "event_type": "device.telemetry.received",
                    "recipient_user_ids": [],
                    "data": {},
                }
            )

        create_notification.assert_not_called()

    async def test_delivery_worker_marks_configured_channel_delivered(self):
        delivery = {
            "delivery_id": "30000000-0000-4000-8000-000000000001",
            "channel": "email",
            "attempts": 1,
            "notification": {
                "id": "40000000-0000-4000-8000-000000000001",
                "user_id": "20000000-0000-4000-8000-000000000001",
                "event_type": "management.technician_assigned",
                "title": "Assignment",
                "message": "Assigned",
            },
        }

        with (
            patch(
                "app.consumer.repositories.claim_pending_delivery",
                side_effect=[delivery, None],
            ),
            patch(
                "app.consumer.repositories.get_user_email",
                return_value=("owner@example.com", "Owner"),
            ),
            patch("app.consumer.send_email", return_value=True) as send_email,
            patch(
                "app.consumer.repositories.finish_delivery",
            ) as finish_delivery,
            patch(
                "app.consumer.asyncio.sleep",
                new_callable=AsyncMock,
                side_effect=asyncio.CancelledError,
            ),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await deliver_pending_notifications()

        send_email.assert_called_once()
        finish_delivery.assert_called_once_with(
            delivery["delivery_id"],
            status="delivered",
        )

    async def test_delivery_worker_schedules_retry_after_channel_error(self):
        delivery = {
            "delivery_id": "30000000-0000-4000-8000-000000000001",
            "channel": "email",
            "attempts": 1,
            "notification": {
                "id": "40000000-0000-4000-8000-000000000001",
                "user_id": "20000000-0000-4000-8000-000000000001",
                "event_type": "management.technician_assigned",
                "title": "Assignment",
                "message": "Assigned",
            },
        }

        with (
            patch(
                "app.consumer.repositories.claim_pending_delivery",
                side_effect=[delivery, None],
            ),
            patch(
                "app.consumer.repositories.get_user_email",
                return_value=("owner@example.com", "Owner"),
            ),
            patch(
                "app.consumer.send_email",
                side_effect=RuntimeError("SMTP unavailable"),
            ),
            patch(
                "app.consumer.repositories.finish_delivery",
            ) as finish_delivery,
            patch(
                "app.consumer.asyncio.sleep",
                new_callable=AsyncMock,
                side_effect=asyncio.CancelledError,
            ),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await deliver_pending_notifications()

        finish_delivery.assert_called_once_with(
            delivery["delivery_id"],
            status="failed",
            error="SMTP unavailable",
            retry_delay_seconds=5,
        )


class NotificationApiTests(unittest.TestCase):
    def test_health_endpoint_is_available(self):
        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "notification-service")

    def test_notification_list_requires_authentication(self):
        with TestClient(app) as client:
            response = client.get("/api/notifications")

        self.assertEqual(response.status_code, 401)

    def test_fcm_token_requires_supported_platform(self):
        with self.assertRaises(ValueError):
            FcmTokenRequest.model_validate(
                {"token": "token-value", "platform": "desktop"}
            )

    def test_register_fcm_token_requires_authentication(self):
        with TestClient(app) as client:
            response = client.post(
                "/api/notifications/fcm-tokens",
                json={"token": "token-value", "platform": "android"},
            )

        self.assertEqual(response.status_code, 401)

    def test_register_fcm_token_saves_token_for_authenticated_user(self):
        with (
            patch(
                "app.routes.get_user_from_authorization",
                new_callable=AsyncMock,
                return_value={"id": "20000000-0000-4000-8000-000000000001"},
            ),
            patch("app.routes.repositories.save_fcm_token") as save_token,
            TestClient(app) as client,
        ):
            response = client.post(
                "/api/notifications/fcm-tokens",
                headers={"Authorization": "Bearer test-token"},
                json={"token": "device-token", "platform": "android"},
            )

        self.assertEqual(response.status_code, 204)
        save_token.assert_called_once_with(
            "20000000-0000-4000-8000-000000000001",
            "device-token",
            "android",
        )
