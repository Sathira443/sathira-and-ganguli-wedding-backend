from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Wedding RSVP API"
    environment: str = "development"
    cors_origins: list[str] = Field(default_factory=lambda: [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ])
    max_guest_count: int = Field(default=10, ge=1, le=100)
    rsvp_deadline: str | None = None
    invitation_cache_control: str = "no-store"
    spreadsheet_id: str | None = None
    worksheet_name: str = "RSVP"
    google_service_account_json: str | None = None
    google_service_account_file: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def normalize_cors_origins(cls, origins: list[str]) -> list[str]:
        return [origin.rstrip("/") for origin in origins]


@lru_cache
def get_settings() -> Settings:
    return Settings()
