import numpy as np

from swiftletcare_ai.frame_clean import FrameCleaner


def test_invalid_and_black_frames_are_rejected():
    c = FrameCleaner()
    assert c.clean(None)[0] is None
    assert c.clean(np.zeros((10, 10, 3), np.uint8))[0] is None      # too small
    assert c.clean(np.zeros((100, 100, 3), np.uint8))[0] is None    # black
    assert c.stats.bad == 3


def test_dark_frame_is_brightened_and_size_kept():
    c = FrameCleaner(dark_threshold=60, target_brightness=100)
    img = np.full((100, 120, 3), 25, np.uint8)
    out, info = c.clean(img)
    assert info["enhanced"] and out.shape == img.shape
    assert 80 < out.mean() < 120


def test_normal_frame_untouched():
    c = FrameCleaner()
    img = np.full((100, 100, 3), 120, np.uint8)
    out, info = c.clean(img)
    assert not info["enhanced"] and (out == img).all()