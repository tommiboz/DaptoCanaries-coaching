"""
Derive aggregated stats from tagged video_events and export them to match_stats
via the existing insert_match_stats() function in database.py.
"""
from __future__ import annotations

import os
import sys
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from database import get_conn, insert_match_stats  # noqa: E402
from video_analysis.db.video_database import (  # noqa: E402
    get_session_events,
    get_session,
    upsert_derived_stats,
    mark_stats_exported,
    get_derived_stats,
)


def derive_stats_from_events(session_id: int) -> dict[str, dict]:
    """
    Aggregate video_events for session_id into stat counts per team_side.

    Returns:
        {
            "home": {"tries": N, "tackles": N, ...},
            "away": {"tries": N, "tackles": N, ...},
        }
    """
    events = get_session_events(session_id)

    results: dict[str, dict] = {
        "home": _empty_stats(),
        "away": _empty_stats(),
    }

    for ev in events:
        side = ev.get("team_side") or "home"
        if side not in results:
            results[side] = _empty_stats()

        etype = ev["event_type"]
        if etype == "try":
            results[side]["tries"] += 1
        elif etype == "tackle":
            results[side]["tackles"] += 1
        elif etype == "missed_tackle":
            results[side]["missed_tackles"] += 1
        elif etype == "linebreak":
            results[side]["linebreaks"] += 1
        elif etype == "offload":
            results[side]["offloads"] += 1
        elif etype == "error":
            results[side]["errors"] += 1
        elif etype == "penalty":
            results[side]["penalties"] += 1
        elif etype == "kick":
            results[side]["kicks"] += 1

    # Persist derived stats
    for side, stats in results.items():
        upsert_derived_stats(session_id, side, stats)

    return results


def export_to_match_stats(session_id: int, team_side: str,
                           team_id: int, merge: bool = False) -> bool:
    """
    Export video-derived stats for one team_side into match_stats.

    Parameters
    ----------
    session_id : int
    team_side  : "home" or "away"
    team_id    : DB id from teams table for the team being exported
    merge      : If True, ADD video stats to any existing match_stats row.
                 If False, INSERT a new row.

    Returns True on success.
    """
    session = get_session(session_id)
    if not session or not session.get("match_id"):
        raise ValueError(
            f"Session {session_id} has no linked match. "
            "Link the session to a match before exporting."
        )

    match_id = session["match_id"]
    derived = get_derived_stats(session_id)
    stats_row = next((d for d in derived if d["team_side"] == team_side), None)

    if not stats_row:
        raise ValueError(f"No derived stats found for session {session_id} / {team_side}")

    export_dict = _derived_to_match_stats(stats_row)

    if merge:
        _merge_into_match_stats(match_id, team_id, export_dict)
    else:
        insert_match_stats(match_id, team_id, export_dict)

    mark_stats_exported(session_id, team_side)
    return True


def preview_export(session_id: int) -> dict[str, dict]:
    """
    Return derived stats (without saving) for the export preview dialog.
    Also returns any existing match_stats rows for comparison.
    """
    derived = get_derived_stats(session_id)
    session = get_session(session_id)
    existing: list[dict] = []

    if session and session.get("match_id"):
        conn = get_conn()
        rows = conn.execute("""
            SELECT ms.*, t.name as team_name
            FROM match_stats ms
            JOIN teams t ON ms.team_id = t.id
            WHERE ms.match_id = ?
        """, (session["match_id"],)).fetchall()
        conn.close()
        existing = [dict(r) for r in rows]

    return {
        "derived": {d["team_side"]: d for d in derived},
        "existing": existing,
        "session":  session,
    }


# ── helpers ───────────────────────────────────────────────────────────────────

def _empty_stats() -> dict:
    return {
        "tries": 0, "tackles": 0, "missed_tackles": 0,
        "linebreaks": 0, "offloads": 0, "errors": 0,
        "penalties": 0, "kicks": 0,
    }


def _derived_to_match_stats(row: dict) -> dict:
    """Map video_derived_stats fields to insert_match_stats() dict keys."""
    return {
        "tries":                row.get("tries", 0),
        "tackles_made":         row.get("tackles", 0),
        "missed_tackles":       row.get("missed_tackles", 0),
        "linebreaks":           row.get("linebreaks", 0),
        "offloads":             row.get("offloads", 0),
        "errors":               row.get("errors", 0),
        "penalties_conceded":   row.get("penalties", 0),
        "kicks_general_play":   row.get("kicks", 0),
        # Fields not tracked by video — leave at 0 / default
        "possession_pct":       50,
        "sets_received":        0,
        "sets_completed":       0,
        "conversions_made":     0,
        "conversions_attempted": 0,
        "penalty_goals":        0,
        "field_goals":          0,
        "metres_gained":        0,
        "linebreaks_conceded":  0,
        "set_restarts_conceded": 0,
        "kick_metres":          0,
        "notes":                "Imported from video analysis",
    }


def _merge_into_match_stats(match_id: int, team_id: int, new_stats: dict):
    """Add video-derived values onto an existing match_stats row. Inserts if missing."""
    conn = get_conn()
    existing = conn.execute("""
        SELECT * FROM match_stats WHERE match_id=? AND team_id=?
    """, (match_id, team_id)).fetchone()

    mergeable = [
        "tries", "errors", "linebreaks", "offloads",
        "tackles_made", "missed_tackles", "penalties_conceded",
        "kicks_general_play",
    ]

    if existing:
        updates = {k: (existing[k] or 0) + new_stats.get(k, 0) for k in mergeable}
        placeholders = ", ".join(f"{k}=?" for k in updates)
        conn.execute(
            f"UPDATE match_stats SET {placeholders} WHERE match_id=? AND team_id=?",
            list(updates.values()) + [match_id, team_id],
        )
        conn.commit()
        conn.close()
    else:
        conn.close()
        insert_match_stats(match_id, team_id, new_stats)
