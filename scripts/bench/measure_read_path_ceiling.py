"""Measure the in-memory ceiling of the shipped CSV read path.

Why this exists: nothing in this repository had ever measured how large an input the tool can
actually accept. ``CLAUDE.md`` records a detector-pass expectation ("under 2 seconds on a
10k-row CSV") but no memory figure at any size, and there is no ``chunksize`` anywhere in
``dataforge/`` -- the whole frame is held as Python strings, which is the correct choice for
correctness (type inference loses precision on identifiers and money) and simultaneously the
most memory-expensive representation available.

An unmeasured ceiling is a crash waiting for a large input, and a crash is the one failure
mode this product's doctrine has no answer for: ``PRODUCT.md`` treats a *named refusal* as a
first-class honest output, and an OOM kill is not one.

Two rules this harness follows, both from ``PRODUCT.md`` section 1.4:

* **It imports the shipped read path** (:func:`dataforge.table.read_csv`) rather than calling
  pandas itself. A shorter local loop is evidence *against* a measurement here, because the
  reimplementation is exactly what drifts from the code a user runs.
* **It reports what it measured, not a projection.** Extrapolating a ceiling from small
  samples would be inventing a number, so the artifact records the grid that was actually
  run and the largest cell count that actually succeeded.

Usage::

    python scripts/bench/measure_read_path_ceiling.py --out eval/results/read_path_ceiling.json
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import platform
import sys
import tempfile
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dataforge.table import read_csv, row_count  # noqa: E402

#: Grid measured by default. Deliberately modest so the harness is reproducible on a laptop
#: and in CI; the point is a measured curve and a measured ceiling, not a record attempt.
DEFAULT_GRID: tuple[tuple[int, int], ...] = (
    (1_000, 10),
    (10_000, 10),
    (10_000, 50),
    (100_000, 10),
    (100_000, 50),
    (250_000, 20),
)


@dataclass(frozen=True)
class ReadMeasurement:
    """One point on the read-path curve."""

    rows: int
    columns: int
    cells: int
    file_bytes: int
    peak_tracemalloc_bytes: int
    bytes_per_cell: float
    read_seconds: float
    ok: bool
    error: str | None = None


def _write_synthetic_csv(path: Path, rows: int, columns: int) -> int:
    """Write a deterministic CSV and return its size in bytes.

    Values are fixed-width and identifier-like on purpose: that is the shape ``dtype=str``
    exists to preserve, so measuring anything narrower would understate the cost.
    """
    header = [f"col_{index:03d}" for index in range(columns)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row_index in range(rows):
            writer.writerow([f"v{row_index:08d}_{col:03d}" for col in range(columns)])
    return path.stat().st_size


def measure_point(rows: int, columns: int, workdir: Path) -> ReadMeasurement:
    """Measure peak memory and wall clock for one (rows, columns) point."""
    path = workdir / f"synthetic_{rows}x{columns}.csv"
    file_bytes = _write_synthetic_csv(path, rows, columns)
    cells = rows * columns

    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    error: str | None = None
    ok = True
    try:
        table = read_csv(path)
        # Touch the frame so a lazy reader cannot make the measurement a lie.
        observed_rows = row_count(table)
        if observed_rows != rows:
            error = f"read {observed_rows} rows, expected {rows}"
            ok = False
        del table
    except MemoryError as exc:
        ok = False
        error = f"MemoryError: {exc}"
    except Exception as exc:  # noqa: BLE001 - the ceiling is whatever actually stops us
        ok = False
        error = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    path.unlink(missing_ok=True)
    gc.collect()

    return ReadMeasurement(
        rows=rows,
        columns=columns,
        cells=cells,
        file_bytes=file_bytes,
        peak_tracemalloc_bytes=peak,
        bytes_per_cell=(peak / cells) if cells else 0.0,
        read_seconds=elapsed,
        ok=ok,
        error=error,
    )


def run(grid: tuple[tuple[int, int], ...]) -> dict[str, Any]:
    """Run the grid and return the artifact payload."""
    measurements: list[ReadMeasurement] = []
    with tempfile.TemporaryDirectory() as raw_dir:
        workdir = Path(raw_dir)
        for rows, columns in grid:
            measurements.append(measure_point(rows, columns, workdir))

    successful = [m for m in measurements if m.ok]
    per_cell = [m.bytes_per_cell for m in successful if m.cells >= 10_000]
    return {
        "schema_version": "read_path_ceiling_v1",
        "what_this_measures": (
            "Peak Python heap (tracemalloc) and wall clock for dataforge.table.read_csv on "
            "synthetic identifier-like CSVs. Imports the shipped read path; does not "
            "reimplement it."
        ),
        "what_this_does_not_measure": (
            "Total process RSS, the detector or repairer passes, SMT verification, or any "
            "input larger than the largest grid point below. The ceiling reported here is "
            "the largest cell count MEASURED to succeed, not an extrapolated limit."
        ),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "measurements": [asdict(m) for m in measurements],
        "largest_successful_cells": max((m.cells for m in successful), default=0),
        "largest_successful_peak_bytes": max(
            (m.peak_tracemalloc_bytes for m in successful), default=0
        ),
        "observed_bytes_per_cell_min": min(per_cell, default=0.0),
        "observed_bytes_per_cell_max": max(per_cell, default=0.0),
        "failures": [asdict(m) for m in measurements if not m.ok],
    }


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None, help="Write the artifact here.")
    args = parser.parse_args(argv)

    payload = run(DEFAULT_GRID)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(rendered)

    for measurement in payload["measurements"]:
        status = "ok  " if measurement["ok"] else "FAIL"
        print(
            f"{status} {measurement['rows']:>8,} x {measurement['columns']:>3} "
            f"= {measurement['cells']:>10,} cells  "
            f"peak {measurement['peak_tracemalloc_bytes'] / 1e6:>8.1f} MB  "
            f"{measurement['bytes_per_cell']:>6.1f} B/cell  "
            f"{measurement['read_seconds']:>6.2f}s"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
