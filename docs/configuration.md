# 📄 docs/configuration.md

```markdown
# Configuration Guide

All configuration is at the top of `cogs/watchtower_logger.py`.

| Variable                  | Type   | Description                                                                 | Recommended Value / Notes                                      |
|---------------------------|--------|-----------------------------------------------------------------------------|----------------------------------------------------------------|
| `WATCHTOWER_CHANNEL_ID`   | int    | ID of the staff-only Watchtower channel (text or forum)                     | Right-click channel → Copy ID                                  |
| `POINTS_API_URL`          | str    | Full URL of your Points Bot warning endpoint                                | e.g., `"https://points.example.com/api/warn"` (use HTTPS in prod) |
| `POINTS_API_TOKEN`        | str    | Bearer token for authenticating with Points Bot                              | **Never hardcode in prod** — use `os.getenv("POINTS_TOKEN")`   |
| `TRANSCRIPT_DIRECTORY`    | str    | Folder where HTML transcripts are temporarily saved before upload           | Default `"transcripts"` — ensure bot has write permission      |
| `ATTACHMENT_BATCH_SIZE`   | int    | Number of files per message (Discord limit is 10)                           | Keep at 10 unless Discord changes limits                       |

### Production Security Recommendations
```python
import os

POINTS_API_TOKEN = os.getenv("POINTS_API_TOKEN")
if not POINTS_API_TOKEN:
    raise ValueError("POINTS_API_TOKEN environment variable required")
Add to .env:
textPOINTS_API_TOKEN=your_super_secret_token
Use a secrets manager (Docker secrets, Railway variables, etc.) in hosted environments.
Permissions

Watchtower channel: Staff-only (deny @everyone and member roles View Channel/Send Messages).
Bot needs: View Channel, Send Messages, Manage Threads, Attach Files, Embed Links, Read Message History in Watchtower and ticket channels.