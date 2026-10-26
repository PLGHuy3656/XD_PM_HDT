"""Detect -> track -> count -> predator events on a video, image folder, image or camera.

  python scripts/track_video.py --source data/samples/nest.mp4 --save-video outputs/track.mp4
  python scripts/track_video.py --source data/samples/nest.mp4 --line 0.1 0.5 0.9 0.5 --inside positive --show
  python scripts/track_video.py --source data/samples/predators --repeat 3 --cooldown 0      # predator images
  python scripts/track_video.py --source rtsp://user:pass@ip/stream                          # camera, later
Writes outputs/track_events.jsonl (counts + events), snapshots, optional annotated video.
"""
import argparse
import json
import logging
import time
from pathlib import Path

import cv2
import numpy as np

import _bootstrap
from _bootstrap import ROOT

from swiftletcare_ai.config import load_cameras, load_pipeline_config, resolve_path
from swiftletcare_ai.counter import LineCounter
from swiftletcare_ai.detector import YoloDetector
from swiftletcare_ai.predator import PredatorMonitor
from swiftletcare_ai.schemas import (CLASS_SWIFTLET, EVENT_PREDATOR, AnomalyEvent, CountMessage, FramePacket)
from swiftletcare_ai.snapshot import SnapshotStore, draw_detections
from swiftletcare_ai.tracker import build_tracker
from swiftletcare_ai.video_source import ImageDirSource, ListFrameSource, open_source

log = logging.getLogger("track_video")


def repeat_frames(source, n):
    """Repeat each image n times (a still animal seen in consecutive frames)."""
    k, base = 0, None
    for pkt in source:
        base = pkt.timestamp if base is None else base
        for _ in range(n):
            yield FramePacket(pkt.camera_id, k, base + k / source.fps, pkt.image)
            k += 1


def parse_args(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="video file, image folder, image, camera index or URL")
    ap.add_argument("--source-type", default="auto")
    ap.add_argument("--camera", default="CAM-01")
    ap.add_argument("--config", default=str(ROOT / "configs/pipeline.yaml"))
    ap.add_argument("--cameras", default=str(ROOT / "configs/cameras.yaml"))
    ap.add_argument("--line", nargs=4, type=float, metavar=("X1", "Y1", "X2", "Y2"), help="normalized 0..1")
    ap.add_argument("--inside", choices=["positive", "negative"], default=None)
    ap.add_argument("--tracker", choices=["bytetrack", "centroid"], default=None)
    ap.add_argument("--conf", type=float, default=None, help="override model.min_conf")
    ap.add_argument("--imgsz", type=int, default=None)
    ap.add_argument("--predator-frames", type=int, default=None)
    ap.add_argument("--cooldown", type=float, default=None, help="predator cooldown in source seconds")
    ap.add_argument("--frame-skip", type=int, default=0)
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--repeat", type=int, default=1, help="repeat each image N times (image sources)")
    ap.add_argument("--save-video", default=None)
    ap.add_argument("--out", default=str(ROOT / "outputs/track_events.jsonl"))
    ap.add_argument("--show", action="store_true")
    return ap.parse_args(argv)


def pick_line(args, cfg):
    """Priority: CLI > cameras.yaml entry for this camera > default."""
    line, inside = ((0.1, 0.5), (0.9, 0.5)), cfg["counting"].get("inside_side", "positive")
    try:
        for c in load_cameras(args.cameras):
            if c.camera_id == args.camera:
                line, inside = c.line, c.inside_side
    except Exception:
        pass
    if args.line:
        line = ((args.line[0], args.line[1]), (args.line[2], args.line[3]))
    return line, (args.inside or inside)


