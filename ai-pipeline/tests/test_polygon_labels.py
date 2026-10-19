"""Polygon label support in dataset_tools."""
import pytest

from swiftletcare_ai.dataset_tools import parse_label_file, scan_dataset

NAMES = {0: "swiftlet", 1: "rat", 2: "snake"}


def test_polygon_label_converted_to_bbox(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("2 0.2 0.2 0.6 0.2 0.6 0.8 0.2 0.8\n", encoding="utf-8")
    boxes, issues = parse_label_file(f, 3)
    assert not issues
    assert boxes == [(2, pytest.approx(0.4), pytest.approx(0.5), pytest.approx(0.4), pytest.approx(0.6))]


def test_bad_length_label_still_error(tmp_path):
    f = tmp_path / "b.txt"
    f.write_text("0 0.1 0.2 0.3\n", encoding="utf-8")
    boxes, issues = parse_label_file(f, 3)
    assert not boxes and len(issues) == 1


def test_scan_counts_polygon_as_box(tmp_path):
    (tmp_path / "train" / "images").mkdir(parents=True)
    (tmp_path / "train" / "labels").mkdir(parents=True)
    (tmp_path / "train" / "images" / "s1.jpg").write_bytes(b"x")
    (tmp_path / "train" / "labels" / "s1.txt").write_text(
        "2 0.1 0.1 0.5 0.1 0.5 0.5 0.1 0.5\n", encoding="utf-8")
    rep = scan_dataset(tmp_path, NAMES)
    assert rep.ok
    assert rep.polygons == 1
    assert rep.splits["train"].boxes["snake"] == 1