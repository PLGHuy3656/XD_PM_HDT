"""Train / fine-tune YOLO26 (needs ultralytics, GPU recommended).

  python scripts/train.py --data Dataset_SC_NOPUSH/data.local.yaml --epochs 100 --install
  python scripts/train.py --model yolo26n.pt --epochs 120 --patience 30 --data ...   # close to original recipe
  python scripts/train.py --data ... --resume
Note: default start is models/best.pt (fine-tune) with extra augmentation, so it differs from the original run.
"""
import argparse
import shutil
from pathlib import Path

import _bootstrap
from _bootstrap import ROOT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--model", default=str(ROOT / "models/best.pt"), help="start weights")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--patience", type=int, default=30)
    ap.add_argument("--name", default="exp")
    ap.add_argument("--project", default=str(ROOT / "runs/swiftletcare"))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--install", action="store_true", help="copy new best.pt to models/ (old one -> best_prev.pt)")
    a = ap.parse_args()

    from ultralytics import YOLO
    model = YOLO(a.model)
    if a.resume:
        model.train(resume=True)
    else:
        model.train(data=a.data, epochs=a.epochs, imgsz=a.imgsz, batch=a.batch, device=a.device, workers=a.workers,
                    patience=a.patience, project=a.project, name=a.name, exist_ok=True,
                    fliplr=0.5, flipud=0.0, mosaic=1.0, close_mosaic=10, hsv_v=0.5, degrees=5.0)
    best = Path(a.project) / a.name / "weights" / "best.pt"
    print("best.pt:", best, "(found)" if best.exists() else "(NOT found)")
    if a.install and best.exists():
        dst = ROOT / "models/best.pt"
        if dst.exists():
            shutil.copy2(dst, ROOT / "models/best_prev.pt")
        shutil.copy2(best, dst)
        print("installed", dst, "- run evaluate_detection.py before pushing")


if __name__ == "__main__":
    main()