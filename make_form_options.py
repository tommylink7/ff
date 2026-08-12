"""Generate the dropdown options for the Google Form.

Run this once, a week before the deadline, and paste the output into the
form's multiple-choice questions. Because the options come from the same API
the scorer reads, a pick can never fail to match -- which is what kills the
"Van Dyke" / "Odegard" / "Mbueno" problem for good.

    python make_form_options.py            # for the upcoming season (SEASON)
    python make_form_options.py 2027       # override the season if needed

SEASON is the starting year: 2026 means the 2026-27 season. Pre-kickoff the
league TABLES still show last season's clubs, so we pull the club lists from
the season-aware teams endpoint instead, which is populated as soon as the
new fixtures are published.
"""

from __future__ import annotations

import sys

from sources import fetch_pl_players, fetch_teams

# The season the next competition runs in, as its starting year.
SEASON = 2026


def section(title: str, items) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")
    for item in items:
        print(item)


def main() -> None:
    season = int(sys.argv[1]) if len(sys.argv) > 1 else SEASON

    pl = fetch_teams("PL", season)
    championship = fetch_teams("ELC", season)
    goals, club_of = fetch_pl_players()

    # Cross-check: FPL should be on the same season as the club list. If a
    # player's club isn't among this season's PL clubs, FPL hasn't rolled over
    # yet (it updates in late July) -- so the player list is stale even though
    # the club list is correct.
    pl_set = set(pl)
    fpl_clubs = set(club_of.values())
    if fpl_clubs and not (fpl_clubs & pl_set) >= (fpl_clubs - {"?"}):
        stale = sorted(fpl_clubs - pl_set - {"?"})
        if stale:
            print("# WARNING: the FPL player list still shows clubs that are "
                  "not in the\n# " + str(season) + "-" + str((season + 1) % 100).zfill(2)
                  + " Premier League: " + ", ".join(stale) + ".")
            print("# FPL usually updates in late July. Re-run once it has "
                  "rolled over, or the\n# Blackjack / top-scorer dropdowns will "
                  "list last season's squads.\n")

    section("PREMIER LEAGUE CLUBS -- top 6 and bottom 3 questions", sorted(pl))
    section("CHAMPIONSHIP CLUBS -- 1st, 2nd and play-off winner questions",
            sorted(championship))

    # Blackjack and top scorer: forwards and attacking mids mostly, but the
    # rules don't restrict position, so list everyone by club.
    by_club: dict[str, list[str]] = {}
    for player, club in club_of.items():
        by_club.setdefault(club, []).append(player)

    print(f"\n{'=' * 60}\nPL PLAYERS -- Blackjack and top scorer questions\n{'=' * 60}")
    for club in sorted(by_club):
        for player in sorted(by_club[club]):
            print(f"{player} - {club}")

    print(f"\n{'=' * 60}\nMANAGERS -- first manager out question\n{'=' * 60}")
    print("No free API lists current managers, so type these by hand:")
    for club in sorted(pl):
        print(f"  {club}: ")

    print(f"\n\n{len(pl)} PL clubs, {len(championship)} Championship clubs, "
          f"{len(goals)} players.")
    print("Reminder: also add an 'Other' free-text option to each question so "
          "a late signing doesn't block someone's entry.")


if __name__ == "__main__":
    main()