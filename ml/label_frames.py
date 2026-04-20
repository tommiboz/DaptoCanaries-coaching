"""
Step 2 — Label extracted frames.

Opens each frame in a window. Press a key to label it and move it to the
correct class folder. Press 'd' to skip/delete useless frames.

Controls:
    0  penalty            7  sin_bin
    1  10m                8  send_off
    2  offside            9  try
    3  high_tackle        a  no_try
    4  knock_on           b  obstruction
    5  forward_pass       c  hand_on_ball
    6  held               e  strip
                          n  no_signal
    d  delete/skip (not useful)
    q  quit and save progress

Usage:
    python ml/label_frames.py
    python ml/label_frames.py --video rugby_referee_hand_signals
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import cv2

ROOT       = Path(__file__).parent.parent
FRAMES_DIR = ROOT / "ml" / "data" / "frames"
LABELED_DIR = ROOT / "ml" / "data" / "labeled"
DELETED_DIR = ROOT / "ml" / "data" / "deleted"

SIGNAL_CLASSES = [
    "penalty",
    "10m",
    "offside",
    "high_tackle",
    "knock_on",
    "forward_pass",
    "held",
    "sin_bin",
    "send_off",
    "try",
    "no_try",
    "obstruction",
    "hand_on_ball",
    "strip",
    "no_signal",
]

# Key → class index mapping
KEY_MAP: dict[int, str] = {
    ord("0"): "penalty",
    ord("1"): "10m",
    ord("2"): "offside",
    ord("3"): "high_tackle",
    ord("4"): "knock_on",
    ord("5"): "forward_pass",
    ord("6"): "held",
    ord("7"): "sin_bin",
    ord("8"): "send_off",
    ord("9"): "try",
    ord("a"): "no_try",
    ord("b"): "obstruction",
    ord("c"): "hand_on_ball",
    ord("e"): "strip",
    ord("n"): "no_signal",
    ord("d"): "__delete__",
    ord("q"): "__quit__",
}


def get_unlabeled_frames(video_filter: str | None) -> list[Path]:
    """Collect all frames not yet labeled or deleted."""
    all_frames: list[Path] = []

    if video_filter:
        dirs = [FRAMES_DIR / video_filter]
    else:
        dirs = sorted(FRAMES_DIR.iterdir()) if FRAMES_DIR.exists() else []

    for d in dirs:
        if d.is_dir():
            all_frames.extend(sorted(d.glob("*.jpg")))

    # Filter out already-labeled frames
    labeled = {p.name for cls in SIGNAL_CLASSES for p in (LABELED_DIR / cls).glob("*.jpg")} if LABELED_DIR.exists() else set()
    deleted = {p.name for p in DELETED_DIR.glob("*.jpg")} if DELETED_DIR.exists() else set()

    return [f for f in all_frames if f.name not in labeled and f.name not in deleted]


def draw_overlay(frame, label_text: str, current: int, total: int):
    """Draw help overlay on frame."""
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 120), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    cv2.putText(frame, f"Frame {current}/{total}", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, label_text, (10, 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 100), 2)

    hint = "0=penalty 1=10m 2=offside 3=high_tackle 4=knock_on 5=forward_pass 6=held"
    hint2 = "7=sin_bin 8=send_off 9=try a=no_try b=obstruct c=hand_on_ball e=strip n=no_signal"
    hint3 = "d=skip/delete   q=quit"
    cv2.putText(frame, hint,  (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    cv2.putText(frame, hint2, (10, 98), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    cv2.putText(frame, hint3, (10, 116), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 50), 1)
    return frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default=None,
                        help="Only label frames from this video folder name")
    args = parser.parse_args()

    # Create output dirs
    for cls in SIGNAL_CLASSES:
        (LABELED_DIR / cls).mkdir(parents=True, exist_ok=True)
    DELETED_DIR.mkdir(parents=True, exist_ok=True)

    frames = get_unlabeled_frames(args.video)

    if not frames:
        print("No unlabeled frames found.")
        print(f"Run  python ml/collect_signal_frames.py  first.")
        sys.exit(0)

    print(f"Found {len(frames)} unlabeled frames.")
    print("Press keys to label frames. Press 'q' to quit and save progress.\n")

    labeled_count = 0
    deleted_count = 0

    cv2.namedWindow("Referee Signal Labeler", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Referee Signal Labeler", 960, 600)

    for i, frame_path in enumerate(frames):
        frame = cv2.imread(str(frame_path))
        if frame is None:
            continue

        label_text = f"Video: {frame_path.parent.name} | File: {frame_path.name}"
        display = draw_overlay(frame.copy(), label_text, i + 1, len(frames))

        cv2.imshow("Referee Signal Labeler", display)

        while True:
            key = cv2.waitKey(0) & 0xFF

            if key not in KEY_MAP:
                continue

            action = KEY_MAP[key]

            if action == "__quit__":
                print(f"\nStopped. Labeled: {labeled_count} | Deleted: {deleted_count}")
                cv2.destroyAllWindows()
                _print_summary()
                sys.exit(0)

            if action == "__delete__":
                shutil.move(str(frame_path), str(DELETED_DIR / frame_path.name))
                deleted_count += 1
                break

            # Label it
            dest = LABELED_DIR / action / f"{frame_path.parent.name}_{frame_path.name}"
            shutil.copy2(str(frame_path), str(dest))
            shutil.move(str(frame_path), str(DELETED_DIR / f"_done_{frame_path.name}"))
            labeled_count += 1
            print(f"  [{i+1}/{len(frames)}] {action:20s} ← {frame_path.name}")
            break

    cv2.destroyAllWindows()
    print(f"\nAll done. Labeled: {labeled_count} | Deleted: {deleted_count}")
    _print_summary()


def _print_summary():
    print("\nLabeled frames per class:")
    for cls in SIGNAL_CLASSES:
        cls_dir = LABELED_DIR / cls
        count = len(list(cls_dir.glob("*.jpg"))) if cls_dir.exists() else 0
        bar = "█" * (count // 5)
        print(f"  {cls:20s} {count:4d}  {bar}")
    print(f"\nNext step: python ml/train_signal_classifier.py")


if __name__ == "__main__":
    main()
