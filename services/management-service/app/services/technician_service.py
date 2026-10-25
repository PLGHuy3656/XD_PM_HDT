from app.repositories.technician_repository import TechnicianRepository


class TechnicianService:
    def __init__(
        self,
        repository: TechnicianRepository | None = None,
    ):
        self.repository = repository or TechnicianRepository()

    def get_profile(self, technician_id: str):
        if not technician_id:
            raise ValueError("technician_id is required")

        return self.repository.get_profile(technician_id)

    def get_assigned_farms(self, technician_id: str):
        if not technician_id:
            raise ValueError("technician_id is required")

        return self.repository.get_assigned_farms(
            technician_id,
        )

    def get_assigned_farm_detail(
        self,
        technician_id: str,
        farm_id: str,
    ):
        if not technician_id:
            raise ValueError("technician_id is required")

        if not farm_id:
            raise ValueError("farm_id is required")

        return self.repository.get_assigned_farm_detail(
            technician_id,
            farm_id,
        )

    def get_assigned_farm_devices(
        self,
        technician_id: str,
        farm_id: str,
    ):
        if not technician_id:
            raise ValueError("technician_id is required")

        if not farm_id:
            raise ValueError("farm_id is required")

        return self.repository.get_assigned_farm_devices(
            technician_id,
            farm_id,
        )

    def get_assigned_farm_device_detail(
        self,
        technician_id: str,
        farm_id: str,
        device_id: str,
    ):
        if not technician_id:
            raise ValueError("technician_id is required")

        if not farm_id:
            raise ValueError("farm_id is required")

        if not device_id:
            raise ValueError("device_id is required")

        return self.repository.get_assigned_farm_device_detail(
            technician_id,
            farm_id,
            device_id,
        )

    def get_dashboard_summary(
        self,
        technician_id: str,
    ):
        if not technician_id:
            raise ValueError("technician_id is required")

        return self.repository.get_dashboard_summary(
            technician_id,
        )
