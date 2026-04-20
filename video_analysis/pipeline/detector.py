"""
YOLOv8 person detector wrapper.

Uses ultralytics YOLOv8m. Only the 'person' class (index 0) is returned.
Model file is downloaded automatically by ultralytics on first run.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except ImportError:
    _YOLO_AVAILABLE = False

from video_analysis.utils.constants import (
    YOLO_MODEL, YOLO_CONFIDENCE, YOLO_CLASS_PERSON, YOLO_IOU
)


@dataclass
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float


class PersonDetector:
    """
    Wraps YOLOv8m for person detection.
    Call detect(frame) to get a list of Detection objects.
    """

    def __init__(self, model_path: str = YOLO_MODEL, device: str = "auto"):
        if not _YOLO_AVAILABLE:
            raise ImportError(
                "ultralytics is not installed. "
                "Run: pip install ultralytics"
            )

        if device == "auto":
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self.device = device
        self.model = YOLO(model_path)
        self.model.to(device)
        self._confidence = YOLO_CONFIDENCE
        self._iou = YOLO_IOU

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """
        Run inference on a single BGR frame.
        Returns only person-class detections above the confidence threshold.
        """
        results = self.model(
            frame,
            conf=self._confidence,
            iou=self._iou,
            classes=[YOLO_CLASS_PERSON],
            verbose=False,
        )
        detections: list[Detection] = []
        if results and results[0].boxes is not None:
            for box in results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                detections.append(Detection(x1=x1, y1=y1, x2=x2, y2=y2, confidence=conf))
        return detections

    @property
    def using_gpu(self) -> bool:
        return "cuda" in self.device
