"""
Team assignment via KMeans clustering on jersey HSV colour.

Two clusters are fitted to all player ROIs in a segment of play.
The cluster closer to Dapto's gold is labelled 'home'; the other is 'away'.
"""
from __future__ import annotations

import numpy as np
from typing import Optional

try:
    from sklearn.cluster import KMeans
    _SK_AVAILABLE = True
except ImportError:
    _SK_AVAILABLE = False

from video_analysis.utils.constants import (
    DAPTO_GOLD_HSV_LOWER, DAPTO_GOLD_HSV_UPPER, TEAM_HOME, TEAM_AWAY
)
from video_analysis.utils.frame_utils import dominant_hsv_colour


class TeamAssigner:
    """
    Classifies track IDs into 'home' or 'away' using KMeans on jersey colour.

    Usage:
        assigner = TeamAssigner()
        assigner.add_sample(track_id, frame, x1, y1, x2, y2)
        ...
        assigner.fit()
        side = assigner.get_side(track_id)
    """

    def __init__(self):
        if not _SK_AVAILABLE:
            raise ImportError(
                "scikit-learn is not installed. "
                "Run: pip install scikit-learn"
            )
        self._samples: dict[int, list[np.ndarray]] = {}  # track_id -> list of HSV centres
        self._assignments: dict[int, str] = {}
        self._fitted = False

    def add_sample(self, track_id: int, frame: np.ndarray,
                   x1: int, y1: int, x2: int, y2: int):
        """Collect a dominant HSV colour sample for track_id."""
        import cv2
        roi = frame[max(0, y1):y2, max(0, x1):x2]
        colour = dominant_hsv_colour(roi, k=2)
        if colour is not None:
            self._samples.setdefault(track_id, []).append(colour)

    def fit(self) -> dict[int, str]:
        """
        Run KMeans(k=2) on all collected samples and assign home/away.
        Returns the assignment dict {track_id: 'home'/'away'}.
        """
        if not self._samples:
            return {}

        # Average colour per track
        track_ids = list(self._samples.keys())
        avg_colours = np.array([
            np.mean(self._samples[tid], axis=0) for tid in track_ids
        ])

        if len(track_ids) < 2:
            self._assignments = {track_ids[0]: TEAM_HOME}
            self._fitted = True
            return self._assignments

        km = KMeans(n_clusters=2, n_init=10, random_state=42)
        labels = km.fit_predict(avg_colours)

        # Identify which cluster is 'home' (Dapto gold)
        gold_h = (DAPTO_GOLD_HSV_LOWER[0] + DAPTO_GOLD_HSV_UPPER[0]) / 2
        gold_s = (DAPTO_GOLD_HSV_LOWER[1] + DAPTO_GOLD_HSV_UPPER[1]) / 2
        gold_v = (DAPTO_GOLD_HSV_LOWER[2] + DAPTO_GOLD_HSV_UPPER[2]) / 2
        gold_ref = np.array([gold_h, gold_s, gold_v])

        c0_dist = np.linalg.norm(km.cluster_centers_[0] - gold_ref)
        c1_dist = np.linalg.norm(km.cluster_centers_[1] - gold_ref)
        home_cluster = 0 if c0_dist < c1_dist else 1

        self._assignments = {
            tid: (TEAM_HOME if labels[i] == home_cluster else TEAM_AWAY)
            for i, tid in enumerate(track_ids)
        }
        self._fitted = True
        return self._assignments

    def get_side(self, track_id: int) -> Optional[str]:
        return self._assignments.get(track_id)

    @property
    def fitted(self) -> bool:
        return self._fitted
