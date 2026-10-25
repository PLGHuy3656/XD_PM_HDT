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


zone_service = ZoneService()
