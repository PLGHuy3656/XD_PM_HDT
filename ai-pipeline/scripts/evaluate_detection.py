"""Evaluate detector on a held-out split (AI-NFR-003): precision, recall, mAP50, mAP50-95 per class.

  python scripts/evaluate_detection.py --data Dataset_SC_NOPUSH/data.local.yaml --split test
"""
import argparse
import json
from pathlib import Path

import _bootstrap
from _bootstrap import ROOT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(ROOT / "models/best.pt"))
    ap.add_argument("--data", required=True, help="data yaml that contains the split")
    ap.add_argument("--split", default="test", choices=["val", "test"])
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.001, help="low conf for standard mAP")
    ap.add_argument("--device", default=None)
    ap.add_argument("--out", default=str(ROOT / "outputs/eval_detection.json"))
    a = ap.parse_args()

    from ultralytics import YOLO
    m = YOLO(a.model)
    r = m.val(data=a.data, split=a.split, imgsz=a.imgsz, conf=a.conf, device=a.device, plots=True, verbose=False)
    per_class = {}
    for i, ci in enumerate(r.box.ap_class_index):
        per_class[m.names[int(ci)]] = {"precision": float(r.box.p[i]), "recall": float(r.box.r[i]),
                                        "ap50": float(r.box.ap50[i]), "ap50_95": float(r.box.ap[i])}
    out = {"split": a.split, "precision": float(r.box.mp), "recall": float(r.box.mr),
           "mAP50": float(r.box.map50), "mAP50_95": float(r.box.map), "per_class": per_class,
           "speed_ms": {k: float(v) for k, v in r.speed.items()}}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()