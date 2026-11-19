"""Configuration and settings for Firebase Cloud Messaging (CP6.4)."""
from __future__ import annotations

import os
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

FCMProviderType = Literal["mock", "firebase", "disabled"]


class FCMSettings(BaseModel):
    """Runtime configuration for push notification dispatch."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    provider: FCMProviderType = Field(
        default="mock",
        description="FCM provider backend selection ('mock', 'firebase', 'disabled')",
    )
    enabled: bool = Field(
        default=True,
        description="Master switch for FCM push channel. If False, equivalent to 'disabled'.",
    )
    project_id: Optional[str] = Field(
        default=None,
        description="Google Cloud / Firebase Project ID",
    )
    credentials_path: Optional[str] = Field(
        default=None,
        description="Filesystem path to serviceAccountKey.json",
    )

    @classmethod
    def from_env(cls) -> "FCMSettings":
        """Load settings from environment variables."""
        provider_env = os.getenv("FCM_PROVIDER", "").strip().lower()
        enabled_env = os.getenv("FCM_ENABLED", "").strip().lower()

        # Resolve provider
        if provider_env in ("mock", "firebase", "disabled"):
            provider = provider_env  # type: ignore[assignment]
        elif enabled_env in ("false", "0", "no", "off"):
            provider = "disabled"
        elif enabled_env in ("true", "1", "yes", "on"):
            provider = "firebase"
        else:
            provider = "mock"

        enabled = provider != "disabled"

        return cls(
            provider=provider,
            enabled=enabled,
            project_id=os.getenv("FIREBASE_PROJECT_ID"),
            credentials_path=os.getenv("FIREBASE_CREDENTIALS_PATH"),
        )

    def validate_for_runtime(self) -> None:
        """Validate settings when running with real Firebase."""
        if self.provider == "firebase":
            if not self.credentials_path and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                raise ValueError(
                    "FCM_PROVIDER='firebase' requires 'FIREBASE_CREDENTIALS_PATH' or "
                    "'GOOGLE_APPLICATION_CREDENTIALS' to be set."
                )
            if self.credentials_path and not os.path.isfile(self.credentials_path):
                raise ValueError(
                    f"Firebase credentials file not found at: '{self.credentials_path}'"
                )


__all__ = [
    "FCMProviderType",
    "FCMSettings",
]
