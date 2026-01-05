# Frequently Asked Questions & Troubleshooting

Q: The cog can't see message content — Recent Context shows "Context unavailable."
A: Ensure your bot has MESSAGE_CONTENT intent enabled in the Developer Portal and you instantiate discord.py with `intents = discord.Intents.default(); intents.message_content = True` and pass it to `commands.Bot(intents=intents)`.

Q: Attachments are missing or not uploaded to Catbox
A: Catbox has file size limits and rate limits. The cog:
- Skips extremely large files (>250MB).
- Attempts to upload each file individually; if upload fails and the file is small (<25MB), the cog will attach it directly to the Watchtower thread as a fallback.
- If many uploads fail, check network connectivity and `CATBOX_USERHASH` validity.

Q: Thread creation fails in a Forum channel
A: Forum APIs changed across discord.py versions. The cog attempts multiple strategies:
- `forum.create_post()` / `forum.create_thread()`
- Sending a starter message and calling `.create_thread()` on the message
If failure persists, share your discord.py version and stack trace. We can tune for specific API variants.

Q: Repeat offender detection is inconsistent
A: Repeat detection matches the `reason` string exactly. To ensure consistent detection:
- Use standardized rule names (e.g., "Over packing rexes" consistently).
- The cog records a reason equal to `rule` if present, otherwise `notes` or `Points:<points>`.

Q: I don't want evidence hosted on Catbox (privacy)
A: Replace `CatboxUploader.upload_bytes` to point to your internal storage (S3, GCS). If you need help adding S3 support, open an issue or request a patch.

Q: Are catbox URLs public?
A: Yes. Anyone with the URL can access the uploaded file. Do not upload private or sensitive files to Catbox.

Q: Disk space still grows — why?
A: The cog writes no persistent transcripts by default. If you modified it to write transcripts locally, check `transcripts/` and the `.gitignore`. Remove or rotate files if needed.

Q: How do I standardize rules so repeat detection works well?
A: Consider a short code for each rule, e.g., `RP_PACKING`, `SPAM_CHAT`. Store a mapping in your moderation docs and display both code + human text in embeds.

Q: Logging & debugging
A: The cog uses Python's `logging`. Configure your bot's logging to capture INFO/DEBUG logs. Common troubleshooting steps:
- Enable DEBUG in development to capture stack traces (be careful in production).
- Inspect raw HTTP responses when Points API or Catbox uploads fail.

Q: I want the cog to auto-close tickets after inactivity
A: This cog focuses on logging. Implement ticket lifecycle actions in your ticketing bot and call `log_from_resolve(...)` when closing.