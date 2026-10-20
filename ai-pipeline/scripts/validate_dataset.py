"""Check a YOLO dataset: bad labels, split leakage, class balance. Optionally write data.local.yaml.

  python scripts/validate_dataset.py --root Dataset_SC_NOPUSH --write-yaml
"""
import argparse
import json
import sys
from pathlib import Path

import _bootstrap
from _bootstrap import ROOT

from swiftletcare_ai.dataset_tools import (detect_layout, imbalance_warnings, read_names_from_yaml,
                                           scan_dataset, write_local_yaml)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="dataset folder (roboflow or yolo layout)")
    ap.add_argument("--names", nargs="+", default=None, help="class names by id; default: read <root>/data.yaml")
    ap.add_argument("--write-yaml", action="store_true", help="write <root>/data.local.yaml (absolute paths)")
    ap.add_argument("--out", default=str(ROOT / "outputs/dataset_report.json"))
    a = ap.parse_args()
    root = Path(a.root)
    if a.names:
        names = dict(enumerate(a.names))
    elif (root / "data.yaml").exists():
        names = read_names_from_yaml(root / "data.yaml")
    else:
        names = {0: "swiftlet", 1: "rat", 2: "snake"}
    print("layout:", detect_layout(root), "| classes:", names)
    rep = scan_dataset(root, names)
    if not rep.splits:
        print("no images found in any split", file=sys.stderr)
        return 2
    print(f"{'split':<7}{'images':>8}{'labeled':>9}{'bg':>6}" + "".join(f"{n:>10}" for n in names.values()))
    for sp, s in rep.splits.items():
        print(f"{sp:<7}{s.images:>8}{s.labeled:>9}{s.background:>6}" + "".join(f"{s.boxes.get(n, 0):>10}" for n in names.values()))
    warns = imbalance_warnings(rep, names)
    for w in warns:
        print("WARNING:", w)
    if rep.polygons:
        print(f"NOTE: {rep.polygons} polygon label rows converted to bbox (ok for detect training)")
    for i in rep.issues[:20]:
        print(f"LABEL ERROR: {i.file}:{i.line} {i.message}")
    if len(rep.issues) > 20:
        print(f"... and {len(rep.issues) - 20} more")
    for l in rep.leaks[:20]:
        print("LEAK:", l)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({
        "ok": rep.ok, "warnings": warns, "issues": len(rep.issues), "leaks": len(rep.leaks),
        "polygons": rep.polygons,
        "splits": {k: {"images": v.images, "labeled": v.labeled, "background": v.background, "boxes": dict(v.boxes)}
                   for k, v in rep.splits.items()}}, indent=2, ensure_ascii=False), encoding="utf-8")
    if a.write_yaml:
        print("wrote:", write_local_yaml(root, names))
    print("RESULT:", "OK" if rep.ok else "PROBLEMS FOUND")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())