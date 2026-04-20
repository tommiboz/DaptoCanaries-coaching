# Referee Signal Classifier — Build Guide

Trains an AI to recognise rugby league referee hand signals from video frames.

## Setup

```
pip install -r requirements_ml.txt
```

## Step 1 — Collect frames

Downloads tutorial videos from YouTube and extracts frames:

```
python ml/collect_signal_frames.py
```

Frames land in `ml/data/frames/`.

## Step 2 — Label frames

Opens each frame. Press a key to label it:

```
python ml/label_frames.py
```

| Key | Signal |
|-----|--------|
| 0 | penalty |
| 1 | 10m |
| 2 | offside |
| 3 | high_tackle |
| 4 | knock_on |
| 5 | forward_pass |
| 6 | held |
| 7 | sin_bin |
| 8 | send_off |
| 9 | try |
| a | no_try |
| b | obstruction |
| c | hand_on_ball |
| e | strip |
| n | no_signal (background) |
| d | delete / skip |
| q | quit and save progress |

**Target:** 50+ frames per class minimum. 200+ for good accuracy.

## Step 3 — Train

```
python ml/train_signal_classifier.py
```

Model saved to `ml/models/signal_classifier.pt`.

## Step 4 — Video pipeline integration

The trained model plugs into the video analysis pipeline.
After a tackle cluster is detected, the pipeline watches the referee's
position for the next 3 seconds and classifies the signal automatically.

This populates the Referee Tagger events without manual input.
