"""Fetch, score, write. This is what the cron job runs.

    python build.py            # normal run
    python build.py --check    # validate entries, score nothing

Writes docs/data/leaderboard.json, which the static page reads. Nothing else
in the repo changes, so the git diff each morning is one file.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from loaders import build_facts, load_manual_facts, load_predictions
from scoring import CUP_FIELDS, championship_group, score_league, validate_entry
from sources import fetch_pl_players, fetch_table, top_scorers_from

ROOT = Path(__file__).parent
PREDICTIONS = ROOT / "data" / "predictions.csv"
MANUAL = ROOT / "data" / "manual.yml"
OUT = ROOT / "docs" / "data" / "leaderboard.json"

CATEGORY_LABELS = {
    "pl_top6": "Premier League top 6",
    "pl_bottom3": "Premier League bottom 3",
    "champ_top3": "Championship promotion",
    "top_scorer": "Top scorer",
    "poty": "Player of the Year",
    "ypoty": "Young Player of the Year",
    "fa_cup": "FA Cup",
    "carabao_cup": "Carabao Cup",
    "champions_league": "Champions League",
    "europa_league": "Europa League",
    "conference_league": "Conference League",
    "first_manager_out": "First manager out",
    "managers_out_count": "Managers out (count)",
    "blackjack": "Blackjack",
}


def check_entries(entries, club_of) -> int:
    """Print a validation report. Returns the number of broken entries."""
    broken = 0
    seen: set[str] = set()
    for e in entries:
        problems = validate_entry(e, club_of)
        if not e.name:
            problems.append("no name given")
        elif e.name.lower() in seen:
            problems.append("duplicate entrant name")
        seen.add(e.name.lower())

        if problems:
            broken += 1
            print(f"\n  {e.name or '(unnamed)'}")
            for p in problems:
                print(f"    - {p}")

    if broken:
        print(f"\n{broken} of {len(entries)} entries need fixing.")
    else:
        print(f"All {len(entries)} entries are valid.")
    return broken


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="validate entries and exit, no scoring")
    args = ap.parse_args()

    print("Loading predictions...")
    entries = load_predictions(PREDICTIONS)
    print(f"  {len(entries)} entries")

    print("Fetching PL players (FPL)...")
    pl_goals, club_of = fetch_pl_players()
    print(f"  {len(pl_goals)} players")

    if args.check:
        return 1 if check_entries(entries, club_of) else 0

    print("Fetching league tables (football-data.org)...")
    pl_table = fetch_table("PL")
    championship_table = fetch_table("ELC")
    print(f"  PL: {len(pl_table)} clubs, Championship: {len(championship_table)}")

    manual = load_manual_facts(MANUAL)
    decided = [k for k, v in manual.items() if v]
    print(f"Manual facts decided: {', '.join(decided) if decided else 'none yet'}")

    facts = build_facts(
        pl_table=pl_table,
        championship_table=championship_table,
        pl_goals=pl_goals,
        top_scorers=top_scorers_from(pl_goals),
        manual=manual,
    )

    table = score_league(entries, facts)

    rows = []
    for rank, (entry, b) in enumerate(table, start=1):
        rows.append({
            "rank": rank,
            "name": entry.name,
            "total": b.total,
            "exactHits": b.exact_hits,
            "blackjack": {
                "players": entry.blackjack,
                "goals": [facts.pl_goals.get(p, 0) for p in entry.blackjack],
                "total": b.blackjack_total,
                "bust": b.blackjack_bust,
            },
            "categories": [
                {"key": k, "label": CATEGORY_LABELS.get(k, k), "points": v}
                for k, v in b.points.items()
            ],
            "picks": {
                "pl_top6": entry.pl_top6,
                "pl_bottom3": entry.pl_bottom3,
                "champ_top3": entry.champ_top3,
                "top_scorer": entry.top_scorer,
                "poty": entry.poty,
                "ypoty": entry.ypoty,
                "first_manager_out": entry.first_manager_out,
                "managers_out_count": entry.managers_out_count,
                **{c: getattr(entry, c) for c in CUP_FIELDS},
            },
        })

    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "actual": {
            "pl_top6": facts.pl_table[:6],
            "pl_bottom3": facts.pl_table[-3:] if len(facts.pl_table) >= 3 else [],
            "champ_promotion": championship_group(facts),
            "top_scorers": facts.top_scorers,
            "top_scorer_goals": max(facts.pl_goals.values()) if facts.pl_goals else 0,
            "decided": {
                CATEGORY_LABELS.get(k, k): getattr(facts, k)
                for k in ("poty", "ypoty", *CUP_FIELDS,
                          "first_manager_out", "managers_out_count")
            },
        },
        "standings": rows,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\nWrote {OUT.relative_to(ROOT)}")
    for r in rows[:5]:
        print(f"  {r['rank']:>2}. {r['name']:<24} {r['total']:>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
