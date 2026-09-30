"""Application settings, loaded from the environment."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    app_name: str = "rat-detection-robot-backend"
    log_level: str = "INFO"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "sqlite:///./rat_detection.db"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    device_offline_timeout_s: float = 15.0
    offline_scan_interval_s: float = 2.0

    telemetry_persist_interval_s: float = 5.0
    max_payload_bytes: int = 64 * 1024

    device_clock_skew_tolerance_s: int = 900
    event_retention_days: int = 0

    allowed_device_ids: str = ""
    api_keys: str = ""

    history_default_limit: int = 100
    history_max_limit: int = 1000

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        return value.upper()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_device_id_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_device_ids.split(",") if item.strip()]

    @property
    def api_key_list(self) -> list[str]:
        return [item.strip() for item in self.api_keys.split(",") if item.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
