"""
TODO(MANAGEMENT-IDENTITY):
Legacy backend does not provide a unified User/Auth/RBAC persistence model.
The final Management Service identity model will be designed when Management
database ownership is introduced. Do not use frontend mock credentials as
backend persistence.
"""
from enum import Enum


class RoleEnum(str, Enum):
    ADMIN = "ADMIN"
    FARM_OWNER = "FARM_OWNER"
    TECHNICIAN = "TECHNICIAN"
