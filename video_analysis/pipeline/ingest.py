"""
Video ingestor: open a file, extract metadata, validate it is a usable video.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import cv2


@dataclass
class VideoMeta:
    file_path: str
    file_name: str
    fps: float
    total_frames: int
    duration_secs: float
    width: int
    height: int


class IngestError(Exception):
    pass


def ingest_video(file_path: str) -> VideoMeta:
    """
    Open a video file and return its metadata.
    Raises IngestError if the file cannot be opened or has no video stream.
    """
    if not os.path.isfile(file_path):
        raise IngestError(f"File not found: {file_path}")

    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        raise IngestError(f"OpenCV could not open: {file_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if total_frames <= 0 or fps <= 0:
        raise IngestError(f"Video has no readable frames: {file_path}")

    duration_secs = total_frames / fps

    return VideoMeta(
        file_path=file_path,
        file_name=os.path.basename(file_path),
        fps=fps,
        total_frames=total_frames,
        duration_secs=duration_secs,
        width=width,
        height=height,
    )


def open_capture(file_path: str) -> cv2.VideoCapture:
    """Return an opened VideoCapture. Caller must release it."""
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        raise IngestError(f"Could not open video: {file_path}")
    return cap


def read_frame(cap: cv2.VideoCapture, frame_number: Optional[int] = None):
    """
    Read one frame. If frame_number is given, seek first.
    Returns (success, frame_ndarray).
    """
    if frame_number is not None:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    return cap.read()
