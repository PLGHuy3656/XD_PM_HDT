
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ControlSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModeRequest(ControlSchema):
    mode: Literal["AUTO", "MANUAL"]


class RelayCommandRequest(ControlSchema):
    action: Literal["SET_RELAY"]
    target: Literal["misting", "fan", "heater", "alarm"]
    state: Literal[0, 1]



class ThresholdCommandRequest(ControlSchema):
    action: Literal["UPDATE_THRESHOLDS"]
    targetTemp: float | None = Field(
        default=None,
        ge=-20,
        le=80,
        allow_inf_nan=False,
    )
    targetHum: float | None = Field(
        default=None,
        ge=0,
        le=100,
        allow_inf_nan=False,
    )
    isAutoMode: bool | None = None

    @model_validator(mode="after")
    def require_at_least_one_setting(self):
        if (
            self.targetTemp is None
            and self.targetHum is None
            and self.isAutoMode is None
        ):
            raise ValueError(
                "At least one of targetTemp, targetHum, "
                "or isAutoMode must be provided"
            )
        return self
