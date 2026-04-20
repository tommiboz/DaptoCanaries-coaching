"""
Video Analysis entry point.

Run with:
    python -m video_analysis.app
or double-click launch_video_analysis.bat
"""
from __future__ import annotations

import os
import sys

# Ensure the project root is on sys.path regardless of how this is launched
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import torch
from PyQt6.QtWidgets import QApplication, QMessageBox

from database import init_db  # noqa: E402
from video_analysis.ui.main_window import MainWindow  # noqa: E402


def check_cuda_warning(app: QApplication):
    """Warn the coach if no GPU is detected."""
    if not torch.cuda.is_available():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("No GPU Detected")
        msg.setText(
            "CUDA / GPU not found.\n\n"
            "Video processing will run on CPU and may take 2+ hours per match.\n"
            "Consider running overnight or on a machine with an NVIDIA GPU."
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()


def main():
    init_db()
    app = QApplication(sys.argv)
    app.setApplicationName("Dapto Canaries Video Analysis")
    app.setOrganizationName("Dapto Canaries RLFC")

    # Apply dark stylesheet
    app.setStyleSheet(_dark_stylesheet())

    check_cuda_warning(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


def _dark_stylesheet() -> str:
    return """
    QWidget {
        background-color: #1e1e1e;
        color: #dcdcdc;
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 12px;
    }
    QGroupBox {
        border: 1px solid #444;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 4px;
        font-weight: bold;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 8px;
        color: #FFD700;
    }
    QPushButton {
        background-color: #3a3a3a;
        border: 1px solid #555;
        border-radius: 4px;
        padding: 4px 10px;
        color: #dcdcdc;
    }
    QPushButton:hover {
        background-color: #4a4a4a;
        border-color: #FFD700;
    }
    QPushButton:disabled {
        color: #666;
        background-color: #2a2a2a;
    }
    QProgressBar {
        border: 1px solid #444;
        border-radius: 3px;
        text-align: center;
        background-color: #2a2a2a;
    }
    QProgressBar::chunk {
        background-color: #FFD700;
        border-radius: 2px;
    }
    QListWidget, QTableWidget {
        background-color: #252525;
        border: 1px solid #444;
        alternate-background-color: #2a2a2a;
    }
    QListWidget::item:selected, QTableWidget::item:selected {
        background-color: #1a3a6a;
    }
    QComboBox, QSpinBox {
        background-color: #2a2a2a;
        border: 1px solid #555;
        border-radius: 3px;
        padding: 2px 6px;
    }
    QSlider::groove:horizontal {
        height: 4px;
        background: #444;
        border-radius: 2px;
    }
    QSlider::handle:horizontal {
        background: #FFD700;
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }
    QScrollBar:vertical {
        background: #2a2a2a;
        width: 10px;
    }
    QScrollBar::handle:vertical {
        background: #555;
        border-radius: 4px;
        min-height: 20px;
    }
    QStatusBar {
        background-color: #161616;
        border-top: 1px solid #333;
    }
    """


if __name__ == "__main__":
    main()
