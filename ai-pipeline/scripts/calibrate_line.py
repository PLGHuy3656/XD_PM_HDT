"""Pick the counting line with the mouse on one frame; prints YAML for configs/cameras.yaml.

  python scripts/calibrate_line.py --source data/samples/nest.mp4 --frame 100
Click 2 points (line ends), then 1 point INSIDE the house. Keys: r = redo, q/Enter = done.
"""
import argparse
from pathlib import Path

import cv2

import _bootstrap  # noqa: F401
from swiftletcare_ai.video_source import IMG_EXT, read_image


def side_of(a, b, p) -> float:
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def grab_frame(source, frame_no=0):
    if Path(source).suffix.lower() in IMG_EXT:
        return read_image(source)
    cap = cv2.VideoCapture(source)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
    ok, img = cap.read()
    cap.release()
    return img if ok else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="video file or image")
    ap.add_argument("--frame", type=int, default=0, help="frame number to use")
    ap.add_argument("--camera", default="CAM-01")
    a = ap.parse_args()
    img = grab_frame(a.source, a.frame)
    if img is None:
        raise SystemExit("cannot read a frame from source")
    h, w = img.shape[:2]
    pts = []

    def on_mouse(ev, x, y, *_):
        if ev == cv2.EVENT_LBUTTONDOWN and len(pts) < 3:
            pts.append((x, y))

    cv2.namedWindow("calibrate")
    cv2.setMouseCallback("calibrate", on_mouse)
    while True:
        view = img.copy()
        for p in pts:
            cv2.circle(view, p, 4, (0, 255, 255), -1)
        if len(pts) >= 2:
            cv2.line(view, pts[0], pts[1], (255, 255, 0), 2)
        cv2.putText(view, "2 line ends, then 1 point INSIDE | r=redo q=done", (8, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.imshow("calibrate", view)
        k = cv2.waitKey(30) & 0xFF
        if k == ord("r"):
            pts.clear()
        if k in (ord("q"), 13) and len(pts) == 3:
            break
    cv2.destroyAllWindows()
    p1, p2, inside = pts
    side = "positive" if side_of(p1, p2, inside) > 0 else "negative"
    print("Paste into configs/cameras.yaml:")
    print(f"  - camera_id: {a.camera}")
    print("    counting_line:")
    print(f"      start: [{p1[0] / w:.3f}, {p1[1] / h:.3f}]")
    print(f"      end:   [{p2[0] / w:.3f}, {p2[1] / h:.3f}]")
    print(f"    inside_side: {side}")
    print(f"Or CLI: --line {p1[0] / w:.3f} {p1[1] / h:.3f} {p2[0] / w:.3f} {p2[1] / h:.3f} --inside {side}")


if __name__ == "__main__":
    main()