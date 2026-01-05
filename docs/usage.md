# Points API integration

Watchtower Logger optionally integrates with a Points API to apply point penalties automatically.

Request payload
- `POST` to `POINTS_API_URL` with header `Authorization: Bearer <POINTS_API_TOKEN>` and JSON body:
```json
{
  "steamid": "76561198000000000",
  "points": 2,
  "reason": "Over packing rexes",
  "notes": "Public notes | Ticket 123",
  "issuer": "Moderator#0000"
}
```

Expected responses
- 200 OK with JSON — the cog will parse JSON and display fields such as `total_points` and `action` (if present).
  Example:
  ```json
  {
    "total_points": 5,
    "action": "warning"
  }
  ```
- Non-200 — cog logs the response text and posts a "Points application failed" flag in the thread.

Retry & resilience
- The cog retries transient errors (HTTP 429 / 502 / 503 / 504) with exponential backoff (3 attempts).
- If `POINTS_API_TOKEN` is missing or equals `CHANGE_ME`, the cog skips Points API calls and logs a warning.

Security
- Use a strong secret for `POINTS_API_TOKEN`.
- Restrict the Points API endpoint to accept only connections from trusted IPs (or protect with other network controls) if possible.

Server-side considerations (Points API implementer)
- Return meaningful JSON for `total_points` and `action` when appropriate.
- Validate input and authenticate using bearer token.
- Rate-limit clients to avoid accidental spam from automated recon attempts.

Troubleshooting
- If points are not applied:
  - Confirm `POINTS_API_URL` and `POINTS_API_TOKEN`.
  - Test the API via curl:
    ```bash
    curl -X POST -H "Authorization: Bearer $POINTS_API_TOKEN" -H "Content-Type: application/json" \
         -d '{"steamid":"76561198000000000","points":1,"reason":"Test","notes":"test","issuer":"me"}' \
         https://points.example/api/warn
    ```
  - Inspect Watchtower bot logs for the raw response body when the response is non-200.