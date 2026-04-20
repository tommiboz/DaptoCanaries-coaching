"""
Player Confirm Dialog.

After processing, the coach reviews every tracked player:
  - See a strip of thumbnails from across the match
  - Confirm or correct the OCR jersey number
  - Assign team side if not already set
  - Optionally link to a known player in the players table
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QComboBox, QScrollArea, QWidget, QFrame,
    QDialogButtonBox, QGroupBox,
)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from database import get_conn  # noqa: E402
from video_analysis.db.video_database import (  # noqa: E402
    get_unconfirmed_players, get_session_players, confirm_player,
    get_session,
)
from video_analysis.pipeline.ingest import open_capture  # noqa: E402
from video_analysis.utils.frame_utils import make_thumbnail  # noqa: E402
from video_analysis.utils.constants import TEAM_HOME, TEAM_AWAY  # noqa: E402


class PlayerConfirmDialog(QDialog):
    """
    Modal dialog showing each unconfirmed track with its OCR suggestion.
    Coach can accept or override the jersey number and team side.
    """

    def __init__(self, session_id: int, parent=None):
        super().__init__(parent)
        self.session_id = session_id
        self._players = get_unconfirmed_players(session_id)
        self._session = get_session(session_id)
        self._known_players = self._load_known_players()

        self.setWindowTitle("Confirm Player Identities")
        self.setMinimumSize(800, 600)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(
            f"Review and confirm jersey numbers for {len(self._players)} tracked players.\n"
            "OCR accuracy is 55-70% on broadcast footage — please verify each entry."
        )
        header.setWordWrap(True)
        header.setStyleSheet("color: #aaa; padding: 4px;")
        layout.addWidget(header)

        # Scrollable player list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._player_layout = QVBoxLayout(container)
        self._player_layout.setSpacing(6)
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        # Build a row per player
        self._rows: list[dict] = []
        for player in self._players:
            row_widget, row_data = self._build_player_row(player)
            self._player_layout.addWidget(row_widget)
            self._rows.append(row_data)

        self._player_layout.addStretch()

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _build_player_row(self, player: dict) -> tuple[QFrame, dict]:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("background: #2a2a2a; border-radius: 4px; padding: 4px;")
        row = QHBoxLayout(frame)
        row.setContentsMargins(6, 6, 6, 6)

        # Thumbnail strip (up to 3 frames)
        thumb_box = QHBoxLayout()
        thumb_box.setSpacing(2)
        self._add_thumbnails(thumb_box, player)
        thumb_frame = QWidget()
        thumb_frame.setLayout(thumb_box)
        thumb_frame.setFixedWidth(250)
        row.addWidget(thumb_frame)

        # Track info
        info = QVBoxLayout()
        ocr_conf = player.get("ocr_confidence") or 0
        track_label = QLabel(
            f"Track ID: {player['track_id']}\n"
            f"OCR suggestion: #{player.get('jersey_number') or '?'} "
            f"(confidence: {ocr_conf:.0%})"
        )
        track_label.setStyleSheet("color: #ccc; font-size: 11px;")
        info.addWidget(track_label)

        # Jersey number spin box
        jersey_row = QHBoxLayout()
        jersey_row.addWidget(QLabel("Jersey #:"))
        jersey_spin = QSpinBox()
        jersey_spin.setRange(1, 20)
        jersey_spin.setValue(player.get("jersey_number") or 1)
        jersey_row.addWidget(jersey_spin)
        info.addLayout(jersey_row)

        # Team side
        side_row = QHBoxLayout()
        side_row.addWidget(QLabel("Team:"))
        side_combo = QComboBox()
        side_combo.addItem("Home", TEAM_HOME)
        side_combo.addItem("Away", TEAM_AWAY)
        current_side = player.get("team_side") or TEAM_HOME
        side_combo.setCurrentIndex(0 if current_side == TEAM_HOME else 1)
        side_row.addWidget(side_combo)
        info.addLayout(side_row)

        # Known player link
        known_row = QHBoxLayout()
        known_row.addWidget(QLabel("Player:"))
        known_combo = QComboBox()
        known_combo.addItem("— Unknown —", None)
        for p in self._known_players:
            known_combo.addItem(f"#{p['jersey']} {p['name']}", p["id"])
        known_row.addWidget(known_combo)
        info.addLayout(known_row)

        row.addLayout(info, stretch=1)

        row_data = {
            "player_id": player["id"],
            "jersey_spin": jersey_spin,
            "side_combo": side_combo,
            "known_combo": known_combo,
        }
        return frame, row_data

    def _add_thumbnails(self, layout: QHBoxLayout, player: dict):
        """Try to grab 3 thumbnail frames from DB detections for this track."""
        conn = get_conn()
        sample_frames = conn.execute("""
            SELECT frame_number, x1, y1, x2, y2
            FROM video_detections
            WHERE session_id=? AND track_id=?
            ORDER BY frame_number
            LIMIT 3
        """, (self.session_id, player["track_id"])).fetchall()
        conn.close()

        if not sample_frames or not self._session:
            placeholder = QLabel("No\nthumb")
            placeholder.setFixedSize(80, 160)
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("background:#444; color:#888;")
            layout.addWidget(placeholder)
            return

        try:
            cap = open_capture(self._session["file_path"])
            for sf in sample_frames:
                cap.set(cv2.CAP_PROP_POS_FRAMES, sf[0])
                ret, frame = cap.read()
                if ret:
                    thumb = make_thumbnail(frame, int(sf[1]), int(sf[2]),
                                          int(sf[3]), int(sf[4]))
                    label = self._ndarray_to_qlabel(thumb)
                    layout.addWidget(label)
            cap.release()
        except Exception:
            pass

    @staticmethod
    def _ndarray_to_qlabel(arr: np.ndarray) -> QLabel:
        rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        lbl = QLabel()
        lbl.setPixmap(QPixmap.fromImage(img))
        lbl.setFixedSize(w, h)
        return lbl

    def _on_accept(self):
        for row in self._rows:
            jersey = row["jersey_spin"].value()
            side = row["side_combo"].currentData()
            linked = row["known_combo"].currentData()
            confirm_player(row["player_id"], jersey, side, linked)
        self.accept()

    def _load_known_players(self) -> list[dict]:
        conn = get_conn()
        rows = conn.execute(
            "SELECT id, name, jersey FROM players WHERE active=1 ORDER BY jersey"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
