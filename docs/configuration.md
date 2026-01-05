# Configuration

All runtime configuration is driven via environment variables. This keeps secrets out of source control and simplifies deployment.

Required variables
- WATCHTOWER_CHANNEL_ID — numeric channel ID for your Watchtower channel (text channel or forum). Example: `123456789012345678`

Recommended variables
- POINTS_API_URL — URL of your Points API endpoint (default: `http://127.0.0.1:5000/api/warn`)
- POINTS_API_TOKEN — Bearer token used to authenticate to the Points API. If missing or set to `CHANGE_ME` the cog will skip calls to the Points API.
- CATBOX_USERHASH — Optional userhash for catbox.moe uploads. If set, Catbox uploads are associated with your Catbox account. If not, anonymous uploads are used.
- ATTACHMENT_BATCH_SIZE — Number of files to attach to a Discord message when sending fallback attachments (default: `10`)

Example `.env` file
```env
WATCHTOWER_CHANNEL_ID=123456789012345678
POINTS_API_URL=https://points.example.com/api/warn
POINTS_API_TOKEN=super-secret-token
CATBOX_USERHASH=yourcatboxuserhash_optional
ATTACHMENT_BATCH_SIZE=10
```

Database schema & migration
- The cog expects a `users` table for SteamID ↔ Discord mapping. Minimum columns used:
  - `users(steamid TEXT, discordid INTEGER, ign TEXT, total_points INTEGER optional)`

- Recommended infractions table schema (used for per-rule repeat detection and history):
```sql
CREATE TABLE IF NOT EXISTS infractions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  steamid TEXT,
  discordid INTEGER,
  reason TEXT,
  timestamp INTEGER
);

-- index for faster lookups per steamid+reason
CREATE INDEX IF NOT EXISTS infractions_steamid_reason_idx ON infractions(steamid, reason);
CREATE INDEX IF NOT EXISTS infractions_discordid_reason_idx ON infractions(discordid, reason);
```

Notes
- If you cannot add an `infractions` table, the cog will fall back to checking `users.total_points` for a simple repeat signal where available.
- Use migrations appropriate to your DB layer (e.g., Alembic for SQLAlchemy, Django migrations, or raw SQL scripts for SQLite).

Security recommendations
- Never store `POINTS_API_TOKEN` in source control. Use environment variables or a secrets manager.
- Lock down your bot token and restrict the watchtower channel permissions to staff only.
- If running in a container/platform, provide environment variables via the platform's secrets facility (e.g., Docker secrets, Kubernetes secrets).

Catbox limits & behavior
- Catbox typically restricts file size (historically ~200MB); uploads above that can fail. The cog will skip extremely large files (e.g., >250MB) and fallback-only sends smaller files to Discord if catbox upload fails.
- Catbox is a public host — links are accessible by anyone who has them. Do NOT upload private data you do not want to be publicly available.

Discord API notes
- The cog tries multiple methods of creating threads and forum posts to maintain compatibility across discord.py versions, but edge cases exist:
  - Forum channels have multiple API shapes across versions. If thread creation fails, provide your discord.py version and logs so the code can be tuned.

Logging & monitoring
- The cog uses the standard `logging` module. Integrate with your existing logging aggregation and alerting for production visibility.
- Consider running a periodic job to purge or audit old infractions if privacy/regulatory concerns exist.

Advanced
- To use your own storage instead of Catbox (S3, GCS), replace `CatboxUploader.upload_bytes` with your storage code and return a public or signed URL.