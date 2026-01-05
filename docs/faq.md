# 📄 docs/faq.md

```markdown
# Frequently Asked Questions & Troubleshooting

### Q: Nothing happens when I resolve a ticket
- Check bot logs for errors (e.g., missing permissions, invalid channel ID).
- Ensure the cog loaded successfully (`await bot.load_extension("cogs.watchtower_logger")`).
- Verify `WATCHTOWER_CHANNEL_ID` is correct and bot can see the channel.

### Q: "Watchtower channel invalid" message
- The channel ID is wrong or the bot lacks View Channel permission.
- The channel must be a Text Channel or Forum Channel.

### Q: No thread is created
- Bot needs **Manage Threads** permission in Watchtower.
- For forum channels: bot needs Create Public Threads.

### Q: Transcript/attachments not uploading
- Bot needs **Attach Files** permission.
- Check disk space/write permission for `transcripts/` folder.
- Very large tickets (>1000 messages) may take time — increase interaction timeout if needed.

### Q: Points not applying
- Check Points Bot logs for authentication or payload errors.
- Verify `POINTS_API_TOKEN` matches.
- Test endpoint with curl/Postman:
  ```bash
  curl -X POST https://your-api/api/warn \
    -H "Authorization: Bearer your_token" \
    -H "Content-Type: application/json" \
    -d '{"steamid":"76561198000000000","points":1,"reason":"Test","notes":"FAQ test","issuer":"Bot"}'
Q: Duplicate threads appearing

Thread search uses exact name match. Ensure offender resolution returns consistent Discord name/SteamID.

Q: Too many attachment messages

The cog batches automatically (10 per message). Large tickets naturally create multiple messages.

Q: HTML transcript looks broken

Basic styling only. Open in browser for best view.
Discord displays it as a downloadable file.

Q: How to clean up old transcripts
Add a cleanup task:
Python@tasks.loop(hours=24)
async def cleanup_transcripts():
    for file in os.listdir("transcripts"):
        if file.endswith(".html") and os.path.getctime(f"transcripts/{file}") < time.time() - 86400:
            os.remove(f"transcripts/{file}")
Q: Running in Docker/Replit

Ensure volume mount for transcripts/ if persistence needed.
Use environment variables for secrets.

Still stuck? Open an issue with bot logs and error messages.