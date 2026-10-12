"""Per-mode manifest (metadata) size and bytes on the wire for one PUT, from raw records.

Reads only until every mode has been seen, so it stops early in each file.

    python analysis/metadata_sizes.py experiments/final-b/<stamp> experiments/final-a/<stamp>
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from pqcstore.benchmark.records import iter_lines

MODES = ("B0", "B1", "R1", "B2", "P1", "P2", "P3")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("experiments", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, default=Path("results/final/metadata.csv"))
    args = parser.parse_args()
    found: dict[str, dict] = {}
    for run_dir in args.experiments:
        for line in iter_lines(run_dir):
            if '"operation":"put"' not in line or '"success":true' not in line:
                continue
            r = json.loads(line)
            if r["mode"] in MODES and r["mode"] not in found:
                found[r["mode"]] = {"mode": r["mode"], "object_size_bytes": r["object_size_bytes"],
                                    "metadata_bytes": r["metadata_bytes"],
                                    "overhead_bytes": r["bytes_sent"] - r["object_size_bytes"],
                                    "source": run_dir.parent.name}
            if len(found) == len(MODES):
                break
        if len(found) == len(MODES):
            break
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(next(iter(found.values()))))
        writer.writeheader()
        writer.writerows(found[m] for m in MODES if m in found)
    print({m: found[m]["metadata_bytes"] for m in found})


if __name__ == "__main__":
    main()
