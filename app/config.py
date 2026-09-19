from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Wedding RSVP API"
    environment: str = "development"
    cors_origins: list[str] = Field(default_factory=list)
    max_guest_count: int = Field(default=10, ge=1, le=100)
    rsvp_deadline: str | None = None
    spreadsheet_id: str | None = None
    worksheet_name: str = "RSVP"
    google_service_account_json: str | None = None
    google_service_account_file: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
