"""
Watchtower Logger Cog (media-order + per-file Catbox uploads + embed-first layout)

This cog ensures:
- Ticket text (rule + public notes + recent context) is included in the main embed so mods can read everything
  without opening external links.
- All media (attachments + transcript) are uploaded individually to catbox.moe (one upload per file).
  No batch upload to catbox.
- Media links are posted directly under the embed in the same relative order and with author/timestamp
  context, so moderators can read the ticket text and see which media belongs to which message without
  opening the links.
- Small attachments that fail to upload are attached to the Watchtower thread as Discord files
  (fallback).
- Per-rule repeat-offender detection and infraction recording remains intact.

Environment variables:
- WATCHTOWER_CHANNEL_ID (required) — watchtower channel id
- POINTS_API_URL, POINTS_API_TOKEN — points API config
- CATBOX_USERHASH — optional catbox userhash to attribute uploads
- ATTACHMENT_BATCH_SIZE — how many files to attach to a single Discord message (fallback)

Database expectations:
- users(steamid TEXT, discordid INTEGER, ign TEXT, total_points INTEGER optional)
- infractions(id, steamid, discordid, reason, timestamp) — used to detect repeats by rule
"""

from __future__ import annotations

import os
import re
import time
import logging
import asyncio
from typing import Optional, List, Dict, Any

import aiohttp
import discord
from discord.ext import commands

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Config (env-overrides)
WATCHTOWER_CHANNEL_ID: int = int(os.getenv("WATCHTOWER_CHANNEL_ID", "0"))
POINTS_API_URL: str = os.getenv("POINTS_API_URL", "http://127.0.0.1:5000/api/warn")
POINTS_API_TOKEN: str = os.getenv("POINTS_API_TOKEN", "CHANGE_ME")
CATBOX_USERHASH: str = os.getenv("CATBOX_USERHASH", "")
ATTACHMENT_BATCH_SIZE: int = int(os.getenv("ATTACHMENT_BATCH_SIZE", "10"))


# ---- parsing + resolution helpers (unchanged semantics) ----


def parse_offender_line(line: str) -> Optional[Dict[str, str]]:
    if not line or not line.strip():
        return None
    parts = [p.strip() for p in line.split("|", 2)]
    left = parts[0]
    mod_notes = parts[1] if len(parts) > 1 else ""
    notes = parts[2] if len(parts) > 2 else ""
    m = re.match(r"^\s*(?P<identifier><@!?\d+>|\d{1,30})\s*(?P<points>\d+)?\s*(?P<rule>.*)?$", left)
    if not m:
        logger.debug("parse_offender_line: failed to parse: %s", line)
        return None
    identifier = m.group("identifier")
    points = m.group("points") or "0"
    rule = (m.group("rule") or "").strip()
    return {"identifier": identifier, "points": points, "rule": rule, "mod_notes": mod_notes, "notes": notes}


async def _safe_fetch_user_name(bot: commands.Bot, user_id: int) -> str:
    try:
        user = await bot.fetch_user(user_id)
        return getattr(user, "display_name", None) or getattr(user, "name", "Unknown")
    except Exception:
        logger.debug("Failed to fetch user %s", user_id, exc_info=True)
        return "Unresolved User"


