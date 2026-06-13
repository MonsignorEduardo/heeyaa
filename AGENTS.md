# AGENTS.md

## Project Shape
- This is a small Discord voice bot, not a packaged library; run the app from `src/main.py`.
- Source files under `src/` are top-level modules, not a package; imports use forms like `from settings import settings`, not package-relative imports.
- `src/main.py` wires events and slash commands; `src/bot.py` creates the `discord.Client` and syncs `app_commands`; `src/playback.py` owns per-guild random playback tasks.
- `src/audio.py` owns non-recursive audio discovery/playback for `.flac`, `.m4a`, `.mp3`, `.ogg`, and `.wav`; `src/voice.py` owns voice disconnect helpers; `src/interactions.py` logs slash-command responses/followups.
- `src/settings.py` owns all env loading via `pydantic-settings`.

## Commands
- Install/sync dependencies with `uv sync`; Python is pinned to `3.14` by `.python-version` and `requires-python = ">=3.14"`.
- Run the bot locally with `uv run python src/main.py`; this requires `DISCORD_TOKEN`, FFmpeg on the host, and playable audio files in `data/` unless `AUDIO_DIR` is set.
- Verify Python changes with `uv run ruff check .`, `uv run ruff format --check .`, and `uv run python -m py_compile src/*.py`.
- Format with `uv run ruff format .` when needed; Ruff is strict (`select = ["ALL"]`) but ignores docstrings (`D`) and formatter-conflicting `COM812`.
- Build the local container with `docker build -t heeyaa:local .`.
- Run the example compose deployment with `docker compose --env-file .env -f docs/docker-compose.example.yml up -d` and view logs with `docker compose -f docs/docker-compose.example.yml logs -f heeyaa`.

## Runtime Gotchas
- Do not read, print, or commit local `.env` files; they are gitignored and may contain the Discord token.
- `DISCORD_TOKEN` is the only required setting; optional settings are `DISCORD_CLIENT_ID`, `DISCORD_GUILD_ID`, `AUDIO_DIR`, `CHECK_INTERVAL_SECONDS`, and `RANDOM_SOUND_CHANCE`.
- `AUDIO_DIR` defaults to repo-local `data/`; `data/` is gitignored and dockerignored, so Docker/Compose runs need a volume mounted at `/app/data`.
- `DISCORD_GUILD_ID` switches slash command sync to guild-scoped sync for faster iteration; omitting it syncs global commands.
- `DISCORD_CLIENT_ID` is optional and only helps log an install URL; the bot can fall back to Discord-provided IDs after login.
- Voice currently needs both `pynacl` and `davey`; do not replace this with `discord.py[voice]` without checking `uv` resolution, because it conflicted with the current `pynacl>=1.6.2` constraint.
- Docker sets `PYTHONPATH=/app/src`, `AUDIO_DIR=/app/data`, installs `ffmpeg` and `libopus0`, and excludes local `data/`, `.env*`, and `docs/` from the build context.

## Verification Notes
- There is no test suite or test runner config yet; do not present `pytest` as an available required check unless tests are added.
- No `.github/workflows` are present in the current repo; do not assume CI exists even though README mentions a GHCR workflow.
- When changing dependencies, update `uv.lock`; the Docker build uses `uv sync --frozen --no-dev --no-install-project`.
