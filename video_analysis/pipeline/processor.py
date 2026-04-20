"""
QThread orchestrator: runs the full processing pipeline in a background thread.

Pipeline:
    Ingest → Camera Cut Detection → YOLOv8 Detection (every 2nd frame)
    → ByteTrack Tracking → Jersey OCR (every 10 frames per track)
    → Team Assignment → Persist to DB → Signal UI complete
"""
from __future__ import annotations

import os
import sys
import time
from collections import defaultdict
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from database import init_db  # noqa: E402
from video_analysis.pipeline.ingest import ingest_video, open_capture, IngestError  # noqa: E402
from video_analysis.pipeline.detector import PersonDetector  # noqa: E402
from video_analysis.pipeline.tracker import PlayerTracker  # noqa: E402
from video_analysis.pipeline.ocr_reader import JerseyOCR  # noqa: E402
from video_analysis.pipeline.team_assigner import TeamAssigner  # noqa: E402
from video_analysis.utils.constants import (  # noqa: E402
    DETECTION_FRAME_SKIP, OCR_FRAME_INTERVAL, STATUS_PROCESSING, STATUS_DONE, STATUS_ERROR
)
from video_analysis.db.video_database import (  # noqa: E402
    create_session, update_session_metadata, update_session_status,
    upsert_player, bulk_insert_detections,
)

import cv2


class ProcessingWorker(QThread):
    """
    Background QThread that processes a single video file end-to-end.

    Signals emitted to the UI:
        progress(int)           — percent complete 0-100
        status_message(str)     — human-readable status line
        frame_ready(int, bytes) — frame_number + JPEG bytes of a preview frame
        finished(int)           — session_id on success
        error(str)              — error message on failure
    """

    progress       = pyqtSignal(int)
    status_message = pyqtSignal(str)
    frame_ready    = pyqtSignal(int, bytes)
    finished       = pyqtSignal(int)
    error          = pyqtSignal(str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.session_id: Optional[int] = None
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        init_db()
        try:
            self._process()
        except Exception as exc:
            update_session_status(self.session_id or 0, STATUS_ERROR)
            self.error.emit(str(exc))

    def _process(self):
        # ── 1. Ingest ────────────────────────────────────────────────────────
        self.status_message.emit("Reading video metadata…")
        try:
            meta = ingest_video(self.file_path)
        except IngestError as e:
            self.error.emit(str(e))
            return

        self.session_id = create_session(self.file_path)
        update_session_metadata(
            self.session_id, meta.duration_secs, meta.fps, meta.total_frames
        )

        # ── 2. Initialise pipeline components ────────────────────────────────
        self.status_message.emit("Loading YOLOv8 model…")
        detector = PersonDetector()
        using_gpu = detector.using_gpu
        self.status_message.emit(
            f"Using {'GPU' if using_gpu else 'CPU'} — "
            f"{'~25 min' if using_gpu else '~2+ hours'} estimated"
        )

        tracker  = PlayerTracker()
        ocr      = JerseyOCR(gpu=using_gpu)
        assigner = TeamAssigner()

        cap = open_capture(self.file_path)

        # Track when we last ran OCR per track_id
        last_ocr_frame: dict[int, int] = defaultdict(lambda: -OCR_FRAME_INTERVAL)
        detection_batch: list[tuple] = []

        total = meta.total_frames
        BATCH_SIZE = 200   # flush detections to DB every N frames

        # ── 3. Main frame loop ────────────────────────────────────────────────
        frame_num = 0
        while True:
            if self._stop_requested:
                break

            ret, frame = cap.read()
            if not ret:
                break

            # Camera cut check
            tracker.check_cut(frame)

            # Only detect on every Nth frame
            if frame_num % DETECTION_FRAME_SKIP == 0:
                detections = detector.detect(frame)
                tracks = tracker.update(detections, frame)

                for track in tracks:
                    x1, y1, x2, y2 = (
                        int(track.x1), int(track.y1),
                        int(track.x2), int(track.y2)
                    )
                    detection_batch.append((
                        frame_num, track.track_id,
                        track.x1, track.y1, track.x2, track.y2,
                        track.confidence,
                    ))

                    # Collect colour sample for team assignment
                    assigner.add_sample(track.track_id, frame, x1, y1, x2, y2)

                    # Run OCR periodically per track
                    frames_since_ocr = frame_num - last_ocr_frame[track.track_id]
                    if frames_since_ocr >= OCR_FRAME_INTERVAL:
                        ocr_result = ocr.read_jersey(frame, x1, y1, x2, y2)
                        if ocr_result.jersey_number is not None:
                            upsert_player(
                                self.session_id,
                                track.track_id,
                                ocr_result.jersey_number,
                                ocr_result.confidence,
                                team_side=None,  # assigned after fit()
                            )
                        last_ocr_frame[track.track_id] = frame_num

                # Flush detection batch
                if len(detection_batch) >= BATCH_SIZE:
                    bulk_insert_detections(self.session_id, detection_batch)
                    detection_batch.clear()

                # Emit a preview frame every ~2 seconds of video
                preview_interval = max(1, int(meta.fps * 2))
                if frame_num % preview_interval == 0:
                    _, jpg = cv2.imencode(".jpg", cv2.resize(frame, (640, 360)),
                                         [cv2.IMWRITE_JPEG_QUALITY, 70])
                    self.frame_ready.emit(frame_num, bytes(jpg.tobytes()))

            # Report progress
            pct = int(frame_num / total * 100)
            self.progress.emit(pct)
            frame_num += 1

        cap.release()

        # Flush remaining detections
        if detection_batch:
            bulk_insert_detections(self.session_id, detection_batch)

        if self._stop_requested:
            update_session_status(self.session_id, STATUS_ERROR)
            return

        # ── 4. Team assignment ────────────────────────────────────────────────
        self.status_message.emit("Assigning teams by jersey colour…")
        assignments = assigner.fit()
        for track_id, side in assignments.items():
            upsert_player(
                self.session_id, track_id,
                jersey_number=None, ocr_confidence=0.0, team_side=side
            )

        # ── 5. Done ───────────────────────────────────────────────────────────
        update_session_status(self.session_id, STATUS_DONE)
        self.progress.emit(100)
        self.status_message.emit("Processing complete.")
        self.finished.emit(self.session_id)
