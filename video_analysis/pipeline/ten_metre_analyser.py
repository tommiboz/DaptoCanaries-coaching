"""
10m Analyser — post-processing pass over tracking data.

Detects play-the-ball moments by finding frames where players from both teams
cluster together (tackle), then measures the nearest defender's distance from
the ruck at the moment of dispersal (play-the-ball).

Requires field calibration: a homography matrix mapping pixel coordinates to
real-world metres on the field.

Usage:
    analyser = TenMetreAnalyser(session_id, homography_matrix)
    results  = analyser.run()
    # results is a list of TenMetreEvent dataclasses
"""
from __future__ import annotations

import sqlite3
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from database import get_conn  # noqa: E402


# ── Configuration ─────────────────────────────────────────────────────────────
CLUSTER_RADIUS_PX   = 120   # pixels — players within this radius = tackle cluster
MIN_CLUSTER_SIZE    = 3     # minimum players in cluster to call it a tackle
DISPERSE_FRAMES     = 8     # frames after cluster breaks = play-the-ball
MIN_FRAMES_BETWEEN  = 30    # minimum frames between two separate tackle events
TEN_METRES_M        = 10.0  # the legal distance in metres


@dataclass
class TenMetreEvent:
    frame_number: int
    play_the_ball_x_px: float
    play_the_ball_y_px: float
    play_the_ball_x_m: float
    play_the_ball_y_m: float
    nearest_defender_dist_m: float
    team_side: str              # "home" or "away" — the defending team
    is_10m_compliant: bool      # True if nearest defender >= 10m away
    cluster_size: int


