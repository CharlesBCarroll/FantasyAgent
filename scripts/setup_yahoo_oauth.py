#!/usr/bin/env python3
"""One-time interactive Yahoo OAuth setup.

Run this after filling in YAHOO_CLIENT_ID / YAHOO_CLIENT_SECRET in .env and
at least one enabled entry under yahoo: in config/leagues.yaml. yfpy will
open a browser window for you to authorize the app, then store the
resulting token in secrets/ so future runs never need to re-authenticate.

The OAuth token is tied to your Yahoo account, not a specific league, so
this only needs to run once even if you're in multiple Yahoo leagues.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
import yaml

from fantasy_agent.platforms.yahoo_client import get_query

load_dotenv()


def main() -> None:
    config_path = Path(__file__).resolve().parents[1] / "config" / "leagues.yaml"
    config = yaml.safe_load(config_path.read_text())

    enabled = next((cfg for cfg in config.get("yahoo", []) if cfg.get("enabled") and cfg.get("team_key")), None)
    if enabled is None:
        print("Set team_key and enabled: true on at least one entry under yahoo: in config/leagues.yaml.")
        sys.exit(1)

    print("Starting Yahoo OAuth flow (a browser window should open)...")
    query = get_query(int(config["season"]), enabled)
    # Any query forces yfpy through the OAuth handshake on first run.
    info = query.get_league_info()
    print(f"Authorized successfully for league: {info.name} ({query.league_id})")
    print(f"Token data saved under: {query.env_file_location}")


if __name__ == "__main__":
    main()
