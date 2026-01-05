# Integration — Installing Watchtower Logger into an existing ticketing bot

This guide explains how to add the Watchtower Logger cog into an existing ticketing bot and how to enable Catbox hosting for transcripts & attachments.

Prerequisites
- Python 3.10+
- discord.py v2.x
- Bot token with permissions:
  - Read Message History
  - Send Messages
  - Create Threads / Create Forum Posts
  - Manage Messages (optional)
  - Attach Files (fallback)

1) Install dependencies
```bash
python -m pip install -r requirements.txt
```

2) Environment variables (recommended)
- WATCHTOWER_CHANNEL_ID — (required) ID of the channel used as Watchtower (text or forum). Example: `123456789012345678`
- POINTS_API_URL — (optional) Points API endpoint (default: `http://127.0.0.1:5000/api/warn`)
- POINTS_API_TOKEN — (recommended) Bearer token for Points API; if missing, points application is skipped.
- CATBOX_USERHASH — (optional) Your catbox.moe userhash; if set, uploads are attributed to your account.
Set variables, e.g.:
```bash
export WATCHTOWER_CHANNEL_ID="123456789012345678"
export POINTS_API_TOKEN="supersecret"
export CATBOX_USERHASH="..."
```

3) Copy files
- cogs/watchtower_logger.py
- cogs/parser.py

Place under your bot's `cogs/` directory (or import path).

4) Load cog
If your bot uses `load_extension`:
```python
await bot.load_extension("cogs.watchtower_logger")
```
or:
```python
from cogs.watchtower_logger import WatchtowerLogger
await bot.add_cog(WatchtowerLogger(bot))
```

5) Calling from your ticket flow
From the code that marks tickets resolved, call:
```python
watchtower = bot.get_cog("WatchtowerLogger")
await watchtower.log_from_resolve(interaction, ticket_channel, db_cursor, db_conn, ticket_id="123")
```
- `interaction`: discord.Interaction (or an object with `.user`/`.channel` for prompting).
- `ticket_channel`: TextChannel or Thread containing the ticket.
- `db_cursor`: sqlite3.Cursor or equivalent DB cursor used to resolve steamid/discordid/ign.
- `db_conn`: optional DB connection.

6) DB expectations
The cog attempts a few strategies:
- Preferred: an `infractions` table with rows for previous infractions:
  `infractions( id INTEGER PRIMARY KEY, steamid TEXT, discordid INTEGER, reason TEXT, timestamp INTEGER )`
- Fallback: a `users` table with `steamid`, `discordid`, `ign`, and optionally `total_points`.
If your schema differs, adapt `cogs/parser.py` resolve logic or create the `infractions` table.

7) Catbox considerations
- Catbox limits vary; the cog will skip extremely large files.
- If uploads fail, the cog falls back to sending smaller files directly to Discord.

8) Testing
Run unit tests:
```bash
pytest -q
```

9) Next steps / Customization
- Adjust thresholds (repeat-offender detection) in cogs/parser.py
- Add DB migration to create `infractions` table and record infractions when applying points
- Add admin commands to configure watchtower channel at runtime
```