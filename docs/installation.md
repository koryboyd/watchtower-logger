# Installation

This guide takes you from zero → running the Watchtower Logger cog inside an existing bot.

Requirements
- Python 3.10+ (3.11 recommended)
- discord.py v2.x (tested on 2.0+)
- Bot token with required intents and permissions (detailed below)
- Optional: a SQLite DB (or any DB with Python DB-API) for user/infractions lookups

Repository dependencies
- discord.py
- aiohttp
- beautifulsoup4 (used by earlier transcript variants; harmless if unused)
- pytest, pytest-asyncio (for running tests)

Install dependencies:
```bash
python -m pip install -r requirements.txt
```

Virtual environment (recommended)
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Bot intents and permissions
- Intents:
  - MESSAGE_CONTENT intent must be enabled in the Developer Portal and in your bot if you need to access raw message content. The cog reads `clean_content` which is subject to message content intent in many situations.
  - GUILD_MESSAGES, GUILD_MESSAGE_REACTIONS, GUILDS are also needed.
- Permissions:
  - Read Message History (to generate transcripts and collect attachments)
  - Send Messages (to watchtower thread/channel)
  - Create Threads / Create Forum Posts (to create watchtower threads or forum posts)
  - Manage Messages (optional; used to delete moderator paste)
  - Attach Files (fallback for small media)

File placement
- Copy `cogs/watchtower_logger.py` into your bot's `cogs/` directory.
- Optionally copy `cogs/parser.py` and `tests/` for unit testing.

Load cog (example)
```python
# using load_extension
await bot.load_extension("cogs.watchtower_logger")

# or directly
from cogs.watchtower_logger import WatchtowerLogger
await bot.add_cog(WatchtowerLogger(bot))
```

Run unit tests
```bash
pytest -q
```

CI suggestion (GitHub Actions)
- Basic workflow: run `python -m pip install -r requirements.txt`, run `pytest`.
- Optionally run a linting step (flake8/ruff) and type checking (mypy).

Notes
- If your production bot uses Docker, bind environment variables via Docker secrets.
- If you use a different DB than SQLite, ensure the `db_cursor` object passed to the cog supports `.execute()` and `.fetchone()` semantics used in the cog.