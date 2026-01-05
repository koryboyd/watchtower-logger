```markdown
# Configuration

All runtime configuration is sourced from environment variables (recommended) with sensible defaults:

- WATCHTOWER_CHANNEL_ID (required): ID of the Watchtower channel (text or forum).
- POINTS_API_URL: Points API endpoint (default: http://127.0.0.1:5000/api/warn).
- POINTS_API_TOKEN: Bearer token to authenticate to the Points API. If unset or set to CHANGE_ME, points application is skipped.
- CATBOX_USERHASH: Optional catbox.moe userhash to attribute uploads.
- ATTACHMENT_BATCH_SIZE: How many files to send per Discord message (default 10).

Database:
- The cog expects a DB cursor with the following queries available:
  - `SELECT steamid, ign FROM users WHERE discordid=?`
  - `SELECT discordid, ign FROM users WHERE steamid=?`
  - Optionally an `infractions` table is used to flag repeat offenders:
    - `SELECT COUNT(*) FROM infractions WHERE steamid=?`

If you cannot create an `infractions` table, the cog will attempt to check `users.total_points` (if present) as a fallback method to detect repeat offenders.

Migration example (SQLite):
```sql
CREATE TABLE IF NOT EXISTS infractions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  steamid TEXT NOT NULL,
  discordid INTEGER,
  reason TEXT,
  timestamp INTEGER DEFAULT (strftime('%s','now'))
);
```

Security
- Never hard-code POINTS_API_TOKEN in source.
- Use environment secrets (e.g., process env or Docker secrets).
```