import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.consumer import process_event
from app.main import app
from app.repositories import notification_content
from app.schemas import PushSubscriptionRequest


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


class NotificationConsumerTests(unittest.IsolatedAsyncioTestCase):
    async def test_event_is_persisted_once_per_unique_recipient(self):
        event = {
            "event_id": "event-id",
            "event_type": "management.technician_assigned",
            "recipient_user_ids": ["user-id", "user-id"],
            "data": {
                "technician_id": "user-id",
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
            patch(
                "app.consumer._deliver_channels",
                new_callable=AsyncMock,
            ) as deliver,
        ):
            await process_event(event)

        create_notification.assert_called_once()
        broadcast.assert_awaited_once_with(
            "user-id",
            {"type": "notification", "notification": notification},
        )
        deliver.assert_awaited_once_with(notification, "user-id")

    async def test_rejects_event_without_recipient_list(self):
        with self.assertRaises(ValueError):
            await process_event(
                {
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
