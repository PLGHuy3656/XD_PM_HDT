import numpy as np

from swiftletcare_ai.schemas import Detection
from swiftletcare_ai.snapshot import SnapshotStore, draw_detections


def test_snapshot_roundtrip(tmp_path):
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    vis = draw_detections(img, [Detection("rat", 0.9, [10, 10, 50, 50])])
    assert vis.shape == img.shape and vis.sum() > 0 and img.sum() == 0   # original untouched
    store = SnapshotStore(str(tmp_path / "snap"), public_base_url="http://x/s/")
    url = store.save(vis, "CAM-01", "PREDATOR_DETECTED", 1728135000.5)
    assert url == "http://x/s/CAM-01_PREDATOR_DETECTED_1728135000_500.jpg"
    assert (tmp_path / "snap" / url.rsplit("/", 1)[1]).stat().st_size > 0