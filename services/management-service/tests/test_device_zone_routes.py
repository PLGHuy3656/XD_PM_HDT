import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.routes.device_routes import update_device_zone
from app.schemas.device import DeviceZoneUpdateRequest


class DeviceZoneRouteTests(unittest.TestCase):
    def test_owner_cannot_move_device_zone(self):
        with self.assertRaises(HTTPException) as raised:
            update_device_zone(
                "node-01",
                DeviceZoneUpdateRequest(zone_id="zone-02"),
                {"roles": ["FARM_OWNER"]},
            )

        self.assertEqual(raised.exception.status_code, 403)

    @patch("app.routes.device_routes.device_controller.update_device_zone")
    @patch("app.routes.device_routes.verify_farm_resource_access")
    @patch("app.routes.device_routes.user_repository.get_farm_id_for_zone")
    @patch("app.routes.device_routes.user_repository.get_farm_id_for_device")
    def test_rejects_zone_from_another_farm(
        self,
        get_farm_for_device,
        get_farm_for_zone,
        verify_access,
        update,
    ):
        get_farm_for_device.return_value = "farm-01"
        get_farm_for_zone.return_value = "farm-02"

        with self.assertRaises(HTTPException) as raised:
            update_device_zone(
                "node-01",
                DeviceZoneUpdateRequest(zone_id="zone-02"),
                {"id": "technician-01", "roles": ["TECHNICIAN"]},
            )

        self.assertEqual(raised.exception.status_code, 400)
        verify_access.assert_called_once()
        update.assert_not_called()

    @patch(
        "app.routes.device_routes.device_controller.update_device_zone",
        return_value={"status": "updated"},
    )
    @patch("app.routes.device_routes.verify_farm_resource_access")
    @patch("app.routes.device_routes.user_repository.get_farm_id_for_zone")
    @patch("app.routes.device_routes.user_repository.get_farm_id_for_device")
    def test_allows_assigned_technician_to_move_device_within_farm(
        self,
        get_farm_for_device,
        get_farm_for_zone,
        verify_access,
        update,
    ):
        get_farm_for_device.return_value = "farm-01"
        get_farm_for_zone.return_value = "farm-01"

        result = update_device_zone(
            "node-01",
            DeviceZoneUpdateRequest(zone_id="zone-02"),
            {"id": "technician-01", "roles": ["TECHNICIAN"]},
        )

        self.assertEqual(result, {"status": "updated"})
        verify_access.assert_called_once()
        update.assert_called_once_with("node-01", "farm-01", "zone-02")


if __name__ == "__main__":
    unittest.main()
