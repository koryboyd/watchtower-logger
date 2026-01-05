# Usage Guide

This guide explains exactly how moderators use **Watchtower Logger** during ticket resolution.

The process is simple, bulk-friendly, and flexible — designed for speed in high-volume moderation.

### Moderator Workflow

1. **Resolve the Ticket**  
   Your ticket bot calls `log_from_resolve` (as shown in Integration Guide).

2. **Bot Prompts You** (ephemeral message, only you see it):
Bulk paste offenders (one per line):
@DiscordUser [points] [rule] | [mod_notes] | [notes]
SteamID64     [points] [rule] | [mod_notes] | [notes]

Points optional (default 0)
Rule optional
Mod notes = internal staff only
Notes = public in embed
SteamID64 works even if not linked to Discord

text3. **Paste Your Offenders** (one line per offender)  
Send a message with the list. The bot deletes it immediately for privacy.

4. **Bot Confirms** (ephemeral):
Logged X offender(s) to Watchtower with full evidence.
SteamID-only entries are fully supported.
text5. **Done** — Watchtower receives:
- Per-offender thread (or appends to existing)
- Clean embed with all details
- Staff-only moderator notes
- Points API feedback (totals, escalations)
- Full HTML transcript + **all** attachments (batched if many)

### Input Format (Flexible)
identifier [points] [rule] | [mod_notes] | [public_notes]
text- **`identifier`**: Either `@DiscordMention` or raw `SteamID64` (17-19 digits)
- **`[points]`**: Integer (optional, default 0)
- **`[rule]`**: Short rule name (e.g., RDM, Toxicity) — optional
- **`|` separates sections**
- **`[mod_notes]`**: Staff-only internal notes (never shown in main embed)
- **`[public_notes]`**: Visible in embed "Public Notes" field

#### Examples

**Standard linked player:**
@PlayerOne 3 RDM | Repeat offender, watch closely | Spawn camping near main base
text**SteamID-only (unlinked player):**
76561198000000000 1 Chat Abuse | First offense, verbal warning given | Excessive swearing
text**No points (info/warning only):**
@PlayerTwo 0 | Discussed rules in voice | Verbal reminder about mic spam
text**Minimal entry:**
76561198123456789
text→ Logs with 0 points, all other fields "—"

**Multiple offenders (bulk):**
@JohnDoe 5 Griefing | Known griefer, consider ban | Destroyed team base
76561198234567890 2 RDM | New player, lenient | Killed teammate at spawn
@JaneSmith 0 | No violation found | False report, explained rules
text### What Happens in Watchtower

For each offender:
- Thread named: `DiscordName | SteamID` or just `SteamID` if unlinked
- Main embed (public to staff):
  - Discord / SteamID / IGN
  - Points Applied / Rule Broken / Public Notes
  - Recent ticket context (last 20 messages)
- Separate message: `**Staff Notes:**` (if provided)
- Points feedback (e.g., "New total: 15 points", "Escalation: Temp ban applied")
- **First offender only**: Full evidence package
  - HTML transcript (downloadable)
  - All ticket attachments (batched messages if >10)

### Tips for Moderators

- Use SteamID64 for players without Discord link — works perfectly.
- Keep mod_notes for internal discussion (e.g., "Escalate if repeats").
- Public notes for factual summary visible in embed.
- No need to worry about file limits — everything uploads automatically.
- If something fails (rare), it's noted in the thread (e.g., API down).

This system ensures complete audit trails with zero manual effort beyond the paste.