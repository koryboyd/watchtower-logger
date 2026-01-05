# Integration Guide

This cog is designed as a **drop-in logging module** — it does **not** create or manage tickets.  
You must call it from your existing ticket resolution logic (e.g., slash command, button, modal, or event handler).

### Core Integration Point

```python
cog = bot.get_cog("WatchtowerLogger")
if cog:
    await cog.log_from_resolve(
        interaction=interaction,                  # The original discord.Interaction
        ticket_channel=interaction.channel,       # The ticket channel or thread being resolved
        db_cursor=your_db_cursor,                 # Active SQLite cursor (or compatible)
        db_conn=your_db_connection,               # Full connection object (for potential commits)
        ticket_id="1234"                          # Optional: Your internal ticket ID/number
    )

    Common Integration Scenarios
    1. Slash Command Resolver
    @bot.slash_command(name="resolve")
async def resolve_ticket(interaction: discord.Interaction):
    # Your existing validation, cleanup, etc.
    
    cog = bot.get_cog("WatchtowerLogger")
    if cog:
        await cog.log_from_resolve(
            interaction=interaction,
            ticket_channel=interaction.channel,
            db_cursor=cursor,
            db_conn=conn,
            ticket_id=ticket_panel_id  # e.g., from DB or channel name
        )
    
    await interaction.channel.delete()  # or archive
    await interaction.response.send_message("Ticket resolved.", ephemeral=True)
    2. Button-Based Close
    class CloseButton(discord.ui.View):
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger)
    async def close(self, button: discord.ui.Button, interaction: discord.Interaction):
        cog = self.bot.get_cog("WatchtowerLogger")
        if cog:
            await cog.log_from_resolve(
                interaction=interaction,
                ticket_channel=interaction.channel,
                db_cursor=cursor,
                db_conn=conn,
                ticket_id=self.ticket_id
            )
        
        await interaction.channel.delete()
        await interaction.response.send_message("Ticket closed and logged.", ephemeral=True)
        
        3. Modal Submission
If you collect resolution details via modal, pass the same parameters after submission.
Important Notes

The function never raises — all errors are caught and logged.
It defers the interaction and uses followups (ephemeral).
Transcript/attachment upload happens only once (first offender) to avoid spam.
You can safely call it before or after deleting/archiving the ticket channel.

Database Access
The cog only reads from the users table. No writes are performed.
Provide an active cursor; the connection is passed for compatibility only.
text