"""
Export Dialog — Derive Stats & Export to match_stats.

Shows:
  - Video-derived stats vs existing manual stats side by side
  - Team side assignment (which DB team_id maps to 'home'/'away')
  - Merge or Replace toggle
  - Confirm export button
"""
from __future__ import annotations

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QDialogButtonBox, QRadioButton, QButtonGroup, QMessageBox,
)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from database import get_conn  # noqa: E402
from video_analysis.db.export import (  # noqa: E402
    derive_stats_from_events, export_to_match_stats, preview_export
)


class ExportDialog(QDialog):
    """
    Two-step dialog:
      1. Derive stats from events (auto on open)
      2. Review and confirm export
    """

    def __init__(self, session_id: int, parent=None):
        super().__init__(parent)
        self.session_id = session_id
        self.setWindowTitle("Derive Stats & Export to Coaching Hub")
        self.setMinimumSize(900, 600)

        self._teams = self._load_teams()
        self._derived: dict = {}
        self._existing: list[dict] = []
        self._session: dict = {}

        self._build_ui()
        self._run_derivation()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QLabel(
            "Stats are automatically derived from your tagged events. "
            "Review them against any existing manual stats, then export."
        )
        hdr.setWordWrap(True)
        hdr.setStyleSheet("color: #aaa;")
        layout.addWidget(hdr)

        # ── Team mapping ──────────────────────────────────────────────────────
        map_group = QGroupBox("Team Assignment")
        map_layout = QHBoxLayout(map_group)

        map_layout.addWidget(QLabel("Home side in video ="))
        self._home_team_combo = QComboBox()
        for t in self._teams:
            self._home_team_combo.addItem(t["name"], t["id"])
        map_layout.addWidget(self._home_team_combo)

        map_layout.addWidget(QLabel("    Away side in video ="))
        self._away_team_combo = QComboBox()
        for t in self._teams:
            self._away_team_combo.addItem(t["name"], t["id"])
        if len(self._teams) > 1:
            self._away_team_combo.setCurrentIndex(1)
        map_layout.addWidget(self._away_team_combo)

        layout.addWidget(map_group)

        # ── Stats comparison table ────────────────────────────────────────────
        table_group = QGroupBox("Stats Comparison")
        table_layout = QVBoxLayout(table_group)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels([
            "Stat", "Video (Home)", "Video (Away)", "Existing (manual)"
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table_layout.addWidget(self._table)
        layout.addWidget(table_group, stretch=1)

        # ── Merge / Replace ───────────────────────────────────────────────────
        mode_group = QGroupBox("Export Mode")
        mode_layout = QHBoxLayout(mode_group)
        self._mode_group = QButtonGroup(self)

        self._replace_rb = QRadioButton("Replace — insert new match_stats row(s)")
        self._merge_rb = QRadioButton("Merge — add video counts to existing rows")
        self._replace_rb.setChecked(True)
        self._mode_group.addButton(self._replace_rb)
        self._mode_group.addButton(self._merge_rb)
        mode_layout.addWidget(self._replace_rb)
        mode_layout.addWidget(self._merge_rb)
        layout.addWidget(mode_group)

        # ── Side selection for export ─────────────────────────────────────────
        side_group = QGroupBox("Export Which Team")
        side_layout = QHBoxLayout(side_group)
        self._side_group = QButtonGroup(self)

        self._both_rb = QRadioButton("Both Home & Away")
        self._home_only_rb = QRadioButton("Home Only")
        self._away_only_rb = QRadioButton("Away Only")
        self._both_rb.setChecked(True)
        for rb in [self._both_rb, self._home_only_rb, self._away_only_rb]:
            self._side_group.addButton(rb)
            side_layout.addWidget(rb)
        layout.addWidget(side_group)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_box = QDialogButtonBox()
        self._export_btn = btn_box.addButton(
            "Export to Coaching Hub", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._export_btn.setStyleSheet(
            "background: #1a6a1a; color: white; font-weight: bold; padding: 6px 16px;"
        )
        self._export_btn.clicked.connect(self._on_export)

        cancel_btn = btn_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_box)

    def _run_derivation(self):
        """Derive stats from events and populate the comparison table."""
        try:
            self._derived = derive_stats_from_events(self.session_id)
            preview = preview_export(self.session_id)
            self._existing = preview.get("existing", [])
            self._session = preview.get("session") or {}
        except Exception as e:
            QMessageBox.warning(self, "Derivation Error", str(e))
            return

        self._populate_table()

    def _populate_table(self):
        stat_keys = [
            ("tries", "Tries"),
            ("tackles", "Tackles Made"),
            ("missed_tackles", "Missed Tackles"),
            ("linebreaks", "Linebreaks"),
            ("offloads", "Offloads"),
            ("errors", "Errors"),
            ("penalties", "Penalties"),
            ("kicks", "Kicks"),
        ]

        home_d = self._derived.get("home", {})
        away_d = self._derived.get("away", {})

        # Build existing summary per team_name
        existing_summary: dict[str, str] = {}
        for ex in self._existing:
            name = ex.get("team_name", "?")
            parts = [f"tries:{ex.get('tries',0)}", f"errors:{ex.get('errors',0)}"]
            existing_summary[name] = ", ".join(parts)

        self._table.setRowCount(len(stat_keys))
        for row_idx, (key, label) in enumerate(stat_keys):
            self._table.setItem(row_idx, 0, QTableWidgetItem(label))
            self._table.setItem(row_idx, 1,
                                QTableWidgetItem(str(home_d.get(key, 0))))
            self._table.setItem(row_idx, 2,
                                QTableWidgetItem(str(away_d.get(key, 0))))
            existing_cell = "; ".join(
                f"{n}: {v}" for n, v in existing_summary.items()
            ) if row_idx == 0 else ""
            self._table.setItem(row_idx, 3, QTableWidgetItem(existing_cell))

        self._table.resizeColumnsToContents()

    def _on_export(self):
        if not self._session.get("match_id"):
            QMessageBox.warning(
                self, "No Match Linked",
                "Please link this video session to a match first\n"
                "(use the Session panel on the left)."
            )
            return

        merge = self._merge_rb.isChecked()
        home_team_id = self._home_team_combo.currentData()
        away_team_id = self._away_team_combo.currentData()

        sides_to_export = []
        if self._both_rb.isChecked():
            sides_to_export = [("home", home_team_id), ("away", away_team_id)]
        elif self._home_only_rb.isChecked():
            sides_to_export = [("home", home_team_id)]
        else:
            sides_to_export = [("away", away_team_id)]

        errors: list[str] = []
        for side, team_id in sides_to_export:
            try:
                export_to_match_stats(self.session_id, side, team_id, merge=merge)
            except Exception as e:
                errors.append(f"{side}: {e}")

        if errors:
            QMessageBox.warning(self, "Export Errors", "\n".join(errors))
        else:
            QMessageBox.information(
                self, "Exported",
                "Stats exported successfully. "
                "The Streamlit hub will show them on next reload."
            )
            self.accept()

    def _load_teams(self) -> list[dict]:
        conn = get_conn()
        rows = conn.execute(
            "SELECT id, name, is_dapto FROM teams ORDER BY is_dapto DESC, name"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
