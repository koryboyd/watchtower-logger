# Points Bot Integration

The cog will call the configured `POINTS_API_URL` with a JSON payload:
```json
{
  "steamid": "7656119...",
  "points": 2,
  "reason": "Griefing",
  "notes": "Public notes | Ticket 123",
  "issuer": "Moderator#0000"
}
```

Expected behavior:
- If the API returns 200 and JSON, the cog will display any returned fields such as `total_points` and `action`.
- If the API is not configured, the cog will skip application and log a warning.

Tips:
- Make your Points API return `{"total_points": N, "action": "ban"}` etc. The cog will show these fields when present.
- Consider adding a webhook endpoint to notify the cog when points are changed outside the flow (optional).
```