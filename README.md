# Heeyaa

Heeyaa is a Discord voice bot that joins a voice channel and randomly plays audio files over time. It uses slash commands, `discord.py`, FFmpeg, and local audio files from the `data/` directory.

## Requirements

- Python 3.14
- `uv`
- FFmpeg, required for local audio playback
- A Discord bot token
- Audio files in `data/` or another directory configured with `AUDIO_DIR`

## Configuration

Create a local `.env` file for development and compose-based runs.

```env
DISCORD_TOKEN=your-bot-token
DISCORD_CLIENT_ID=123456789012345678
DISCORD_GUILD_ID=123456789012345678
AUDIO_DIR=data
CHECK_INTERVAL_SECONDS=1
RANDOM_SOUND_CHANCE=0.01
```

| Variable | Required | Description |
| --- | --- | --- |
| `DISCORD_TOKEN` | Yes | Discord bot token used to start the bot. |
| `DISCORD_CLIENT_ID` | No | Discord application client ID used to log an invite URL. |
| `DISCORD_GUILD_ID` | No | Guild ID for faster guild-scoped slash command syncing. If omitted, commands sync globally. |
| `AUDIO_DIR` | No | Directory containing `.flac`, `.m4a`, `.mp3`, `.ogg`, or `.wav` files. Defaults to `data/`. |
| `CHECK_INTERVAL_SECONDS` | No | Delay between random playback checks. Defaults to `1`. |
| `RANDOM_SOUND_CHANCE` | No | Chance of playing a sound on each check, between `0` and `1`. Defaults to `0.01`. |

## Local Development

Install dependencies:

```bash
uv sync
```

Run the bot:

```bash
uv run python src/main.py
```

Lint the project:

```bash
uv run ruff check .
```

## Discord Usage

Start the bot and invite it to a server with permissions to view channels, connect, speak, and use voice activity. The bot logs an install URL when `DISCORD_CLIENT_ID` is set or when Discord provides the application ID.

Use these slash commands in a server:

- `/start`: joins your current voice channel and starts random audio playback.
- `/stop`: stops playback and leaves the voice channel.

## Docker

Build the image locally:

```bash
docker build -t heeyaa:local .
```

Run the image with your local `.env` file and audio directory:

```bash
docker run --rm \
  --env-file .env \
  -e AUDIO_DIR=/app/data \
  -v "$(pwd)/data:/app/data:ro" \
  heeyaa:local
```

The image includes FFmpeg and Opus runtime packages and runs as a non-root user.

## Docker Compose

An example compose file is available at `docs/docker-compose.example.yml`.

Update the image name to match your GitHub repository, then run:

```bash
docker compose --env-file .env -f docs/docker-compose.example.yml up -d
```

View logs:

```bash
docker compose -f docs/docker-compose.example.yml logs -f heeyaa
```

## GitHub Container Registry

The workflow at `.github/workflows/docker-publish.yml` builds a multi-platform image for `linux/amd64` and `linux/arm64`.

It pushes to GitHub Container Registry as:

```text
ghcr.io/monsignoreduardo/heeyaa
```

Images are pushed for default-branch builds, `v*.*.*` tags, and manual workflow runs. Pull requests build the image without pushing it.

Tags include branch names, pull request refs, semantic versions, `sha-*`, and `latest` for the default branch.
