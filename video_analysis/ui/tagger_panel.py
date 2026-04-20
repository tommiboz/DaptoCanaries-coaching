"""
Right panel — Event Tagger.

Controls:
  - Event type selector (radio buttons + keyboard shortcut display)
  - Team side selector (Home / Away)
  - Primary + secondary player dropdowns
  - Tag button
  - Scrollable event log with delete
  - "Derive Stats & Export" button
"""
from __future__ import annotations

import os
import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QScrollArea, QFrame, QButtonGroup,
    QRadioButton, QMessageBox, QSizePolicy,
)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from video_analysis.utils.constants import EVENT_TYPES, EVENT_LABELS, TEAM_HOME, TEAM_AWAY  # noqa: E402
from video_analysis.db.video_database import (  # noqa: E402
    get_session_players, get_session_events, insert_event, delete_event
)


class TaggerPanel(QWidget):
    """
    Signals:
        export_requested(int)  — session_id, user wants to open export dialog
    """

    export_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session_id: int | None = None
        self._players: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # ── Event type ────────────────────────────────────────────────────────
        type_group = QGroupBox("Event Type")
        type_layout = QVBoxLayout(type_group)
        self._type_btn_group = QButtonGroup(self)

        for i, etype in enumerate(EVENT_TYPES):
            rb = QRadioButton(f"{i+1}  {EVENT_LABELS[etype]}")
            rb.setProperty("event_type", etype)
            self._type_btn_group.addButton(rb)
            type_layout.addWidget(rb)
            if i == 0:
                rb.setChecked(True)

        layout.addWidget(type_group)

        # ── Team side ─────────────────────────────────────────────────────────
        team_group = QGroupBox("Team  (H=Home  A=Away)")
        team_layout = QHBoxLayout(team_group)
        self._team_btn_group = QButtonGroup(self)

        self._home_rb = QRadioButton("Home")
        self._away_rb = QRadioButton("Away")
        self._home_rb.setChecked(True)
        self._team_btn_group.addButton(self._home_rb)
        self._team_btn_group.addButton(self._away_rb)
        team_layout.addWidget(self._home_rb)
        team_layout.addWidget(self._away_rb)
        layout.addWidget(team_group)

        # ── Players ───────────────────────────────────────────────────────────
        player_group = QGroupBox("Players")
        player_layout = QVBoxLayout(player_group)

        player_layout.addWidget(QLabel("Primary Player:"))
        self._primary_combo = QComboBox()
        player_layout.addWidget(self._primary_combo)

        player_layout.addWidget(QLabel("Secondary Player (optional):"))
        self._secondary_combo = QComboBox()
        self._secondary_combo.addItem("— none —", None)
        player_layout.addWidget(self._secondary_combo)
        layout.addWidget(player_group)

        # ── Tag button ────────────────────────────────────────────────────────
        self._tag_btn = QPushButton("Tag Event  [T]")
        self._tag_btn.setStyleSheet(
            "background: #2a7a2a; color: white; font-size: 14px; "
            "font-weight: bold; padding: 8px;"
        )
        self._tag_btn.setEnabled(False)
        self._tag_btn.clicked.connect(self._on_tag)
        layout.addWidget(self._tag_btn)

        # ── Event log ─────────────────────────────────────────────────────────
        log_group = QGroupBox("Tagged Events")
        log_layout = QVBoxLayout(log_group)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(200)

        self._log_widget = QWidget()
        self._log_layout = QVBoxLayout(self._log_widget)
        self._log_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._log_layout.setSpacing(2)
        scroll.setWidget(self._log_widget)

        log_layout.addWidget(scroll)
        layout.addWidget(log_group)

        # ── Export button ─────────────────────────────────────────────────────
        self._export_btn = QPushButton("Derive Stats & Export…")
        self._export_btn.setStyleSheet(
            "background: #1a4a8a; color: white; font-size: 13px; padding: 6px;"
        )
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export)
        layout.addWidget(self._export_btn)

        layout.addStretch()

        self._frame_num = 0
        self._timestamp = 0.0

    # ── Public API ────────────────────────────────────────────────────────────

    def load_session(self, session_id: int):
        self._session_id = session_id
        self._tag_btn.setEnabled(True)
        self._export_btn.setEnabled(True)
        self._refresh_players()
        self._refresh_log()

    def update_frame(self, frame_num: int, timestamp: float):
        """Called when the video panel advances to a new frame."""
        self._frame_num = frame_num
        self._timestamp = timestamp

    def set_event_type(self, etype: str):
        """Called from keyboard shortcut in video panel."""
        for btn in self._type_btn_group.buttons():
            if btn.property("event_type") == etype:
                btn.setChecked(True)
                break

    def set_team_side(self, side: str):
        """Called from keyboard shortcut (H/A) in video panel."""
        if side == TEAM_HOME:
            self._home_rb.setChecked(True)
        else:
            self._away_rb.setChecked(True)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _active_event_type(self) -> str:
        btn = self._type_btn_group.checkedButton()
        return btn.property("event_type") if btn else EVENT_TYPES[0]

    def _active_team_side(self) -> str:
        return TEAM_HOME if self._home_rb.isChecked() else TEAM_AWAY

    def _on_tag(self):
        if self._session_id is None:
            return
        etype = self._active_event_type()
        side = self._active_team_side()
        primary_id = self._primary_combo.currentData()
        secondary_id = self._secondary_combo.currentData()

        insert_event(
            session_id=self._session_id,
            frame_number=self._frame_num,
            timestamp_secs=self._timestamp,
            event_type=etype,
            team_side=side,
            primary_player_id=primary_id,
            secondary_player_id=secondary_id,
        )
        self._refresh_log()

    def _on_export(self):
        if self._session_id is not None:
            self.export_requested.emit(self._session_id)

    def _refresh_players(self):
        if self._session_id is None:
            return
        self._players = get_session_players(self._session_id)

        self._primary_combo.clear()
        self._primary_combo.addItem("— unknown —", None)
        self._secondary_combo.clear()
        self._secondary_combo.addItem("— none —", None)

        for p in self._players:
            jersey = p.get("jersey_number") or "?"
            side = (p.get("team_side") or "?")[0].upper()
            name = p.get("player_name") or f"Track {p['track_id']}"
            label = f"#{jersey} ({side}) {name}"
            self._primary_combo.addItem(label, p["id"])
            self._secondary_combo.addItem(label, p["id"])

    def _refresh_log(self):
        # Clear existing
        while self._log_layout.count():
            item = self._log_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._session_id is None:
            return

        events = get_session_events(self._session_id)
        for ev in reversed(events):
            row = self._make_event_row(ev)
            self._log_layout.addWidget(row)

    def _make_event_row(self, ev: dict) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("background: #2a2a2a; border-radius: 3px;")
        row = QHBoxLayout(frame)
        row.setContentsMargins(4, 2, 4, 2)

        ts = ev.get("timestamp_secs", 0)
        time_str = f"{int(ts//60)}:{int(ts%60):02d}"
        side = (ev.get("team_side") or "?")[0].upper()
        etype = EVENT_LABELS.get(ev["event_type"], ev["event_type"])
        p1 = ev.get("primary_jersey")
        label_text = f"{time_str}  [{side}]  {etype}"
        if p1:
            label_text += f"  #{p1}"

        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #ddd; font-size: 11px;")
        row.addWidget(lbl, stretch=1)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(22, 22)
        del_btn.setStyleSheet("color: #e55; border: none; font-weight: bold;")
        ev_id = ev["id"]
        del_btn.clicked.connect(lambda _, eid=ev_id: self._delete_event(eid))
        row.addWidget(del_btn)

        return frame

    def _delete_event(self, event_id: int):
        delete_event(event_id)
        self._refresh_log()
