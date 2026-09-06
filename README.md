# Fantasy Manager Agent

A self-improving NFL fantasy football assistant that pulls your Yahoo and
ESPN rosters, blends multiple projection signals, does live web research on
notable players, and gives you weekly start/sit and waiver recommendations —
both on a schedule and on demand.

## How it works

1. **Data/engine layer** (`fantasy_agent/`, pure Python) — fetches your
   roster, matchup, and available free agents from Yahoo and/or ESPN, blends
   projections from multiple sources, grades last week's predictions against
   real results, and updates its own source weights accordingly. Outputs
   structured JSON + a markdown report skeleton.
2. **Research/synthesis layer** — a Claude Code agent (scheduled weekly, or
   run on demand) that runs the pipeline above, then does a full web research
   sweep across that week's fantasy articles/injury reports/beat-writer notes
   for your rostered players and top waiver targets, and writes the final
   recommendation combining data + fresh news + its own track record.

## One-time setup

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Yahoo Fantasy API access

1. Go to https://developer.yahoo.com/apps/ and create an app.
   - Redirect URI: `https://localhost:8080` (or any placeholder — yfpy
     handles the OAuth redirect locally).
   - Permissions: Fantasy Sports (read).
2. Copy the generated **Client ID** and **Client Secret** into `.env` (copy
   `.env.example` to `.env` first) as `YAHOO_CLIENT_ID` / `YAHOO_CLIENT_SECRET`.
3. Find your league/team identifiers: open your Yahoo league, and from the
   URL grab your `league_id`. Your `team_key` has the form
   `<game_key>.l.<league_id>.t.<team_id>` — visible in the URL when viewing
   your team, or via Yahoo's league settings page.
4. `config/leagues.yaml`'s `yahoo:` key is a **list** — add one entry per
   Yahoo league you're in, each with its own `label`, `team_key`, and
   `enabled: true`.
5. Run the one-time OAuth handshake:
   ```bash
   python scripts/setup_yahoo_oauth.py
   ```
   This opens a browser window to authorize the app once, then stores a
   refresh token under `secrets/` so future runs never prompt again.

### 3. ESPN Fantasy API access

Public leagues need no auth. Private leagues need two cookies from a
logged-in browser session on fantasy.espn.com:

1. Log into your ESPN Fantasy league in a browser.
2. Open DevTools → Application (Chrome) or Storage (Firefox) → Cookies →
   `https://fantasy.espn.com`.
3. Copy the values of `espn_s2` and `SWID` (SWID includes the curly braces)
   into `.env` as `ESPN_S2` / `ESPN_SWID`.
4. Find your `league_id` (from the league URL `?leagueId=...`) and your
   `team_id` (your team's numeric id within that league — visible in the
   team URL or by matching your team name in `league.teams`).
5. `config/leagues.yaml`'s `espn:` key is a **list** — add one entry per
   ESPN league you're in, each with its own `label`, `league_id`, `team_id`,
   and `enabled: true`. The same `ESPN_S2`/`ESPN_SWID` cookies work across
   all leagues on your account.

### 4. Sanity check

```bash
python -m fantasy_agent.main run --platform all
```

This should print a JSON blob containing lineup recommendations, waiver
suggestions, and a markdown report for each enabled platform. The first run
creates `fantasy_agent.db` (SQLite) in the project root to log predictions
for future grading — this file, `secrets/`, and `.env` are all gitignored.

## Manual, on-demand runs

You don't have to wait for the weekly schedule — run the CLI directly for
one team:

```bash
python -m fantasy_agent.main run --platform yahoo
python -m fantasy_agent.main run --platform espn --week 5
```

Or just ask Claude in this project (e.g. "check my ESPN lineup this week")
— it runs the same pipeline scoped to that platform and layers on live web
research before giving you the final call.

## The learning loop

Every run logs each rostered player's blended projection (and which source
contributed what) to `fantasy_agent.db`. On the next run, any past week that
now has final results gets graded automatically — actual points are pulled
from nflverse data via `nfl_data_py`, compared to what each projection
source predicted, and `engine/learning.py` reweights sources per position by
their historical accuracy (lower error → higher weight). This needs a
handful of graded games per position before it starts adjusting weights
away from the equal-weight default.

## Project layout

See `fantasy_agent/` for the data/engine layer (platforms, projections,
engine, storage, grading, reporting) and `scripts/setup_yahoo_oauth.py` for
the one-time Yahoo auth flow. Tests live in `tests/` (`pytest`).
