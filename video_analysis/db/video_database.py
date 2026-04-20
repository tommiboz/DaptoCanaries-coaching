"""
CRUD operations for the 5 video analysis tables.
All functions operate on the shared coaching.db via sys.path-injected database module.
"""
from __future__ import annotations

import os
import sys
import sqlite3
from datetime import datetime
from typing import Optional

# Allow importing from the project root
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from database import get_conn  # noqa: E402


# ── video_sessions ────────────────────────────────────────────────────────────

def create_session(file_path: str) -> int:
    """Insert a new video session row. Returns the new session id."""
    file_name = os.path.basename(file_path)
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO video_sessions (file_path, file_name, status, created_at)
        VALUES (?, ?, 'pending', ?)
    """, (file_path, file_name, datetime.now().isoformat()))
    sid = c.lastrowid
    conn.commit()
    conn.close()
    return sid


def update_session_metadata(session_id: int, duration_secs: float,
                             fps: float, total_frames: int):
    conn = get_conn()
    conn.execute("""
        UPDATE video_sessions
        SET duration_secs=?, fps=?, total_frames=?, status='processing'
        WHERE id=?
    """, (duration_secs, fps, total_frames, session_id))
    conn.commit()
    conn.close()


def update_session_status(session_id: int, status: str):
    conn = get_conn()
    processed_at = datetime.now().isoformat() if status == "done" else None
    conn.execute("""
        UPDATE video_sessions SET status=?, processed_at=? WHERE id=?
    """, (status, processed_at, session_id))
    conn.commit()
    conn.close()


def link_session_to_match(session_id: int, match_id: int):
    conn = get_conn()
    conn.execute("UPDATE video_sessions SET match_id=? WHERE id=?",
                 (match_id, session_id))
    conn.commit()
    conn.close()


def get_all_sessions() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT vs.*, m.round, m.match_date,
               ht.name as home_team, at.name as away_team
        FROM video_sessions vs
        LEFT JOIN matches m ON vs.match_id = m.id
        LEFT JOIN teams ht ON m.home_team_id = ht.id
        LEFT JOIN teams at ON m.away_team_id = at.id
        ORDER BY vs.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session(session_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM video_sessions WHERE id=?",
                       (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_session(session_id: int):
    """Delete a session and all its associated data."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM video_events WHERE session_id=?", (session_id,))
    c.execute("DELETE FROM video_detections WHERE session_id=?", (session_id,))
    c.execute("DELETE FROM video_players WHERE session_id=?", (session_id,))
    c.execute("DELETE FROM video_derived_stats WHERE session_id=?", (session_id,))
    c.execute("DELETE FROM video_sessions WHERE id=?", (session_id,))
    conn.commit()
    conn.close()


# ── video_players ─────────────────────────────────────────────────────────────