class TenMetreAnalyser:
    """
    Post-processing pass over a processed video session's tracking data.

    Parameters
    ----------
    session_id : int
        The video_sessions.id to analyse.
    homography : np.ndarray | None
        3x3 homography matrix mapping (px_x, px_y) → (field_x_m, field_y_m).
        If None, pixel distances are returned with is_10m_compliant always None.
    attacking_side : str
        "home" or "away" — which team is attacking (determines who must be 10m back).
        Provide for first half; the analyser flips automatically at frame 50%.
    fps : float
        Video frames per second — used to compute ruck duration.
    """

    def __init__(
        self,
        session_id: int,
        homography: Optional[np.ndarray] = None,
        attacking_side: str = "home",
        fps: float = 25.0,
    ):
        self.session_id = session_id
        self.H = homography
        self.attacking_side = attacking_side
        self.defending_side = "away" if attacking_side == "home" else "home"
        self.fps = fps

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> list[TenMetreEvent]:
        """Run the full analysis. Returns a list of TenMetreEvent."""
        tracks = self._load_tracks()
        if not tracks:
            return []

        team_map = self._load_team_map()
        total_frames = max(f for f, _, _, _, _, _, _ in tracks)
        half_frame = total_frames // 2

        events: list[TenMetreEvent] = []
        last_tackle_frame = -MIN_FRAMES_BETWEEN

        # Group detections by frame
        frames: dict[int, list[tuple]] = {}
        for row in tracks:
            fn = row[0]
            frames.setdefault(fn, []).append(row)

        for frame_num in sorted(frames.keys()):
            if frame_num - last_tackle_frame < MIN_FRAMES_BETWEEN:
                continue

            # Flip attacking/defending side at half time
            if frame_num > half_frame:
                att = self.defending_side
                dfn = self.attacking_side
            else:
                att = self.attacking_side
                dfn = self.defending_side

            detections = frames[frame_num]
            cluster = self._find_tackle_cluster(detections, team_map)

            if cluster is None:
                continue

            cluster_centre, cluster_players = cluster
            cx_px, cy_px = cluster_centre

            # Find the nearest defender not in the cluster
            defenders = [
                d for d in detections
                if team_map.get(d[1], "") == dfn and d[1] not in cluster_players
            ]

            if not defenders:
                continue

            nearest_dist_px = min(
                self._dist(cx_px, cy_px, (d[2] + d[4]) / 2, (d[3] + d[5]) / 2)
                for d in defenders
            )

            if self.H is not None:
                cx_m, cy_m = self._px_to_m(cx_px, cy_px)
                # find nearest defender in metres
                def_dists_m = [
                    self._dist_m(cx_m, cy_m, *self._px_to_m(
                        (d[2] + d[4]) / 2, (d[3] + d[5]) / 2
                    ))
                    for d in defenders
                ]
                nearest_dist_m = min(def_dists_m)
                compliant = nearest_dist_m >= TEN_METRES_M
            else:
                cx_m, cy_m = cx_px, cy_px
                nearest_dist_m = nearest_dist_px  # pixels — no calibration
                compliant = False  # can't determine without calibration

            events.append(TenMetreEvent(
                frame_number=frame_num,
                play_the_ball_x_px=cx_px,
                play_the_ball_y_px=cy_px,
                play_the_ball_x_m=cx_m,
                play_the_ball_y_m=cy_m,
                nearest_defender_dist_m=round(nearest_dist_m, 2),
                team_side=dfn,
                is_10m_compliant=compliant if self.H is not None else None,
                cluster_size=len(cluster_players),
            ))
            last_tackle_frame = frame_num

        return events

    def save_results(self, events: list[TenMetreEvent],
                     match_id: int | None = None,
                     referee_id: int | None = None):
        """Persist results to referee_10m_measurements table."""
        if not events:
            return
        conn = get_conn()
        rows = [
            (
                self.session_id,
                match_id,
                referee_id,
                e.frame_number,
                e.play_the_ball_x_m,
                e.play_the_ball_y_m,
                e.nearest_defender_dist_m,
                e.team_side,
            )
            for e in events
        ]
        conn.executemany("""
            INSERT INTO referee_10m_measurements
                (session_id, match_id, referee_id, frame_number,
                 play_the_ball_x, play_the_ball_y,
                 nearest_defender_dist_m, team_side)
            VALUES (?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()
        conn.close()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _load_tracks(self) -> list[tuple]:
        conn = get_conn()
        rows = conn.execute("""
            SELECT frame_number, track_id, x1, y1, x2, y2, confidence
            FROM video_detections
            WHERE session_id = ?
            ORDER BY frame_number
        """, (self.session_id,)).fetchall()
        conn.close()
        return rows

    def _load_team_map(self) -> dict[int, str]:
        """Returns {track_id: team_side}."""
        conn = get_conn()
        rows = conn.execute("""
            SELECT track_id, team_side FROM video_players
            WHERE session_id = ? AND team_side IS NOT NULL
        """, (self.session_id,)).fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}

    def _find_tackle_cluster(
        self, detections: list[tuple], team_map: dict[int, str]
    ) -> Optional[tuple[tuple[float, float], set[int]]]:
        """
        Find a cluster of MIN_CLUSTER_SIZE+ players from BOTH teams within
        CLUSTER_RADIUS_PX of each other. Returns (centre, set_of_track_ids).
        """
        if len(detections) < MIN_CLUSTER_SIZE:
            return None

        centres = {
            d[1]: ((d[2] + d[4]) / 2, (d[3] + d[5]) / 2)
            for d in detections
        }

        for anchor_id, (ax, ay) in centres.items():
            nearby = {
                tid for tid, (px, py) in centres.items()
                if self._dist(ax, ay, px, py) <= CLUSTER_RADIUS_PX
            }
            if len(nearby) < MIN_CLUSTER_SIZE:
                continue

            teams_present = {team_map.get(tid, "") for tid in nearby} - {""}
            if len(teams_present) < 2:
                continue  # need players from both teams

            cx = sum(centres[t][0] for t in nearby) / len(nearby)
            cy = sum(centres[t][1] for t in nearby) / len(nearby)
            return (cx, cy), nearby

        return None

    @staticmethod
    def _dist(x1: float, y1: float, x2: float, y2: float) -> float:
        return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5

    @staticmethod
    def _dist_m(x1: float, y1: float, x2: float, y2: float) -> float:
        return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5

    def _px_to_m(self, px: float, py: float) -> tuple[float, float]:
        """Apply homography to convert pixel → metres."""
        pt = np.array([[[px, py]]], dtype=np.float32)
        result = cv2_perspective_transform(pt, self.H)
        return float(result[0][0][0]), float(result[0][0][1])


def cv2_perspective_transform(pt: np.ndarray, H: np.ndarray) -> np.ndarray:
    """Thin wrapper so the main module doesn't need a hard cv2 import."""
    try:
        import cv2
        return cv2.perspectiveTransform(pt, H)
    except ImportError:
        # Fallback: manual homography application
        x, y = pt[0][0]
        denom = H[2, 0] * x + H[2, 1] * y + H[2, 2]
        mx = (H[0, 0] * x + H[0, 1] * y + H[0, 2]) / denom
        my = (H[1, 0] * x + H[1, 1] * y + H[1, 2]) / denom
        return np.array([[[mx, my]]], dtype=np.float32)
