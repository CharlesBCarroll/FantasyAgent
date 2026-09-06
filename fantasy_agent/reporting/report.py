"""Render structured recommendation data into a markdown report skeleton.

This is intentionally "just the facts" — number tables and flags, no prose.
The scheduled Claude agent (or an ad-hoc manual chat request) is expected to
read this alongside its own web research and write the final human-readable
recommendation; this module just guarantees a consistent, complete baseline.
"""


def _fmt(value) -> str:
    return f"{value:.1f}" if isinstance(value, (int, float)) else "—"


_SOURCE_LABELS = {"native": "native", "trend": "trend", "fantasypros": "FP", "weather_adjustment_factor": "weather"}


def _breakdown_str(breakdown: dict) -> str:
    if not breakdown:
        return "—"
    parts = []
    for key, value in breakdown.items():
        if key == "matchup_adjustment_factor":
            parts.append(f"matchup ×{value:.2f}")
        elif key == "weather_adjustment_factor":
            parts.append(f"weather ×{value:.2f}")
        else:
            label = _SOURCE_LABELS.get(key, key)
            parts.append(f"{label} {_fmt(value)}")
    return ", ".join(parts)


def _rest_of_season_str(matchups: list) -> str:
    if not matchups:
        return "—"
    return ", ".join(f"wk{m['week']} {m['opponent']} ({m['label']})" for m in matchups)


def render_team_report(lineup_rec: dict, waiver_rec: dict, graded_count: int) -> str:
    lines = [f"## {lineup_rec['team_name']} ({lineup_rec['platform'].upper()}) — Week {lineup_rec['week']}"]

    if graded_count:
        lines.append(f"\n_Graded {graded_count} player result(s) from prior week(s) this run._")

    if lineup_rec["status_alerts"]:
        lines.append("\n### ⚠️ Status Alerts (needs research)")
        for alert in lineup_rec["status_alerts"]:
            line = f"- **{alert['name']}** ({alert['lineup_slot']}) — {alert['status']}"
            replacement = alert.get("suggested_replacement")
            if replacement:
                buzz = f", 🔥 {replacement['trending_adds']:,} adds" if replacement.get("trending_adds") else ""
                line += (
                    f" — likely handcuff: **{replacement['name']}** ({replacement['nfl_team']}) "
                    f"{_fmt(replacement['projection'])} pts{buzz}"
                )
            lines.append(line)

    if lineup_rec.get("trending_down_alerts"):
        lines.append("\n### 📉 Trending Down (early warning, needs research)")
        for alert in lineup_rec["trending_down_alerts"]:
            lines.append(
                f"- **{alert['name']}** ({alert['lineup_slot']}) — "
                f"{alert['drop_count']:,} drops across Sleeper in last 24h"
            )

    if lineup_rec["start_sit_swaps"]:
        lines.append("\n### Suggested Start/Sit Swaps")
        for swap in lineup_rec["start_sit_swaps"]:
            lines.append(
                f"- Sit **{swap['sit']}** ({_fmt(swap['sit_projection'])} pts) for "
                f"**{swap['start']}** ({_fmt(swap['start_projection'])} pts) at {swap['slot']} "
                f"(+{_fmt(swap['margin'])})"
            )

    if lineup_rec["close_calls"]:
        lines.append("\n### Close Calls (needs research)")
        for call in lineup_rec["close_calls"]:
            lines.append(
                f"- {call['slot']}: **{call['current_starter']}** ({_fmt(call['current_starter_projection'])}) "
                f"vs bench **{call['bench_alternative']}** ({_fmt(call['bench_alternative_projection'])}), "
                f"margin {_fmt(call['margin'])}"
            )

    lines.append("\n### Full Roster Projections")
    lines.append("| Player | Pos | Slot | Status | Projection | Breakdown | Next 3 |")
    lines.append("|---|---|---|---|---|---|---|")
    for info in lineup_rec["projections"].values():
        lines.append(
            f"| {info['name']} | {info['position']} | {info['lineup_slot']} | "
            f"{info['status']} | {_fmt(info['blended_projection'])} | {_breakdown_str(info['breakdown'])} | "
            f"{_rest_of_season_str(info.get('rest_of_season', []))} |"
        )

    if waiver_rec:
        lines.append("\n### Waiver Wire Suggestions")
        for position, candidates in waiver_rec.items():
            if not candidates:
                continue
            lines.append(f"\n**{position}**")
            for c in candidates:
                flag = " (upgrade over your weakest rostered player)" if c["beats_weakest_rostered"] else ""
                trending = c.get("trending_adds")
                buzz = f", 🔥 {trending:,} adds in last 24h" if trending else ""
                lines.append(f"- {c['name']} ({c['nfl_team']}) — {_fmt(c['projection'])} pts{buzz}{flag}")

    return "\n".join(lines)


def render_accuracy_summary(summary: dict) -> str:
    """Makes the self-learning loop visible: how close recent projections were, and current weights."""
    if not summary or not summary.get("sample_size"):
        return (
            "## Learning Loop\n\n"
            "_Not enough graded history yet to report accuracy — this fills in "
            "as weeks get graded._"
        )

    lines = [
        "## Learning Loop",
        f"\n_Based on {summary['sample_size']} graded player result(s) over the last "
        f"{summary['weeks_back']} week(s)._",
        f"\n**Overall average error:** {_fmt(summary['overall_mae'])} pts",
    ]

    if summary["position_mae"]:
        lines.append("\n**By position:**")
        for position, mae in sorted(summary["position_mae"].items()):
            lines.append(f"- {position}: {_fmt(mae)} pts avg error")

    if summary["source_weights"]:
        lines.append("\n**Current source weights** (higher = more trusted, learned from accuracy):")
        for key, weight in sorted(summary["source_weights"].items()):
            lines.append(f"- {key}: {weight:.2f}")

    return "\n".join(lines)


def render_trade_report(label: str, proposals: list, graded_history: list) -> str:
    lines = [f"## Trade Analysis — {label}"]

    if graded_history:
        lines.append("\n### Past Suggestion Track Record")
        for row in graded_history[:5]:
            delta = row["get_actual_total"] - row["give_actual_total"]
            verdict = "would have helped" if delta > 0 else "would not have helped"
            lines.append(
                f"- Week {row['week_suggested']}: {row['give_player_name']} for {row['get_player_name']} "
                f"({row['other_team_name']}) — actual {_fmt(row['get_actual_total'])} vs "
                f"{_fmt(row['give_actual_total'])} pts since, {verdict}"
            )

    if not proposals:
        lines.append("\n_No clear mutually beneficial trade found this week._")
        return "\n".join(lines)

    lines.append("\n### Suggested Trades")
    for p in proposals:
        lines.append(
            f"- With **{p['team_name']}**: give {p['give_player']} ({p['give_position']}, "
            f"{_fmt(p['give_value'])} pts) for {p['get_player']} ({p['get_position']}, "
            f"{_fmt(p['get_value'])} pts) — value delta {_fmt(p['value_delta'])}"
        )

    return "\n".join(lines)


def render_full_report(season: int, week: int, team_sections: list[str]) -> str:
    header = f"# Fantasy Lineup Report — {season} Week {week}\n"
    return header + "\n\n".join(team_sections)