async def resolve_offender(bot: commands.Bot, identifier: str, db_cursor, rule: Optional[str] = None, min_steamid_len: int = 17) -> Dict[str, Any]:
    steamid: Optional[str] = None
    discord_id: Optional[int] = None
    discord_name: str = "Unknown"
    ign: str = "Unknown"
    repeat = False
    try:
        id_str = identifier.strip()
        m = re.match(r"<@!?(?P<id>\d+)>$", id_str)
        if m:
            discord_id = int(m.group("id"))
            try:
                db_cursor.execute("SELECT steamid, ign FROM users WHERE discordid=?", (discord_id,))
                row = db_cursor.fetchone()
                if row:
                    steamid_candidate, ign_candidate = row
                    steamid = steamid_candidate or steamid
                    ign = ign_candidate or ign
            except Exception:
                logger.debug("DB users lookup by discordid failed", exc_info=True)
            discord_name = await _safe_fetch_user_name(bot, discord_id)
        else:
            cleaned = id_str
            if cleaned.isdigit():
                if len(cleaned) >= min_steamid_len:
                    steamid = cleaned
                    try:
                        db_cursor.execute("SELECT discordid, ign FROM users WHERE steamid=?", (steamid,))
                        row = db_cursor.fetchone()
                        if row:
                            discord_candidate, ign_candidate = row
                            discord_id = discord_candidate or discord_id
                            ign = ign_candidate or ign
                            if discord_candidate:
                                discord_name = await _safe_fetch_user_name(bot, discord_candidate)
                    except Exception:
                        logger.debug("DB users lookup by steamid failed", exc_info=True)
                else:
                    try:
                        discord_id = int(cleaned)
                        db_cursor.execute("SELECT steamid, ign FROM users WHERE discordid=?", (discord_id,))
                        row = db_cursor.fetchone()
                        if row:
                            steamid_candidate, ign_candidate = row
                            steamid = steamid_candidate or steamid
                            ign = ign_candidate or ign
                        discord_name = await _safe_fetch_user_name(bot, discord_id)
                    except Exception:
                        logger.debug("Short numeric treated as discord id but failed", exc_info=True)
            else:
                digits = re.sub(r"\D", "", cleaned)
                if digits and len(digits) >= min_steamid_len:
                    steamid = digits
                    try:
                        db_cursor.execute("SELECT discordid, ign FROM users WHERE steamid=?", (steamid,))
                        row = db_cursor.fetchone()
                        if row:
                            discord_candidate, ign_candidate = row
                            discord_id = discord_candidate or discord_id
                            ign = ign_candidate or ign
                            if discord_candidate:
                                discord_name = await _safe_fetch_user_name(bot, discord_candidate)
                    except Exception:
                        logger.debug("DB lookup stripped steamid failed", exc_info=True)

        # repeat-by-rule detection if rule provided
        try:
            if rule and rule.strip():
                rule_check = rule.strip()
                if steamid and steamid != "Unknown":
                    try:
                        db_cursor.execute("SELECT COUNT(*) FROM infractions WHERE steamid=? AND reason=?", (steamid, rule_check))
                        row = db_cursor.fetchone()
                        if row and row[0] and int(row[0]) > 0:
                            repeat = True
                    except Exception:
                        logger.debug("infractions lookup steamid+reason failed", exc_info=True)
                elif discord_id:
                    try:
                        db_cursor.execute("SELECT COUNT(*) FROM infractions WHERE discordid=? AND reason=?", (discord_id, rule_check))
                        row = db_cursor.fetchone()
                        if row and row[0] and int(row[0]) > 0:
                            repeat = True
                    except Exception:
                        logger.debug("infractions lookup discordid+reason failed", exc_info=True)
            else:
                # fallback: any previous infraction or total_points
                if steamid and steamid != "Unknown":
                    try:
                        db_cursor.execute("SELECT COUNT(*) FROM infractions WHERE steamid=?", (steamid,))
                        row = db_cursor.fetchone()
                        if row and row[0] and int(row[0]) > 0:
                            repeat = True
                        else:
                            db_cursor.execute("SELECT total_points FROM users WHERE steamid=?", (steamid,))
                            row = db_cursor.fetchone()
                            if row and row[0] and int(row[0]) > 0:
                                repeat = True
                    except Exception:
                        logger.debug("generic repeat detection by steamid failed", exc_info=True)
                elif discord_id:
                    try:
                        db_cursor.execute("SELECT COUNT(*) FROM infractions WHERE discordid=?", (discord_id,))
                        row = db_cursor.fetchone()
                        if row and row[0] and int(row[0]) > 0:
                            repeat = True
                        else:
                            db_cursor.execute("SELECT total_points FROM users WHERE discordid=?", (discord_id,))
                            row = db_cursor.fetchone()
                            if row and row[0] and int(row[0]) > 0:
                                repeat = True
                    except Exception:
                        logger.debug("generic repeat detection by discordid failed", exc_info=True)
        except Exception:
            logger.debug("repeat detection queries failed", exc_info=True)
    except Exception:
        logger.exception("Unexpected error in resolve_offender", exc_info=True)

    if not steamid:
        digits = re.sub(r"\D", "", identifier)
        if digits and len(digits) >= 17:
            steamid = digits

    return {
        "steamid": steamid or "Unknown",
        "discord_id": discord_id,
        "discord_name": discord_name or "Unknown",
        "ign": ign or "Unknown",
        "repeat_offender": bool(repeat),
    }


# ---- Catbox uploader (single file uploads only) ----


