"""
Footy Predictions League — scoring engine.

Pure functions: predictions + season facts -> points. No I/O, no network.
That is deliberate — it means you can unit-test every rule offline and
re-run a whole season's scoring in milliseconds.

RULE SWITCHES — the four edges we hadn't pinned down. Change these here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Rule switches
# ---------------------------------------------------------------------------

# Championship promotion group: the top 2 (automatic) plus the play-off
# winner. The third slot is therefore NOT third in the table -- it stays
# undecided until the play-off final in late May.
CHAMPIONSHIP_GROUP = "top2_plus_playoff_winner"

# Joint Golden Boot: everyone who picked any joint winner gets the full 15.
# Set False to divide 15 between the joint winners' backers.
JOINT_TOP_SCORER_PAYS_FULL = True

# Blackjack: if nobody hits 21, everyone tied at the closest total below 21
# gets the full 7. Set False to split 7 between them.
BLACKJACK_CLOSEST_PAYS_FULL = True

# ---------------------------------------------------------------------------
# Points
# ---------------------------------------------------------------------------

PTS_TEAM_IN_GROUP = 5      # right team, anywhere in the group
PTS_EXACT_POSITION = 3     # ...and in the right slot
PTS_ORDER_BONUS = 10       # whole ordered run correct — STACKS with the above
PTS_TOP_SCORER = 15
PTS_AWARD = 10             # POTY, YPOTY
PTS_CUP = 10               # FA, Carabao, CL, EL, ECL
PTS_MANAGER = 8
PTS_BLACKJACK_EXACT = 15
PTS_BLACKJACK_CLOSEST = 7

BLACKJACK_TARGET = 21

CUP_FIELDS = (
    "fa_cup",
    "carabao_cup",
    "champions_league",
    "europa_league",
    "conference_league",
)


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class SeasonFacts:
    """What actually happened. Mid-season, this is the state as of today.

    Anything not yet decided stays None and simply scores zero, which is what
    makes the same function work for both live and final scoring.
    """

    # Full ordered league tables, position 1 first.
    pl_table: list[str] = field(default_factory=list)
    championship_table: list[str] = field(default_factory=list)

    # Decided by the play-off final in late May; None until then.
    championship_playoff_winner: str | None = None

    # Premier League goals per player, own goals excluded.
    pl_goals: dict[str, int] = field(default_factory=dict)

    # Joint winners are allowed, hence a list.
    top_scorers: list[str] = field(default_factory=list)

    poty: str | None = None
    ypoty: str | None = None
    fa_cup: str | None = None
    carabao_cup: str | None = None
    champions_league: str | None = None
    europa_league: str | None = None
    conference_league: str | None = None
    first_manager_out: str | None = None


@dataclass
class Entry:
    """One person's predictions, already normalised to canonical names."""

    name: str
    pl_top6: list[str]          # 6 teams, 1st -> 6th
    pl_bottom3: list[str]       # 3 teams, 18th -> 20th
    top_scorer: str
    poty: str
    ypoty: str
    champ_top3: list[str]       # 3 teams, 1st -> 3rd
    fa_cup: str
    carabao_cup: str
    champions_league: str
    europa_league: str
    conference_league: str
    first_manager_out: str
    blackjack: list[str]        # 3 players from 3 different clubs


@dataclass
class Breakdown:
    """Per-category points, so the site can show where a score came from."""

    points: dict[str, int] = field(default_factory=dict)
    exact_hits: int = 0
    blackjack_total: int = 0
    blackjack_bust: bool = False

    @property
    def total(self) -> int:
        return sum(self.points.values())


# ---------------------------------------------------------------------------
# Placement scoring
# ---------------------------------------------------------------------------

def score_placement(
    predicted: list[str],
    actual: list[str | None],
    order_bonus_depth: int,
) -> tuple[int, int]:
    """Score an ordered group prediction against the actual ordered group.

    Returns (points, exact_hits).

    - PTS_TEAM_IN_GROUP for each predicted team present anywhere in `actual`
    - PTS_EXACT_POSITION extra for each one in its exact slot
    - PTS_ORDER_BONUS if the first `order_bonus_depth` slots are all exact

    The order bonus STACKS with the exact-position points.

    A slot may be None, meaning "not decided yet" (e.g. the Championship
    play-off winner in March). None never matches anything and blocks the
    order bonus, so points can only ever go up as the season resolves.
    """
    if not actual:
        return 0, 0

    actual_set = {t for t in actual if t is not None}
    points = 0
    exact = 0

    for i, team in enumerate(predicted):
        if team in actual_set:
            points += PTS_TEAM_IN_GROUP
        if i < len(actual) and actual[i] is not None and team == actual[i]:
            points += PTS_EXACT_POSITION
            exact += 1

    depth = order_bonus_depth
    if (
        len(predicted) >= depth
        and len(actual) >= depth
        and all(slot is not None for slot in actual[:depth])
        and predicted[:depth] == actual[:depth]
    ):
        points += PTS_ORDER_BONUS

    return points, exact


def championship_group(facts: SeasonFacts) -> list[str | None]:
    """The three promoted sides: 1st, 2nd, and the play-off winner.

    Mid-season the play-off slot is None. Note it is scored positionally --
    picking the eventual play-off winner in slot 1 earns the in-group 5 but
    not the exact-position 3.
    """
    top2: list[str | None] = list(facts.championship_table[:2])
    while len(top2) < 2:
        top2.append(None)
    return top2 + [facts.championship_playoff_winner]


