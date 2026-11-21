"""INT03-R1: Management business events rendering, explicit recipients, location enrichment."""
import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app import consumer
from app.repositories import notification_content

OWNER = str(uuid.uuid4())
TECH = str(uuid.uuid4())
ADMIN = str(uuid.uuid4())
FARM = str(uuid.uuid4())


def envelope(event_type, payload):
    return {"eventId": str(uuid.uuid4()), "eventType": event_type, "eventVersion": "1.0",
            "occurredAt": "2026-11-21T00:00:00+00:00", "producer": "management-service", "payload": payload}


@pytest.mark.parametrize("event_type", sorted(e for e in consumer.SUPPORTED_EVENT_TYPES if e.startswith("management.") and "." in e[11:]))
def test_every_supported_management_event_renders(event_type):
    title, message, category = notification_content(event_type, {"farmName": "Farm A", "requestCode": "IR-1"}, OWNER)
    assert title and message and category in {"info", "warning", "danger"}


def test_farm_rejected_shows_reason_and_is_not_critical():
    title, message, category = notification_content("management.farm.rejected", {"farmName": "Farm A", "rejectionReason": "Thiếu hồ sơ"}, OWNER)
    assert "Thiếu hồ sơ" in message and category == "warning"


def test_assignment_message_differs_for_technician_and_owner():
    data = {"farmName": "Farm A", "technicianId": TECH, "technicianName": "Kỹ thuật viên B"}
    t_title, _, _ = notification_content("management.technician.assigned", data, TECH)
    o_title, o_msg, _ = notification_content("management.technician.assigned", data, OWNER)
    assert t_title == "Phân công nhà yến mới" and "Kỹ thuật viên B" in o_msg and o_title != t_title


def test_device_registered_is_registered_not_online():
    _, msg, cat = notification_content("management.device.registered", {"farmName": "Farm A", "deviceName": "ESP-1", "deviceType": "CONTROLLER"}, OWNER)
    assert "chờ dữ liệu kết nối" in msg and "chưa phân bổ khu vực" in msg and cat == "info"


def test_management_event_uses_explicit_recipients_only():
    ev = envelope("management.farm.approval_requested", {"farmId": FARM, "farmName": "Farm A", "recipientUserIds": [ADMIN]})
    with patch.object(consumer, "resolve_farm_recipients", AsyncMock(return_value=[OWNER, TECH])) as farm_lookup:
        adapted = asyncio.run(consumer.adapt_incoming_event(ev))
    assert adapted["recipient_user_ids"] == [ADMIN]
    farm_lookup.assert_not_awaited()
    assert "password" not in adapted["data"]


def test_location_enrichment_adds_zone_from_management():
    ev = envelope("iot.device.offline", {"farmId": FARM, "deviceId": "ESP-1"})
    loc = {"deviceId": "d1", "nodeId": "ESP-1", "deviceName": "Bộ điều khiển 1", "farmId": FARM, "farmName": "Farm A", "zoneId": "z1", "zoneName": "Tầng 2"}
    with patch.object(consumer, "resolve_farm_recipients", AsyncMock(return_value=[OWNER])), \
         patch.object(consumer, "resolve_device_location", AsyncMock(return_value=loc)):
        adapted = asyncio.run(consumer.adapt_incoming_event(ev))
    assert adapted["data"]["zoneName"] == "Tầng 2" and adapted["data"]["farmName"] == "Farm A"


def test_location_enrichment_unallocated_zone_label():
    ev = envelope("iot.device.online", {"farmId": FARM, "deviceId": "ESP-1"})
    loc = {"farmId": FARM, "farmName": "Farm A", "zoneId": None, "zoneName": None, "deviceName": "ESP-1"}
    with patch.object(consumer, "resolve_farm_recipients", AsyncMock(return_value=[OWNER])), \
         patch.object(consumer, "resolve_device_location", AsyncMock(return_value=loc)):
        adapted = asyncio.run(consumer.adapt_incoming_event(ev))
    assert adapted["data"]["zoneLabel"] == "Chưa phân bổ khu vực" and "zoneName" not in adapted["data"]


def test_location_enrichment_discarded_on_farm_mismatch():
    ev = envelope("iot.device.offline", {"farmId": FARM, "deviceId": "ESP-1"})
    loc = {"farmId": str(uuid.uuid4()), "farmName": "Other farm", "zoneId": "z9", "zoneName": "Khác"}
    with patch.object(consumer, "resolve_farm_recipients", AsyncMock(return_value=[OWNER])), \
         patch.object(consumer, "resolve_device_location", AsyncMock(return_value=loc)):
        adapted = asyncio.run(consumer.adapt_incoming_event(ev))
    assert "zoneName" not in adapted["data"] and "farmName" not in adapted["data"]


def test_location_lookup_failure_keeps_event():
    ev = envelope("iot.device.offline", {"farmId": FARM, "deviceId": "ESP-1"})
    with patch.object(consumer, "resolve_farm_recipients", AsyncMock(return_value=[OWNER])), \
         patch.object(consumer, "resolve_device_location", AsyncMock(return_value=None)):
        adapted = asyncio.run(consumer.adapt_incoming_event(ev))
    assert adapted is not None and adapted["recipient_user_ids"] == [OWNER]


def test_iot_event_cannot_redirect_recipients_with_explicit_list():
    """Security: an IoT/AI producer may not choose recipients; farm scoping always applies."""
    ev = envelope("iot.device.offline", {"farmId": FARM, "deviceId": "ESP-1", "recipientUserIds": [ADMIN]})
    ev["producer"] = "iot-service"
    with patch.object(consumer, "resolve_farm_recipients", AsyncMock(return_value=[OWNER])), \
         patch.object(consumer, "resolve_device_location", AsyncMock(return_value=None)):
        adapted = asyncio.run(consumer.adapt_incoming_event(ev))
    assert adapted["recipient_user_ids"] == [OWNER]


def test_management_event_from_other_producer_is_not_fanned_out():
    ev = envelope("management.farm.approved", {"farmId": FARM, "recipientUserIds": [ADMIN]})
    ev["producer"] = "ai-service"
    with patch.object(consumer, "resolve_farm_recipients", AsyncMock(return_value=[OWNER])) as farm_lookup:
        adapted = asyncio.run(consumer.adapt_incoming_event(ev))
    assert adapted is None
    farm_lookup.assert_not_awaited()


def test_recipient_list_is_not_persisted_in_notification_data():
    ev = envelope("management.technician.assigned", {"farmId": FARM, "technicianId": TECH, "recipientUserIds": [TECH, OWNER]})
    adapted = asyncio.run(consumer.adapt_incoming_event(ev))
    assert sorted(adapted["recipient_user_ids"]) == sorted([TECH, OWNER])
    assert "recipientUserIds" not in adapted["data"] and "recipient_user_ids" not in adapted["data"]
