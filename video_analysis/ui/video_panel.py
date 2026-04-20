"""
Centre panel — Video Viewer.

Shows a video frame with player bounding boxes overlaid.
Handles video playback and keyboard shortcuts:
    Space  — play / pause
    T      — open tag dialog for current frame
    1-8    — set event type (map from constants.EVENT_KEYS)
    H / A  — set active team side to Home / Away
    Left / Right arrow — step backward / forward one frame
"""
from __future__ import annotations

import os
import sys
from typing import Optional

import cv2
import numpy as np

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QKeyEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QSizePolicy,
)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from video_analysis.utils.frame_utils import draw_detections  # noqa: E402
from video_analysis.utils.constants import EVENT_KEYS  # noqa: E402
from video_analysis.db.video_database import get_detections_for_frame  # noqa: E402
from video_analysis.pipeline.ingest import open_capture  # noqa: E402


class VideoPanel(QWidget):
    """
    Signals:
        tag_requested(int, float)   — frame_number, timestamp_secs
        event_type_changed(str)     — shortcut key changed active event type
        team_side_changed(str)      — 'H'/'A' shortcut changed active team
    """

    tag_requested      = pyqtSignal(int, float)
    event_type_changed = pyqtSignal(str)
    team_side_changed  = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cap: Optional[cv2.VideoCapture] = None
        self._session_id: Optional[int] = None
        self._total_frames = 1
        self._fps = 25.0
        self._current_frame = 0
        self._playing = False
        self._confirmed_jerseys: dict[int, str] = {}

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)

        self._build_ui()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Frame display
        self._frame_label = QLabel("Load a video to begin")
        self._frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._frame_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._frame_label.setStyleSheet("background: #111; color: #666;")
        self._frame_label.setMinimumSize(640, 360)
        layout.addWidget(self._frame_label, stretch=1)

        # Scrub bar
        self._scrub = QSlider(Qt.Orientation.Horizontal)
        self._scrub.setRange(0, 0)
        self._scrub.sliderPressed.connect(self._on_scrub_pressed)
        self._scrub.sliderReleased.connect(self._on_scrub_released)
        self._scrub.valueChanged.connect(self._on_scrub_moved)
        layout.addWidget(self._scrub)

        # Playback controls
        ctrl_row = QHBoxLayout()

        self._play_btn = QPushButton("▶ Play")
        self._play_btn.setFixedWidth(90)
        self._play_btn.clicked.connect(self.toggle_play)
        ctrl_row.addWidget(self._play_btn)

        self._prev_btn = QPushButton("◀ Frame")
        self._prev_btn.clicked.connect(self.step_back)
        ctrl_row.addWidget(self._prev_btn)

        self._next_btn = QPushButton("Frame ▶")
        self._next_btn.clicked.connect(self.step_forward)
        ctrl_row.addWidget(self._next_btn)

        self._tag_btn = QPushButton("T — Tag Event")
        self._tag_btn.setStyleSheet("background: #2a5; color: white; font-weight: bold;")
        self._tag_btn.clicked.connect(self._emit_tag)
        ctrl_row.addWidget(self._tag_btn)

        ctrl_row.addStretch()

        self._time_label = QLabel("0:00 / 0:00")
        ctrl_row.addWidget(self._time_label)

        layout.addLayout(ctrl_row)

        # Shortcut hint
        hint = QLabel(
            "Shortcuts:  Space=Play/Pause  T=Tag  1-8=Event  H=Home  A=Away  ←/→=Step"
        )
        hint.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(hint)

    # ── Public API ────────────────────────────────────────────────────────────

    def load_video(self, file_path: str, session_id: int,
                   total_frames: int, fps: float):
        if self._cap:
            self._cap.release()
        self._cap = open_capture(file_path)
        self._session_id = session_id
        self._total_frames = max(1, total_frames)
        self._fps = fps or 25.0
        self._current_frame = 0
        self._scrub.setRange(0, self._total_frames - 1)
        self._scrub.setValue(0)
        self._show_frame(0)

    def set_confirmed_jerseys(self, jerseys: dict[int, str]):
        """jerseys: {track_id: '#7'} — shown on bounding boxes."""
        self._confirmed_jerseys = jerseys

    def show_jpeg_preview(self, frame_num: int, jpeg_bytes: bytes):
        """Display a JPEG preview emitted during processing."""
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is not None:
            self._display_ndarray(img)
            self._current_frame = frame_num
            self._scrub.setValue(frame_num)

    def toggle_play(self):
        if self._cap is None:
            return
        self._playing = not self._playing
        if self._playing:
            self._play_btn.setText("⏸ Pause")
            interval = max(1, int(1000 / self._fps))
            self._timer.start(interval)
        else:
            self._play_btn.setText("▶ Play")
            self._timer.stop()

    def step_forward(self):
        self._show_frame(min(self._current_frame + 1, self._total_frames - 1))

    def step_back(self):
        self._show_frame(max(0, self._current_frame - 1))

    # ── Keyboard shortcuts ────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        text = event.text().upper()

        if key == Qt.Key.Key_Space:
            self.toggle_play()
        elif key == Qt.Key.Key_T:
            self._emit_tag()
        elif text in EVENT_KEYS:
            self.event_type_changed.emit(EVENT_KEYS[text])
        elif text == "H":
            self.team_side_changed.emit("home")
        elif text == "A":
            self.team_side_changed.emit("away")
        elif key == Qt.Key.Key_Left:
            self.step_back()
        elif key == Qt.Key.Key_Right:
            self.step_forward()
        else:
            super().keyPressEvent(event)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _next_frame(self):
        if self._cap is None:
            return
        self._show_frame(self._current_frame + 1)
        if self._current_frame >= self._total_frames - 1:
            self.toggle_play()

    def _show_frame(self, frame_num: int):
        if self._cap is None:
            return
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = self._cap.read()
        if not ret:
            return
        self._current_frame = frame_num

        # Overlay bounding boxes if session is set
        if self._session_id is not None:
            dets = get_detections_for_frame(self._session_id, frame_num)
            if dets:
                frame = draw_detections(frame, dets, self._confirmed_jerseys)

        self._display_ndarray(frame)

        # Update scrub + time label (block signals to avoid feedback loop)
        self._scrub.blockSignals(True)
        self._scrub.setValue(frame_num)
        self._scrub.blockSignals(False)

        secs = frame_num / self._fps
        total_secs = self._total_frames / self._fps
        self._time_label.setText(
            f"{int(secs//60)}:{int(secs%60):02d} / "
            f"{int(total_secs//60)}:{int(total_secs%60):02d}"
        )

    def _display_ndarray(self, bgr: np.ndarray):
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            self._frame_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._frame_label.setPixmap(pix)

    def _emit_tag(self):
        ts = self._current_frame / self._fps
        self.tag_requested.emit(self._current_frame, ts)

    def _on_scrub_pressed(self):
        self._timer.stop()

    def _on_scrub_released(self):
        self._show_frame(self._scrub.value())
        if self._playing:
            self._timer.start(max(1, int(1000 / self._fps)))

    def _on_scrub_moved(self, value: int):
        # Only seek if user is dragging (not from programmatic setValue)
        if self._scrub.isSliderDown():
            self._show_frame(value)

    @property
    def current_frame(self) -> int:
        return self._current_frame

    @property
    def current_timestamp(self) -> float:
        return self._current_frame / self._fps
