from __future__ import annotations

import asyncio
import contextlib
import secrets
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from loguru import logger

from settings import settings

if TYPE_CHECKING:
    from pathlib import Path

AUDIO_EXTENSIONS = {".flac", ".m4a", ".mp3", ".ogg", ".wav"}
CHANCE_SCALE = 1_000_000


class AudioBot(discord.Client):
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


intents = discord.Intents.default()
intents.voice_states = True

bot = AudioBot(intents=intents)
playback_tasks: dict[int, asyncio.Task[None]] = {}


def log_sent_interaction_message(
    interaction: discord.Interaction,
    delivery: str,
    content: str,
    *,
    ephemeral: bool,
) -> None:
    logger.info(
        "Sent {} interaction message to user={} guild={} channel={} ephemeral={}: {}",
        delivery,
        interaction.user,
        interaction.guild_id,
        interaction.channel_id,
        ephemeral,
        content,
    )


async def send_response(
    interaction: discord.Interaction,
    content: str,
    *,
    ephemeral: bool = True,
) -> None:
    await interaction.response.send_message(content, ephemeral=ephemeral)
    log_sent_interaction_message(
        interaction,
        "response",
        content,
        ephemeral=ephemeral,
    )


async def send_followup(
    interaction: discord.Interaction,
    content: str,
    *,
    ephemeral: bool = True,
) -> None:
    await interaction.followup.send(content, ephemeral=ephemeral)
    log_sent_interaction_message(
        interaction,
        "followup",
        content,
        ephemeral=ephemeral,
    )


def build_install_url() -> str | None:
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


def voice_channel_has_people(
    channel: discord.VoiceChannel | discord.StageChannel,
) -> bool:
    return any(not member.bot for member in channel.members)


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


async def random_sound_loop(guild_id: int) -> None:
    try:
        while True:
            guild = bot.get_guild(guild_id)
            if guild is None:
                return

            voice_client = guild.voice_client
            if not isinstance(voice_client, discord.VoiceClient):
                return

            if not voice_client.is_connected():
                return

            if (
                not voice_client.is_playing()
                and not voice_client.is_paused()
                and should_play_random_sound()
            ):
                try:
                    audio_file = play_random_audio(voice_client)
                except (discord.ClientException, OSError) as error:
                    logger.error("Could not play audio: {}", error)
                else:
                    if audio_file is None:
                        logger.warning(
                            "No audio files found in {}.", settings.audio_dir
                        )
                    else:
                        logger.info("Playing {} in {}", audio_file.name, guild.name)

            await asyncio.sleep(settings.check_interval_seconds)

    finally:
        current_task = asyncio.current_task()
        if playback_tasks.get(guild_id) is current_task:
            playback_tasks.pop(guild_id, None)


async def cancel_playback_task(guild_id: int) -> bool:
    task = playback_tasks.pop(guild_id, None)
    if task is None or task.done():
        return False

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    return True


async def disconnect_voice_client(
    guild: discord.Guild,
    voice_client: discord.VoiceClient,
    *,
    reason: str,
) -> None:
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    await voice_client.disconnect()
    logger.info("Disconnected from voice in guild {}: {}", guild.name, reason)


@bot.event
async def on_ready() -> None:
    logger.info("Logged in as {}", bot.user)

    if not bot.install_link_logged:
        install_url = build_install_url()
        if install_url is None:
            logger.warning("Could not build install link: missing Discord client ID")
        else:
            logger.info("Install link: {}", install_url)
        bot.install_link_logged = True


@bot.event
async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
) -> None:
    if member.bot or member.guild is None:
        return

    voice_client = member.guild.voice_client
    if not isinstance(voice_client, discord.VoiceClient):
        return

    channel = voice_client.channel
    if not isinstance(channel, discord.VoiceChannel | discord.StageChannel):
        return

    if before.channel != channel or after.channel == channel:
        return

    if voice_channel_has_people(channel):
        return

    logger.info(
        "Voice channel {} in guild {} is empty; disconnecting bot",
        channel.name,
        member.guild.name,
    )
    await cancel_playback_task(member.guild.id)

    try:
        await disconnect_voice_client(
            member.guild,
            voice_client,
            reason="everyone left the voice channel",
        )
    except discord.ClientException as error:
        logger.error("Could not auto-disconnect from voice: {}", error)


@bot.tree.command(
    name="start",
    description="Join your voice channel and randomly play sounds over time.",
)
@app_commands.guild_only()
async def start(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await send_response(interaction, "Use this command inside a server.")
        return

    if not isinstance(interaction.user, discord.Member):
        await send_response(interaction, "I could not find your voice channel.")
        return

    voice_state = interaction.user.voice
    if voice_state is None or voice_state.channel is None:
        await send_response(
            interaction,
            "Join a voice channel first, then use /start.",
        )
        return

    audio_file = choose_audio_file()
    if audio_file is None:
        await send_response(
            interaction,
            f"No audio files found in {settings.audio_dir}.",
        )
        return

    await interaction.response.defer(ephemeral=True)

    voice_client = interaction.guild.voice_client
    try:
        if isinstance(voice_client, discord.VoiceClient):
            if voice_client.channel != voice_state.channel:
                await voice_client.move_to(voice_state.channel)
        else:
            voice_client = await voice_state.channel.connect()
    except (discord.ClientException, RuntimeError) as error:
        await send_followup(
            interaction,
            f"Could not join voice: {error}",
        )
        return

    task = playback_tasks.get(interaction.guild.id)
    if task is not None and task.done():
        playback_tasks.pop(interaction.guild.id, None)
        task = None

    if task is not None:
        await send_followup(
            interaction,
            "Random audio is already running. I moved to your voice channel.",
        )
        return

    playback_tasks[interaction.guild.id] = bot.loop.create_task(
        random_sound_loop(interaction.guild.id),
    )
    await send_followup(
        interaction,
        "Started random audio. Every second there is a 1% chance I play a sound.",
    )


@bot.tree.command(
    name="stop",
    description="Stop random sounds and leave the voice channel.",
)
@app_commands.guild_only()
async def stop(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await send_response(interaction, "Use this command inside a server.")
        return

    await interaction.response.defer(ephemeral=True)

    stopped_task = await cancel_playback_task(interaction.guild.id)
    voice_client = interaction.guild.voice_client
    disconnected = False

    if isinstance(voice_client, discord.VoiceClient):
        try:
            await disconnect_voice_client(
                interaction.guild,
                voice_client,
                reason="/stop command",
            )
        except discord.ClientException as error:
            await send_followup(
                interaction,
                f"Stopped random audio, but could not leave voice: {error}",
            )
            return
        disconnected = True

    if stopped_task or disconnected:
        await send_followup(
            interaction,
            "Stopped random audio and left the voice channel.",
        )
        return

    await send_followup(
        interaction,
        "Nothing was running, and I was not in a voice channel.",
    )


def main() -> None:
    if not settings.discord_token:
        message = "Set DISCORD_TOKEN before starting the bot."
        raise RuntimeError(message)

    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
