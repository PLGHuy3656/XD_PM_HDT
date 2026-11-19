"""Generate authoritative positive and negative test video fixtures for CP13 video counting verification.

Fixtures generated:
1. fixture_swiftlet_positive.avi: Swiftlet in flight crossing counting line (downwards: ENTRY=1, EXIT=0).
2. fixture_swiftlet_bidirectional.avi: Two swiftlets crossing (one downward ENTRY=1, one upward EXIT=1).
3. fixture_swiftlet_negative.avi: Barn entrance with no birds (ENTRY=0, EXIT=0).
"""
import cv2
import numpy as np
from pathlib import Path

def draw_swiftlet(frame, cx, cy, scale=0.6, angle_deg=0):
    """Draw a realistic swiftlet silhouette in flight (boomerang wings, fuselage, notched tail)."""
    pts = np.array([
        [0, -15], [8, -5], [45, -25], [120, -55], [90, -35], [40, -15],
        [10, 5], [15, 35], [0, 22], [-15, 35], [-10, 5], [-40, -15],
        [-90, -35], [-120, -55], [-45, -25], [-8, -5]
    ], dtype=np.float32) * scale
    rad = np.radians(angle_deg)
    cos_a, sin_a = np.cos(rad), np.sin(rad)
    R = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
    pts = pts @ R.T
    pts[:, 0] += cx
    pts[:, 1] += cy
    cv2.fillPoly(frame, [pts.astype(np.int32)], (30, 30, 35))

def generate_fixtures(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    W, H, FPS = 640, 480, 10

    # 1. Positive Single-Entry Video (30 frames, swiftlet enters from top to bottom)
    pos_path = output_dir / "fixture_swiftlet_positive.avi"
    writer = cv2.VideoWriter(str(pos_path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (W, H))
    for i in range(30):
        frame = np.full((H, W, 3), 200, dtype=np.uint8)
        # Background entrance doorway line
        cv2.line(frame, (50, 240), (590, 240), (0, 255, 0), 2)
        cy = int(100 + i * (280 / 30))  # from 100 to 380, crosses y=240 at frame 15
        cx = 320
        draw_swiftlet(frame, cx, cy, scale=0.6, angle_deg=180)
        writer.write(frame)
    writer.release()
    print("Generated:", pos_path)

    # 2. Positive Bidirectional Video (35 frames: bird 1 enters, bird 2 exits)
    bi_path = output_dir / "fixture_swiftlet_bidirectional.avi"
    writer = cv2.VideoWriter(str(bi_path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (W, H))
    for i in range(35):
        frame = np.full((H, W, 3), 200, dtype=np.uint8)
        cv2.line(frame, (50, 240), (590, 240), (0, 255, 0), 2)
        if i < 30:
            cy1 = int(80 + i * (300 / 30))
            draw_swiftlet(frame, 200, cy1, scale=0.6, angle_deg=180)
        if 5 <= i < 35:
            cy2 = int(400 - (i - 5) * (300 / 30))
            draw_swiftlet(frame, 440, cy2, scale=0.6, angle_deg=0)
        writer.write(frame)
    writer.release()
    print("Generated:", bi_path)

    # 3. Negative Video (30 frames: doorway background only, no birds)
    neg_path = output_dir / "fixture_swiftlet_negative.avi"
    writer = cv2.VideoWriter(str(neg_path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (W, H))
    for i in range(30):
        frame = np.full((H, W, 3), 200, dtype=np.uint8)
        cv2.line(frame, (50, 240), (590, 240), (0, 255, 0), 2)
        writer.write(frame)
    writer.release()
    print("Generated:", neg_path)

if __name__ == "__main__":
    target = Path(__file__).resolve().parent.parent / "data" / "samples"
    generate_fixtures(target)
