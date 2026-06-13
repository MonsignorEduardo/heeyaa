from __future__ import annotations

import asyncio
import contextlib

import discord
from discord import app_commands
from loguru import logger

from audio_bot import AudioBotPy
from settings import settings
from utils import build_install_url
from utils.audio import (
    choose_audio_file,
    play_random_audio,
    should_play_random_sound,
)

intents = discord.Intents.default()
intents.voice_states = True

bot = AudioBotPy(intents=intents)
playback_tasks: dict[int, asyncio.Task[None]] = {}


def main() -> None:
    if not settings.discord_token:
        message = "Set DISCORD_TOKEN before starting the bot."
        raise RuntimeError(message)

    bot.run(settings.discord_token)


@bot.event
async def on_ready() -> None:
    logger.info("Logged in as {}", bot.user)

    if not bot.install_link_logged:
        install_url = build_install_url(bot)
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

    if _voice_channel_has_people(channel):
        return

    logger.info(
        "Voice channel {} in guild {} is empty; disconnecting bot",
        channel.name,
        member.guild.name,
    )
    await _cancel_playback_task(member.guild.id)

    try:
        await _disconnect_voice_client(
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
    await interaction.response.defer(ephemeral=True)

    voice_state = await _get_start_voice_state(interaction)
    if voice_state is None or interaction.guild is None:
        return

    audio_file = choose_audio_file()
    if audio_file is None:
        await interaction.followup.send(
            f"No audio files found in {settings.audio_dir}.",
            ephemeral=True,
        )
        return

    voice_client = interaction.guild.voice_client
    try:
        if isinstance(voice_client, discord.VoiceClient):
            if voice_client.channel != voice_state.channel:
                await voice_client.move_to(voice_state.channel)
        else:
            voice_client = await voice_state.channel.connect()
    except (discord.ClientException, RuntimeError) as error:
        await interaction.followup.send(
            f"Could not join voice: {error}",
            ephemeral=True,
        )
        return

    task = playback_tasks.get(interaction.guild.id)
    if task is not None and task.done():
        playback_tasks.pop(interaction.guild.id, None)
        task = None

    if task is not None:
        await interaction.followup.send(
            "Random audio is already running. I moved to your voice channel.",
            ephemeral=True,
        )
        return

    if not await _play_start_sound(interaction, voice_client):
        return

    playback_tasks[interaction.guild.id] = bot.loop.create_task(
        _random_sound_loop(interaction.guild.id),
    )
    await interaction.followup.send(
        "Started random audio. Every second there is a "
        f"{settings.random_sound_chance:.0%} chance I play a sound.",
        ephemeral=True,
    )


@bot.tree.command(
    name="stop",
    description="Stop random sounds and leave the voice channel.",
)
@app_commands.guild_only()
async def stop(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "Use this command inside a server.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    stopped_task = await _cancel_playback_task(interaction.guild.id)
    voice_client = interaction.guild.voice_client
    disconnected = False

    if isinstance(voice_client, discord.VoiceClient):
        try:
            await _disconnect_voice_client(
                interaction.guild,
                voice_client,
                reason="/stop command",
            )
        except discord.ClientException as error:
            await interaction.followup.send(
                f"Stopped random audio, but could not leave voice: {error}",
                ephemeral=True,
            )
            return
        disconnected = True

    if stopped_task or disconnected:
        await interaction.followup.send(
            "Stopped random audio and left the voice channel.",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        "Nothing was running, and I was not in a voice channel.",
        ephemeral=True,
    )


def _voice_channel_has_people(
    channel: discord.VoiceChannel | discord.StageChannel,
) -> bool:
    return any(not member.bot for member in channel.members)


async def _get_start_voice_state(
    interaction: discord.Interaction,
) -> discord.VoiceState | None:
    if interaction.guild is None:
        await interaction.followup.send(
            "Use this command inside a server.",
            ephemeral=True,
        )
        return None

    if not isinstance(interaction.user, discord.Member):
        await interaction.followup.send(
            "I could not find your voice channel.",
            ephemeral=True,
        )
        return None

    voice_state = interaction.user.voice
    if voice_state is None or voice_state.channel is None:
        await interaction.followup.send(
            "Join a voice channel first, then use /start.",
            ephemeral=True,
        )
        return None

    return voice_state


async def _play_start_sound(
    interaction: discord.Interaction,
    voice_client: discord.VoiceClient,
) -> bool:
    try:
        audio_file = play_random_audio(voice_client)
    except (
        discord.ClientException,
        discord.opus.OpusError,
        OSError,
    ) as error:
        await interaction.followup.send(
            f"Joined voice, but could not play audio: {error}",
            ephemeral=True,
        )
        return False

    if audio_file is None:
        await interaction.followup.send(
            f"No audio files found in {settings.audio_dir}.",
            ephemeral=True,
        )
        return False

    guild_name = interaction.guild.name if interaction.guild is not None else "unknown"
    logger.info("Playing {} in {}", audio_file.name, guild_name)
    return True


async def _random_sound_loop(guild_id: int) -> None:
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
                except (
                    discord.ClientException,
                    discord.opus.OpusError,
                    OSError,
                ) as error:
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


async def _cancel_playback_task(guild_id: int) -> bool:
    task = playback_tasks.pop(guild_id, None)
    if task is None or task.done():
        return False

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    return True


async def _disconnect_voice_client(
    guild: discord.Guild,
    voice_client: discord.VoiceClient,
    *,
    reason: str,
) -> None:
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    await voice_client.disconnect()
    logger.info("Disconnected from voice in guild {}: {}", guild.name, reason)


if __name__ == "__main__":
    main()
