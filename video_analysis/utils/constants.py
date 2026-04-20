"""
Shared constants for the Video Analysis module.
"""

# ── Event types ───────────────────────────────────────────────────────────────
EVENT_TYPES = [
    "try",
    "tackle",
    "missed_tackle",
    "linebreak",
    "offload",
    "error",
    "penalty",
    "kick",
]

EVENT_LABELS = {
    "try":           "Try",
    "tackle":        "Tackle",
    "missed_tackle": "Missed Tackle",
    "linebreak":     "Linebreak",
    "offload":       "Offload",
    "error":         "Error",
    "penalty":       "Penalty",
    "kick":          "Kick",
}

# Keyboard shortcuts 1-8 map to event types
EVENT_KEYS = {str(i + 1): EVENT_TYPES[i] for i in range(len(EVENT_TYPES))}

# ── Team sides ────────────────────────────────────────────────────────────────
TEAM_HOME = "home"
TEAM_AWAY = "away"
TEAM_SIDES = [TEAM_HOME, TEAM_AWAY]

# ── Processing parameters ─────────────────────────────────────────────────────
DETECTION_FRAME_SKIP = 2       # Run detection on every Nth frame
OCR_FRAME_INTERVAL = 10        # Re-run OCR on a track every N frames
CAMERA_CUT_THRESHOLD = 0.6     # Histogram difference threshold for cut detection

# ── YOLO ─────────────────────────────────────────────────────────────────────
YOLO_MODEL = "yolov8m.pt"
YOLO_CONFIDENCE = 0.4
YOLO_CLASS_PERSON = 0          # COCO class index for "person"
YOLO_IOU = 0.5

# ── OCR ──────────────────────────────────────────────────────────────────────
OCR_MIN_CONFIDENCE = 0.3
OCR_LANGUAGES = ["en"]

# ── Jersey numbers ────────────────────────────────────────────────────────────
JERSEY_MIN = 1
JERSEY_MAX = 20

# ── Team colour reference (HSV) ───────────────────────────────────────────────
# Dapto Canaries — gold jerseys
DAPTO_GOLD_HSV_LOWER = (15, 100, 100)
DAPTO_GOLD_HSV_UPPER = (35, 255, 255)

# ── Video processing status values ────────────────────────────────────────────
STATUS_PENDING    = "pending"
STATUS_PROCESSING = "processing"
STATUS_DONE       = "done"
STATUS_ERROR      = "error"

# ── Thumbnail dimensions ──────────────────────────────────────────────────────
THUMB_W = 80
THUMB_H = 160
