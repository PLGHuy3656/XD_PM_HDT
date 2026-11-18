from app.repositories.zone_repository import ZoneRepository, zone_repository


class ZoneService:
    def __init__(self, repository: ZoneRepository | None = None):
        self.repository = repository or zone_repository

    def list_zones_by_farm(self, farm_id: str):
        if not farm_id:
            raise ValueError("farm_id is required")
        return self.repository.list_zones_by_farm(farm_id)

    def get_zone(self, zone_id: str):
        if not zone_id:
            raise ValueError("zone_id is required")
        return self.repository.get_zone_by_id(zone_id)

    def create_zone(self, farm_uuid: str, zone_code: str, name: str):
        if not farm_uuid:
            raise ValueError("farm_id is required")
        if not zone_code or not zone_code.strip():
            raise ValueError("zone_code is required")
        if not name or not name.strip():
            raise ValueError("name is required")
        return self.repository.create_zone(farm_uuid=farm_uuid, zone_code=zone_code, name=name)

    def update_zone(self, zone_id: str, zone_code: str | None = None, name: str | None = None):
        if not zone_id:
            raise ValueError("zone_id is required")
        return self.repository.update_zone(zone_id=zone_id, zone_code=zone_code, name=name)

    def delete_zone(self, zone_id: str) -> bool:
        if not zone_id:
            raise ValueError("zone_id is required")
        return self.repository.delete_zone(zone_id)


zone_service = ZoneService()
