"""YOLO dataset tools (pure Python, no torch): label check, class stats, group-aware split.

Supported layouts:
  roboflow: <root>/{train,valid,test}/{images,labels}
  yolo:     <root>/{images,labels}/{train,val,test}
Label line: cls cx cy w h (normalized 0..1), or polygon: cls x1 y1 x2 y2 ... (converted to bbox).
"""
from __future__ import annotations

import random
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLIT_ALIASES = {"train": ("train",), "val": ("val", "valid", "validation"), "test": ("test",)}
_RF_SUFFIX = re.compile(r"[._-](jpg|jpeg|png)\.rf\.[0-9a-fA-F]+$")


@dataclass
class LabelIssue:
    file: str
    line: int
    message: str


@dataclass
class SplitReport:
    images: int = 0
    labeled: int = 0              # images with >= 1 box
    background: int = 0           # empty or missing label (valid background image)
    missing_label_file: int = 0
    boxes: Counter = field(default_factory=Counter)   # per class name


@dataclass
class DatasetReport:
    splits: Dict[str, SplitReport] = field(default_factory=dict)
    issues: List[LabelIssue] = field(default_factory=list)
    leaks: List[str] = field(default_factory=list)    # same source image in several splits
    polygons: int = 0                                  # polygon label rows converted to bbox

    @property
    def ok(self) -> bool:
        return not self.issues and not self.leaks

    def class_totals(self) -> Counter:
        c: Counter = Counter()
        for s in self.splits.values():
            c.update(s.boxes)
        return c


def list_images(d: Path) -> List[Path]:
    return sorted(p for p in d.rglob("*") if p.suffix.lower() in IMG_EXT) if d.exists() else []


