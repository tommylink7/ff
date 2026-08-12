"""Reading predictions and hand-entered facts.

The Google Form writes a wide CSV: one row per person, one column per
question. COLUMN_MAP is the only thing you touch if you reword a question --
match on a distinctive fragment of the question text, lowercased.
"""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from aliases import canon
from scoring import Entry, SeasonFacts

# Fragment of the form question -> (entry field, index within that field).
# Ordered groups get one column per slot. THIS LIST IS ORDER-SENSITIVE: the
# first fragment that matches wins, so more specific rules must come first.
# "PL Young Player of the Year" contains "player of the year", which is why
# the young-player rule sits above it.
COLUMN_RULES: list[tuple[str, tuple[str, int]]] = [
    ("top 6 - 1st", ("pl_top6", 0)),
    ("top 6 - 2nd", ("pl_top6", 1)),
    ("top 6 - 3rd", ("pl_top6", 2)),
    ("top 6 - 4th", ("pl_top6", 3)),
    ("top 6 - 5th", ("pl_top6", 4)),
    ("top 6 - 6th", ("pl_top6", 5)),
    ("bottom 3 - 18th", ("pl_bottom3", 0)),
    ("bottom 3 - 19th", ("pl_bottom3", 1)),
    ("bottom 3 - 20th", ("pl_bottom3", 2)),
    ("championship - 1st", ("champ_top3", 0)),
    ("championship - 2nd", ("champ_top3", 1)),
    ("championship - play-off winner", ("champ_top3", 2)),
    ("blackjack - player 1", ("blackjack", 0)),
    ("blackjack - player 2", ("blackjack", 1)),
    ("blackjack - player 3", ("blackjack", 2)),
    ("top scorer", ("top_scorer", -1)),
    ("young player", ("ypoty", -1)),          # must precede poty
    ("player of the year", ("poty", -1)),
    ("fa cup", ("fa_cup", -1)),
    ("carabao", ("carabao_cup", -1)),
    ("champions league", ("champions_league", -1)),
    ("europa", ("europa_league", -1)),
    ("conference", ("conference_league", -1)),
    # "number of ... managers" must precede the "manager" rule below, because
    # "manager" is a substring of "managers" and first match wins.
    ("number of", ("managers_out_count", -1)),
    ("manager", ("first_manager_out", -1)),
]

# Fields whose value is a whole number, not a name.
NUMERIC_FIELDS = {"managers_out_count"}

SINGLE_FIELDS = [f for _, (f, i) in COLUMN_RULES if i == -1]

NAME_HINTS = ("your name", "name", "nickname")

GROUP_SIZES = {"pl_top6": 6, "pl_bottom3": 3, "champ_top3": 3, "blackjack": 3}


def _match_column(header: str) -> tuple[str, int] | None:
    """First matching rule wins -- see the note on COLUMN_RULES ordering."""
    h = header.strip().lower()
    for fragment, target in COLUMN_RULES:
        if fragment in h:
            return target
    return None


def _parse_int(value) -> int | None:
    """First run of digits in a string, or None. '8' -> 8, 'around 9' -> 9."""
    import re
    if value is None:
        return None
    m = re.search(r"\d+", str(value))
    return int(m.group()) if m else None


def load_predictions(path: str | Path) -> list[Entry]:
    """Read the frozen predictions CSV into Entry objects.

    Player names are NOT alias-mapped -- they come from a dropdown built from
    the same API we score against, so they already match. Team names ARE
    mapped, because the APIs spell them verbosely.
    """
    entries: list[Entry] = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []

        name_col = next(
            (h for hint in NAME_HINTS for h in headers if hint in h.strip().lower()),
            None,
        )
        if name_col is None:
            raise RuntimeError(f"No name column found. Headers: {headers}")

        for row in reader:
            fields: dict = {g: [""] * n for g, n in GROUP_SIZES.items()}
            fields.update({f: "" for f in SINGLE_FIELDS})
            matched: set[str] = set()
            for header, value in row.items():
                if header is None or header == name_col:
                    continue
                target = _match_column(header)
                if target is None:
                    continue
                field_name, idx = target
                value = (value or "").strip()
                matched.add(field_name)
                if idx == -1:
                    fields[field_name] = value
                else:
                    fields[field_name][idx] = value

            missing = (set(GROUP_SIZES) | set(SINGLE_FIELDS)) - matched
            if missing:
                raise RuntimeError(
                    "No CSV column matched these fields: "
                    + ", ".join(sorted(missing))
                    + ".\nEdit COLUMN_RULES in loaders.py to match your form's "
                    "question wording.\nHeaders found: " + ", ".join(headers)
                )

            # Teams get normalised; players are already canonical.
            for group in ("pl_top6", "pl_bottom3", "champ_top3"):
                fields[group] = [canon(v) for v in fields[group]]
            for single in (
                "fa_cup", "carabao_cup", "champions_league",
                "europa_league", "conference_league",
            ):
                fields[single] = canon(fields.get(single, ""))

            # The manager count is a number, not a name. Pull the first digits
            # out ("about 8" -> 8); leave None if they wrote nothing usable, so
            # a blank guess simply never scores rather than crashing the build.
            fields["managers_out_count"] = _parse_int(fields.get("managers_out_count"))

            entries.append(Entry(name=(row[name_col] or "").strip(), **fields))

    return entries


def load_manual_facts(path: str | Path) -> dict:
    """Read data/manual.yml. Blank values mean 'not decided yet'."""
    text = Path(path).read_text(encoding="utf-8")
    raw = yaml.safe_load(text) or {}
    return {k: (v if v not in ("", None) else None) for k, v in raw.items()}


def build_facts(
    pl_table: list[str],
    championship_table: list[str],
    pl_goals: dict[str, int],
    top_scorers: list[str],
    manual: dict,
) -> SeasonFacts:
    """Merge the automatic and manual halves into one SeasonFacts.

    A manual top_scorers entry overrides the derived one -- useful if the
    official Golden Boot disagrees with FPL's count, which happens when a
    goal is reassigned by the dubious goals panel.
    """
    override = manual.get("top_scorers")
    if isinstance(override, str):
        override = [override]

    return SeasonFacts(
        pl_table=pl_table,
        championship_table=championship_table,
        championship_playoff_winner=canon(manual.get("championship_playoff_winner")),
        pl_goals=pl_goals,
        top_scorers=override or top_scorers,
        poty=manual.get("poty"),
        ypoty=manual.get("ypoty"),
        fa_cup=canon(manual.get("fa_cup")),
        carabao_cup=canon(manual.get("carabao_cup")),
        champions_league=canon(manual.get("champions_league")),
        europa_league=canon(manual.get("europa_league")),
        conference_league=canon(manual.get("conference_league")),
        first_manager_out=manual.get("first_manager_out"),
        managers_out_count=_parse_int(manual.get("managers_out_count")),
    )
