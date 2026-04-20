"""
Frame manipulation utilities: CLAHE, histogram comparison, thumbnail generation.
"""
from __future__ import annotations

import cv2
import numpy as np
from typing import Optional


def apply_clahe(roi: np.ndarray) -> np.ndarray:
    """
    Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to a BGR ROI.
    Improves OCR accuracy on coloured jerseys with motion blur.
    """
    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    l_eq = clahe.apply(l)
    lab_eq = cv2.merge([l_eq, a, b])
    return cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)


def histogram_diff(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """
    Compute normalised histogram difference between two BGR frames.
    Returns a value in [0, 1] where > 0.6 indicates a camera cut.
    """
    diffs = []
    for ch in range(3):
        hist_a = cv2.calcHist([frame_a], [ch], None, [64], [0, 256])
        hist_b = cv2.calcHist([frame_b], [ch], None, [64], [0, 256])
        cv2.normalize(hist_a, hist_a)
        cv2.normalize(hist_b, hist_b)
        diff = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_BHATTACHARYYA)
        diffs.append(diff)
    return float(np.mean(diffs))


def crop_player(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int,
                pad: int = 4) -> np.ndarray:
    """Return a cropped BGR image of a player bounding box with optional padding."""
    h, w = frame.shape[:2]
    x1c = max(0, x1 - pad)
    y1c = max(0, y1 - pad)
    x2c = min(w, x2 + pad)
    y2c = min(h, y2 + pad)
    return frame[y1c:y2c, x1c:x2c].copy()


def make_thumbnail(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int,
                   width: int = 80, height: int = 160) -> np.ndarray:
    """Crop a player region and resize to a fixed thumbnail."""
    crop = crop_player(frame, x1, y1, x2, y2)
    if crop.size == 0:
        return np.zeros((height, width, 3), dtype=np.uint8)
    return cv2.resize(crop, (width, height), interpolation=cv2.INTER_AREA)


def encode_thumbnail_png(thumb: np.ndarray) -> bytes:
    """Encode a thumbnail ndarray to PNG bytes for DB storage."""
    _, buf = cv2.imencode(".png", thumb)
    return buf.tobytes()


def dominant_hsv_colour(roi: np.ndarray, k: int = 2) -> Optional[np.ndarray]:
    """
    Return the dominant HSV colour cluster centres for a player ROI.
    Used by team_assigner for jersey colour classification.
    """
    if roi.size == 0:
        return None
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    pixels = hsv.reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centres = cv2.kmeans(
        pixels, k, None, criteria, 3, cv2.KMEANS_RANDOM_CENTERS
    )
    counts = np.bincount(labels.flatten())
    dominant_idx = np.argmax(counts)
    return centres[dominant_idx]


def draw_detections(
    frame: np.ndarray,
    detections: list[dict],
    confirmed_jerseys: dict[int, str] | None = None,
) -> np.ndarray:
    """
    Overlay bounding boxes and jersey numbers on a frame copy.

    detections: list of dicts with keys track_id, x1, y1, x2, y2
    confirmed_jerseys: map track_id -> jersey label string
    """
    out = frame.copy()
    if confirmed_jerseys is None:
        confirmed_jerseys = {}

    for det in detections:
        tid = det["track_id"]
        x1, y1, x2, y2 = int(det["x1"]), int(det["y1"]), int(det["x2"]), int(det["y2"])
        label = confirmed_jerseys.get(tid, f"#{tid}")
        colour = (0, 200, 0) if tid in confirmed_jerseys else (200, 200, 0)
        cv2.rectangle(out, (x1, y1), (x2, y2), colour, 2)
        cv2.putText(out, label, (x1, max(y1 - 5, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
    return out
