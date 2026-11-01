from app.repositories.farm_repository import FarmRepository, farm_repository


class FarmService:
    def __init__(self, repository: FarmRepository | None = None):
        self.repository = repository or farm_repository

    def list_farms(self, current_user: dict):
        user_id = current_user.get("id")
        if not user_id:
            raise ValueError("Authenticated user id is required")

        roles = set(current_user.get("roles") or [])

        return self.repository.list_farms(
            user_id=str(user_id),
            is_admin="ADMIN" in roles,
            is_owner="FARM_OWNER" in roles,
            is_technician="TECHNICIAN" in roles,
        )

    def get_farm(self, farm_id: str):
        if not farm_id:
            raise ValueError("farm_id is required")
        return self.repository.get_farm_by_id(farm_id)


farm_service = FarmService()
