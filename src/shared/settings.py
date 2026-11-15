"""Typed application settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(default="", validation_alias="BOT_TOKEN")
    admin_id: int | None = Field(default=None, validation_alias="ADMIN_ID")
    channel_id: str | None = Field(default=None, validation_alias="CHANNEL_ID")
    render_url: str = Field(
        default="https://smartoffice-moms.onrender.com",
        validation_alias="RENDER_URL",
    )
    webapp_init_data_max_age: int = Field(
        default=86_400,
        validation_alias="WEBAPP_INIT_DATA_MAX_AGE",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