def _polygon_to_bbox(vals: Sequence[float]) -> Tuple[float, float, float, float]:
    """Polygon points [x1,y1,x2,y2,...] -> (cx, cy, w, h) of its bounding box."""
    xs, ys = vals[0::2], vals[1::2]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    return (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0


def parse_label_file(path: Path, num_classes: int, stats: Optional[Counter] = None):
    """Return (boxes, issues). Accept bbox (5 values) or polygon (1+2n, n>=3) -> bbox."""
    boxes, issues = [], []
    if not path.exists():
        return boxes, issues
    for i, raw in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        parts = raw.split()
        if not parts:
            continue
        is_poly = len(parts) >= 7 and len(parts) % 2 == 1
        if len(parts) != 5 and not is_poly:
            issues.append(LabelIssue(str(path), i, f"expected 5 values or polygon (1+2n), got {len(parts)}"))
            continue
        try:
            cls = int(float(parts[0]))
            vals = [float(v) for v in parts[1:]]
        except ValueError:
            issues.append(LabelIssue(str(path), i, "non-numeric value"))
            continue
        if is_poly:
            if not all(0.0 <= v <= 1.0 for v in vals):
                issues.append(LabelIssue(str(path), i, "polygon coords outside [0,1]"))
                continue
            cx, cy, w, h = _polygon_to_bbox(vals)
            if stats is not None:
                stats["polygon"] += 1
        else:
            cx, cy, w, h = vals
        if not (0 <= cls < num_classes):
            issues.append(LabelIssue(str(path), i, f"class id {cls} out of range 0..{num_classes - 1}"))
            continue
        if not all(0.0 <= v <= 1.0 for v in (cx, cy, w, h)) or w <= 0 or h <= 0:
            issues.append(LabelIssue(str(path), i, "coords outside [0,1] or w/h <= 0"))
            continue
        boxes.append((cls, cx, cy, w, h))
    return boxes, issues


def base_name(stem: str) -> str:
    """Strip Roboflow suffix (xxx_jpg.rf.<hash>) to find the same source image across splits."""
    return _RF_SUFFIX.sub("", stem)


def detect_layout(root: Path) -> Optional[str]:
    for names in SPLIT_ALIASES.values():
        for n in names:
            if (root / n / "images").exists():
                return "roboflow"
    if (root / "images").exists():
        return "yolo"
    return None


def split_dirs(root: Path, split: str, layout: Optional[str] = None) -> Tuple[Path, Path]:
    layout = layout or detect_layout(root)
    for n in SPLIT_ALIASES[split]:
        if layout == "roboflow" and (root / n / "images").exists():
            return root / n / "images", root / n / "labels"
        if layout == "yolo" and (root / "images" / n).exists():
            return root / "images" / n, root / "labels" / n
    return root / "images" / split, root / "labels" / split   # missing -> list_images returns []


def read_names_from_yaml(path: Path) -> Dict[int, str]:
    import yaml
    d = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    n = d.get("names", {})
    return {int(k): v for k, v in n.items()} if isinstance(n, dict) else dict(enumerate(n))


def scan_dataset(root: Path, names: Dict[int, str], splits: Sequence[str] = ("train", "val", "test")) -> DatasetReport:
    rep = DatasetReport()
    layout = detect_layout(root)
    seen: Dict[str, str] = {}
    stats: Counter = Counter()
    for sp in splits:
        img_dir, lbl_dir = split_dirs(root, sp, layout)
        imgs = list_images(img_dir)
        if not imgs:
            continue
        sr = SplitReport(images=len(imgs))
        for im in imgs:
            lbl = lbl_dir / (im.stem + ".txt")
            if not lbl.exists():
                sr.missing_label_file += 1
                sr.background += 1
            boxes, issues = parse_label_file(lbl, len(names), stats)
            rep.issues.extend(issues)
            if boxes:
                sr.labeled += 1
                for b in boxes:
                    sr.boxes[names[b[0]]] += 1
            elif lbl.exists():
                sr.background += 1
            key = base_name(im.stem)
            if key in seen and seen[key] != sp:
                rep.leaks.append(f"{im.name}: source '{key}' in {seen[key]} and {sp}")
            seen.setdefault(key, sp)
        rep.splits[sp] = sr
    rep.polygons = stats["polygon"]
    return rep


def imbalance_warnings(rep: DatasetReport, names: Dict[int, str], min_boxes: int = 100, ratio: float = 10.0) -> List[str]:
    tot = rep.class_totals()
    out = []
    for n in names.values():
        if tot.get(n, 0) == 0:
            out.append(f"class '{n}' has no boxes")
        elif tot[n] < min_boxes:
            out.append(f"class '{n}' has only {tot[n]} boxes (< {min_boxes})")
    nonzero = [v for v in tot.values() if v > 0]
    if nonzero and max(nonzero) / min(nonzero) >= ratio:
        out.append(f"class imbalance max/min = {max(nonzero) / min(nonzero):.1f}x (consider more predator data)")
    for sp, s in rep.splits.items():
        for n in names.values():
            if n != "swiftlet" and tot.get(n, 0) > 0 and s.boxes.get(n, 0) == 0 and sp in ("val", "test"):
                out.append(f"split '{sp}' has no '{n}' samples; its metrics cannot be measured")
    return out


def group_key(stem: str, group_regex: Optional[str]) -> str:
    """Group frames of one video so they stay in one split. regex: 1 group = video name."""
    if group_regex:
        m = re.match(group_regex, stem)
        if m:
            return m.group(1)
    return stem


def split_dataset(src: Path, out: Path, ratios=(0.7, 0.2, 0.1), seed: int = 42,
                  group_regex: Optional[str] = None, move: bool = False) -> Dict[str, int]:
    """Split flat src/{images,labels} by group; predator groups are spread across all splits."""
    assert abs(sum(ratios) - 1.0) < 1e-6, "ratios must sum to 1"
    groups: Dict[str, List[Path]] = defaultdict(list)
    for im in list_images(src / "images"):
        groups[group_key(im.stem, group_regex)].append(im)

    def has_predator(g: List[Path]) -> bool:
        for im in g:
            lbl = src / "labels" / (im.stem + ".txt")
            if lbl.exists() and any(l.split() and l.split()[0] != "0" for l in lbl.read_text().splitlines()):
                return True
        return False

    rnd = random.Random(seed)
    pred_g = [k for k, g in groups.items() if has_predator(g)]
    pred_set = set(pred_g)
    norm_g = [k for k in groups if k not in pred_set]
    assign: Dict[str, str] = {}
    for keys in (pred_g, norm_g):
        rnd.shuffle(keys)
        n = len(keys)
        n_tr = max(1, round(n * ratios[0])) if n else 0
        n_va = round(n * ratios[1])
        for i, k in enumerate(keys):
            assign[k] = "train" if i < n_tr else ("val" if i < n_tr + n_va else "test")
    counts: Counter = Counter()
    op = shutil.move if move else shutil.copy2
    for k, g in groups.items():
        sp = assign[k]
        (out / "images" / sp).mkdir(parents=True, exist_ok=True)
        (out / "labels" / sp).mkdir(parents=True, exist_ok=True)
        for im in g:
            op(str(im), str(out / "images" / sp / im.name))
            lbl = src / "labels" / (im.stem + ".txt")
            if lbl.exists():
                op(str(lbl), str(out / "labels" / sp / lbl.name))
            counts[sp] += 1
    return dict(counts)


def write_data_yaml(out: Path, names: Dict[int, str]) -> Path:
    p = out / "data.yaml"
    lines = [f"path: {out.resolve().as_posix()}", "train: images/train", "val: images/val", "test: images/test", "names:"]
    lines += [f"  {i}: {n}" for i, n in sorted(names.items())]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def write_local_yaml(root: Path, names: Dict[int, str], out: Optional[Path] = None) -> Path:
    """Write data.local.yaml with an absolute path (avoids Roboflow '../train/images' issues)."""
    root = root.resolve()
    layout = detect_layout(root)
    lines = [f"path: {root.as_posix()}"]
    for key in ("train", "val", "test"):
        img_dir, _ = split_dirs(root, key, layout)
        if img_dir.exists():
            lines.append(f"{key}: {img_dir.relative_to(root).as_posix()}")
    lines.append("names:")
    lines += [f"  {i}: {n}" for i, n in sorted(names.items())]
    p = out or (root / "data.local.yaml")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p