# Model Card - SwiftletCare AI (best.pt)

Cap nhat: 2026-10-19

## Tong quan
- Model: YOLO26n (2.375M params, 5.3 GFLOPs), khoi tao tu yolo26n.pt (COCO)
- Tac vu: object detection, dau vao 640x640
- Class: 0 swiftlet, 1 rat, 2 snake
- File: best.pt (5.1 MB), khong push len git

## Train
- Lenh: `yolo train model=yolo26n.pt data=.../data.yaml epochs=120 imgsz=640 patience=30`
- Moi truong: Colab, Tesla T4 14.9 GB, Python 3.13.15, torch 2.11.0+cu130
- Ultralytics 8.4.174, augmentation mac dinh
- Best epoch: epoch 99/120 dat mAP50-95(B): 0.67716 (highest).

## Du lieu (Roboflow layout)
| Split | Anh | Co nhan | Nen (bg) | swiftlet | rat | snake |
|---|---|---|---|---|---|---|
| train | 2758 | 2720 | 38 | 4715 | 1222 | 678 |
| val | 413 | 411 | 2 | 699 | 240 | 92 |
| test | 277 | 273 | 4 | 512 | 113 | 77 |

- 850 dong nhan polygon (chu yeu lop snake) duoc doi sang bbox khi kiem tra/train/eval.
- Kiem tra ro ri giua cac split: khong phat hien (validate_dataset OK).
- Nguon dataset: anh thu thap tu web/roboflow, chi dung cho muc dich hoc tap

## Ket qua tren test (277 anh, 702 instance)
Lenh: `python scripts/evaluate_detection.py --data Dataset_SC_NOPUSH/data.local.yaml --split test`

| Class | Precision | Recall | AP50 | AP50-95 |
|---|---|---|---|---|
| all | 0.894 | 0.836 | 0.892 | 0.647 |
| swiftlet | 0.878 | 0.762 | 0.845 | 0.413 |
| rat | 0.908 | 0.903 | 0.957 | 0.838 |
| snake | 0.895 | 0.844 | 0.874 | 0.690 |

Toc do (CPU i7-13620H, PyTorch): preprocess 1.1 ms, inference 32.5 ms, postprocess 0.3 ms / anh.

## Han che
- swiftlet recall thap nhat (0.76), AP50-95 chi 0.41: chim nho, nhanh, de miss khi dem.
- Snake it mau (77 instance test), ket qua kem on dinh.
- Chua danh gia tren video cua nha yen that; counting accuracy can do rieng voi ground truth.
- Anh thieu sang, nguoc sang, motion blur co the giam do chinh xac.
- Test chi co 4 anh nen (bg): ti le canh bao sai (false positive) tren khung hinh trong chua duoc do tot.
- Nhieu anh snake/rat duoc lay tu web: co the lech so voi canh that trong nha yen.
