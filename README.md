# Footy Predictions

Automated scoring and a live leaderboard for the annual predictions league.
Runs entirely on free tiers: no server, no database, no monthly bill.

```
Google Form  ->  predictions.csv  ->  build.py  ->  leaderboard.json  ->  GitHub Pages
                                          ^
                    football-data.org + FPL API + data/manual.yml
```

---

## The rules, as the code implements them

**Premier League top 6** — 5 points per team that finishes in the top 6
anywhere in your list, plus 3 more for each one in the exact position, plus a
10-point bonus if your top 4 are exactly right. The bonus **stacks** with the
exact-position points. A perfect top 6 is 58.

**Premier League bottom 3** — same, listed 18th / 19th / 20th. The 10-point
bonus needs all three exactly right. A perfect bottom 3 is 34.

**Championship promotion** — 1st, 2nd, and the play-off winner. The third slot
is the play-off winner, *not* third in the table, and it stays undecided until
late May. Scored the same way; a perfect group is 34.

**Top scorer** — 15 points. Joint Golden Boots pay full to everyone who picked
any joint winner.

**Player of the Year / Young Player of the Year** — 10 each. These are the PFA
Players' Player awards, not the Premier League's own.

**FA Cup, Carabao Cup, Champions League, Europa League, Conference League** —
10 each.

**First Premier League manager out** — 8 points. Sacked or departed, whichever
comes first.

**Number of managers out** — 8 points for guessing the exact total number of
PL managers sacked or who leave, counted from 21 August 2026. Exact match only,
no closest-wins. Because the count climbs all season, its value in `manual.yml`
stays blank until May and is filled in once with the final figure — otherwise
live scores would rise and fall as managers go.

**Blackjack** — three players from three different Premier League clubs.
Premier League goals only. Own goals don't count. A player sold in January
keeps the goals he scored before leaving; he just stops accruing. Exactly 21
is worth 15 — and nothing otherwise. There's no consolation for the closest:
20 scores the same as bust, which is nothing.

**Ties** — most predictions exactly right, then alphabetically.

A flawless entry is worth **242**.

---

## One-time setup

1. **Get a free football-data.org key** at
   `football-data.org/client/register`. Add it to the repo under
   Settings → Secrets and variables → Actions → New repository secret, named
   `FOOTBALL_DATA_TOKEN`.

2. **Turn on GitHub Pages**: Settings → Pages → Source: *Deploy from a
   branch*, branch `main`, folder `/docs`. Your leaderboard URL appears within
   a minute or two — that's the link you share.

3. **Install locally** so you can test before pushing:
   ```bash
   pip install -r requirements.txt
   python -m pytest test_scoring.py -q
   ```

## Each season

4. **Generate the dropdown options** about a week before the deadline, once
   the transfer window has settled:
   ```bash
   export FOOTBALL_DATA_TOKEN=your_key
   python make_form_options.py > form_options.txt
   ```
   This is the step that eliminates the "Van Dyke" / "Odegard" / "Mbueno"
   problem. Because the options come from the same API the scorer reads, a
   pick can't fail to match.

5. **Build the Google Form.** One question per slot — six separate questions
   for the top 6, not one free-text box. Paste the generated options into
   each. Question wording must contain the fragments listed in `COLUMN_RULES`
   at the top of `loaders.py` (e.g. "PL top 6 - 1st", "Blackjack - player 1");
   change either side to suit, as long as they agree.

6. **Close the form, export responses to CSV**, save as `data/predictions.csv`
   and run the validator:
   ```bash
   python build.py --check
   ```
   It reports duplicate picks, a team in both top 6 and bottom 3, Blackjack
   trios sharing a club, and unknown player names. Chase people, re-export,
   repeat until clean.

7. **Commit the frozen CSV.** This is your tamper-proof record — timestamped
   in git history, so nobody can claim they picked something else in May.

8. **During the season**, edit `data/manual.yml` when a cup is won, an award
   is announced, or the first manager goes. Committing it triggers a rebuild
   within a minute. Everything else updates itself each morning.

---

## Files

| File | What it does |
|---|---|
| `scoring.py` | All the rules. Pure functions, no I/O. Rule switches at the top. |
| `test_scoring.py` | 22 tests pinning each rule so a refactor can't quietly change scoring. |
| `sources.py` | Fetches league tables and goal counts. Caches to `cache/`. |
| `loaders.py` | Reads the predictions CSV and `manual.yml`. |
| `aliases.py` | Maps "Tottering" and "Man U." to canonical names. |
| `build.py` | Ties it together, writes `docs/data/leaderboard.json`. |
| `make_form_options.py` | Generates the form's dropdown lists. |
| `make_fixtures.py` | Fake season + fake entries, for testing offline. |
| `docs/index.html` | The public leaderboard. Reads the JSON, no build step. |

## Notes

- **Nothing breaks mid-season.** Undecided facts are `None` and score zero, so
  scores only ever rise. There's no separate in-progress code path.
- **A source outage degrades to stale, not blank.** Each fetcher falls back to
  its cached response and says so in the log.
- **Free-tier coverage.** football-data.org's free plan covers the Premier
  League and the Championship, but not the Europa League, Conference League,
  FA Cup or Carabao Cup — hence `manual.yml`. That's about nine values a
  season.
- **The FPL API is unofficial.** It's been public and stable for years, but
  it carries no uptime promise. If it ever disappears, `fetch_pl_players` is
  the only function that needs replacing.

## Testing offline

```bash
python make_fixtures.py                    # fake season into cache/ and data/
FOOTBALL_DATA_TOKEN=fake python build.py   # network fails, cache serves
python -m http.server -d docs 8000         # open localhost:8000
```
