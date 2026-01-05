📄 README.md 
Watchtower Logger
Python
discord.py
License: MIT
GitHub Stars 
A professional, production-grade moderation logging cog for Discord ticket systems.
Designed for seamless integration into any ticketing bot (e.g., Ticket Tool, Tickets Bot, or custom). Logs resolved tickets to a staff-only Watchtower channel with full evidence preservation, including transcripts, attachments, and points application via API.
Key Features

Bulk Offender Logging: Handle multiple offenders per ticket with flexible input.
Offender Resolution: Auto-resolve SteamID ↔ Discord via your database.
Full Transcripts: HTML transcripts of the entire ticket for auditing.
Unlimited Attachments: Batch-sends all ticket attachments (no limits).
Staff Notes: Private moderator notes separate from public logs.
Ticket ID Referencing: Embed ticket numbers for easy tracking.
Points API Integration: Apply points securely; display feedback like totals/escalations.
Forum/Text Channel Support: Duplicate-safe threads; no auto-archiving.
Fail-Safe Design: Errors logged, never blocks ticket closure.
No Anonymity: Direct offender details (since offenders can't access Watchtower).

This cog focuses on logging and evidence – it does not manage tickets or points tracking (delegate to your points bot).

Why Use Watchtower Logger?

Compliance & Safety: ToS-safe API for points (no bot-on-bot commands).
Evidence Preservation: Complete transcripts + attachments for disputes/reviews.
Efficiency: Bulk input, auto-threading, batched uploads.
Customizable: Easy config; integrates with any ticket resolve hook.
Production Ready: Typed code, robust error handling, logging.


Prerequisites

Python 3.10+
discord.py 2.4+
aiohttp & beautifulsoup4 (for transcripts)
A Discord bot with ticket system (must provide DB cursor/conn for offender resolution).
SQLite (or similar) DB with users table (see Database Schema below).
Points Bot with HTTP /api/warn endpoint (see Points API Spec).


Installation & Setup
Follow these steps exactly to add this cog to your existing ticketing bot. Assumes you have a bot project with cogs support.
Step 1: Clone or Download the Repository
Bashgit clone https://github.com/yourusername/watchtower-logger.git
cd watchtower-logger
(Replace with your repo URL.)
Step 2: Install Dependencies
Run in your bot's root directory:
Bashpip install -r requirements.txt
Step 3: Copy the Cog File

Move cogs/watchtower_logger.py into your bot's cogs/ folder.
If no cogs/ folder, create one.

Step 4: Configure the Cog
Open cogs/watchtower_logger.py and edit the config section:
PythonWATCHTOWER_CHANNEL_ID = 123456789012345678  # Your Watchtower channel ID (staff-only permissions)
POINTS_API_URL = "http://127.0.0.1:5000/api/warn"  # Your Points Bot API
POINTS_API_TOKEN = "CHANGE_ME"  # Auth token (use os.getenv('POINTS_API_TOKEN') for security)
TRANSCRIPT_DIRECTORY = "transcripts"  # Customize if needed
ATTACHMENT_BATCH_SIZE = 10  # Don't change unless Discord limits evolve

Set Watchtower permissions: Deny view/send to offenders/public roles.
For production: Load token from .env via dotenv.

Step 5: Database Schema
Ensure your bot's DB has this table (SQLite example):
SQLCREATE TABLE IF NOT EXISTS users (
    steamid TEXT PRIMARY KEY,
    discordid TEXT,
    ign TEXT
);

Populate with user data as needed.

Step 6: Load the Cog in Your Bot
In your bot's main file (e.g., bot.py):
Pythonimport discord
from discord.ext import commands

bot = commands.Bot(...)  # Your bot setup

async def main():
    async with bot:
        await bot.load_extension("cogs.watchtower_logger")  # Load here
        await bot.start("YOUR_BOT_TOKEN")

asyncio.run(main())
Step 7: Integrate with Ticket Resolution
Hook into your ticket bot's resolve logic. Example for a slash command resolver:
Python@commands.slash_command(name="resolve_ticket")
async def resolve_ticket(self, interaction: discord.Interaction):
    # Your existing resolve code...
    
    cog = self.bot.get_cog("WatchtowerLogger")
    if cog:
        await cog.log_from_resolve(
            interaction=interaction,
            ticket_channel=interaction.channel,  # The ticket channel/thread
            db_cursor=your_db_cursor,  # From your DB connection
            db_conn=your_db_conn,  # Full connection (for commits if needed)
            ticket_id="1234"  # Optional: Your ticket number
        )
    
    # Continue with channel delete/archival...
    await interaction.channel.delete()

Adapt to your ticket system (e.g., button handler or event).
Pass active DB cursor/conn – cog doesn't manage DB.

Step 8: Test the Integration

Create a test ticket.
Resolve it, paste offenders when prompted.
Verify: Watchtower thread created, log embedded, evidence attached (batched if many), points applied.

Step 9: Deploy & Monitor

Run your bot.
Check logs for errors (uses Python's logging).
For large attachments: Ensure bot has storage space.


Points API Spec
Your Points Bot must expose:
textPOST /api/warn
JSON Payload:
JSON{
  "steamid": "7656119...",
  "points": 5,
  "reason": "RDM",
  "notes": "Public notes | Ticket 1234",
  "issuer": "ModName"
}
Optional Response (for feedback):
JSON{
  "total_points": 12,
  "action": "Temp ban applied"
}

Usage
When resolving:

Bot prompts for bulk offenders.
Paste (one per line):text@Player 3 RDM | Internal: Watch closely | Spawn camping
7656119... 0 | Reviewed evidence | Verbal warning
Logs to Watchtower: Embed + staff notes + API feedback + evidence.


Troubleshooting

Thread Not Found: Ensure Watchtower is a text/forum channel.
DB Errors: Verify schema and cursor.
API Failures: Logged in thread; check points bot.
Large Files: Discord limits per file (25MB); cog skips oversized.
See docs/faq.md for more.


Contributing
Fork, PRs welcome! Follow MIT license.
License
MIT – see LICENSE file.
Built for reliability in 2026 moderation workflows.
Star on GitHub | Report Issue
