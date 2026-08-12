"""Where the facts come from.

Two free sources, no paid tier:

  football-data.org  -- Premier League and Championship tables.
                        Free key, 10 requests/min. We make 2 calls a day.
  Fantasy PL API     -- every PL player's goals and club, no key at all.
                        Unofficial but long-standing and public.

Everything else (cups, awards, first sacking, play-off winner) lives in
data/manual.yml, because no free tier covers those competitions.

Every fetcher caches its raw response to cache/. If a source is down, the
build falls back to the cache and the leaderboard keeps working -- it just
goes stale rather than blank.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from aliases import canon

CACHE = Path(__file__).parent / "cache"
FD_BASE = "https://api.football-data.org/v4"
FPL_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"

USER_AGENT = "footy-predictions/1.0"


def _get_json(url: str, headers: dict[str, str], cache_name: str) -> dict:
    """Fetch JSON, caching on success and falling back to cache on failure."""
    CACHE.mkdir(exist_ok=True)
    cache_file = CACHE / f"{cache_name}.json"

    req = Request(url, headers={"User-Agent": USER_AGENT, **headers})
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        cache_file.write_text(json.dumps(data))
        return data
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        if cache_file.exists():
            age_h = (time.time() - cache_file.stat().st_mtime) / 3600
            print(f"  ! {cache_name}: {exc} -- using cache ({age_h:.0f}h old)")
            return json.loads(cache_file.read_text())
        raise RuntimeError(f"{cache_name} failed and no cache exists: {exc}") from exc


# ---------------------------------------------------------------------------
# football-data.org
# ---------------------------------------------------------------------------

def _fd_headers() -> dict[str, str]:
    token = os.environ.get("FOOTBALL_DATA_TOKEN", "")
    if not token:
        raise RuntimeError(
            "FOOTBALL_DATA_TOKEN is not set. Get a free key at "
            "football-data.org/client/register and export it."
        )
    return {"X-Auth-Token": token}


def fetch_table(competition: str) -> list[str]:
    """Ordered list of club names, 1st first. competition is 'PL' or 'ELC'."""
    data = _get_json(
        f"{FD_BASE}/competitions/{competition}/standings",
        _fd_headers(),
        f"standings_{competition}",
    )
    total = next(
        (s for s in data.get("standings", []) if s.get("type") == "TOTAL"), None
    )
    if total is None:
        raise RuntimeError(f"No TOTAL standings block for {competition}")

    rows = sorted(total["table"], key=lambda r: r["position"])
    return [
        canon(r["team"].get("shortName") or r["team"]["name"]) for r in rows
    ]


def fetch_teams(competition: str, season: int | None = None) -> list[str]:
    """Alphabetical list of clubs in a competition for a given season.

    Unlike standings, the teams endpoint accepts ?season=YYYY (the starting
    year, so 2026 means 2026-27) and works BEFORE any match is played. That's
    what we want for the form: pre-season, the "current" standings still hold
    last season's clubs, but the teams list for the new season is already set
    once the fixtures are published.
    """
    url = f"{FD_BASE}/competitions/{competition}/teams"
    cache = f"teams_{competition}"
    if season is not None:
        url += f"?season={season}"
        cache += f"_{season}"

    data = _get_json(url, _fd_headers(), cache)
    teams = data.get("teams", [])
    names = [canon(t.get("shortName") or t["name"]) for t in teams]
    return sorted(names)


# ---------------------------------------------------------------------------
# Fantasy Premier League
# ---------------------------------------------------------------------------

def fetch_pl_players() -> tuple[dict[str, int], dict[str, str]]:
    """Return (goals_by_player, club_by_player).

    FPL's goals_scored field already excludes own goals -- those sit in a
    separate own_goals field -- which is exactly the rule we want.

    Player keys are display names. Where two players share a surname the club
    is appended, so 'Silva' becomes 'Silva (Fulham)'. make_form_options.py
    emits these same keys, so the dropdown and the scorer can never disagree.
    """
    data = _get_json(FPL_URL, {}, "fpl_bootstrap")

    clubs = {t["id"]: canon(t["name"]) for t in data["teams"]}

    counts: dict[str, int] = {}
    for el in data["elements"]:
        counts[el["web_name"]] = counts.get(el["web_name"], 0) + 1

    goals: dict[str, int] = {}
    club_of: dict[str, str] = {}
    for el in data["elements"]:
        name = el["web_name"]
        club = clubs.get(el["team"], "?")
        key = f"{name} ({club})" if counts[name] > 1 else name
        goals[key] = el.get("goals_scored", 0)
        club_of[key] = club

    return goals, club_of


def top_scorers_from(goals: dict[str, int]) -> list[str]:
    """Everyone tied on the most PL goals. Empty early in the season when
    nobody has scored, which correctly scores zero for everyone.
    """
    if not goals:
        return []
    best = max(goals.values())
    if best == 0:
        return []
    return sorted(p for p, g in goals.items() if g == best)
