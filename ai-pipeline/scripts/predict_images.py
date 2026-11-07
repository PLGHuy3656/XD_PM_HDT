"""Run the detector on an image or folder; save annotated images + predictions.json (AI-FR-006/007).

  python scripts/predict_images.py --source Dataset_SC_NOPUSH/test/images --out outputs/predict
"""
import argparse
import json
import time
from pathlib import Path

import cv2

import _bootstrap
from _bootstrap import ROOT

from swiftletcare_ai.config import load_pipeline_config, resolve_path
# list_images replaced with Path.rglob
from swiftletcare_ai.detector import YoloDetector
from swiftletcare_ai.schemas import DetectionMessage
from swiftletcare_ai.snapshot import draw_detections


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="image file or folder")
    ap.add_argument("--out", default=str(ROOT / "outputs/predict"))
    ap.add_argument("--config", default=str(ROOT / "configs/pipeline.yaml"))
    ap.add_argument("--camera", default="CAM-01")
    ap.add_argument("--conf", type=float, default=None, help="override model.min_conf")
    a = ap.parse_args()
    cfg = load_pipeline_config(a.config)
    if a.conf is not None:
        cfg["model"]["min_conf"] = a.conf
    m = cfg["model"]
    det = YoloDetector(resolve_path(m["path"], ROOT), imgsz=m.get("imgsz", 640), device=m.get("device", "auto"),
                       half=m.get("half", False), min_conf=m.get("min_conf", 0.15), iou=m.get("iou", 0.5))
    src = Path(a.source)
    valid_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    files = [src] if src.is_file() else sorted([p for p in src.rglob("*") if p.is_file() and p.suffix.lower() in valid_exts])
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for f in files:
        img = cv2.imread(str(f))
        if img is None:
            continue
        dets = det.detect(img)
        cv2.imwrite(str(out / f.name), draw_detections(img, dets))
        results.append({"image": f.name, **DetectionMessage(a.camera, int(time.time()), dets).to_dict()})
    (out / "predictions.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(results)} images -> {out}")


if __name__ == "__main__":
    main()