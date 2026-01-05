# Watchtower Logger

Watchtower Logger is a Discord cog that logs resolved tickets from any ticketing workflow into a staff-only Watchtower channel. It preserves full evidence (transcripts and per-file media), uploads media to Catbox (catbox.moe) to avoid storing many files locally, integrates with a Points API for automated point application, and detects repeat offenses by rule.

This README gives a full setup guide, integration examples, operational considerations, and troubleshooting tips so you can plug this into an existing ticketing bot quickly and safely.

---

## Key features

- SteamID-first resolution: SteamID64 works even if Discord <-> Steam is not linked.
- Embed-first layout: ticket text (rule + public notes + recent context) appears in the embed so moderators can read everything without opening external links.
- Per-file Catbox uploads: each attachment and transcript are uploaded individually to catbox.moe (no batch uploads).
- Media ordering & context: media are listed under the embed in chronological order with author/timestamp/message-text so moderators can map media to the ticket conversation without opening links.
- Points API integration: optional, configurable, with retries and graceful failure handling.
- Per-rule repeat-offender detection: checks infractions for previous entries against the same rule/reason and flags embeds accordingly.
- Infraction recording: each processed line records an infraction row so repeat detection improves over time.
- Robust Discord compatibility: supports TextChannel and ForumChannel creation paths across discord.py versions, with defensive error handling.
- Testing: parsing & resolution logic is separated to allow unit tests (pytest + pytest-asyncio).

---

## Quick summary (if you want to try fast)

1. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
2. Set environment variables (see below).
3. Copy `cogs/watchtower_logger.py` into your bot's `cogs/` folder.
4. Load the cog from your bot:
   ```py
   await bot.load_extension("cogs.watchtower_logger")
   # or
   await bot.add_cog(WatchtowerLogger(bot))
   ```
5. From your ticket resolution flow call:
   ```py
   watchtower = bot.get_cog("WatchtowerLogger")
   await watchtower.log_from_resolve(interaction, ticket_channel, db_cursor, db_conn, ticket_id="1234")
   ```

---

## Requirements

- Python 3.10+
- discord.py v2.x (recommended) — compatibility with other forks may vary
- aiohttp
- beautifulsoup4 (only used in transcript generation if present; optional)
- pytest & pytest-asyncio (for running tests)
- A database accessible via a cursor (sqlite3 is the simplest)

Install:
```bash
python -m pip install -r requirements.txt
```

---

## Environment variables

All configuration can be provided via environment variables (recommended for production):

- `WATCHTOWER_CHANNEL_ID` (required) — numeric channel ID where Watchtower threads will be created (TextChannel or ForumChannel).
- `POINTS_API_URL` — Points API endpoint (default `http://127.0.0.1:5000/api/warn`).
- `POINTS_API_TOKEN` — Bearer token for the Points API (recommended). If missing or `CHANGE_ME`, points application is skipped.
- `CATBOX_USERHASH` — Optional Catbox userhash to attribute uploads to your Catbox account. If omitted uploads are anonymous.
- `ATTACHMENT_BATCH_SIZE` — How many fallback Discord files to send per message (default `10`).

Example (Linux/macOS):
```bash
export WATCHTOWER_CHANNEL_ID="123456789012345678"
export POINTS_API_URL="https://points.example/api/warn"
export POINTS_API_TOKEN="super-secret-token"
export CATBOX_USERHASH="optional_userhash_here"
export ATTACHMENT_BATCH_SIZE=8
```

Security note: store `POINTS_API_TOKEN` and `CATBOX_USERHASH` in a secure secrets manager when running in production.

---

## Database expectations & recommended schema

The cog uses your DB cursor to resolve users and track infractions. Minimal required tables/columns:

- `users` (recommended for linking):
  - `steamid` TEXT
  - `discordid` INTEGER
  - `ign` TEXT
  - (optional) `total_points` INTEGER

