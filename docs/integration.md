# Integration — Integrating Watchtower Logger into an existing ticketing bot

This document explains how to call the cog from an existing ticketing workflow (Ticket Tool, Tickets Bot, or custom).

Public API (what your ticketing bot needs to call)
- Method: `WatchtowerLogger.log_from_resolve(interaction, ticket_channel, db_cursor, db_conn, ticket_id="")`
  - `interaction` — a `discord.Interaction` representing the moderator action (used to prompt the moderator ephemeral)
  - `ticket_channel` — the ticket channel or thread (`discord.TextChannel` or `discord.Thread`)
  - `db_cursor` — DB cursor used to query `users` and `infractions` tables (must implement `execute()` and `fetchone()`)
  - `db_conn` — DB connection used for `commit()` after inserting infractions (optional, may be `None`)
  - `ticket_id` — optional ticket number/reference inserted into embed & points notes

Example integration snippet
```python
watchtower = bot.get_cog("WatchtowerLogger")
if not watchtower:
    await interaction.response.send_message("Watchtower not loaded.", ephemeral=True)
else:
    # db_cursor and db_conn are your application's database objects
    await watchtower.log_from_resolve(interaction, ticket_channel, db_cursor, db_conn, ticket_id="1234")
```

Moderator workflow (what `log_from_resolve` does)
1. Ephemeral prompt asks moderator for a bulk paste of offenders (one per line).
2. Moderator pastes lines of the format:
   - `@DiscordUser [points] [rule] | [mod_notes] | [notes]`
   - `SteamID64     [points] [rule] | [mod_notes] | [notes]`
3. Cog parses lines, resolves offender identity (SteamID/Discord/IGN), creates or finds a watchtower thread, posts an embed (includes rule & public ticket text), posts media links (uploaded individually to Catbox) below the embed, applies points via Points API, and records infractions into the `infractions` table.

Notes about integration
- `log_from_resolve` expects to run as part of an async context (your ticketing bot should await the call).
- The cog will prompt the moderator (via ephemeral followup) and wait for a message from the same moderator in the same channel — ensure your ticket flow allows that interaction.
- If your bot uses a different data layer (ORM or custom DB helper), pass a DB cursor compatible with `.execute()`/`.fetchone()` or write a small adapter wrapper.

Customizing behavior
- You can alter behavior by environment variables (see docs/configuration.md).
- If your ticket flow already prepares transcript and uploads, you may bypass the cog's evidence uploading and instead pass a transcript URL into the embed — modify the cog accordingly or open an issue asking for a hook.

Permissions checklist
- Ensure the bot has channel-level permission to create threads or forum posts and to send messages in the watchtower channel.
- Ensure bot has permission to read message history and view attachments in the ticket channel.

Troubleshooting integration
- If the ephemeral prompt doesn't appear: verify your `interaction` object is valid and that your command handler awaited `interaction.response.defer()` or otherwise didn't complete the interaction elsewhere.
- If the bot cannot fetch messages: check message history permissions and MESSAGE_CONTENT intent.
- If thread creation fails in a Forum channel: check discord.py version and forum API; the cog has fallbacks but some older/newer API combinations may require tiny adjustments.