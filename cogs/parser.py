from __future__ import annotations

import re
import logging
from typing import Optional, Callable, Dict, Any, Awaitable

logger = logging.getLogger(__name__)

IdentifierInfo = Dict[str, Any]
FetchUserCallable = Callable[[int], Awaitable[Any]]


def parse_offender_line(line: str) -> Optional[Dict[str, str]]:
    """
    Parse a single line from the moderator bulk paste.

    Returns a dict:
      {
        "identifier": "<@123...>" or "7656119...",
        "points": "2" or "0",
        "rule": "Griefing",
        "mod_notes": "internal notes",
        "notes": "public notes"
      }
    Returns None if the line cannot be parsed.
    """
    if not line or not line.strip():
        return None

    # Split on pipes for mod_notes and public notes (max 2 splits)
    parts = [p.strip() for p in line.split("|", 2)]
    left = parts[0]
    mod_notes = parts[1] if len(parts) > 1 else ""
    notes = parts[2] if len(parts) > 2 else ""

    # Left side: identifier, optional points, optional rule
    m = re.match(r"^\s*(?P<identifier><@!?\d+>|\d{1,30})\s*(?P<points>\d+)?\s*(?P<rule>.*)?$", left)
    if not m:
        logger.debug("parse_offender_line: regex failed for line: %s", line)
        return None

    identifier = m.group("identifier")
    points = m.group("points") or "0"
    rule = (m.group("rule") or "").strip()

    return {
        "identifier": identifier,
        "points": points,
        "rule": rule,
        "mod_notes": mod_notes,
        "notes": notes,
    }


async def resolve_offender(
    identifier: str,
    db_cursor,
    fetch_user: Optional[FetchUserCallable] = None,
    rule: Optional[str] = None,
    min_steamid_len: int = 17,
) -> IdentifierInfo:
    """
    Resolve identifier to a canonical offender object. Returns keys:
    - steamid (str, or "Unknown")
    - discord_id (int | None)
    - discord_name (str)
    - ign (str)
    - repeat_offender (bool) — true if DB shows previous infractions for the SAME rule

    Parameters:
    - fetch_user: async callable accepting an int id and returning an object with .display_name or .name
    - db_cursor: DB cursor supporting execute()/fetchone()
    - rule: optional rule string to check for repeats of the same rule
    """
    steamid: Optional[str] = None
    discord_id: Optional[int] = None
    discord_name: str = "Unknown"
    ign: str = "Unknown"
    repeat = False

    try:
        # mention form <@123...> or <@!123...>
        m = re.match(r"<@!?(?P<id>\d+)>$", identifier.strip())
        if m:
            discord_id = int(m.group("id"))
            # DB lookups: try users by discordid
            try:
                db_cursor.execute("SELECT steamid, ign FROM users WHERE discordid=?", (discord_id,))
                row = db_cursor.fetchone()
                if row:
                    steamid_candidate, ign_candidate = row
                    if steamid_candidate:
                        steamid = steamid_candidate
                    if ign_candidate:
                        ign = ign_candidate
            except Exception:
                logger.debug("resolve_offender: users lookup by discordid failed, continuing")

            if fetch_user:
                try:
                    user = await fetch_user(discord_id)
                    discord_name = getattr(user, "display_name", None) or getattr(user, "name", "Unresolved User")
                except Exception:
                    logger.debug("resolve_offender: fetch_user failed")
                    discord_name = "Unresolved User"
        else:
            cleaned = identifier.strip()
            if cleaned.isdigit():
                # treat as steamid if long enough
                if len(cleaned) >= min_steamid_len:
                    steamid = cleaned
                    try:
                        db_cursor.execute("SELECT discordid, ign FROM users WHERE steamid=?", (steamid,))
                        row = db_cursor.fetchone()
                        if row:
                            discord_candidate, ign_candidate = row
                            if discord_candidate:
                                discord_id = discord_candidate
                                if fetch_user:
                                    try:
                                        user = await fetch_user(discord_id)
                                        discord_name = getattr(user, "display_name", None) or getattr(user, "name", "Unresolved User")
                                    except Exception:
                                        discord_name = "Unresolved User"
                            if ign_candidate:
                                ign = ign_candidate
                    except Exception:
                        logger.debug("resolve_offender: users lookup by steamid failed")
                else:
                    # short numeric — treat as discord id
                    try:
                        discord_id = int(cleaned)
                        db_cursor.execute("SELECT steamid, ign FROM users WHERE discordid=?", (discord_id,))
                        row = db_cursor.fetchone()
                        if row:
                            steamid_candidate, ign_candidate = row
                            if steamid_candidate:
                                steamid = steamid_candidate
                            if ign_candidate:
                                ign = ign_candidate
                        if fetch_user:
                            try:
                                user = await fetch_user(discord_id)
                                discord_name = getattr(user, "display_name", None) or getattr(user, "name", "Unresolved User")
                            except Exception:
                                discord_name = "Unresolved User"
                    except Exception:
                        logger.debug("resolve_offender: treating short numeric as discord id failed")
            else:
                # non-numeric: treat as raw steamid maybe with dashes
                digits = re.sub(r"\D", "", cleaned)
                if digits and len(digits) >= min_steamid_len:
                    steamid = digits
                    try:
                        db_cursor.execute("SELECT discordid, ign FROM users WHERE steamid=?", (steamid,))
                        row = db_cursor.fetchone()
                        if row:
                            discord_candidate, ign_candidate = row
                            if discord_candidate:
                                discord_id = discord_candidate
                                if fetch_user:
                                    try:
                                        user = await fetch_user(discord_id)
                                        discord_name = getattr(user, "display_name", None) or getattr(user, "name", "Unresolved User")
                                    except Exception:
                                        discord_name = "Unresolved User"
                            if ign_candidate:
                                ign = ign_candidate
                    except Exception:
                        logger.debug("resolve_offender: users lookup by stripped steamid failed")

        # Detect repeat offender for the SAME rule:
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
                        logger.debug("resolve_offender: infractions (steamid+reason) lookup failed")
                elif discord_id:
                    try:
                        db_cursor.execute("SELECT COUNT(*) FROM infractions WHERE discordid=? AND reason=?", (discord_id, rule_check))
                        row = db_cursor.fetchone()
                        if row and row[0] and int(row[0]) > 0:
                            repeat = True
                    except Exception:
                        logger.debug("resolve_offender: infractions (discordid+reason) lookup failed")
            else:
                # No rule provided — fallback to prior behavior (any previous infraction or total_points > 0)
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
                        logger.debug("resolve_offender: generic repeat detection queries failed")
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
                        logger.debug("resolve_offender: generic repeat detection via discordid failed")
        except Exception:
            logger.debug("resolve_offender: repeat detection queries failed")

    except Exception:
        logger.exception("resolve_offender: unexpected error")

    # last-resort steamid guess
    if not steamid:
        digits = re.sub(r"\D", "", identifier)
        if digits and len(digits) >= min_steamid_len:
            steamid = digits

    return {
        "steamid": steamid or "Unknown",
        "discord_id": discord_id,
        "discord_name": discord_name or "Unknown",
        "ign": ign or "Unknown",
        "repeat_offender": bool(repeat),
    }