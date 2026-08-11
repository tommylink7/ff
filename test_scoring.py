"""Rule tests. Each one pins a decision so a future refactor can't quietly
change how the league scores. Run: python -m pytest test_scoring.py -q
"""

import copy

from scoring import (
    Entry,
    championship_group,
    SeasonFacts,
    blackjack_total,
    score_entry,
    score_league,
    score_placement,
    validate_entry,
)

PL = [
    "Liverpool", "Arsenal", "Man City", "Chelsea", "Newcastle", "Aston Villa",
    "Man United", "Tottenham", "Brighton", "Bournemouth", "Crystal Palace",
    "Fulham", "Everton", "Brentford", "West Ham", "Nottingham Forest",
    "Wolves", "Leeds", "Sunderland", "Burnley",
]

CHAMP = ["Ipswich", "Southampton", "Leicester", "Coventry", "Birmingham"]


def base_facts() -> SeasonFacts:
    return SeasonFacts(
        pl_table=list(PL),
        championship_table=list(CHAMP),
        championship_playoff_winner="Coventry",
        pl_goals={"Haaland": 10, "Salah": 7, "Isak": 4, "Palmer": 3, "Watkins": 20},
        top_scorers=["Haaland"],
        poty="Palmer",
        ypoty="Wirtz",
        fa_cup="Arsenal",
        carabao_cup="Man City",
        champions_league="Real Madrid",
        europa_league="Roma",
        conference_league="Fiorentina",
        first_manager_out="Scott Parker",
    )


def entry(name="Tester", **overrides) -> Entry:
    defaults = dict(
        name=name,
        pl_top6=["Liverpool", "Arsenal", "Man City", "Chelsea", "Newcastle", "Aston Villa"],
        pl_bottom3=["Leeds", "Sunderland", "Burnley"],
        top_scorer="Haaland",
        poty="Palmer",
        ypoty="Wirtz",
        champ_top3=["Ipswich", "Southampton", "Coventry"],
        fa_cup="Arsenal",
        carabao_cup="Man City",
        champions_league="Real Madrid",
        europa_league="Roma",
        conference_league="Fiorentina",
        first_manager_out="Scott Parker",
        blackjack=["Haaland", "Salah", "Isak"],
    )
    defaults.update(overrides)
    return Entry(**defaults)


# --- placement rules -------------------------------------------------------

def test_perfect_top6_stacks_order_bonus_with_exact_points():
    pts, hits = score_placement(PL[:6], PL[:6], order_bonus_depth=4)
    # 6 teams x 5 = 30, 6 exact x 3 = 18, +10 order bonus = 58
    assert pts == 58
    assert hits == 6


def test_right_teams_wrong_order_gets_no_bonuses():
    scrambled = list(reversed(PL[:6]))
    pts, hits = score_placement(scrambled, PL[:6], order_bonus_depth=4)
    assert pts == 30  # 6 x 5, nothing exact
    assert hits == 0


def test_top4_exact_but_5_and_6_swapped_still_gets_order_bonus():
    pred = PL[:4] + [PL[5], PL[4]]
    pts, _ = score_placement(pred, PL[:6], order_bonus_depth=4)
    # 30 in-group + 4 exact x 3 = 12 + 10 bonus = 52
    assert pts == 52


def test_bottom3_is_listed_18th_19th_20th():
    facts = base_facts()
    right = score_entry(entry(pl_bottom3=["Leeds", "Sunderland", "Burnley"]), facts)
    flipped = score_entry(entry(pl_bottom3=["Burnley", "Sunderland", "Leeds"]), facts)
    assert right.points["pl_bottom3"] == 15 + 9 + 10   # 34
    assert flipped.points["pl_bottom3"] == 15 + 3      # middle one only


def test_undecided_facts_score_zero_not_crash():
    facts = SeasonFacts()  # nothing has happened yet
    b = score_entry(entry(), facts)
    assert b.total == 0


# --- blackjack -------------------------------------------------------------

def test_blackjack_exact_21():
    facts = base_facts()
    facts.pl_goals = {"A": 10, "B": 7, "C": 4}
    b = score_entry(entry(blackjack=["A", "B", "C"]), facts)
    assert b.blackjack_total == 21
    assert b.points["blackjack"] == 15


def test_blackjack_bust_scores_nothing_even_if_closest():
    facts = base_facts()
    facts.pl_goals = {"A": 20, "B": 5, "C": 1, "D": 3}
    bust = entry("Bust", blackjack=["A", "B", "C"])       # 26
    under = entry("Under", blackjack=["D", "C", "C"])      # 7
    table = score_league([bust, under], facts)
    by_name = {e.name: b for e, b in table}
    assert by_name["Bust"].blackjack_bust
    assert by_name["Bust"].points["blackjack"] == 0
    assert by_name["Under"].points["blackjack"] == 7


def test_blackjack_closest_ties_both_get_seven():
    facts = base_facts()
    facts.pl_goals = {"A": 10, "B": 9, "C": 1, "D": 10, "E": 9, "F": 1}
    a = entry("Anna", blackjack=["A", "B", "C"])   # 20
    b = entry("Bob", blackjack=["D", "E", "F"])    # 20
    table = score_league([a, b], facts)
    assert all(br.points["blackjack"] == 7 for _, br in table)


def test_no_consolation_when_someone_hits_21():
    facts = base_facts()
    facts.pl_goals = {"A": 21, "Z": 20}
    winner = entry("Winner", blackjack=["A", "nobody", "nobody2"])
    near = entry("Near", blackjack=["Z", "nobody", "nobody2"])
    table = score_league([winner, near], facts)
    by_name = {e.name: br for e, br in table}
    assert by_name["Winner"].points["blackjack"] == 15
    assert by_name["Near"].points["blackjack"] == 0