def score_top_scorer(pick: str, facts: SeasonFacts) -> tuple[int, int]:
    if not facts.top_scorers or pick not in facts.top_scorers:
        return 0, 0
    if JOINT_TOP_SCORER_PAYS_FULL or len(facts.top_scorers) == 1:
        return PTS_TOP_SCORER, 1
    return PTS_TOP_SCORER // len(facts.top_scorers), 1


def blackjack_total(trio: list[str], pl_goals: dict[str, int]) -> int:
    """Sum of Premier League goals for the three picks.

    A player who left the league mid-season keeps the goals he scored in it;
    he simply stops accruing. That falls out of pl_goals naturally.
    """
    return sum(pl_goals.get(player, 0) for player in trio)


# ---------------------------------------------------------------------------
# Whole-entry scoring
# ---------------------------------------------------------------------------

def score_entry(entry: Entry, facts: SeasonFacts) -> Breakdown:
    """Score one entry. Blackjack's closest-wins points are NOT included here,
    because they depend on the whole field — score_league() adds them.
    """
    b = Breakdown()

    pts, hits = score_placement(entry.pl_top6, facts.pl_table[:6], order_bonus_depth=4)
    b.points["pl_top6"] = pts
    b.exact_hits += hits

    # Bottom 3, listed 18th -> 20th. The order bonus covers all three.
    bottom3 = facts.pl_table[-3:] if len(facts.pl_table) >= 3 else []
    pts, hits = score_placement(entry.pl_bottom3, bottom3, order_bonus_depth=3)
    b.points["pl_bottom3"] = pts
    b.exact_hits += hits

    champ = championship_group(facts)
    pts, hits = score_placement(entry.champ_top3, champ, order_bonus_depth=3)
    b.points["champ_top3"] = pts
    b.exact_hits += hits

    pts, hits = score_top_scorer(entry.top_scorer, facts)
    b.points["top_scorer"] = pts
    b.exact_hits += hits

    for field_name, award in (("poty", facts.poty), ("ypoty", facts.ypoty)):
        hit = award is not None and getattr(entry, field_name) == award
        b.points[field_name] = PTS_AWARD if hit else 0
        b.exact_hits += int(hit)

    for cup in CUP_FIELDS:
        winner = getattr(facts, cup)
        hit = winner is not None and getattr(entry, cup) == winner
        b.points[cup] = PTS_CUP if hit else 0
        b.exact_hits += int(hit)

    hit = (
        facts.first_manager_out is not None
        and entry.first_manager_out == facts.first_manager_out
    )
    b.points["first_manager_out"] = PTS_MANAGER if hit else 0
    b.exact_hits += int(hit)

    b.blackjack_total = blackjack_total(entry.blackjack, facts.pl_goals)
    b.blackjack_bust = b.blackjack_total > BLACKJACK_TARGET

    if b.blackjack_total == BLACKJACK_TARGET:
        b.points["blackjack"] = PTS_BLACKJACK_EXACT
        b.exact_hits += 1
    else:
        b.points["blackjack"] = 0

    return b


def score_league(
    entries: list[Entry],
    facts: SeasonFacts,
) -> list[tuple[Entry, Breakdown]]:
    """Score everyone, award the Blackjack consolation, and sort.

    Sort order: points desc, then most predictions exactly right, then name
    alphabetically.
    """
    scored = [(e, score_entry(e, facts)) for e in entries]

    # Blackjack consolation only applies if nobody hit 21 exactly.
    nobody_hit_21 = all(b.blackjack_total != BLACKJACK_TARGET for _, b in scored)
    if nobody_hit_21:
        live = [b.blackjack_total for _, b in scored if not b.blackjack_bust]
        if live:
            best = max(live)
            winners = [
                b for _, b in scored
                if not b.blackjack_bust and b.blackjack_total == best
            ]
            award = (
                PTS_BLACKJACK_CLOSEST
                if BLACKJACK_CLOSEST_PAYS_FULL
                else PTS_BLACKJACK_CLOSEST // len(winners)
            )
            for b in winners:
                b.points["blackjack"] = award

    scored.sort(key=lambda pair: (-pair[1].total, -pair[1].exact_hits, pair[0].name.lower()))
    return scored


# ---------------------------------------------------------------------------
# Entry validation — run this before the deadline, not after
# ---------------------------------------------------------------------------

def validate_entry(entry: Entry, player_clubs: dict[str, str]) -> list[str]:
    """Return a list of human-readable problems. Empty list means valid."""
    problems: list[str] = []

    def no_dupes(picks: list[str], label: str, expected: int) -> None:
        if len(picks) != expected:
            problems.append(f"{label}: expected {expected} picks, got {len(picks)}")
        if len(set(picks)) != len(picks):
            problems.append(f"{label}: contains a duplicate")

    no_dupes(entry.pl_top6, "PL top 6", 6)
    no_dupes(entry.pl_bottom3, "PL bottom 3", 3)
    no_dupes(entry.champ_top3, "Championship top 3", 3)
    no_dupes(entry.blackjack, "Blackjack", 3)

    overlap = set(entry.pl_top6) & set(entry.pl_bottom3)
    if overlap:
        problems.append(f"team in both top 6 and bottom 3: {', '.join(sorted(overlap))}")

    clubs = [player_clubs.get(p) for p in entry.blackjack]
    if any(c is None for c in clubs):
        unknown = [p for p, c in zip(entry.blackjack, clubs) if c is None]
        problems.append(f"Blackjack: not a current PL player: {', '.join(unknown)}")
    elif len(set(clubs)) != 3:
        problems.append("Blackjack: the three players must be from three different clubs")

    return problems
