"""
Step 3 — Train the referee signal classifier.

Fine-tunes MobileNetV3-Small on labeled signal frames.
Outputs a model file at ml/models/signal_classifier.pt

Usage:
    python ml/train_signal_classifier.py
    python ml/train_signal_classifier.py --epochs 30 --batch 16

Requirements:
    pip install -r requirements_ml.txt
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, models, transforms

ROOT        = Path(__file__).parent.parent
LABELED_DIR = ROOT / "ml" / "data" / "labeled"
MODELS_DIR  = ROOT / "ml" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH  = MODELS_DIR / "signal_classifier.pt"
LABELS_PATH = MODELS_DIR / "signal_labels.json"

# ── Transforms ────────────────────────────────────────────────────────────────
TRAIN_TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2),
    transforms.RandomRotation(15),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

VAL_TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def check_data() -> dict[str, int]:
    """Return class → frame count. Warn if any class is too low."""
    counts = {}
    for cls_dir in sorted(LABELED_DIR.iterdir()):
        if cls_dir.is_dir():
            n = len(list(cls_dir.glob("*.jpg")))
            counts[cls_dir.name] = n
    return counts


def build_model(num_classes: int) -> nn.Module:
    """MobileNetV3-Small fine-tuned for num_classes."""
    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    # Replace classifier head
    in_features = model.classifier[3].in_features
    model.classifier[3] = nn.Linear(in_features, num_classes)
    return model


def train(epochs: int = 20, batch_size: int = 16, lr: float = 1e-3, val_split: float = 0.15):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # ── Dataset ───────────────────────────────────────────────────────────────
    full_dataset = datasets.ImageFolder(str(LABELED_DIR), transform=TRAIN_TRANSFORM)
    class_names  = full_dataset.classes
    num_classes  = len(class_names)

    print(f"\nClasses ({num_classes}):")
    for i, cls in enumerate(class_names):
        n = len([p for p in (LABELED_DIR / cls).glob("*.jpg")])
        print(f"  {i:2d}  {cls:20s}  {n} frames")

    if num_classes < 2:
        print("\nERROR: Need at least 2 labeled classes to train.")
        return

    val_size   = max(1, int(len(full_dataset) * val_split))
    train_size = len(full_dataset) - val_size
    train_ds, val_ds = random_split(full_dataset, [train_size, val_size])

    # Val uses non-augmented transform
    val_ds.dataset.transform = VAL_TRANSFORM

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,  num_workers=0)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False, num_workers=0)

    # ── Model ─────────────────────────────────────────────────────────────────
    model = build_model(num_classes).to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=8, gamma=0.3)

    best_val_acc = 0.0
    print(f"\nTraining for {epochs} epochs...\n")

    for epoch in range(1, epochs + 1):
        t0 = time.time()

        # Train
        model.train()
        train_loss, train_correct = 0.0, 0
        for imgs, labels in train_loader:
            imgs, labels = imgs.to(device), labels.to(device)
            optimizer.zero_grad()
            out = model(imgs)
            loss = criterion(out, labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * imgs.size(0)
            train_correct += (out.argmax(1) == labels).sum().item()

        # Validate
        model.eval()
        val_loss, val_correct = 0.0, 0
        with torch.no_grad():
            for imgs, labels in val_loader:
                imgs, labels = imgs.to(device), labels.to(device)
                out = model(imgs)
                val_loss += criterion(out, labels).item() * imgs.size(0)
                val_correct += (out.argmax(1) == labels).sum().item()

        train_acc = train_correct / train_size * 100
        val_acc   = val_correct   / val_size   * 100
        elapsed   = time.time() - t0

        print(f"Epoch {epoch:3d}/{epochs}  "
              f"train_acc={train_acc:5.1f}%  val_acc={val_acc:5.1f}%  "
              f"loss={train_loss/train_size:.4f}  {elapsed:.1f}s")

        # Save best
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save({
                "epoch": epoch,
                "model_state": model.state_dict(),
                "class_names": class_names,
                "val_acc": val_acc,
            }, str(MODEL_PATH))
            print(f"           ↑ New best saved ({val_acc:.1f}%)")

        scheduler.step()

    # Save labels
    with open(LABELS_PATH, "w") as f:
        json.dump(class_names, f, indent=2)

    print(f"\nBest validation accuracy: {best_val_acc:.1f}%")
    print(f"Model saved to: {MODEL_PATH}")
    print(f"Labels saved to: {LABELS_PATH}")
    print(f"\nNext step: integrate into video pipeline.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs",  type=int,   default=20)
    parser.add_argument("--batch",   type=int,   default=16)
    parser.add_argument("--lr",      type=float, default=1e-3)
    args = parser.parse_args()

    # Data check
    counts = check_data()
    if not counts:
        print(f"No labeled frames found in {LABELED_DIR}")
        print("Run: python ml/label_frames.py")
        return

    low = {cls: n for cls, n in counts.items() if n < 20}
    if low:
        print("WARNING: These classes have fewer than 20 frames (model may be poor):")
        for cls, n in low.items():
            print(f"  {cls}: {n} frames")
        print("Label more frames or the classifier will underperform.\n")

    train(epochs=args.epochs, batch_size=args.batch, lr=args.lr)


if __name__ == "__main__":
    main()
