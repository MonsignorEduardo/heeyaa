# AGENTS.md

## Project Shape
- This is a small Discord voice bot, not a packaged library; the runtime entrypoint is `src/main.py` and it imports `settings` as a top-level module from the same `src/` directory.
- `src/main.py` owns the `discord.py` client, slash commands, voice connection lifecycle, random playback loop, and `/start` and `/stop` commands.
- `src/settings.py` owns all environment loading via `pydantic-settings` with `env_file = ".env"` and `extra = "ignore"`.

## Commands
- Install/sync dependencies with `uv sync`; Python is pinned to `3.14` by `.python-version` and `requires-python = ">=3.14"`.
- Run the bot locally with `uv run python src/main.py`; this requires `DISCORD_TOKEN`, FFmpeg on the host, and playable audio files.
- Lint with `uv run ruff check .`; Ruff is strict (`select = ["ALL"]`) but ignores docstring rules (`D`) and `COM812`.
- Build the local container with `docker build -t heeyaa:local .`.
- Run the example compose deployment with `docker compose --env-file .env -f docs/docker-compose.example.yml up -d` and view logs with `docker compose -f docs/docker-compose.example.yml logs -f heeyaa`.

## Runtime Gotchas
- Do not read, print, or commit local `.env` files; they are gitignored and may contain the Discord token.
- `DISCORD_TOKEN` is the only required setting at startup; optional settings are `DISCORD_CLIENT_ID`, `DISCORD_GUILD_ID`, `AUDIO_DIR`, `CHECK_INTERVAL_SECONDS`, and `RANDOM_SOUND_CHANCE`.
- Audio discovery is non-recursive and only accepts `.flac`, `.m4a`, `.mp3`, `.ogg`, and `.wav` files in `AUDIO_DIR`.
- `DISCORD_GUILD_ID` switches slash command sync to guild-scoped sync for faster iteration; omitting it syncs global commands.
- Docker sets `PYTHONPATH=/app/src`, `AUDIO_DIR=/app/data`, installs `ffmpeg` and `libopus0`, and excludes local `data/`, `.env*`, and `docs/` from the build context.

## Verification Notes
- There is no test suite or test runner config yet; do not present `pytest` as an available required check unless tests are added.
- CI currently only builds the Docker image and pushes to GHCR on default-branch builds, `v*.*.*` tags, or manual workflow runs; there is no CI lint/typecheck/test job.
- When changing dependencies, update `uv.lock`; the Docker build uses `uv sync --frozen --no-dev --no-install-project`.