def upsert_player(session_id: int, track_id: int, jersey_number: Optional[int],
                  ocr_confidence: float, team_side: Optional[str],
                  thumbnail_path: Optional[str] = None) -> int:
    """Insert or update a tracked player row. Returns row id."""
    conn = get_conn()
    c = conn.cursor()
    existing = c.execute("""
        SELECT id, ocr_confidence FROM video_players
        WHERE session_id=? AND track_id=?
    """, (session_id, track_id)).fetchone()

    if existing:
        row_id = existing["id"]
        # Only update jersey/confidence if new reading is better
        if jersey_number is not None and ocr_confidence > existing["ocr_confidence"]:
            c.execute("""
                UPDATE video_players
                SET jersey_number=?, ocr_confidence=?, team_side=COALESCE(?, team_side),
                    thumbnail_path=COALESCE(?, thumbnail_path)
                WHERE id=?
            """, (jersey_number, ocr_confidence, team_side, thumbnail_path, row_id))
    else:
        c.execute("""
            INSERT INTO video_players
                (session_id, track_id, jersey_number, ocr_confidence, team_side, thumbnail_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, track_id, jersey_number, ocr_confidence, team_side, thumbnail_path))
        row_id = c.lastrowid

    conn.commit()
    conn.close()
    return row_id


def confirm_player(player_id: int, jersey_number: int, team_side: str,
                   linked_player_id: Optional[int] = None):
    conn = get_conn()
    conn.execute("""
        UPDATE video_players
        SET jersey_number=?, team_side=?, confirmed=1, player_id=?
        WHERE id=?
    """, (jersey_number, team_side, linked_player_id, player_id))
    conn.commit()
    conn.close()


def get_session_players(session_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT vp.*, p.name as player_name
        FROM video_players vp
        LEFT JOIN players p ON vp.player_id = p.id
        WHERE vp.session_id=?
        ORDER BY vp.team_side, vp.jersey_number
    """, (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unconfirmed_players(session_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM video_players
        WHERE session_id=? AND confirmed=0
        ORDER BY track_id
    """, (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── video_detections ──────────────────────────────────────────────────────────

def bulk_insert_detections(session_id: int, rows: list[tuple]):
    """
    rows: list of (frame_number, track_id, x1, y1, x2, y2, confidence)
    Batched for performance.
    """
    conn = get_conn()
    conn.executemany("""
        INSERT INTO video_detections
            (session_id, frame_number, track_id, x1, y1, x2, y2, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [(session_id, *r) for r in rows])
    conn.commit()
    conn.close()


def get_detections_for_frame(session_id: int, frame_number: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM video_detections
        WHERE session_id=? AND frame_number=?
    """, (session_id, frame_number)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── video_events ──────────────────────────────────────────────────────────────

def insert_event(session_id: int, frame_number: int, timestamp_secs: float,
                 event_type: str, team_side: str,
                 primary_player_id: Optional[int] = None,
                 secondary_player_id: Optional[int] = None,
                 notes: str = "") -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO video_events
            (session_id, frame_number, timestamp_secs, event_type, team_side,
             primary_player_id, secondary_player_id, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, frame_number, timestamp_secs, event_type, team_side,
          primary_player_id, secondary_player_id, notes,
          datetime.now().isoformat()))
    eid = c.lastrowid
    conn.commit()
    conn.close()
    return eid


def delete_event(event_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM video_events WHERE id=?", (event_id,))
    conn.commit()
    conn.close()


def get_session_events(session_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT ve.*,
               pp.jersey_number as primary_jersey,
               sp.jersey_number as secondary_jersey
        FROM video_events ve
        LEFT JOIN video_players pp ON ve.primary_player_id = pp.id
        LEFT JOIN video_players sp ON ve.secondary_player_id = sp.id
        WHERE ve.session_id=?
        ORDER BY ve.frame_number
    """, (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── video_derived_stats ───────────────────────────────────────────────────────

def upsert_derived_stats(session_id: int, team_side: str, stats: dict) -> int:
    conn = get_conn()
    c = conn.cursor()
    existing = c.execute("""
        SELECT id FROM video_derived_stats WHERE session_id=? AND team_side=?
    """, (session_id, team_side)).fetchone()

    if existing:
        row_id = existing["id"]
        c.execute("""
            UPDATE video_derived_stats
            SET tries=?, tackles=?, missed_tackles=?, errors=?, penalties=?,
                linebreaks=?, offloads=?, kicks=?, exported=0
            WHERE id=?
        """, (stats.get("tries", 0), stats.get("tackles", 0),
              stats.get("missed_tackles", 0), stats.get("errors", 0),
              stats.get("penalties", 0), stats.get("linebreaks", 0),
              stats.get("offloads", 0), stats.get("kicks", 0), row_id))
    else:
        c.execute("""
            INSERT INTO video_derived_stats
                (session_id, team_side, tries, tackles, missed_tackles, errors,
                 penalties, linebreaks, offloads, kicks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, team_side,
              stats.get("tries", 0), stats.get("tackles", 0),
              stats.get("missed_tackles", 0), stats.get("errors", 0),
              stats.get("penalties", 0), stats.get("linebreaks", 0),
              stats.get("offloads", 0), stats.get("kicks", 0)))
        row_id = c.lastrowid

    conn.commit()
    conn.close()
    return row_id


def mark_stats_exported(session_id: int, team_side: str):
    conn = get_conn()
    conn.execute("""
        UPDATE video_derived_stats
        SET exported=1, exported_at=?
        WHERE session_id=? AND team_side=?
    """, (datetime.now().isoformat(), session_id, team_side))
    conn.commit()
    conn.close()


def get_derived_stats(session_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM video_derived_stats WHERE session_id=?
    """, (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
