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

    def create_farm(
        self,
        farm_code: str | None = None,
        farm_name: str = "",
        address: str | None = None,
        status: str = "ACTIVE",
        owner_id: str | None = None,
        approval_status: str = "APPROVED",
        approved_by: str | None = None,
    ):
        if not farm_name or not farm_name.strip():
            raise ValueError("farm_name is required")
        clean_code = farm_code.strip() if isinstance(farm_code, str) and farm_code.strip() else None
        return self.repository.create_farm(
            farm_code=clean_code,
            farm_name=farm_name,
            address=address,
            status=status,
            owner_id=owner_id,
            approval_status=approval_status,
            approved_by=approved_by,
        )

    def approve_farm(self, farm_id: str, admin_user_id: str):
        if not farm_id:
            raise ValueError("farm_id is required")
        if not admin_user_id:
            raise ValueError("admin_user_id is required")
        return self.repository.approve_farm(farm_id=farm_id, admin_user_id=admin_user_id)

    def reject_farm(self, farm_id: str, admin_user_id: str, rejection_reason: str):
        if not farm_id:
            raise ValueError("farm_id is required")
        if not admin_user_id:
            raise ValueError("admin_user_id is required")
        if not rejection_reason or not rejection_reason.strip():
            raise ValueError("rejection_reason is required")
        return self.repository.reject_farm(
            farm_id=farm_id,
            admin_user_id=admin_user_id,
            rejection_reason=rejection_reason,
        )

    def update_farm(
        self,
        farm_id: str,
        farm_name: str | None = None,
        address: str | None = None,
        status: str | None = None,
        owner_id: str | None = None,
    ):
        if not farm_id:
            raise ValueError("farm_id is required")
        return self.repository.update_farm(
            farm_id=farm_id,
            farm_name=farm_name,
            address=address,
            status=status,
            owner_id=owner_id,
        )

    def delete_farm(self, farm_id: str) -> bool:
        if not farm_id:
            raise ValueError("farm_id is required")
        return self.repository.delete_farm(farm_id)

    def get_farm_recipients(self, farm_id: str) -> dict | None:
        if not farm_id:
            raise ValueError("farm_id is required")
        return self.repository.get_farm_recipients(farm_id)


farm_service = FarmService()
