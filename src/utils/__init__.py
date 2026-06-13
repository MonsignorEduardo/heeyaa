from typing import TYPE_CHECKING

import discord

from settings import settings

if TYPE_CHECKING:
    from audio_bot import AudioBotPy


def build_install_url(bot: AudioBotPy) -> str | None:
    client_id = settings.discord_client_id or bot.application_id
    if client_id is None and bot.user is not None:
        client_id = bot.user.id

    if client_id is None:
        return None

    permissions = discord.Permissions(
        view_channel=True,
        connect=True,
        speak=True,
        use_voice_activation=True,
    )
    return discord.utils.oauth_url(client_id, permissions=permissions)
