import cv2
import numpy as np
import pytest

from swiftletcare_ai.video_source import CvFrameSource, ImageDirSource, ListFrameSource, open_source, read_image


def make_avi(path, n=10, fps=10):
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (64, 48))
    for i in range(n):
        w.write(np.full((48, 64, 3), i * 20, np.uint8))
    w.release()


def test_video_file_yields_all_frames_with_rising_time(tmp_path):
    p = tmp_path / "v.avi"
    make_avi(p)
    src = open_source("CAM-01", str(p))
    assert isinstance(src, CvFrameSource) and src.kind == "video"
    pk = list(src)
    assert len(pk) == 10 and [x.frame_id for x in pk] == list(range(10))
    assert pk[-1].timestamp - pk[0].timestamp == pytest.approx(0.9, abs=0.05)   # video time, not wall time
    src.close()


def test_image_dir_and_single_image_and_non_ascii_path(tmp_path):
    d = tmp_path / "thu muc anh"
    d.mkdir()
    for i in range(3):
        cv2.imencode(".png", np.zeros((8, 8, 3), np.uint8))[1].tofile(str(d / f"a{i}.png"))
    assert len(list(ImageDirSource("C", str(d)))) == 3
    assert isinstance(open_source("C", str(d)), ImageDirSource)
    one = open_source("C", str(d / "a0.png"))
    assert isinstance(one, ListFrameSource) and len(list(one)) == 1
    uni = tmp_path / "\u1ea3nh y\u1ebfn"
    uni.mkdir()
    cv2.imencode(".png", np.zeros((8, 8, 3), np.uint8))[1].tofile(str(uni / "x.png"))
    assert read_image(uni / "x.png") is not None


def test_missing_source_raises():
    with pytest.raises(IOError):
        open_source("C", "no_such_file.mp4")


def test_list_source_timestamps():
    pk = list(ListFrameSource("C", [np.zeros((4, 4, 3), np.uint8)] * 3, fps=10, t0=100.0))
    assert [round(p.timestamp, 2) for p in pk] == [100.0, 100.1, 100.2]