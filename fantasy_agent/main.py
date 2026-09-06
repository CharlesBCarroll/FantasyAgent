"""CLI orchestrator: grade -> fetch -> blend -> recommend -> log -> emit JSON.

Usage:
    python -m fantasy_agent.main run [--platform yahoo|espn|all] [--week N]

Runs every enabled league entry for the selected platform(s) — you can be in
multiple leagues on the same platform. Prints a single JSON object to stdout
containing, per league, the lineup recommendations, waiver suggestions, and a
rendered markdown report skeleton. This is consumed either directly by a
human, or by the scheduled Claude agent which layers live web research on
top before writing the final report and sending a notification.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from fantasy_agent.engine.recommend import generate_lineup_recommendations, generate_waiver_recommendations
from fantasy_agent.grading.grade import grade_pending_weeks
from fantasy_agent.platforms import espn_client, yahoo_client
from fantasy_agent.reporting.report import render_full_report, render_team_report
from fantasy_agent.storage import db
from fantasy_agent.utils import current_week

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "leagues.yaml"

CLIENTS = {
    "yahoo": yahoo_client,
    "espn": espn_client,
}


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def run_league(conn, client_module, platform: str, league_cfg: dict, season: int, week: int) -> dict:
    graded_count = grade_pending_weeks(conn, platform, season, week)
    weights = db.get_source_weights(conn)

    roster = client_module.get_roster(season, league_cfg, week)
    free_agents = client_module.get_free_agents(season, league_cfg)

    lineup_rec = generate_lineup_recommendations(roster, season, week, weights)
    waiver_rec = generate_waiver_recommendations(roster, free_agents, season, week, weights)

    for player in roster.players:
        info = lineup_rec["projections"][player.player_id]
        db.record_prediction(
            conn,
            platform=platform,
            team_name=roster.team_name,
            season=season,
            week=week,
            player_id=player.player_id,
            player_name=player.name,
            position=player.position,
            decision="start" if player.is_starter else "sit",
            blended_projection=info["blended_projection"],
            source_breakdown=json.dumps(info["breakdown"]),
        )

    markdown = render_team_report(lineup_rec, waiver_rec, graded_count)

    return {
        "platform": platform,
        "label": league_cfg.get("label", roster.team_name),
        "graded_count": graded_count,
        "lineup_recommendations": lineup_rec,
        "waiver_recommendations": waiver_rec,
        "markdown": markdown,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fantasy manager agent data pipeline")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--platform", choices=["yahoo", "espn", "all"], default="all")
    parser.add_argument("--week", type=int, default=None)
    args = parser.parse_args()

    load_dotenv()
    config = load_config()
    season = int(config["season"])
    week = args.week or current_week(season)

    platforms = ["yahoo", "espn"] if args.platform == "all" else [args.platform]
    enabled_leagues = [
        (platform, league_cfg)
        for platform in platforms
        for league_cfg in config.get(platform, [])
        if league_cfg.get("enabled")
    ]

    if not enabled_leagues:
        print(
            "No enabled leagues found. Set enabled: true on at least one entry "
            "under yahoo/espn in config/leagues.yaml.",
            file=sys.stderr,
        )
        sys.exit(1)

    conn = db.get_connection()
    db.init_db(conn)

    results = []
    for platform, league_cfg in enabled_leagues:
        result = run_league(conn, CLIENTS[platform], platform, league_cfg, season, week)
        results.append(result)

    conn.close()

    full_report = render_full_report(season, week, [r["markdown"] for r in results])

    output = {
        "season": season,
        "week": week,
        "results": results,
        "full_report_markdown": full_report,
    }
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
