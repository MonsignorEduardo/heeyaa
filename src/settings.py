from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_audio_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


class Settings(BaseSettings):
    discord_token: str | None = None
    discord_client_id: int | None = None
    discord_guild_id: int | None = None
    audio_dir: Path = Field(default_factory=default_audio_dir)
    check_interval_seconds: float = Field(default=1.0, gt=0)
    random_sound_chance: float = Field(default=0.01, ge=0, le=1)

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
