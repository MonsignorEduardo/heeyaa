from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

import discord
from loguru import logger

from settings import settings

if TYPE_CHECKING:
    from pathlib import Path

AUDIO_EXTENSIONS = {".flac", ".m4a", ".mp3", ".ogg", ".wav"}
CHANCE_SCALE = 1_000_000


def choose_audio_file() -> Path | None:
    if not settings.audio_dir.exists():
        return None

    audio_files = [
        path
        for path in settings.audio_dir.iterdir()
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    ]
    if not audio_files:
        return None

    return secrets.choice(audio_files)


def should_play_random_sound() -> bool:
    return secrets.randbelow(CHANCE_SCALE) < settings.random_sound_chance * CHANCE_SCALE


def play_random_audio(voice_client: discord.VoiceClient) -> Path | None:
    audio_file = choose_audio_file()
    if audio_file is None:
        return None

    source = discord.FFmpegPCMAudio(str(audio_file))
    voice_client.play(
        source,
        after=lambda error: (
            logger.error("Playback error: {}", error) if error else None
        ),
    )
    return audio_file
