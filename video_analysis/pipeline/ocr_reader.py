"""
EasyOCR-based jersey number reader with CLAHE preprocessing.

Only digits 1-20 are accepted as valid jersey numbers.
Returns the best (highest confidence) single-digit or two-digit number found in the ROI.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    import easyocr
    _EASYOCR_AVAILABLE = True
except ImportError:
    _EASYOCR_AVAILABLE = False

from video_analysis.utils.constants import (
    OCR_MIN_CONFIDENCE, OCR_LANGUAGES, JERSEY_MIN, JERSEY_MAX
)
from video_analysis.utils.frame_utils import apply_clahe, crop_player


@dataclass
class OcrResult:
    jersey_number: Optional[int]
    confidence: float
    raw_text: str


class JerseyOCR:
    """
    Reads jersey numbers from player ROIs using EasyOCR.
    The reader is initialised once and reused across frames.
    """

    def __init__(self, gpu: bool = False):
        if not _EASYOCR_AVAILABLE:
            raise ImportError(
                "easyocr is not installed. "
                "Run: pip install easyocr"
            )
        self._reader = easyocr.Reader(OCR_LANGUAGES, gpu=gpu, verbose=False)

    def read_jersey(self, frame: np.ndarray,
                    x1: int, y1: int, x2: int, y2: int) -> OcrResult:
        """
        Extract jersey number from a player bounding box.
        Applies CLAHE preprocessing before OCR.
        """
        roi = crop_player(frame, x1, y1, x2, y2)
        if roi.size == 0:
            return OcrResult(None, 0.0, "")

        # Use the top-third of the bounding box where the number is printed
        h = roi.shape[0]
        number_region = roi[:max(h // 3, 20), :]
        enhanced = apply_clahe(number_region)

        results = self._reader.readtext(enhanced, allowlist="0123456789")
        return self._best_result(results)

    def _best_result(self, raw_results: list) -> OcrResult:
        """
        Pick the highest-confidence result that parses to a valid jersey number.
        raw_results: list of (bbox, text, confidence) tuples from easyocr.
        """
        best = OcrResult(None, 0.0, "")
        for _bbox, text, conf in raw_results:
            cleaned = re.sub(r"\D", "", text)
            if not cleaned:
                continue
            number = int(cleaned)
            if JERSEY_MIN <= number <= JERSEY_MAX and conf > best.confidence:
                best = OcrResult(jersey_number=number, confidence=conf, raw_text=text)

        if best.jersey_number is None and raw_results:
            # Return the top-confidence raw result even if not a valid jersey
            _bbox, text, conf = max(raw_results, key=lambda r: r[2])
            best = OcrResult(None, float(conf), text)

        return best
