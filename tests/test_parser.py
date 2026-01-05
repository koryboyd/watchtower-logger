import asyncio
import pytest

from cogs.parser import parse_offender_line, resolve_offender

# Simple fake DB cursor to simulate fetchone behavior
class FakeCursor:
    def __init__(self, rows=None):
        # rows is a dict keyed by tuple describing query intention
        # e.g. ("users_by_discord", discordid) -> ("steamid", "ign")
        # ("infractions_by_rule", (steamid, rule)) -> count
        # ("infractions", steamid) -> count
        # ("total_points_steam", steamid) -> points
        self.rows = rows or {}
        self._last_query = None

    def execute(self, query, params=()):
        self._last_query = (query, params)

    def fetchone(self):
        query, params = self._last_query
        q = query.lower()
        # users by discord
        if "from users where discordid" in q:
            discordid = params[0]
            return self.rows.get(("users_by_discord", discordid))
        # users by steamid
        if "from users where steamid" in q:
            steamid = params[0]
            return self.rows.get(("users_by_steam", steamid))
        # infractions by steamid and reason
        if "from infractions where steamid=? and reason=?" in q:
            steamid, reason = params
            return (self.rows.get(("infractions_by_rule", (steamid, reason)), 0),)
        # infractions by discordid and reason
        if "from infractions where discordid=? and reason=?" in q:
            discordid, reason = params
            return (self.rows.get(("infractions_by_rule_discord", (discordid, reason)), 0),)
        # infractions count by steamid
        if "from infractions where steamid=?" in q:
            steamid = params[0]
            return (self.rows.get(("infractions", steamid), 0),)
        # infractions count by discordid
        if "from infractions where discordid=?" in q:
            discordid = params[0]
            return (self.rows.get(("infractions_discord", discordid), 0),)
        if "select total_points from users where steamid" in q:
            steamid = params[0]
            return (self.rows.get(("total_points_steam", steamid), 0),)
        if "select total_points from users where discordid" in q:
            discordid = params[0]
            return (self.rows.get(("total_points_discord", discordid), 0),)
        return None


class DummyUser:
    def __init__(self, id, name, display_name=None):
        self.id = id
        self.name = name
        self.display_name = display_name or name

@pytest.mark.parametrize("line,expected", [
    ("<@123456789012345678> 2 Griefing | Internal | Public note", {
        "identifier": "<@123456789012345678>", "points": "2", "rule": "Griefing", "mod_notes": "Internal", "notes": "Public note"
    }),
    ("76561198000000000 1 Spam || Public", {
        "identifier": "76561198000000000", "points": "1", "rule": "Spam", "mod_notes": "", "notes": "Public"
    }),
    ("76561198000000000", {
        "identifier": "76561198000000000", "points": "0", "rule": "", "mod_notes": "", "notes": ""
    }),
])
def test_parse_offender_line(line, expected):
    parsed = parse_offender_line(line)
    assert parsed is not None
    for k, v in expected.items():
        assert parsed[k] == v

@pytest