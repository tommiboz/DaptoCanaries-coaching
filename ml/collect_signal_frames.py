"""
Step 1 — Collect referee signal frames.

Downloads tutorial videos from YouTube and extracts frames at regular intervals.
Frames land in ml/data/frames/<video_name>/ ready for labelling.

Usage:
    python ml/collect_signal_frames.py

Requirements:
    pip install -r requirements_ml.txt
"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

import cv2

# ── Config ────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent.parent
VIDEOS_DIR = ROOT / "ml" / "data" / "raw_videos"
FRAMES_DIR = ROOT / "ml" / "data" / "frames"

# Frames to extract per second of video (2 = one frame every 0.5s)
FRAMES_PER_SECOND = 2

# YouTube videos covering rugby league referee signals
# Add more as you find them — any clear signal tutorial works
SIGNAL_VIDEOS = [
    {
        "url": "https://www.youtube.com/watch?v=yzHjsQk8ijM",
        "name": "rugby_referee_hand_signals",
        "description": "What Are Common Rugby Referee Hand Signals?",
    },
    {
        "url": "https://www.youtube.com/watch?v=V5OJi7TUTUw",
        "name": "rugby_signals_read_aloud",
        "description": "Rugby Full Referee Signals Read Aloud",
    },
    {
        "url": "https://www.youtube.com/watch?v=Uug9brXDj9A",
        "name": "referee_signals",
        "description": "Referee Signals",
    },
]

# ── Signal classes ────────────────────────────────────────────────────────────
SIGNAL_CLASSES = [
    "penalty",           # one arm raised, pointing direction
    "10m",               # arm sweep indicating retiring distance
    "offside",           # arm extended horizontal toward offending team
    "high_tackle",       # hand to own throat
    "knock_on",          # hand mimes knocking ball forward
    "forward_pass",      # both hands pushed forward
    "held",              # one arm straight up
    "sin_bin",           # 10 fingers spread (both hands)
    "send_off",          # point to touchline
    "try",               # both arms pointing to ground
    "no_try",            # arms waved horizontal
    "obstruction",       # arms crossed in front of chest
    "hand_on_ball",      # hand placed on palm of other hand
    "strip",             # pulling motion on sleeve
    "no_signal",         # background / no signal being made
]


def check_yt_dlp() -> bool:
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def download_video(url: str, output_path: Path) -> bool:
    """Download a YouTube video using yt-dlp. Returns True on success."""
    if output_path.exists():
        print(f"  Already downloaded: {output_path.name}")
        return True

    print(f"  Downloading: {url}")
    result = subprocess.run(
        [
            "yt-dlp",
            "--format", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
            "--merge-output-format", "mp4",
            "--output", str(output_path),
            url,
        ],
        capture_output=False,
    )
    return result.returncode == 0


def extract_frames(video_path: Path, output_dir: Path, fps_target: int = 2):
    """Extract frames from video at fps_target frames per second."""
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  ERROR: Could not open {video_path.name}")
        return 0

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_interval = max(1, int(video_fps / fps_target))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"  Video FPS: {video_fps:.1f} — extracting every {frame_interval} frames")
    print(f"  Total frames: {total_frames} → ~{total_frames // frame_interval} extracts")

    saved = 0
    frame_num = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_num % frame_interval == 0:
            out_path = output_dir / f"frame_{frame_num:06d}.jpg"
            if not out_path.exists():
                cv2.imwrite(str(out_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                saved += 1

        frame_num += 1

    cap.release()
    print(f"  Saved {saved} frames to {output_dir}")
    return saved


def main():
    print("=" * 60)
    print("  Referee Signal Frame Collector")
    print("=" * 60)

    # Check yt-dlp
    if not check_yt_dlp():
        print("\nERROR: yt-dlp not found.")
        print("Install it with:  pip install yt-dlp")
        sys.exit(1)

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    total_frames = 0

    for video in SIGNAL_VIDEOS:
        print(f"\n{'─' * 50}")
        print(f"Video: {video['description']}")

        video_path = VIDEOS_DIR / f"{video['name']}.mp4"
        frames_dir = FRAMES_DIR / video["name"]

        # Download
        if not download_video(video["url"], video_path):
            print(f"  SKIPPED — download failed")
            continue

        # Extract frames
        n = extract_frames(video_path, frames_dir, fps_target=FRAMES_PER_SECOND)
        total_frames += n

    print(f"\n{'=' * 60}")
    print(f"Done. {total_frames} frames extracted.")
    print(f"\nNext step: run  python ml/label_frames.py")
    print(f"\nSignal classes to label:")
    for i, cls in enumerate(SIGNAL_CLASSES):
        print(f"  {i:2d}  {cls}")


if __name__ == "__main__":
    main()
