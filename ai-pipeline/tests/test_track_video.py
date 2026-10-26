"""Functional test of scripts/track_video.py: synthetic video + color-blob fake detector, no model needed."""
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("track_video", ROOT / "scripts" / "track_video.py")
tv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tv)

from swiftletcare_ai.detector import CallableDetector
from swiftletcare_ai.schemas import Detection

W, H, FPS, N = 320, 240, 20, 60


def blobs(img, color_test, cls):
    mask = color_test(img).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    return [Detection(cls, 0.9, [float(x), float(y), float(x + w), float(y + h)])
            for x, y, w, h, a in stats[1:] if a > 20]


def fake_detect(img):
    b, g, r = img[..., 0].astype(int), img[..., 1].astype(int), img[..., 2].astype(int)
    return (blobs(img, lambda _: (g > 200) & (r < 80) & (b < 80), "swiftlet")
            + blobs(img, lambda _: (r > 200) & (g < 80) & (b < 80), "snake"))


def make_video(path):
    wr = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (W, H))
    for i in range(N):
        f = np.zeros((H, W, 3), np.uint8)
        t = min(max((i - 5) / 40.0, 0.0), 1.0)
        cv2.circle(f, (100, int(200 - 160 * t)), 8, (0, 255, 0), -1)    # bird A moves up (inside -> outside)
        cv2.circle(f, (220, int(40 + 160 * t)), 8, (0, 255, 0), -1)     # bird B moves down (outside -> inside)
        if 20 <= i <= 30:
            cv2.circle(f, (160, 60), 10, (0, 0, 255), -1)               # snake for 11 frames
        wr.write(f)
    wr.release()


@pytest.mark.parametrize("tracker", ["centroid", "bytetrack"])
def test_count_and_predator_flow(tmp_path, tracker):
    if tracker == "bytetrack":
        try:
            from swiftletcare_ai.tracker import ByteTrackTracker
            ByteTrackTracker()
        except Exception as e:
            pytest.skip(f"ByteTrack unavailable: {e}")
    cfg = yaml.safe_load((ROOT / "configs/pipeline.yaml").read_text(encoding="utf-8"))
    cfg["snapshot"]["dir"] = str(tmp_path / "snaps")
    (tmp_path / "pipeline.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    make_video(tmp_path / "v.avi")
    out = tmp_path / "ev.jsonl"
    args = tv.parse_args(["--source", str(tmp_path / "v.avi"), "--config", str(tmp_path / "pipeline.yaml"),
                          "--line", "0", "0.5", "1", "0.5", "--inside", "positive", "--tracker", tracker,
                          "--out", str(out), "--save-video", str(tmp_path / "o.mp4")])
    s = tv.run(args, CallableDetector(fake_detect))
    assert s["frames"] == N and (s["entry"], s["exit"]) == (1, 1) and s["predator_events"] == 1
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    ev = [r["payload"] for r in rows if r["kind"] == "events"]
    assert ev[0]["eventType"] == "PREDATOR_DETECTED" and ev[0]["class"] == "snake"
    assert Path(ev[0]["snapshot"]).exists()
    last = [r["payload"] for r in rows if r["kind"] == "counts"][-1]
    assert (last["entryCount"], last["exitCount"], last["netChange"]) == (1, 1, 0)
    assert (tmp_path / "o.mp4").exists()


def test_image_repeat_triggers_predator(tmp_path):
    img = np.zeros((H, W, 3), np.uint8)
    cv2.circle(img, (100, 100), 12, (0, 0, 255), -1)
    d = tmp_path / "imgs"
    d.mkdir()
    cv2.imencode(".png", img)[1].tofile(str(d / "snake.png"))
    cfg = yaml.safe_load((ROOT / "configs/pipeline.yaml").read_text(encoding="utf-8"))
    cfg["snapshot"]["dir"] = str(tmp_path / "snaps")
    (tmp_path / "pipeline.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    args = tv.parse_args(["--source", str(d), "--config", str(tmp_path / "pipeline.yaml"), "--repeat", "3",
                          "--cooldown", "0", "--out", str(tmp_path / "e.jsonl")])
    s = tv.run(args, CallableDetector(fake_detect))
    assert s["frames"] == 3 and s["predator_events"] == 1