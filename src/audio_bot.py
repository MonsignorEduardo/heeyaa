from __future__ import annotations

import discord
from discord import app_commands
from loguru import logger

from settings import settings


class AudioBotPy(discord.Client):
    install_link_logged: bool = False

    def __init__(self, *, intents: discord.Intents) -> None:
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        if settings.discord_guild_id is not None:
            guild = discord.Object(id=settings.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(
                "Synced {} command(s) to guild {}",
                len(synced),
                settings.discord_guild_id,
            )
            return

        synced = await self.tree.sync()
        logger.info("Synced {} global command(s)", len(synced))
