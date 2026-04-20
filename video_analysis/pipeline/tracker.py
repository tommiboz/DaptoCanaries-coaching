"""
ByteTrack player tracker with camera-cut detection.

Uses the `supervision` library's ByteTrack implementation.
On each camera cut (histogram diff > threshold) the tracker state is reset
so stale track IDs from the previous shot do not pollute the new one.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    import supervision as sv
    _SV_AVAILABLE = True
except ImportError:
    _SV_AVAILABLE = False

from video_analysis.utils.constants import CAMERA_CUT_THRESHOLD
from video_analysis.utils.frame_utils import histogram_diff
from video_analysis.pipeline.detector import Detection


@dataclass
class Track:
    track_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float


class PlayerTracker:
    """
    Wraps ByteTrack + automatic camera-cut reset.

    Usage:
        tracker = PlayerTracker()
        for frame_num, frame in frames:
            is_cut = tracker.check_cut(frame)
            tracks = tracker.update(detections, frame)
    """

    def __init__(self):
        if not _SV_AVAILABLE:
            raise ImportError(
                "supervision is not installed. "
                "Run: pip install supervision"
            )
        self._tracker = sv.ByteTrack()
        self._prev_frame: np.ndarray | None = None
        self._cut_threshold = CAMERA_CUT_THRESHOLD
        self.cut_count = 0

    def check_cut(self, frame: np.ndarray) -> bool:
        """
        Compare frame against the previous frame.
        Resets tracker state if a camera cut is detected.
        Returns True if a cut was detected.
        """
        is_cut = False
        if self._prev_frame is not None:
            diff = histogram_diff(self._prev_frame, frame)
            if diff > self._cut_threshold:
                self._tracker = sv.ByteTrack()  # reset tracker state
                self.cut_count += 1
                is_cut = True

        # Downsample for storage efficiency
        self._prev_frame = cv2.resize(frame, (160, 90))
        return is_cut

    def update(self, detections: list[Detection], frame: np.ndarray) -> list[Track]:
        """
        Feed current detections into ByteTrack and return active tracks.
        """
        if not detections:
            # Still update tracker with empty detections to age out lost tracks
            sv_dets = sv.Detections.empty()
        else:
            xyxy = np.array([[d.x1, d.y1, d.x2, d.y2] for d in detections], dtype=float)
            confidence = np.array([d.confidence for d in detections], dtype=float)
            class_id = np.zeros(len(detections), dtype=int)
            sv_dets = sv.Detections(
                xyxy=xyxy,
                confidence=confidence,
                class_id=class_id,
            )

        tracked = self._tracker.update_with_detections(sv_dets)

        tracks: list[Track] = []
        for i in range(len(tracked)):
            x1, y1, x2, y2 = tracked.xyxy[i]
            conf = float(tracked.confidence[i]) if tracked.confidence is not None else 0.0
            tid = int(tracked.tracker_id[i])
            tracks.append(Track(
                track_id=tid,
                x1=float(x1), y1=float(y1),
                x2=float(x2), y2=float(y2),
                confidence=conf,
            ))
        return tracks


# cv2 is needed for the resize in check_cut
try:
    import cv2
except ImportError:
    pass
