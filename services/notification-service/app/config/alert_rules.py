"""Alert rule configuration provider interface and in-memory implementation (CP6.2)."""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class AlertRuleConfig(BaseModel):
    """Safety and operational alert threshold configuration for a farm.

    Note: Control thresholds used by ESP32 AUTO mode are for local hysteresis
    actuator switching and are NOT the same object as these alert thresholds.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        validate_assignment=True,
    )

    farm_id: Optional[str] = Field(default=None, description="Optional target farm identifier")

    high_temp_celsius: float = Field(default=31.0, description="Maximum safe temperature in °C before alert")
    high_temp_recovery_celsius: float = Field(default=30.5, description="Recovery threshold in °C for high temperature")

    low_temp_celsius: float = Field(default=27.0, description="Minimum safe temperature in °C before alert")
    low_temp_recovery_celsius: float = Field(default=27.5, description="Recovery threshold in °C for low temperature")

    high_humidity_pct: float = Field(default=90.0, description="Maximum safe relative humidity % before alert")
    high_humidity_recovery_pct: float = Field(default=88.0, description="Recovery threshold in % for high humidity")

    low_humidity_pct: float = Field(default=70.0, description="Minimum safe relative humidity % before alert")
    low_humidity_recovery_pct: float = Field(default=72.0, description="Recovery threshold in % for low humidity")

    temperature_critical_high: float = Field(default=33.0, description="Temperature triggering CRITICAL severity")
    temperature_critical_low: float = Field(default=25.0, description="Temperature triggering CRITICAL severity")

    environment_cooldown_seconds: float = Field(
        default=60.0,
        ge=0.0,
        description="Cooldown period in seconds before reopening an alert after resolution",
    )
    predator_cooldown_seconds: float = Field(
        default=30.0,
        ge=0.0,
        description="Cooldown period in seconds between predator alerts",
    )
    audio_fault_debounce_count: int = Field(
        default=1,
        ge=1,
        description="Consecutive unhealthy audio readings required before alerting",
    )

    # Legacy/convenience property aliases for camelCase compatibility
    @property
    def temperatureMax(self) -> float:
        return self.high_temp_celsius

    @property
    def temperatureMin(self) -> float:
        return self.low_temp_celsius

    @property
    def humidityMax(self) -> float:
        return self.high_humidity_pct

    @property
    def humidityMin(self) -> float:
        return self.low_humidity_pct


class AlertRuleConfigProvider(ABC):
    """Port for retrieving alert rule threshold configurations."""

    @abstractmethod
    def get_config(self, farm_id: Optional[str] = None) -> AlertRuleConfig:
        """Return the alert rule config for the specified farm, or the default config."""
        pass

    def get_rules_for_farm(self, farm_id: Optional[str] = None) -> AlertRuleConfig:
        return self.get_config(farm_id)


class InMemoryAlertRuleConfigProvider(AlertRuleConfigProvider):
    """Thread-safe in-memory alert rule configuration provider."""

    def __init__(self, default_config: Optional[AlertRuleConfig] = None) -> None:
        self._default = default_config or AlertRuleConfig()
        self._farm_configs: Dict[str, AlertRuleConfig] = {}
        self._lock = threading.RLock()

    def get_config(self, farm_id: Optional[str] = None) -> AlertRuleConfig:
        with self._lock:
            if farm_id and farm_id in self._farm_configs:
                return self._farm_configs[farm_id]
            return self._default

    def get_rules_for_farm(self, farm_id: Optional[str] = None) -> AlertRuleConfig:
        return self.get_config(farm_id)

    def set_default_config(self, config: AlertRuleConfig) -> None:
        with self._lock:
            self._default = config

    def set_farm_config(self, farm_id: str, config: AlertRuleConfig) -> None:
        with self._lock:
            self._farm_configs[farm_id] = config

    def set_rules_for_farm(self, farm_id: str, config: AlertRuleConfig) -> None:
        self.set_farm_config(farm_id, config)

    def remove_farm_config(self, farm_id: str) -> bool:
        with self._lock:
            return self._farm_configs.pop(farm_id, None) is not None


__all__ = [
    "AlertRuleConfig",
    "AlertRuleConfigProvider",
    "InMemoryAlertRuleConfigProvider",
]
