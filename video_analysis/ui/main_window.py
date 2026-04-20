"""
Main window — 3-panel layout for the Video Analysis tool.

Left:   SessionPanel
Centre: VideoPanel
Right:  TaggerPanel
"""
from __future__ import annotations

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QStatusBar, QMessageBox,
)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from database import init_db  # noqa: E402
from video_analysis.pipeline.processor import ProcessingWorker  # noqa: E402
from video_analysis.ui.session_panel import SessionPanel  # noqa: E402
from video_analysis.ui.video_panel import VideoPanel  # noqa: E402
from video_analysis.ui.tagger_panel import TaggerPanel  # noqa: E402
from video_analysis.ui.player_confirm_dialog import PlayerConfirmDialog  # noqa: E402
from video_analysis.ui.export_dialog import ExportDialog  # noqa: E402
from video_analysis.db.video_database import get_session, get_session_players  # noqa: E402


_LOGO_PATH = os.path.join(_ROOT, "assets", "logo.png")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()

        self.setWindowTitle("Dapto Canaries — Video Analysis")
        self.setMinimumSize(1400, 800)
        self.resize(1600, 900)

        if os.path.isfile(_LOGO_PATH):
            self.setWindowIcon(QIcon(_LOGO_PATH))

        self._worker: ProcessingWorker | None = None
        self._current_session_id: int | None = None

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: Session panel ───────────────────────────────────────────────
        self._session_panel = SessionPanel()
        self._session_panel.setMinimumWidth(280)
        self._session_panel.setMaximumWidth(380)

        self._session_panel.load_video_requested.connect(self._start_processing)
        self._session_panel.session_selected.connect(self._on_session_selected)
        self._session_panel.confirm_players_clicked.connect(self._open_confirm_dialog)
        # Override the stop_requested slot
        self._session_panel.stop_requested = self._stop_processing

        # ── Centre: Video panel ───────────────────────────────────────────────
        self._video_panel = VideoPanel()
        self._video_panel.tag_requested.connect(self._on_tag_requested)
        self._video_panel.event_type_changed.connect(
            self._tagger_panel_placeholder
        )
        self._video_panel.team_side_changed.connect(
            self._tagger_panel_side_placeholder
        )

        # ── Right: Tagger panel ───────────────────────────────────────────────
        self._tagger_panel = TaggerPanel()
        self._tagger_panel.setMinimumWidth(260)
        self._tagger_panel.setMaximumWidth(360)
        self._tagger_panel.export_requested.connect(self._open_export_dialog)

        # Wire video panel shortcuts to tagger
        self._video_panel.event_type_changed.connect(
            self._tagger_panel.set_event_type
        )
        self._video_panel.team_side_changed.connect(
            self._tagger_panel.set_team_side
        )

        splitter.addWidget(self._session_panel)
        splitter.addWidget(self._video_panel)
        splitter.addWidget(self._tagger_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        main_layout.addWidget(splitter)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready — load a video to begin")

    # ── Processing ────────────────────────────────────────────────────────────

    def _start_processing(self, file_path: str):
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Busy",
                                "A video is already being processed. Stop it first.")
            return

        self._worker = ProcessingWorker(file_path)
        self._worker.progress.connect(self._session_panel.set_progress)
        self._worker.status_message.connect(self._session_panel.set_status)
        self._worker.status_message.connect(self._status_bar.showMessage)
        self._worker.frame_ready.connect(self._video_panel.show_jpeg_preview)
        self._worker.finished.connect(self._on_processing_finished)
        self._worker.error.connect(self._on_processing_error)

        self._session_panel.set_processing(True)
        self._worker.start()

    def _stop_processing(self):
        if self._worker:
            self._worker.stop()
            self._session_panel.set_processing(False)
            self._status_bar.showMessage("Processing stopped.")

    def _on_processing_finished(self, session_id: int):
        self._session_panel.set_processing(False)
        self._session_panel.on_processing_finished(session_id)
        self._status_bar.showMessage(
            f"Processing complete — session {session_id}. "
            "Click 'Confirm Players' to review OCR results."
        )
        self._on_session_selected(session_id)

    def _on_processing_error(self, msg: str):
        self._session_panel.set_processing(False)
        self._status_bar.showMessage(f"Error: {msg}")
        QMessageBox.critical(self, "Processing Error", msg)

    # ── Session selection ─────────────────────────────────────────────────────

    def _on_session_selected(self, session_id: int):
        self._current_session_id = session_id
        session = get_session(session_id)
        if session and session.get("status") == "done":
            fps = session.get("fps") or 25.0
            total = session.get("total_frames") or 0
            self._video_panel.load_video(
                session["file_path"], session_id, total, fps
            )
            confirmed = self._build_jersey_map(session_id)
            self._video_panel.set_confirmed_jerseys(confirmed)
            self._tagger_panel.load_session(session_id)

    # ── Dialogs ───────────────────────────────────────────────────────────────

    def _open_confirm_dialog(self, session_id: int):
        dlg = PlayerConfirmDialog(session_id, parent=self)
        if dlg.exec():
            # Refresh jersey overlays after confirmation
            confirmed = self._build_jersey_map(session_id)
            self._video_panel.set_confirmed_jerseys(confirmed)
            self._tagger_panel.load_session(session_id)
            self._status_bar.showMessage("Player identities confirmed.")

    def _open_export_dialog(self, session_id: int):
        dlg = ExportDialog(session_id, parent=self)
        dlg.exec()

    def _on_tag_requested(self, frame_num: int, timestamp: float):
        self._tagger_panel.update_frame(frame_num, timestamp)
        self._tagger_panel._on_tag()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_jersey_map(session_id: int) -> dict[int, str]:
        """Build {track_id: '#7 (H)'} map for overlay display."""
        players = get_session_players(session_id)
        result: dict[int, str] = {}
        for p in players:
            if p.get("jersey_number"):
                side_char = (p.get("team_side") or "?")[0].upper()
                result[p["track_id"]] = f"#{p['jersey_number']} ({side_char})"
        return result

    # Placeholder slots (replaced by real wiring above)
    def _tagger_panel_placeholder(self, _): pass
    def _tagger_panel_side_placeholder(self, _): pass
