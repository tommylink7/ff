"""Generate the dropdown options for the Google Form.

Run this once, a week before the deadline, and paste the output into the
form's multiple-choice questions. Because the options come from the same API
the scorer reads, a pick can never fail to match -- which is what kills the
"Van Dyke" / "Odegard" / "Mbueno" problem for good.

    python make_form_options.py > form_options.txt
"""

from __future__ import annotations

from sources import fetch_pl_players, fetch_table


def section(title: str, items) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")
    for item in items:
        print(item)


def main() -> None:
    pl = fetch_table("PL")
    championship = fetch_table("ELC")
    goals, club_of = fetch_pl_players()

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