class CatboxUploader:
    API_URL = "https://catbox.moe/user/api.php"

    def __init__(self, session: aiohttp.ClientSession, userhash: str = ""):
        self.session = session
        self.userhash = userhash

    async def upload_bytes(self, filename: str, data: bytes, content_type: Optional[str] = None) -> Optional[str]:
        """
        Upload a single file to Catbox. Returns URL on success else None.
        """
        try:
            form = aiohttp.FormData()
            form.add_field("reqtype", "fileupload")
            if self.userhash:
                form.add_field("userhash", self.userhash)
            form.add_field("fileToUpload", data, filename=filename, content_type=content_type or "application/octet-stream")
            async with self.session.post(self.API_URL, data=form) as resp:
                text = await resp.text()
                if resp.status == 200 and text and text.startswith("http"):
                    return text.strip()
                logger.error("Catbox upload failed %s: %s", resp.status, text)
                return None
        except Exception:
            logger.exception("Exception uploading to catbox", exc_info=True)
            return None


# ---- The Cog ----


class WatchtowerLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        self.catbox = CatboxUploader(self.session, userhash=CATBOX_USERHASH)

    async def cog_unload(self) -> None:
        try:
            if not self.session.closed:
                await self.session.close()
        except Exception:
            logger.exception("Error closing aiohttp session", exc_info=True)

    async def generate_transcript_url(self, channel: discord.abc.Messageable) -> Optional[str]:
        """
        Create HTML transcript (in-memory) and upload to catbox; returns url or None.
        """
        try:
            parts: List[str] = [
                "<!doctype html>",
                "<html><head><meta charset='utf-8'><title>Transcript</title>",
                "<style>body{font-family:sans-serif;background:#2f3136;color:#dcddde} .message{margin:8px;padding:4px;border-bottom:1px solid rgba(255,255,255,0.03);} .author{font-weight:600;} .timestamp{color:#72767d;font-size:0.8em;margin-right:6px;}</style>",
                "</head><body>"
            ]
            async for msg in channel.history(limit=None, oldest_first=True):
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                author = getattr(msg.author, "display_name", None) or getattr(msg.author, "name", "Unknown")
                content = discord.utils.escape_markdown(msg.clean_content or "")
                content = content.replace("\n", "<br>")
                parts.append(f"<div class='message'><span class='timestamp'>{ts}</span> <span class='author'>{author}:</span> <span class='content'>{content}</span></div>")
            parts.append("</body></html>")
            html_bytes = "\n".join(parts).encode("utf-8")
            filename = f"transcript_{int(time.time())}.html"
            return await self.catbox.upload_bytes(filename, html_bytes, content_type="text/html")
        except Exception:
            logger.exception("Failed to generate/upload transcript", exc_info=True)
            return None

    async def collect_and_upload_attachments(self, channel: discord.abc.Messageable) -> List[Dict[str, Any]]:
        """
        Walk channel history in chronological order and upload each attachment separately.
        Return a list of dicts in chronological order, each dict contains:
         - filename, url (catbox or None), fallback_file (discord.File or None),
         - author_name (str), timestamp (str), message_content (str)
        This allows media to be enumerated exactly as they appear in the ticket.
        """
        results: List[Dict[str, Any]] = []
        try:
            # iterate oldest -> newest so ordering matches how moderators read the ticket
            async for msg in channel.history(limit=None, oldest_first=True):
                # capture message text so we can show it alongside any media posted in that message
                author_name = getattr(msg.author, "display_name", None) or getattr(msg.author, "name", "Unknown")
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                message_text = (msg.clean_content or "").strip()

                # For each attachment in this message, upload separately and append an entry describing it
                for att in msg.attachments:
                    entry: Dict[str, Any] = {
                        "filename": getattr(att, "filename", "attachment"),
                        "url": None,
                        "fallback_file": None,
                        "author_name": author_name,
                        "timestamp": ts,
                        "message_text": message_text,
                    }
                    try:
                        if att.size and att.size >= 250 * 1024 * 1024:
                            logger.warning("Skipping very large attachment %s (%d bytes)", att.filename, att.size)
                            results.append(entry)
                            continue

                        # Download bytes
                        async with self.session.get(att.url) as resp:
                            if resp.status != 200:
                                logger.error("Failed to download attachment %s: HTTP %s", att.url, resp.status)
                                results.append(entry)
                                continue
                            data = await resp.read()

                        # Upload each file individually to Catbox (no batch)
                        url = await self.catbox.upload_bytes(att.filename or f"attachment_{int(time.time())}", data, content_type=getattr(att, "content_type", None))
                        entry["url"] = url

                        if not url:
                            # fallback to discord.File for small files (<25MB)
                            if att.size and att.size < 25 * 1024 * 1024:
                                try:
                                    ff = await att.to_file()
                                    entry["fallback_file"] = ff
                                except Exception:
                                    logger.exception("Fallback to discord.File failed for %s", att.filename, exc_info=True)
                            else:
                                logger.warning("Attachment skipped (no catbox url and too large for Discord): %s", att.filename)
                        results.append(entry)
                    except Exception:
                        logger.exception("Error processing attachment %s", getattr(att, "filename", "<unknown>"), exc_info=True)
                        results.append(entry)
        except Exception:
            logger.exception("Error iterating channel history for attachments", exc_info=True)
        return results

    async def _find_thread(self, watchtower_channel: discord.abc.Messageable, thread_name: str) -> Optional[discord.Thread]:
        try:
            threads = getattr(watchtower_channel, "threads", None)
            if threads:
                for t in threads:
                    if getattr(t, "name", None) == thread_name:
                        return t
        except Exception:
            logger.debug("Error iterating active threads", exc_info=True)
        try:
            archived_callable = getattr(watchtower_channel, "archived_threads", None)
            if callable(archived_callable):
                async for t in archived_callable(limit=None):
                    if getattr(t, "name", None) == thread_name:
                        return t
        except Exception:
            logger.debug("Archived threads lookup not supported or failed", exc_info=True)
        return None

    async def _create_watchtower_thread(self, watchtower_channel: discord.abc.Messageable, thread_name: str, starter_content: str) -> Optional[discord.Thread]:
        try:
            if isinstance(watchtower_channel, discord.ForumChannel):
                try:
                    if hasattr(watchtower_channel, "create_post"):
                        post = await watchtower_channel.create_post(name=thread_name, content=starter_content)
                        return post
                    if hasattr(watchtower_channel, "create_thread"):
                        return await watchtower_channel.create_thread(name=thread_name, content=starter_content)
                except Exception:
                    logger.debug("Forum-specific create failed; falling back", exc_info=True)
                try:
                    sent = await watchtower_channel.send(starter_content)
                    if hasattr(sent, "create_thread"):
                        return await sent.create_thread(name=thread_name)
                    if hasattr(watchtower_channel, "create_thread"):
                        return await watchtower_channel.create_thread(name=thread_name, message=sent)
                except Exception:
                    logger.exception("Fallback forum thread creation failed", exc_info=True)
                    return None
            try:
                sent = await watchtower_channel.send(starter_content)
                if hasattr(sent, "create_thread"):
                    return await sent.create_thread(name=thread_name)
                if hasattr(watchtower_channel, "create_thread"):
                    return await watchtower_channel.create_thread(name=thread_name, message=sent)
            except Exception:
                logger.debug("Text channel create via message failed; trying direct create_thread", exc_info=True)
                try:
                    return await watchtower_channel.create_thread(name=thread_name, content=starter_content)
                except Exception:
                    logger.exception("Direct create_thread failed", exc_info=True)
                    return None
        except Exception:
            logger.exception("Unhandled exception while creating watchtower thread", exc_info=True)
            return None

    async def apply_points(self, steamid: str, points: int, rule: str, notes: str, issuer: str, ticket_id: str) -> Dict[str, Any]:
        if points <= 0 or not steamid or steamid == "Unknown":
            return {"success": True, "response": None}
        if not POINTS_API_TOKEN or POINTS_API_TOKEN == "CHANGE_ME":
            logger.warning("Points API token missing; skipping points application.")
            return {"success": False, "response": None}
        payload = {"steamid": steamid, "points": points, "reason": rule, "notes": notes + (f" | Ticket {ticket_id}" if ticket_id else ""), "issuer": issuer}
        headers = {"Authorization": f"Bearer {POINTS_API_TOKEN}", "Content-Type": "application/json"}
        for attempt in range(3):
            try:
                async with self.session.post(POINTS_API_URL, json=payload, headers=headers) as resp:
                    text = await resp.text()
                    if resp.status == 200:
                        try:
                            data = await resp.json()
                            return {"success": True, "response": data}
                        except Exception:
                            logger.warning("Points API returned non-JSON on 200 (%s)", text)
                            return {"success": True, "response": None}
                    else:
                        logger.error("Points API error %s: %s", resp.status, text)
                        if resp.status in (429, 502, 503, 504):
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return {"success": False, "response": None}
            except Exception:
                logger.exception("Exception while calling Points API, retrying", exc_info=True)
                await asyncio.sleep(2 ** attempt)
        return {"success": False, "response": None}

    def _record_infraction(self, db_cursor, db_conn, steamid: Optional[str], discord_id: Optional[int], reason: str) -> None:
        try:
            ts = int(time.time())
            db_cursor.execute("INSERT INTO infractions (steamid, discordid, reason, timestamp) VALUES (?, ?, ?, ?)", (steamid, discord_id, reason, ts))
            if db_conn:
                try:
                    db_conn.commit()
                except Exception:
                    logger.debug("Failed to commit infraction insert", exc_info=True)
        except Exception:
            logger.exception("Failed to record infraction (table may not exist)", exc_info=True)

    async def _post_media_links(self, thread: discord.abc.Messageable, transcript_url: Optional[str], attachments: List[Dict[str, Any]]) -> None:
        """
        Post media in readable format mirroring the ticket order:
        For each attachment: show author, timestamp, optional message text, then filename: url (or upload failed)
        Each block is one line per media entry; chunked into messages to remain manageable.
        """
        lines: List[str] = []
        if transcript_url:
            lines.append(f"Transcript: {transcript_url}")

        for att in attachments:
            author = att.get("author_name", "Unknown")
            ts = att.get("timestamp", "")
            msg_text = att.get("message_text", "")
            fname = att.get("filename", "attachment")
            if att.get("url"):
                line = f"{author} — {ts}\n{(msg_text + '\n') if msg_text else ''}{fname}: {att.get('url')}"
            else:
                line = f"{author} — {ts}\n{(msg_text + '\n') if msg_text else ''}{fname}: (upload failed)"
            lines.append(line)

        if not lines:
            return

        # Chunk to avoid large single messages and keep readability
        chunk_size = 5  # 5 media entries per message (each entry may be multi-line)
        for i in range(0, len(lines), chunk_size):
            chunk = lines[i : i + chunk_size]
            try:
                await thread.send("**Media:**\n" + "\n\n".join(chunk))
            except Exception:
                logger.exception("Failed to post media links chunk", exc_info=True)

        # Send fallback discord.File attachments (small files that couldn't be uploaded)
        fallback_files = [a["fallback_file"] for a in attachments if a.get("fallback_file")]
        for i in range(0, len(fallback_files), ATTACHMENT_BATCH_SIZE):
            try:
                await thread.send(files=fallback_files[i : i + ATTACHMENT_BATCH_SIZE], content="**Media (fallback attachments)**")
            except Exception:
                logger.exception("Failed to send fallback attachments", exc_info=True)

    async def log_from_resolve(self, interaction: discord.Interaction, ticket_channel: discord.abc.Messageable, db_cursor, db_conn, ticket_id: str = "") -> None:
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
            ephemeral=True,
        )

        def check(m: discord.Message) -> bool:
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            paste_msg: discord.Message = await self.bot.wait_for("message", timeout=1200.0, check=check)
            lines = [l.strip() for l in paste_msg.content.splitlines() if l.strip()]
            try:
                await paste_msg.delete()
            except Exception:
                logger.debug("Could not delete moderator paste", exc_info=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("Timed out waiting for offenders paste.", ephemeral=True)
            return

        # Recent context: latest 20 messages (for embed)
        try:
            recent_msgs = [m async for m in ticket_channel.history(limit=20, oldest_first=False)]
            context = "\n".join(f"{getattr(m.author, 'display_name', None) or m.author.name}: {m.clean_content[:300]}" for m in recent_msgs)
        except Exception:
            logger.exception("Failed to fetch recent context", exc_info=True)
            context = "Context unavailable."

        # Prepare evidence uploads (transcript + per-file attachments). We upload every file separately.
        transcript_url = await self.generate_transcript_url(ticket_channel)
        attachments = await self.collect_and_upload_attachments(ticket_channel)

        # Resolve watchtower channel
        watchtower = self.bot.get_channel(WATCHTOWER_CHANNEL_ID)
        if not watchtower or not isinstance(watchtower, (discord.TextChannel, discord.ForumChannel)):
            await interaction.followup.send("Watchtower channel invalid or inaccessible. Please check configuration.", ephemeral=True)
            return

        processed = 0
        for line in lines:
            parsed = parse_offender_line(line)
            if not parsed:
                logger.warning("Skipping unparsable line: %s", line)
                continue

            try:
                offender = await resolve_offender(self.bot, parsed["identifier"], db_cursor, rule=parsed["rule"])
            except Exception:
                logger.exception("resolve_offender failed; skipping", exc_info=True)
                continue

            thread_name = f"{offender['discord_name']} | {offender['steamid']}" if offender["discord_name"] != "Unknown" else offender["steamid"]

            # Build embed: include rule + ticket text (public notes) plus recent context
            description_parts: List[str] = []
            if parsed["rule"]:
                description_parts.append(f"Rule: {parsed['rule']}")
            if parsed["notes"]:
                # Keep the ticket's public text directly in the embed so mods can read it immediately
                description_parts.append(f"Ticket Text: {parsed['notes']}")
            description = "\n".join(description_parts) or "—"

            embed = discord.Embed(
                title=f"Ticket Resolution {f'#{ticket_id}' if ticket_id else ''}",
                description=description,
                color=0xFF0000 if int(parsed["points"]) > 0 else 0xFFA500,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Discord", value=offender["discord_name"], inline=True)
            embed.add_field(name="SteamID", value=offender["steamid"], inline=True)
            embed.add_field(name="IGN", value=offender["ign"], inline=True)
            embed.add_field(name="Points Applied", value=str(parsed["points"]), inline=True)
            if context:
                embed.add_field(name="Recent Context (latest messages)", value=(context[:1024] if context else "—"), inline=False)
            if offender.get("repeat_offender"):
                embed.add_field(name="Repeat Offender (same rule)", value="Yes — previous infraction for this rule detected", inline=False)

            # Find or create a watchtower thread
            thread = await self._find_thread(watchtower, thread_name)
            if not thread:
                thread = await self._create_watchtower_thread(watchtower, thread_name, "Watchtower thread initialized.")
                if not thread:
                    await interaction.followup.send(f"Failed to create watchtower thread for {thread_name}", ephemeral=True)
                    continue

            # Send embed and mod notes
            try:
                await thread.send(embed=embed)
            except Exception:
                logger.exception("Failed to send embed", exc_info=True)
            if parsed["mod_notes"]:
                try:
                    await thread.send(f"**Staff Notes:** {parsed['mod_notes']}")
                except Exception:
                    logger.exception("Failed to send staff notes", exc_info=True)

            # Apply points
            api_result = await self.apply_points(offender["steamid"], int(parsed["points"]), parsed["rule"], parsed["notes"], str(interaction.user), ticket_id)
            if not api_result.get("success"):
                try:
                    await thread.send("⚠️ Points application failed or was skipped.")
                except Exception:
                    logger.debug("Couldn't notify about points failure", exc_info=True)
            elif api_result.get("response"):
                extra = api_result["response"]
                info_lines: List[str] = []
                if isinstance(extra, dict):
                    if "total_points" in extra:
                        info_lines.append(f"New total: **{extra['total_points']}** points")
                    if "action" in extra:
                        info_lines.append(f"Escalation: {extra['action']}")
                if info_lines:
                    try:
                        await thread.send("\n".join(info_lines))
                    except Exception:
                        logger.exception("Failed to send Points API response", exc_info=True)

            # Record infraction (reason = rule or notes or points)
            try:
                reason_to_record = parsed["rule"] or parsed["notes"] or f"Points:{parsed['points']}"
                self._record_infraction(db_cursor, db_conn, offender.get("steamid"), offender.get("discord_id"), reason_to_record)
            except Exception:
                logger.exception("Failed recording infraction (continuing)", exc_info=True)

            # Post media links (transcript + attachments) directly under the embed in chronological order, preserving
            # author/timestamp/message-text context so mods can read ticket text then glance the media list.
            if processed == 0:
                try:
                    await self._post_media_links(thread, transcript_url, attachments)
                except Exception:
                    logger.exception("Failed to post media links", exc_info=True)

            processed += 1

        await interaction.followup.send(f"Logged {processed} offender(s) to Watchtower.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WatchtowerLogger(bot))