def test_player_leaving_the_league_keeps_his_goals():
    # Someone sold in January: pl_goals still holds what he scored in the PL.
    goals = {"Departed": 8, "Stayer": 6, "Other": 7}
    assert blackjack_total(["Departed", "Stayer", "Other"], goals) == 21


# --- tie-breaks ------------------------------------------------------------

WRONG = dict(
    pl_top6=["Fulham", "Everton", "Brentford", "West Ham", "Wolves", "Leeds"],
    pl_bottom3=["Liverpool", "Arsenal", "Man City"],
    champ_top3=["Stoke", "Millwall", "QPR"],
    top_scorer="Nobody",
    poty="Nobody",
    ypoty="Nobody",
    fa_cup="Nobody",
    carabao_cup="Nobody",
    champions_league="Nobody",
    europa_league="Nobody",
    conference_league="Nobody",
    first_manager_out="Nobody",
    blackjack=["x", "y", "z"],
)


def test_tiebreak_exact_hits_beats_alphabetical():
    facts = base_facts()
    # Both bust on Blackjack, so it contributes nothing either way and the
    # comparison is purely about the tie-break rules.
    facts.pl_goals = {"x": 30}

    # Both land on exactly 30 points by different routes.
    # Adam: six right teams, none in the right slot -> 30 pts, 0 exact hits.
    adam = entry("Adam", **{**WRONG, "pl_top6": list(reversed(PL[:6]))})
    # Zeb: three one-shot categories dead right -> 30 pts, 3 exact hits.
    zeb = entry("Zeb", **{**WRONG, "fa_cup": "Arsenal",
                          "carabao_cup": "Man City", "poty": "Palmer"})

    table = score_league([adam, zeb], facts)
    assert table[0][1].total == table[1][1].total == 30, "totals must be equal"
    assert table[0][1].exact_hits == 3 and table[1][1].exact_hits == 0
    # Zeb wins on exact hits despite losing alphabetically.
    assert [e.name for e, _ in table] == ["Zeb", "Adam"]


def test_dead_heat_falls_back_to_alphabetical():
    facts = base_facts()
    facts.pl_goals = {}
    z = entry("Zoe")
    a = entry("Adam")
    table = score_league([z, a], facts)
    assert table[0][1].total == table[1][1].total
    assert table[0][1].exact_hits == table[1][1].exact_hits
    assert [e.name for e, _ in table] == ["Adam", "Zoe"]


# --- validation ------------------------------------------------------------

def test_validator_catches_the_three_classic_mistakes():
    clubs = {"Haaland": "Man City", "Foden": "Man City", "Salah": "Liverpool"}
    bad = entry(
        pl_top6=["Arsenal", "Arsenal", "Man City", "Chelsea", "Newcastle", "Leeds"],
        pl_bottom3=["Leeds", "Sunderland", "Burnley"],
        blackjack=["Haaland", "Foden", "Salah"],
    )
    problems = validate_entry(bad, clubs)
    joined = " | ".join(problems)
    assert "duplicate" in joined
    assert "both top 6 and bottom 3" in joined
    assert "three different clubs" in joined


def test_valid_entry_passes_clean():
    clubs = {"Haaland": "Man City", "Salah": "Liverpool", "Isak": "Newcastle"}
    assert validate_entry(entry(), clubs) == []


# --- full worked example ---------------------------------------------------

def test_perfect_entry_total():
    facts = base_facts()
    facts.pl_goals = {"Haaland": 10, "Salah": 7, "Isak": 4}
    b = score_entry(entry(), facts)
    expected = (
        58   # top 6 perfect
        + 34  # bottom 3 perfect
        + 34  # championship top 3 perfect
        + 15  # top scorer
        + 10 + 10          # poty, ypoty
        + 10 * 5           # five cups
        + 8                # manager
        + 15               # blackjack 21
    )
    assert b.total == expected
    print(f"\nPerfect entry scores {b.total}")


# --- championship promotion group ------------------------------------------

def test_championship_third_slot_is_the_playoff_winner_not_third_place():
    facts = base_facts()
    # Leicester finished 3rd in the table but did NOT win the play-off.
    assert facts.championship_table[2] == "Leicester"
    picked_third_place = score_entry(entry(
        champ_top3=["Ipswich", "Southampton", "Leicester"]), facts)
    picked_playoff = score_entry(entry(
        champ_top3=["Ipswich", "Southampton", "Coventry"]), facts)
    assert picked_third_place.points["champ_top3"] == 10 + 6   # 2 right, 2 exact
    assert picked_playoff.points["champ_top3"] == 15 + 9 + 10  # perfect


def test_playoff_winner_in_wrong_slot_scores_in_group_only():
    facts = base_facts()
    b = score_entry(entry(champ_top3=["Coventry", "Ipswich", "Southampton"]), facts)
    # all three right, none in the right slot
    assert b.points["champ_top3"] == 15


def test_championship_undecided_playoff_blocks_order_bonus():
    facts = base_facts()
    facts.championship_playoff_winner = None  # it is March
    assert championship_group(facts) == ["Ipswich", "Southampton", None]
    b = score_entry(entry(champ_top3=["Ipswich", "Southampton", "Coventry"]), facts)
    # 2 in group + 2 exact, no bonus yet
    assert b.points["champ_top3"] == 10 + 6

    facts.championship_playoff_winner = "Coventry"  # it is now late May
    after = score_entry(entry(champ_top3=["Ipswich", "Southampton", "Coventry"]), facts)
    assert after.points["champ_top3"] > b.points["champ_top3"], "score must only rise"
