#!/usr/bin/env python3
"""One-time interactive Yahoo OAuth setup.

Run this after filling in YAHOO_CLIENT_ID / YAHOO_CLIENT_SECRET in .env and
league_id/team_key in config/leagues.yaml. yfpy will open a browser window
for you to authorize the app, then store the resulting token in secrets/
so future runs never need to re-authenticate (yfpy refreshes automatically).
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

    if not config["yahoo"]["team_key"]:
        print("Set yahoo.team_key in config/leagues.yaml before running this script.")
        sys.exit(1)

    print("Starting Yahoo OAuth flow (a browser window should open)...")
    query = get_query(config)
    # Any query forces yfpy through the OAuth handshake on first run.
    league_id, _team_id = query.league_id, None
    info = query.get_league_info()
    print(f"Authorized successfully for league: {info.name} ({league_id})")
    print(f"Token data saved under: {query.env_file_location}")


if __name__ == "__main__":
    main()
