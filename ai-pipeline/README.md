# ai-pipeline — SwiftletCare AI Subsystem

Computer Vision & Anomaly Detection cho SwiftletCare: nhận diện **swiftlet / rat / snake** (YOLO26, `models/best.pt`),
tracking (ByteTrack), đếm chim **ra/vào** bằng *Virtual Line*, sinh sự kiện **PREDATOR_DETECTED** kèm snapshot.

```
Frame → YOLO Detect → ByteTrack → Line Counter → Predator Monitor → Events/Snapshot → Publisher → Backend
```

## Cấu trúc
```
ai-pipeline/
├── configs/            pipeline.yaml, cameras.yaml
├── models/best.pt      YOLO26 (classes: 0 swiftlet, 1 rat, 2 snake, imgsz 640)
├── src/swiftletcare_ai/
│   ├── schemas.py      contract JSON (Detection/Count/Anomaly)
│   ├── video_source.py video | image dir | webcam | RTSP | MJPEG (ESP32-CAM)
│   ├── detector.py     BaseDetector, YoloDetector
│   ├── dataset_tools.py kiểm tra nhãn / chia train-val-test theo nhóm video / data.yaml
│   ├── tracker.py      ByteTrack + CentroidTracker (fallback)
│   ├── counter.py      LineCounter (entry/exit)
│   ├── predator.py     ngưỡng, N frame liên tiếp, cooldown
│   ├── snapshot.py     vẽ bbox + lưu snapshot
│   ├── aggregator.py   tổng hợp theo giờ, phát hiện đàn giảm bất thường
│   ├── publisher.py    jsonl | http | mqtt | multi
│   ├── pipeline.py     CameraPipeline (orchestrator)
│   ├── factory.py      dựng pipeline từ YAML
│   └── cli.py
├── scripts/            validate_dataset, split_dataset, train, predict_images, calibrate_line,
│                       run_pipeline, evaluate_detection, evaluate_counting, benchmark_latency, export_model, simulate_demo
├── tests/              pytest (không cần model/torch trừ test ByteTrack)
└── docs/ai-interface.md  contract AI ↔ Backend
```

## Chạy nhanh
```bash
cd ai-pipeline
pip install -r requirements.txt
python scripts/run_pipeline.py --camera CAM-01 --source data/samples/entrance.mp4 --show --save-video outputs/demo.mp4
pytest -q
```
Chỉnh `counting_line` và `inside_side` trong `configs/cameras.yaml` (toạ độ chuẩn hoá 0..1) cho khớp góc camera:
nếu số **entry/exit bị đảo**, đổi `inside_side` giữa `positive` ↔ `negative`.

## Đặt file vào đâu (khớp Drive: Dataset_SwiftletCare/{train,valid,test,data.yaml})
- `runs/detect/train/weights/best.pt` -> `ai-pipeline/models/best.pt` (chú ý đuôi `.pt`, không phải `.py`).
  Nếu để `ai-pipeline/best.pt` thì sửa `model.path: best.pt` trong `configs/pipeline.yaml`.
- Thư mục dataset -> `ai-pipeline/Dataset_SwiftletCare/` (không push lên git). Chỉ test tĩnh thì chỉ cần `Dataset_SwiftletCare/test/`.
- Công cụ tự nhận layout Roboflow (`train/valid/test` mỗi thư mục có `images/`, `labels/`) lẫn layout YOLO (`images/train`...).

## Dataset & huấn luyện
```bash
python scripts/validate_dataset.py --root Dataset_SwiftletCare --write-yaml   # kiểm tra + tạo data.local.yaml (đường dẫn tuyệt đối)
python scripts/split_dataset.py --src <raw> --out <dataset> --group-regex "^(.*)_f\d+$"   # nếu chưa chia split
python scripts/train.py --data Dataset_SwiftletCare/data.local.yaml --epochs 100 --install   # fine-tune từ best.pt, cài best.pt mới
python scripts/predict_images.py --source <dataset>/images/test          # ảnh có bbox + predictions.json
python scripts/calibrate_line.py --source data/samples/entrance.mp4      # click chọn vạch đếm -> YAML
```

## Đánh giá (AI-NFR-003/004/001)
```bash
python scripts/evaluate_detection.py --data Dataset_SwiftletCare/data.local.yaml --split test      # Precision, Recall, mAP
python scripts/evaluate_counting.py  --gt data/ground_truth.csv                    # MAE, accuracy vs đếm tay
python scripts/benchmark_latency.py  --source data/samples/entrance.mp4            # ms/frame, FPS
```

## Truy vết yêu cầu
| Requirement | Thành phần |
|---|---|
| AI-FR-001/010 | `video_source.py` |
| AI-FR-002..006 | `detector.py` (`YoloDetector`) |
| AI-FR-007/014 | `snapshot.py` |
| AI-FR-008 | `predator.py` + `pipeline._predator_event` |
| AI-FR-009 | `publisher.py`, `schemas.py` |
| AI-FR-011 | `tracker.py` |
| AI-FR-012/013 | `counter.py` |
| AI-FR-015 | `aggregator.py`, message `counts` |
| AI-NFR-001/002 | `scripts/benchmark_latency.py` |
| AI-NFR-003/004 | `scripts/evaluate_*.py` |
| AI-NFR-005 | YOLO26 + `export_model.py` |
| AI-NFR-006 | chỉ gửi counts + snapshot (`publish_detections: false`) |
| AI-NFR-007 | `Base*` interface cho detector/tracker/publisher |

## Video / camera flow
```bash
python scripts/calibrate_line.py --source data/samples/nest.mp4 --frame 100      # click the counting line
python scripts/track_video.py --source data/samples/nest.mp4 --line 0.1 0.5 0.9 0.5 --inside positive --save-video outputs/track.mp4
python scripts/track_video.py --source data/samples/predators --repeat 3 --cooldown 0   # rat/snake images
python scripts/track_video.py --source rtsp://user:pass@ip/stream                       # IP camera (later)
```
Output: `outputs/track_events.jsonl` (counts + predator events), snapshots, annotated video.
If entry/exit look swapped, use `--inside negative`.

## Lưu ý / giới hạn
- Model **YOLO26**, train ở **640x640**: giữ `model.imgsz: 640` khi infer/evaluate (detector cảnh báo nếu lệch). Frame không vuông được letterbox, bbox trả về vẫn theo toạ độ frame gốc.
- Audio AI chưa triển khai (Open Question 7.4: chưa có dataset/model/metric).
- Chim yến nhỏ & nhanh: nếu recall thấp, tăng `imgsz`, hạ `model.min_conf`, hoặc đặt camera gần cửa hơn.
- Rắn/chuột ít xuất hiện: dataset mất cân bằng; tinh chỉnh `predator.conf_threshold` theo PR-curve.