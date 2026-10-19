import cv2
import numpy as np

from swiftletcare_ai.dataset_tools import (group_key, imbalance_warnings, parse_label_file, scan_dataset,
                                           split_dataset, write_data_yaml)

NAMES = {0: "swiftlet", 1: "rat", 2: "snake"}


def _mk(root, name, labels):
    (root / "images").mkdir(parents=True, exist_ok=True)
    (root / "labels").mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(root / "images" / f"{name}.jpg"), np.zeros((16, 16, 3), np.uint8))
    if labels is not None:
        (root / "labels" / f"{name}.txt").write_text(labels)


def test_parse_label_valid_and_invalid(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("0 0.5 0.5 0.1 0.1\n1 1.5 0.5 0.1 0.1\n5 0.5 0.5 0.1 0.1\n0 0.1 0.1\n")
    boxes, issues = parse_label_file(p, 3)
    assert len(boxes) == 1 and len(issues) == 3


def test_group_key():
    assert group_key("vid1_f001", r"^(.*)_f\d+$") == "vid1"
    assert group_key("x", None) == "x"


def test_split_no_leak_and_groups(tmp_path):
    src, out = tmp_path / "raw", tmp_path / "ds"
    for v in range(10):
        for f in range(3):
            _mk(src, f"v{v}_f{f}", "1 0.5 0.5 0.1 0.1\n" if v < 4 else "0 0.5 0.5 0.1 0.1\n")
    counts = split_dataset(src, out, (0.6, 0.2, 0.2), seed=1, group_regex=r"^(.*)_f\d+$")
    assert sum(counts.values()) == 30
    rep = scan_dataset(out, NAMES)
    assert rep.ok and not rep.leaks
    # each video stays in one split
    where = {}
    for sp in ("train", "val", "test"):
        for p in (out / "images" / sp).glob("*.jpg"):
            where.setdefault(p.stem.split("_")[0], set()).add(sp)
    assert all(len(s) == 1 for s in where.values())
    assert rep.splits["test"].boxes["rat"] > 0       # predator present in test


def test_scan_reports_imbalance_and_yaml(tmp_path):
    root = tmp_path / "d"
    for i in range(5):
        _mk(root / "tmp", f"i{i}", "0 0.5 0.5 0.1 0.1\n")
    split_dataset(root / "tmp", root, (1.0, 0.0, 0.0))
    rep = scan_dataset(root, NAMES)
    warns = imbalance_warnings(rep, NAMES, min_boxes=3)
    assert any("rat" in w for w in warns) and any("snake" in w for w in warns)
    assert "names:" in write_data_yaml(root, NAMES).read_text()


def test_roboflow_layout_and_leak_and_local_yaml(tmp_path):
    from swiftletcare_ai.dataset_tools import base_name, detect_layout, read_names_from_yaml, write_local_yaml
    root = tmp_path / "Dataset_SwiftletCare"
    for sp, stem in (("train", "a_jpg.rf.abc123"), ("valid", "b_jpg.rf.def456"), ("test", "a_jpg.rf.fff999")):
        (root / sp / "images").mkdir(parents=True); (root / sp / "labels").mkdir(parents=True)
        cv2.imwrite(str(root / sp / "images" / f"{stem}.jpg"), np.zeros((8, 8, 3), np.uint8))
        (root / sp / "labels" / f"{stem}.txt").write_text("2 0.5 0.5 0.2 0.2\n")
    assert base_name("a_jpg.rf.abc123") == "a" and detect_layout(root) == "roboflow"
    rep = scan_dataset(root, NAMES)
    assert set(rep.splits) == {"train", "val", "test"} and rep.splits["val"].boxes["snake"] == 1
    assert len(rep.leaks) == 1                       # source 'a' in train and test
    y = write_local_yaml(root, NAMES)
    assert "val: valid/images" in y.read_text() and read_names_from_yaml(y)[2] == "snake"