- `infractions` (recommended for per-rule repeat detection and history):
  ```sql
  CREATE TABLE IF NOT EXISTS infractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    steamid TEXT,
    discordid INTEGER,
    reason TEXT,
    timestamp INTEGER
  );
  ```

Behavior:
- When resolving an identifier the cog will attempt:
  - `SELECT steamid, ign FROM users WHERE discordid=?`
  - `SELECT discordid, ign FROM users WHERE steamid=?`
- Repeat-by-rule detection uses:
  - `SELECT COUNT(*) FROM infractions WHERE steamid=? AND reason=?`
  - or `SELECT COUNT(*) FROM infractions WHERE discordid=? AND reason=?`
- When logging an infraction the cog inserts:
  - `INSERT INTO infractions (steamid, discordid, reason, timestamp) VALUES (?, ?, ?, ?)`

If your schema differs, either adapt the queries in the cog or provide a small adapter that exposes the same cursor API.

---

## How the workflow maps to the embed & media

- Moderator triggers the ticket resolution flow and the cog prompts (ephemeral) for a bulk paste (one offender per line).
- Line format:
  - `@DiscordUser [points] [rule] | [mod_notes] | [notes]`
  - `SteamID64     [points] [rule] | [mod_notes] | [notes]`
  - Examples:
    ```
    <@123456789012345678> 2 Griefing | Internal: repeat offender | Broke rule #3
    76561198000000000 1 Chat spam | | Public warning text here
    ```
- For each offender the cog:
  1. Resolves offender info (steamid, discord name, ign) and checks repeat-by-rule.
  2. Creates or finds a Watchtower thread (name: "Discord Name | SteamID" or "SteamID" if unknown).
  3. Posts an embed containing:
     - Rule (if provided)
     - Ticket Text (public notes)
     - Recent context (last ~20 messages for context)
     - Discord display name, SteamID, IGN, Points applied
     - Repeat-offender flag if detected
  4. Posts staff-only notes as plaintext messages if present.
  5. Uploads transcript (HTML) to Catbox and uploads each attachment in chronological order—one-by-one—and then posts the media list right below the embed:
     - Media entries include author, timestamp, optional message text, and `filename: catbox-url`.
     - If an attachment upload fails but the file is small (<25MB), the cog will attach it directly to the thread as a fallback Discord file.
     - This layout allows mods to read the ticket text inside the embed and then glance the media URLs below to view media as needed.

---

## Points API contract

The cog sends a POST JSON payload to `POINTS_API_URL`:

Payload:
```json
{
  "steamid": "7656119....",
  "points": 2,
  "reason": "Griefing",
  "notes": "Public notes | Ticket 123",
  "issuer": "Moderator#1234"
}
```

Expectations:
- If the API returns HTTP 200 and JSON, the cog will show returned fields (e.g., `total_points`, `action`) in the thread.
- The cog retries transient errors (HTTP 429/502/503/504) with exponential backoff.
- If `POINTS_API_TOKEN` is not configured, the cog skips points application and logs a warning.

Design tip: have the Points API return structured JSON like:
```json
{"total_points": 4, "action": "none"}
```
so the cog can post helpful summary lines.

---

## Catbox specifics and media limits

- Catbox file limits/behavior are external: extremely large files (e.g., >200–250MB) may fail on upload. The cog skips >250MB files and logs a warning.
- The cog uploads each attachment separately (one HTTP request per file) to preserve ordering and to provide individual links.
- If Catbox upload fails for a small file (<25MB), we attempt to attach it directly to Discord as a fallback. Larger failed uploads are skipped.
- Set `CATBOX_USERHASH` to attribute uploads to your account (optional).
- Keep an eye on network reliability: many uploads in high-volume environments will stress bandwidth and increase latency. Consider rate-limiting or queuing in front of the cog if needed.

---

## Discord permissions required

Bot must have (at minimum):
- Read Messages / Read Message History (ticket channel)
- Send Messages
- Embed Links
- Attach Files (for fallback)
- Create Public/Private Threads and/or Create Forum Posts (on watchtower channel)
- Manage Messages (optional) — for deleting moderator paste message