def run(args, detector=None):
    cfg = load_pipeline_config(args.config)
    if args.conf is not None:
        cfg["model"]["min_conf"] = args.conf
    if args.imgsz is not None:
        cfg["model"]["imgsz"] = args.imgsz
    if detector is None:
        m = cfg["model"]
        detector = YoloDetector(resolve_path(m["path"], ROOT), imgsz=m.get("imgsz", 640), device=m.get("device", "auto"),
                                half=m.get("half", False), min_conf=m.get("min_conf", 0.15), iou=m.get("iou", 0.5))
    source = open_source(args.camera, args.source, args.source_type)
    if args.repeat > 1 and isinstance(source, (ImageDirSource, ListFrameSource)):
        frames = repeat_frames(source, args.repeat)
    else:
        frames = source

    tcfg = dict(cfg["tracker"])
    tcfg["frame_rate"] = int(round(source.fps))
    if args.tracker:
        tcfg["type"] = args.tracker
    tracker = build_tracker(tcfg, log)
    pcfg = cfg["predator"]
    monitor = PredatorMonitor(pcfg["classes"], pcfg["conf_threshold"],
                              args.predator_frames or pcfg["min_consecutive_frames"],
                              pcfg["cooldown_s"] if args.cooldown is None else args.cooldown)
    scfg = cfg["snapshot"]
    snaps = SnapshotStore(resolve_path(scfg["dir"], ROOT), scfg.get("public_base_url", ""), scfg.get("jpeg_quality", 85))
    line_norm, inside = pick_line(args, cfg)
    report_every = cfg["counting"].get("report_interval_s", 5)
    min_hits = cfg["counting"].get("min_track_hits", 2)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(out_path, "w", encoding="utf-8")

    def emit(kind, payload):
        log_f.write(json.dumps({"kind": kind, "payload": payload}, ensure_ascii=False) + "\n")
        log_f.flush()

    counter, writer = None, None
    events, lat, n, last_report, last_ts = [], [], 0, None, 0.0
    try:
        for pkt in frames:
            if args.frame_skip and pkt.frame_id % (args.frame_skip + 1):
                continue
            t0 = time.perf_counter()
            img = pkt.image
            if counter is None:
                counter = LineCounter.from_normalized(line_norm, img.shape, inside, min_hits)
                last_report = pkt.timestamp
            dets = detector.detect(img)
            swiftlets = [d for d in dets if d.cls == CLASS_SWIFTLET]
            others = [d for d in dets if d.cls != CLASS_SWIFTLET]
            tracked = tracker.update(swiftlets, img.shape)
            counter.update(tracked, pkt.frame_id)
            line_px = (counter.a, counter.b)
            for d in monitor.update(others, pkt.timestamp):
                shot = draw_detections(img, tracked + others, line_px, (counter.entry, counter.exit))
                url = snaps.save(shot, args.camera, EVENT_PREDATOR, pkt.timestamp)
                ev = AnomalyEvent(args.camera, EVENT_PREDATOR, d.cls, d.confidence, int(pkt.timestamp), d.bbox, url)
                emit("events", ev.to_dict())
                events.append(ev)
                print(f"PREDATOR {d.cls} conf={d.confidence:.2f} frame={pkt.frame_id} -> {url}")
            if pkt.timestamp - last_report >= report_every:
                emit("counts", CountMessage(args.camera, int(pkt.timestamp), counter.entry, counter.exit).to_dict())
                last_report = pkt.timestamp
            lat.append((time.perf_counter() - t0) * 1000.0)
            n += 1
            last_ts = pkt.timestamp
            if args.save_video or args.show:
                vis = draw_detections(img, tracked + others, line_px, (counter.entry, counter.exit))
                if args.save_video and writer is None:
                    Path(args.save_video).parent.mkdir(parents=True, exist_ok=True)
                    writer = cv2.VideoWriter(args.save_video, cv2.VideoWriter_fourcc(*"mp4v"), source.fps,
                                             (vis.shape[1], vis.shape[0]))
                if writer is not None:
                    writer.write(vis)
                if args.show:
                    cv2.imshow("track_video (q to quit)", vis)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
            if args.max_frames and n >= args.max_frames:
                break
    finally:
        if counter is not None:
            emit("counts", CountMessage(args.camera, int(last_ts), counter.entry, counter.exit).to_dict())
        log_f.close()
        if writer is not None:
            writer.release()
        source.close()
        if args.show:
            cv2.destroyAllWindows()

    a = np.array(lat) if lat else np.zeros(1)
    summary = {"frames": n, "entry": counter.entry if counter else 0, "exit": counter.exit if counter else 0,
               "net": counter.net if counter else 0, "predator_events": len(events),
               "mean_ms": float(a.mean()), "p95_ms": float(np.percentile(a, 95)),
               "fps": float(1000.0 / a.mean()) if a.mean() > 0 else 0.0}
    return summary


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    try:
        s = run(args)
    except IOError as e:
        print("ERROR:", e)
        return 2
    print(f"frames={s['frames']}  ENTRY={s['entry']}  EXIT={s['exit']}  NET={s['net']}  predator_events={s['predator_events']}")
    print(f"latency mean={s['mean_ms']:.1f} ms  p95={s['p95_ms']:.1f} ms  ~{s['fps']:.1f} fps")
    print("events file:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())