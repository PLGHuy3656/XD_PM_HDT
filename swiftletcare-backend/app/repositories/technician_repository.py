class TechnicianRepository:
    """
    Data-access layer for Technician functions.

    SQL will be implemented after the current PostgreSQL
    Technician-Farm assignment schema is verified.
    """

    def get_profile(self, technician_id: str):
        raise NotImplementedError(
            "Technician repository is waiting for verified database schema"
        )

    def get_assigned_farms(self, technician_id: str):
        raise NotImplementedError(
            "Technician-Farm assignment schema has not been verified yet"
        )

    def get_assigned_farm_detail(
        self,
        technician_id: str,
        farm_id: str,
    ):
        raise NotImplementedError(
            "Technician-Farm assignment schema has not been verified yet"
        )