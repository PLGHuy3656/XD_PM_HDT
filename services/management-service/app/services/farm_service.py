from app.repositories.farm_repository import FarmRepository, farm_repository


class FarmService:
    def __init__(self, repository: FarmRepository | None = None):
        self.repository = repository or farm_repository

    def list_farms(self, current_user: dict | None = None):
        if not current_user or not isinstance(current_user, dict) or not current_user.get("id"):
            return []
        try:
            return self.repository.list_farms(current_user)
        except TypeError:
            # Repository error or parameter mismatch: fail closed, do NOT fallback to SELECT ALL
            return []

    def get_farm(self, farm_id: str):
        if not farm_id:
            raise ValueError("farm_id is required")
        return self.repository.get_farm_by_id(farm_id)


farm_service = FarmService()
