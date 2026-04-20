"""
Left panel — Session Manager.

Shows:
  - Load video button + file path display
  - Processing progress bar + status label
  - Scrollable list of past sessions
  - "Link to match" dropdown
  - "Player Confirm" button (post-processing)
"""
from __future__ import annotations

import os
import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QFileDialog, QListWidget, QListWidgetItem,
    QComboBox, QGroupBox, QMessageBox,
)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from database import get_conn  # noqa: E402
from video_analysis.db.video_database import (  # noqa: E402
    get_all_sessions, link_session_to_match, delete_session
)


class SessionPanel(QWidget):
    """Emits signals to the main window when user actions require pipeline/UI updates."""

    load_video_requested   = pyqtSignal(str)          # file_path
    session_selected       = pyqtSignal(int)          # session_id
    confirm_players_clicked = pyqtSignal(int)         # session_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_session_id: int | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # ── Load video ────────────────────────────────────────────────────────
        load_group = QGroupBox("Load Video")
        load_layout = QVBoxLayout(load_group)

        self._file_label = QLabel("No file selected")
        self._file_label.setWordWrap(True)
        self._file_label.setStyleSheet("color: #aaa; font-size: 11px;")

        self._load_btn = QPushButton("Browse…")
        self._load_btn.clicked.connect(self._on_browse)

        load_layout.addWidget(self._load_btn)
        load_layout.addWidget(self._file_label)
        layout.addWidget(load_group)

        # ── Progress ──────────────────────────────────────────────────────────
        prog_group = QGroupBox("Processing")
        prog_layout = QVBoxLayout(prog_group)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)

        self._status_label = QLabel("Idle")
        self._status_label.setStyleSheet("font-size: 11px; color: #ccc;")
        self._status_label.setWordWrap(True)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.stop_requested)

        prog_layout.addWidget(self._progress_bar)
        prog_layout.addWidget(self._status_label)
        prog_layout.addWidget(self._stop_btn)
        layout.addWidget(prog_group)

        # ── Session list ──────────────────────────────────────────────────────
        sess_group = QGroupBox("Video Sessions")
        sess_layout = QVBoxLayout(sess_group)

        self._session_list = QListWidget()
        self._session_list.setMinimumHeight(180)
        self._session_list.currentItemChanged.connect(self._on_session_selected)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_sessions)

        delete_btn = QPushButton("Delete Session")
        delete_btn.setStyleSheet("color: #e55;")
        delete_btn.clicked.connect(self._on_delete_session)

        sess_layout.addWidget(self._session_list)
        btn_row = QHBoxLayout()
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(delete_btn)
        sess_layout.addLayout(btn_row)
        layout.addWidget(sess_group)

        # ── Link to match ─────────────────────────────────────────────────────
        link_group = QGroupBox("Link to Match")
        link_layout = QVBoxLayout(link_group)

        self._match_combo = QComboBox()
        self._match_combo.addItem("— select match —", None)

        link_btn = QPushButton("Link")
        link_btn.clicked.connect(self._on_link_match)

        link_layout.addWidget(self._match_combo)
        link_layout.addWidget(link_btn)
        layout.addWidget(link_group)

        # ── Player confirm ────────────────────────────────────────────────────
        self._confirm_btn = QPushButton("Confirm Players…")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._on_confirm_players)
        layout.addWidget(self._confirm_btn)

        layout.addStretch()

        self.refresh_sessions()
        self._refresh_matches()

    # ── public slots ─────────────────────────────────────────────────────────

    def set_progress(self, value: int):
        self._progress_bar.setValue(value)

    def set_status(self, text: str):
        self._status_label.setText(text)

    def set_processing(self, active: bool):
        self._load_btn.setEnabled(not active)
        self._stop_btn.setEnabled(active)

    def refresh_sessions(self):
        self._session_list.clear()
        for sess in get_all_sessions():
            label = self._session_label(sess)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, sess["id"])
            self._session_list.addItem(item)

    def on_processing_finished(self, session_id: int):
        self.refresh_sessions()
        self._current_session_id = session_id
        self._confirm_btn.setEnabled(True)
        # Auto-select the finished session
        for i in range(self._session_list.count()):
            if self._session_list.item(i).data(Qt.ItemDataRole.UserRole) == session_id:
                self._session_list.setCurrentRow(i)
                break

    # ── internal ─────────────────────────────────────────────────────────────

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video File", "",
            "Video Files (*.mp4 *.avi *.mkv *.mov *.ts *.wmv);;All Files (*)"
        )
        if path:
            self._file_label.setText(os.path.basename(path))
            self.load_video_requested.emit(path)

    def _on_session_selected(self, current, _previous):
        if current is None:
            return
        sid = current.data(Qt.ItemDataRole.UserRole)
        self._current_session_id = sid
        self._confirm_btn.setEnabled(True)
        self.session_selected.emit(sid)

    def _on_delete_session(self):
        if self._current_session_id is None:
            return
        reply = QMessageBox.question(
            self, "Delete Session",
            "Delete this session and all its detections, events, and stats?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_session(self._current_session_id)
            self._current_session_id = None
            self.refresh_sessions()

    def _on_link_match(self):
        if self._current_session_id is None:
            QMessageBox.warning(self, "No session", "Select a session first.")
            return
        match_id = self._match_combo.currentData()
        if match_id is None:
            QMessageBox.warning(self, "No match", "Select a match to link.")
            return
        link_session_to_match(self._current_session_id, match_id)
        QMessageBox.information(self, "Linked", "Session linked to match.")
        self.refresh_sessions()

    def _on_confirm_players(self):
        if self._current_session_id is not None:
            self.confirm_players_clicked.emit(self._current_session_id)

    def _refresh_matches(self):
        self._match_combo.clear()
        self._match_combo.addItem("— select match —", None)
        conn = get_conn()
        rows = conn.execute("""
            SELECT m.id, m.round, m.match_date, ht.name, at.name
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.id
            JOIN teams at ON m.away_team_id = at.id
            ORDER BY m.round DESC
        """).fetchall()
        conn.close()
        for row in rows:
            label = f"Rd {row[1]}  {row[3]} vs {row[4]}  ({row[2] or 'no date'})"
            self._match_combo.addItem(label, row[0])

    @staticmethod
    def _session_label(sess: dict) -> str:
        status = sess.get("status", "?")
        name = sess.get("file_name", "unknown")
        match_info = ""
        if sess.get("round"):
            match_info = f"  |  Rd {sess['round']} {sess.get('home_team','')} vs {sess.get('away_team','')}"
        dur = sess.get("duration_secs")
        dur_str = f"  {int(dur//60)}:{int(dur%60):02d}" if dur else ""
        return f"[{status.upper()}]  {name}{dur_str}{match_info}"

    # stop_requested is connected externally to the worker
    def stop_requested(self):
        pass  # overridden in main_window
