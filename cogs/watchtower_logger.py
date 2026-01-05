from __future__ import annotations

import discord
from discord.ext import commands
import asyncio
import aiohttp
import logging
import re
import os
import time
from typing import Optional, List

from bs4 import BeautifulSoup

# ================= CONFIG =================

WATCHTOWER_CHANNEL_ID: int = 123456789012345678  # Replace with your Watchtower channel ID (text or forum)

POINTS_API_URL: str = "http://127.0.0.1:5000/api/warn"  # Points Bot API endpoint
POINTS_API_TOKEN: str = "CHANGE_ME"  # API auth token (use env vars in prod)

TRANSCRIPT_DIRECTORY: str = "transcripts"  # Directory for saving HTML transcripts (created automatically)
ATTACHMENT_BATCH_SIZE: int = 10  # Max files per message (Discord limit); batches for unlimited

# ==========================================

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class WatchtowerLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        os.makedirs(TRANSCRIPT_DIRECTORY, exist_ok=True)

    async def cog_unload(self) -> None:
        if not self.session.closed:
            await self.session.close()

    # ---------- helpers ----------

    async def find_existing_thread(self, channel: discord.TextChannel | discord.ForumChannel, offender: dict) -> Optional[discord.Thread]:
        if not channel:
            return None

        # Prioritise SteamID in thread name for reliability when Discord unlinked
        thread_name = f"{offender['discord_name']} | {offender['steamid']}" if offender['discord_name'] != "Unknown" else offender['steamid']

        for thread in channel.threads:
            if thread.name == thread_name:
                return thread

        try:
            async for thread in channel.archived_threads(limit=None):
                if thread.name == thread_name:
                    return thread
        except discord.HTTPException as e:
            logger.error(f"Error searching archived threads: {e}")

        return None

    async def resolve_offender(self, identifier: str, db_cursor) -> dict:
        steamid: Optional[str] = None
        discord_id: Optional[int] = None
        discord_name: str = "Unknown"
        ign: str = "Unknown"

        try:
            if identifier.startswith("<@"):
                # Discord mention provided
                discord_id = int(identifier.strip("<@!>"))
                db_cursor.execute("SELECT steamid, ign FROM users WHERE discordid=?", (discord_id,))
                row = db_cursor.fetchone()
                if row:
                    steamid, ign = row

                # Fetch Discord name regardless of link
                try:
                    user = await self.bot.fetch_user(discord_id)
                    discord_name = user.display_name or user.name
                except discord.HTTPException:
                    discord_name = "Unresolved User"
            else:
                # Direct SteamID64 provided
                steamid = identifier
                db_cursor.execute("SELECT discordid, ign FROM users WHERE steamid=?", (steamid,))
                row = db_cursor.fetchone()
                if row:
                    discord_id, ign = row
                    if discord_id:
                        try:
                            user = await self.bot.fetch_user(discord_id)
                            discord_name = user.display_name or user.name
                        except discord.HTTPException:
                            discord_name = "Unknown (Unlinked)"
                else:
                    # No DB entry at all — still usable via SteamID
                    ign = "Unknown"

        except Exception as e:
            logger.error(f"Error resolving offender {identifier}: {e}")

        # Ensure steamid is always set when provided directly
        if not steamid and identifier.isdigit() and len(identifier) >= 17:
            steamid = identifier

        return {
            "steamid": steamid or "Unknown",
            "discord_id": discord_id,
            "discord_name": discord_name,
            "ign": ign or "Unknown"
        }

    async def apply_points(self, offender: dict, points: int, rule: str, notes: str, issuer: str, ticket_id: str) -> dict:
        if points <= 0 or offender["steamid"] == "Unknown":
            return {"success": True, "response": None}

        payload = {
            "steamid": offender["steamid"],
            "points": points,
            "reason": rule,
            "notes": notes + (f" | Ticket {ticket_id}" if ticket_id else ""),
            "issuer": issuer
        }

        headers = {
            "Authorization": f"Bearer {POINTS_API_TOKEN}",
            "Content-Type": "application/json"
        }

        try:
            async with self.session.post(POINTS_API_URL, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        return {"success": True, "response": data}
                    except:
                        return {"success": True, "response": None}
                else:
                    text = await resp.text()
                    logger.error(f"Points API error {resp.status}: {text}")
                    return {"success": False, "response": None}
        except Exception as e:
            logger.error(f"Exception applying points: {e}")
            return {"success": False, "response": None}

    async def generate_transcript(self, channel: discord.TextChannel | discord.Thread) -> Optional[discord.File]:
        try:
            html = [
                "<html><head><meta charset='utf-8'><title>Transcript - {}</title>".format(channel.name),
                "<style>body {font-family: sans-serif; background:#36393f; color:#dcddde;} .message {margin:8px;} .author {font-weight:bold;} .timestamp {color:#72767d; font-size:0.8em;}</style></head><body>"
            ]

            async for message in channel.history(limit=None, oldest_first=True):
                timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                author = message.author.display_name
                content = discord.utils.escape_markdown(message.clean_content)
                content = content.replace("\n", "<br>")

                html.append(f"<div class='message'><span class='timestamp'>{timestamp}</span> <span class='author'>{author}:</span> {content}</div>")

            html.append("</body></html>")

            filename = f"{TRANSCRIPT_DIRECTORY}/transcript_{channel.id}_{int(time.time())}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("\n".join(html))

            return discord.File(filename, filename=f"transcript_{channel.id}.html")
        except Exception as e:
            logger.error(f"Failed to generate transcript: {e}")
            return None

    async def get_key_attachments(self, channel: discord.TextChannel | discord.Thread) -> List[discord.File]:
        files = []
        try:
            async for message in channel.history(limit=None, oldest_first=False):
                for att in message.attachments:
                    if att.size < 25 * 1024 * 1024:  # <25MB
                        try:
                            saved = await att.to_file()
                            files.append(saved)
                        except Exception as e:
                            logger.error(f"Error saving attachment {att.filename}: {e}")
        except Exception as e:
            logger.error(f"Error fetching attachments: {e}")
        return files

    async def send_batched_files(self, thread: discord.Thread, files: List[discord.File], content: str) -> None:
        for i in range(0, len(files), ATTACHMENT_BATCH_SIZE):
            batch = files[i:i + ATTACHMENT_BATCH_SIZE]
            try:
                await thread.send(content=content if i == 0 else "Continued evidence...", files=batch)
            except discord.HTTPException as e:
                logger.error(f"Error sending batch {i//ATTACHMENT_BATCH_SIZE + 1}: {e}")

    # ---------- main entry ----------

    async def log_from_resolve(
        self,
        interaction: discord.Interaction,
        ticket_channel: discord.TextChannel | discord.Thread,
        db_cursor,
        db_conn,
        ticket_id: str = ""  # Optional ticket number/reference
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        await interaction.followup.send(
            "Bulk paste offenders (one per line):\n"
            "`@DiscordUser [points] [rule] | [mod_notes] | [notes]`\n"
            "`SteamID64     [points] [rule] | [mod_notes] | [notes]`\n"
            "- Points optional (default 0)\n"
            "- Rule optional\n"
            "- Mod notes = internal staff only\n"
            "- Notes = public in embed\n"
            "- **SteamID64 works even if not linked to Discord**",
            ephemeral=True
        )

        def check(m: discord.Message) -> bool:
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", timeout=1200.0, check=check)
            lines = [line.strip() for line in msg.content.splitlines() if line.strip()]
            await msg.delete()
        except asyncio.TimeoutError:
            await interaction.followup.send("Timed out.", ephemeral=True)
            return

        # Recent context
        try:
            history = ticket_channel.history(limit=20, oldest_first=False)
            context_msgs = [m async for m in history]
            context = "\n".join(f"{m.author.display_name}: {m.clean_content[:200]}" for m in context_msgs)
        except:
            context = "Context unavailable."

        # Generate transcript & attachments
        transcript_file = await self.generate_transcript(ticket_channel)
        key_attachments = await self.get_key_attachments(ticket_channel)

        watchtower = self.bot.get_channel(WATCHTOWER_CHANNEL_ID)
        if not watchtower or not isinstance(watchtower, (discord.TextChannel, discord.ForumChannel)):
            await interaction.followup.send("Watchtower channel invalid.", ephemeral=True)
            return

        processed = 0
        for line in lines:
            try:
                match = re.match(r"(<@!?\d+>|\d{17,19})\s*(\d+)?\s*([^|]*?)(?:\s*\|\s*(.*?))?(?:\s*\|\s*(.*))?$", line)
                if not match:
                    continue

                identifier, points_str, rule, mod_notes, notes = match.groups()
                points = int(points_str) if points_str else 0
                rule = (rule or "").strip()
                mod_notes = (mod_notes or "").strip()
                notes = (notes or "").strip()

                offender = await self.resolve_offender(identifier, db_cursor)

                # Fallback thread name: SteamID only if no Discord name
                thread_name = f"{offender['discord_name']} | {offender['steamid']}" if offender['discord_name'] != "Unknown" else offender['steamid']

                embed = discord.Embed(
                    title=f"Ticket Resolution Log {f'#{ticket_id}' if ticket_id else ''}",
                    color=0xff0000 if points > 0 else 0xffa500,
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="Discord", value=offender["discord_name"], inline=True)
                embed.add_field(name="SteamID", value=offender["steamid"], inline=True)
                embed.add_field(name="IGN", value=offender["ign"], inline=True)
                embed.add_field(name="Points Applied", value=str(points), inline=True)
                embed.add_field(name="Rule Broken", value=rule or "—", inline=False)
                embed.add_field(name="Public Notes", value=notes or "—", inline=False)
                if context:
                    embed.add_field(name="Recent Context", value=context[:1024], inline=False)

                thread = await self.find_existing_thread(watchtower, offender)
                if not thread:
                    thread = await watchtower.create_thread(
                        name=thread_name,
                        content="Watchtower thread initialized."
                    )

                await thread.send(embed=embed)

                if mod_notes:
                    await thread.send(f"**Staff Notes:** {mod_notes}")

                api_result = await self.apply_points(offender, points, rule, notes, str(interaction.user), ticket_id)
                if not api_result["success"]:
                    await thread.send("⚠️ Points application failed.")
                elif api_result["response"]:
                    extra = api_result["response"]
                    info = []
                    if "total_points" in extra:
                        info.append(f"New total: **{extra['total_points']}** points")
                    if "action" in extra:
                        info.append(f"Escalation: {extra['action']}")
                    if info:
                        await thread.send("\n".join(info))

                if processed == 0:
                    files = []
                    if transcript_file:
                        files.append(transcript_file)
                    files.extend(key_attachments)
                    if files:
                        await self.send_batched_files(
                            thread,
                            files,
                            "**Ticket Evidence:** Full transcript + all attachments"
                        )

                processed += 1
            except Exception as e:
                logger.error(f"Error processing line '{line}': {e}")

        await interaction.followup.send(
            f"Logged {processed} offender(s) to Watchtower with full evidence.\nSteamID-only entries are fully supported.",
            ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WatchtowerLogger(bot))