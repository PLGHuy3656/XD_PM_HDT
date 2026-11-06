"""Split a flat dataset (images/, labels/) into train/val/test by video group and write data.yaml.

  python scripts/split_dataset.py --src raw --out Dataset_SC_NOPUSH --group-regex "^(.*)_f\\d+$"
Only needed if the dataset is not split yet.
"""
import argparse
from pathlib import Path

import _bootstrap  # noqa: F401

from swiftletcare_ai.dataset_tools import split_dataset, write_data_yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ratios", nargs=3, type=float, default=[0.7, 0.2, 0.1])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--group-regex", default=None, help="regex with 1 group capturing the video name")
    ap.add_argument("--names", nargs="+", default=["swiftlet", "rat", "snake"])
    ap.add_argument("--move", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    counts = split_dataset(Path(a.src), out, tuple(a.ratios), a.seed, a.group_regex, a.move)
    print("images per split:", counts, "| data.yaml:", write_data_yaml(out, dict(enumerate(a.names))))


if __name__ == "__main__":
    main()