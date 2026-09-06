"""Render structured recommendation data into a markdown report skeleton.

This is intentionally "just the facts" — number tables and flags, no prose.
The scheduled Claude agent (or an ad-hoc manual chat request) is expected to
read this alongside its own web research and write the final human-readable
recommendation; this module just guarantees a consistent, complete baseline.
"""


def _fmt(value) -> str:
    return f"{value:.1f}" if isinstance(value, (int, float)) else "—"


def render_team_report(lineup_rec: dict, waiver_rec: dict, graded_count: int) -> str:
    lines = [f"## {lineup_rec['team_name']} ({lineup_rec['platform'].upper()}) — Week {lineup_rec['week']}"]

    if graded_count:
        lines.append(f"\n_Graded {graded_count} player result(s) from prior week(s) this run._")

    if lineup_rec["status_alerts"]:
        lines.append("\n### ⚠️ Status Alerts (needs research)")
        for alert in lineup_rec["status_alerts"]:
            lines.append(f"- **{alert['name']}** ({alert['lineup_slot']}) — {alert['status']}")

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
    lines.append("| Player | Pos | Slot | Status | Projection |")
    lines.append("|---|---|---|---|---|")
    for info in lineup_rec["projections"].values():
        lines.append(
            f"| {info['name']} | {info['position']} | {info['lineup_slot']} | "
            f"{info['status']} | {_fmt(info['blended_projection'])} |"
        )

    if waiver_rec:
        lines.append("\n### Waiver Wire Suggestions")
        for position, candidates in waiver_rec.items():
            if not candidates:
                continue
            lines.append(f"\n**{position}**")
            for c in candidates:
                flag = " (upgrade over your weakest rostered player)" if c["beats_weakest_rostered"] else ""
                lines.append(f"- {c['name']} ({c['nfl_team']}) — {_fmt(c['projection'])} pts{flag}")

    return "\n".join(lines)


def render_full_report(season: int, week: int, team_sections: list[str]) -> str:
    header = f"# Fantasy Lineup Report — {season} Week {week}\n"
    return header + "\n\n".join(team_sections)
