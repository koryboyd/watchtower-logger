# 📄 docs/points-bot.md

```markdown
# Points Bot Integration

The cog applies points via a **secure HTTP API** — this is the only ToS-compliant way to integrate with another bot.

### Required Endpoint
POST /api/warn
text### Request Headers
```headers
Authorization: Bearer <POINTS_API_TOKEN>
Content-Type: application/json
Request Body (JSON)
JSON{
  "steamid": "76561198000000000",
  "points": 3,
  "reason": "RDM",
  "notes": "Spawn camping | Ticket 1234",
  "issuer": "ModeratorName#1234"
}
Expected Responses

200 OK: Success. Optional JSON body for feedback:JSON{
  "total_points": 15,
  "action": "Temporary ban applied",
  "previous_points": 12
}These fields will be displayed in the Watchtower thread.
Non-200: Treated as failure. Error is logged in the Watchtower thread.

Implementation Tips for Your Points Bot

Validate the bearer token.
Accept both integer and string points.
Append ticket reference to notes if desired.
Return useful escalation info — moderators love seeing "New total: 15 → Ban threshold reached".
Rate-limit if exposed publicly.

Why HTTP API?
Discord explicitly disallows bots invoking other bots' slash commands.
This method is clean, reliable, auditable, and fully compliant.