"""Export best.pt to ONNX/NCNN/TFLite/OpenVINO for edge devices (AI-NFR-005). Contract is unchanged."""
import argparse

import _bootstrap
from _bootstrap import ROOT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(ROOT / "models/best.pt"))
    ap.add_argument("--format", default="onnx", choices=["onnx", "ncnn", "tflite", "openvino"])
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--half", action="store_true")
    a = ap.parse_args()
    from ultralytics import YOLO
    print("exported:", YOLO(a.model).export(format=a.format, imgsz=a.imgsz, half=a.half))


if __name__ == "__main__":
    main()