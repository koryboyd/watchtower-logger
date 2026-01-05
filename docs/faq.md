# Frequently Asked Questions & Troubleshooting

Q: Can I use this without Catbox?
A: Yes. The cog will attempt Catbox upload first (if configured). If Catbox is not configured or upload fails, small attachments may be sent directly to Discord; transcripts will be attempted but may not be preserved if upload fails.

Q: Do I need to store transcripts on disk?
A: No. By default the cog uploads transcripts to Catbox in-memory and posts links to the Watchtower thread to avoid disk growth.

Q: What if my bot doesn't have permission to delete the moderator paste?
A: The cog will attempt deletion but the paste will remain if it lacks permission — harmless but noisy.

Q: How are repeat offenders detected?
A: The cog checks an `infractions` table (preferred) for prior records with the same SteamID. If that table doesn't exist, it tries to read `total_points` from the `users` table as a fallback.

Q: My environment uses a different DB schema. Can I adapt?
A: Yes — the resolution logic is in `cogs/parser.py`. You can either adapt queries there or provide a small adapter that exposes the expected query interface.

Q: How does SteamID-only support work?
A: The cog accepts SteamID64 values and uses them for thread naming and Points API calls. If a SteamID is not linked to a Discord ID in your DB, the cog will still create a Watchtower thread named with the SteamID and still call the Points API where configured.

Q: What permissions does the bot need?
A: Read message history, send messages, attach files, create threads or forum posts, and manage messages (optional).

Q: How do I change the Watchtower channel at runtime?
A: Not supported out-of-the-box. You can change the WATCHTOWER_CHANNEL_ID env var and restart, or extend the cog to include an admin command to set it.