If your Watchtower channel is a ForumChannel, verify the bot has "Create Posts" permission.

---

## Installation & integration (detailed)

1. Place file(s):
   - Copy `cogs/watchtower_logger.py` (and `cogs/parser.py` if using the split layout) into your bot's `cogs/` directory.

2. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```

3. Configure environment variables.

4. Load the cog at bot startup:
   ```py
   # async context
   await bot.load_extension("cogs.watchtower_logger")
   # or
   await bot.add_cog(WatchtowerLogger(bot))
   ```

5. Call `log_from_resolve(...)` from your ticket resolution handler:
   ```py
   # interaction: discord.Interaction that initiated the resolve
   # ticket_channel: TextChannel or Thread where the ticket conversation occurred
   # db_cursor/db_conn: a DB cursor and connection for queries and recording infractions
   watchtower = bot.get_cog("WatchtowerLogger")
   if watchtower:
       await watchtower.log_from_resolve(interaction, ticket_channel, db_cursor, db_conn, ticket_id="123")
   else:
       await interaction.response.send_message("Watchtower Logger not loaded.", ephemeral=True)
   ```

Notes:
- The cog expects a DB cursor that supports `.execute()` and `.fetchone()`.
- You may adapt by wrapping your DB access in a small adapter object exposing those methods.

---

## Unit tests

Parsing & resolution are designed to be testable. Example test files (in repository) use `pytest` and `pytest-asyncio`.

Run tests:
```bash
python -m pip install -r requirements.txt
pytest -q
```

If your test environment needs to simulate `fetch_user` or DB responses, the tests include simple fakes/mocks.

---

## Troubleshooting & potential issues

- "Watchtower channel invalid" — check `WATCHTOWER_CHANNEL_ID`, bot permissions, and that the channel is visible to the bot.
- Thread creation fails in Forum channels — discord.py versions vary. If `create_post` or `create_thread` isn't available, the cog falls back to sending a starter message then creating a thread from it. If your bot still can't create threads, ensure it has the right permissions and confirm the discord.py version for more specialized compatibility changes.
- Catbox upload failures — check network connectivity, file sizes, and that catbox.moe isn't rate-limiting your IP. Consider using an S3-like object store if Catbox isn't suitable for your scale.
- Points API errors — ensure `POINTS_API_TOKEN` and `POINTS_API_URL` are correct and that the Points API accepts the expected JSON schema. Inspect cog logs for HTTP status and API response text.
- DB errors inserting `infractions` — if your DB has a different schema, adapt the insert or add an `infractions` table as recommended.
- Large ticket channels (very long history) — transcript generation and attachment collection traverse entire history by default. For extremely long channels you may want to limit history size (e.g., last N messages) to reduce runtime and upload volume. This is safe to adjust based on your moderation policy.

---

## Operational tips

- Rotate `POINTS_API_TOKEN` regularly and keep it in a secure store.
- Add a periodic cleanup job if you keep local artifacts (current default design uploads to Catbox so no disk bloat).
- If your environment is high-volume, add rate limiting on Catbox uploads or process evidence uploads asynchronously in a worker queue to avoid blocking the moderation flow.
- Consider providing an admin command to update `WATCHTOWER_CHANNEL_ID` at runtime (persisted to DB) to avoid editing environment variables and redeploys.
- If you require auditability, keep transcripts and a copy of the evidence links in a secure storage (S3/DB) instead of or in addition to Catbox.

---

## Contributing & extending

- If you want S3 support instead of Catbox, add a storage adapter implementing `upload_bytes(filename, data, content_type)` and wire it into the cog.
- For custom DB schemas, extract the DB queries into a small adapter module and pass it to the cog.
- Open PRs for bug fixes, tests, or enhancements. If you'd like, I can prepare a patch/PR that adds:
  - Admin commands for runtime configuration
  - DB migration script to create `infractions` table and index it
  - Option to limit history depth for transcripts

---

## License

This project is licensed under the repository LICENSE file — check it for details.
