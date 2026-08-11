"""Canonical names.

Two different worlds produce names here: the APIs ("Manchester City FC",
"Tottenham Hotspur FC") and your mates ("Man City", "Tottering"). Everything
gets funnelled through canon() before it reaches the scorer.

The long-term fix for player names is to build the form's dropdown from the
same API you score against -- see make_form_options.py. This map exists for
historical entries and for team names, which the APIs spell verbosely.
"""

from __future__ import annotations

import re
import unicodedata

# Left: anything anyone has ever written. Right: the canonical name.
TEAM_ALIASES: dict[str, str] = {
    # API spellings
    "arsenal fc": "Arsenal",
    "aston villa fc": "Aston Villa",
    "afc bournemouth": "Bournemouth",
    "brentford fc": "Brentford",
    "brighton & hove albion fc": "Brighton",
    "burnley fc": "Burnley",
    "chelsea fc": "Chelsea",
    "crystal palace fc": "Crystal Palace",
    "everton fc": "Everton",
    "fulham fc": "Fulham",
    "leeds united fc": "Leeds",
    "liverpool fc": "Liverpool",
    "manchester city fc": "Man City",
    "manchester united fc": "Man United",
    "newcastle united fc": "Newcastle",
    "nottingham forest fc": "Nottingham Forest",
    "sunderland afc": "Sunderland",
    "tottenham hotspur fc": "Tottenham",
    "west ham united fc": "West Ham",
    "wolverhampton wanderers fc": "Wolves",
    # human spellings, including last season's typos and the running jokes
    "spurs": "Tottenham",
    "tottering": "Tottenham",
    "man c.": "Man City",
    "man cty": "Man City",
    "man u.": "Man United",
    "man u,": "Man United",
    "man utd": "Man United",
    "united": "Man United",
    "villa": "Aston Villa",
    "asrton villa": "Aston Villa",
    "liverpol": "Liverpool",
    "forest": "Nottingham Forest",
    "palace": "Crystal Palace",
    # Championship
    "sheff. u.": "Sheffield United",
    "sheff u.": "Sheffield United",
    "sheff u,": "Sheffield United",
    "sheff. utd.": "Sheffield United",
    "sheffield w.": "Sheffield Wednesday",
    "middlesboro": "Middlesbrough",
    "middlesborough": "Middlesbrough",
    "wba": "West Brom",
    "west bromwich albion fc": "West Brom",
    # Europe
    "as roma": "Roma",
    "bayern mun.": "Bayern Munich",
    "fc bayern munchen": "Bayern Munich",
    "real madrid cf": "Real Madrid",
    "fc barcelona": "Barcelona",
    "paris saint-germain fc": "PSG",
    "acf fiorentina": "Fiorentina",
    "real betis balompie": "Real Betis",
}


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def _key(name: str) -> str:
    """Loose lookup key: lowercase, no accents, collapsed whitespace."""
    name = _strip_accents(name).lower().strip()
    return re.sub(r"\s+", " ", name)


def canon(name: str | None, aliases: dict[str, str] | None = None) -> str | None:
    """Map any spelling to the canonical one. Unknown names pass through
    with whitespace tidied, so a new club doesn't silently become None.
    """
    if name is None:
        return None
    table = aliases if aliases is not None else TEAM_ALIASES
    k = _key(name)
    if k in table:
        return table[k]
    # Trailing "FC" is noise on almost every API name.
    stripped = re.sub(r"\s+fc$", "", k)
    if stripped in table:
        return table[stripped]
    return re.sub(r"\s+", " ", name.strip())


def canon_list(names, aliases: dict[str, str] | None = None) -> list:
    return [canon(n, aliases) for n in names]


def unknown_names(names, known: set[str]) -> list[str]:
    """Names that survived canon() but aren't in the known set -- i.e. either
    a typo or a genuinely new entity. Report these; never guess.
    """
    return sorted({n for n in names if n and n not in known})
