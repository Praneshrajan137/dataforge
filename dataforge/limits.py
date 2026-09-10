"""Input-size limits for the in-memory read path.

The read path holds the entire frame as Python strings -- ``dtype=str``, no ``chunksize``
anywhere in the package -- because that is what preserves identifier and monetary precision
(``CLAUDE.md``). It is also the most memory-expensive representation available, and until
2026-09-10 nothing had measured what that costs, so the tool's response to an input larger
than memory was to be OOM-killed.

That is the one failure mode this product's doctrine cannot absorb. ``PRODUCT.md`` treats a
*named refusal* as a first-class honest output; a process killed by the kernel produces no
receipt, no reason, no exit code a caller can branch on, and -- for the autonomous agent this
product now targets -- nothing to act on.

**No new tuned constant is introduced here**, which matters because ``PRODUCT.md`` section 1.4
records refusing to ship a fitted parameter even when it looked like a clean win. The guard
composes two things that are not guesses:

* :data:`MEASURED_BYTES_PER_CELL` -- a *physical* constant measured on the shipped read path
  and pinned to a committed artifact by ``tests/unit/test_input_limits.py``. It is the
  conservative end of the measured range, because under-estimating cost is the unsafe
  direction.
* The machine's actual available memory, read at call time via ``psutil`` (already a declared
  dependency). Nothing is assumed about the host.

What remains is a policy fraction -- how much of available memory a single read may claim --
which is a deliberate operator choice with a stated default rather than a fitted value, and is
overridable per call and by environment variable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

#: Peak Python heap per cell, in bytes, for the shipped ``read_csv`` path.
#:
#: Measured 2026-09-10 across 10k to 5M cells on identifier-like data: the observed range was
#: 77.6 to 85.9 bytes per cell, linear in cell count with no inflection. This constant is the
#: TOP of that range, rounded up, because a guard that under-estimates cost fails in the
#: direction it exists to prevent.
#:
#: Bound to ``eval/results/read_path_ceiling.json`` by ``tests/unit/test_input_limits.py``, so
#: re-measuring on different hardware fails the test rather than silently disagreeing with a
#: published number. Regenerate with ``scripts/bench/measure_read_path_ceiling.py``.
MEASURED_BYTES_PER_CELL = 86

#: Largest cell count actually measured to succeed. Anything above this is EXTRAPOLATION.
#:
#: Recorded separately from the guard because the two answer different questions: the guard
#: asks "will this fit in memory now", while this says "how far does our evidence reach".
#: Beyond it the linear model is an assumption, and the refusal message says so.
LARGEST_MEASURED_CELLS = 5_000_000

#: Fraction of *available* memory a single read may claim by default.
#:
#: A policy default, not a measurement. Set below one because the frame is not the only
#: allocation a run makes -- detectors, the repairer and the verifier all build structures on
#: top of it -- and because leaving the host with no headroom converts a refusal into a
#: system-wide stall. Override per call, or with ``DATAFORGE_MAX_READ_MEMORY_FRACTION``.
DEFAULT_MEMORY_FRACTION = 0.5

#: Environment overrides, so an operator who knows their host can raise or lower the guard
#: without editing code or passing arguments through every layer.
MEMORY_FRACTION_ENV = "DATAFORGE_MAX_READ_MEMORY_FRACTION"
MAX_CELLS_ENV = "DATAFORGE_MAX_READ_CELLS"


class InputTooLargeError(RuntimeError):
    """Raised when a read is estimated not to fit in available memory.

    A distinct type because the remedy is distinct and a machine caller must be able to
    branch on it: this is not a malformed file and not a permission problem, and retrying the
    same input unchanged on the same host will fail the same way. The caller's options are to
    split the input, raise the limit deliberately, or run somewhere larger.
    """


@dataclass(frozen=True)
class ReadCostEstimate:
    """An estimate of what reading a file will cost, and whether it is permitted."""

    rows: int
    columns: int
    cells: int
    file_bytes: int
    estimated_frame_bytes: int
    available_bytes: int
    limit_bytes: int
    beyond_measured_evidence: bool

    @property
    def permitted(self) -> bool:
        """Return whether the estimated cost fits within the limit."""
        return self.estimated_frame_bytes <= self.limit_bytes

    def to_dict(self) -> dict[str, object]:
        """Serialize for a receipt so a caller can size its own work."""
        return {
            "rows": self.rows,
            "columns": self.columns,
            "cells": self.cells,
            "file_bytes": self.file_bytes,
            "estimated_frame_bytes": self.estimated_frame_bytes,
            "available_bytes": self.available_bytes,
            "limit_bytes": self.limit_bytes,
            "permitted": self.permitted,
            "beyond_measured_evidence": self.beyond_measured_evidence,
        }


def _available_bytes() -> int:
    """Return available system memory, or a large sentinel if it cannot be determined.

    Falling back to "effectively unlimited" is deliberate. If the host cannot be measured,
    refusing every read would break the tool on platforms where ``psutil`` is degraded, while
    permitting it merely restores the pre-2026-09-10 behaviour -- which is the status quo, not
    a regression.
    """
    try:
        import psutil

        return int(psutil.virtual_memory().available)
    except Exception:  # noqa: BLE001 - any failure means "unknown", handled above
        return sys_maxsize_fallback()


def sys_maxsize_fallback() -> int:
    """Return the sentinel used when available memory is unknown."""
    return 1 << 62


def _memory_fraction(explicit: float | None) -> float:
    """Resolve the memory fraction from an argument, the environment, then the default."""
    if explicit is not None:
        return explicit
    raw = os.environ.get(MEMORY_FRACTION_ENV)
    if raw:
        try:
            parsed = float(raw)
        except ValueError:
            return DEFAULT_MEMORY_FRACTION
        if 0.0 < parsed <= 1.0:
            return parsed
    return DEFAULT_MEMORY_FRACTION


def estimate_csv_shape(path: Path) -> tuple[int, int]:
    """Return ``(data_rows, columns)`` for a CSV without materialising it.

    Counts newlines in binary chunks and reads only the header for the column count. This is
    an *estimate*: a quoted field containing newlines inflates the row count, which errs
    toward refusing -- the safe direction for a guard.
    """
    with path.open("rb") as handle:
        first_line = handle.readline()
        columns = first_line.count(b",") + 1 if first_line else 0
        newlines = 0
        while True:
            chunk = handle.read(1 << 20)
            if not chunk:
                break
            newlines += chunk.count(b"\n")
    # `newlines` counts terminators after the header; a file without a trailing newline still
    # has one final unterminated row, so this can undercount by one. Immaterial at the scale
    # this guard operates on, and stated rather than silently rounded.
    return max(0, newlines), max(0, columns)


def estimate_read_cost(
    path: Path,
    *,
    memory_fraction: float | None = None,
    bytes_per_cell: int = MEASURED_BYTES_PER_CELL,
) -> ReadCostEstimate:
    """Estimate the memory cost of reading ``path`` and whether it is permitted."""
    rows, columns = estimate_csv_shape(path)
    cells = rows * columns
    available = _available_bytes()
    fraction = _memory_fraction(memory_fraction)
    limit = int(available * fraction)

    max_cells_raw = os.environ.get(MAX_CELLS_ENV)
    if max_cells_raw:
        try:
            max_cells = int(max_cells_raw)
        except ValueError:
            max_cells = 0
        if max_cells > 0:
            # An explicit cell cap is an operator statement about their host and overrides the
            # memory-derived limit in both directions.
            limit = max_cells * bytes_per_cell

    return ReadCostEstimate(
        rows=rows,
        columns=columns,
        cells=cells,
        file_bytes=path.stat().st_size if path.exists() else 0,
        estimated_frame_bytes=cells * bytes_per_cell,
        available_bytes=available,
        limit_bytes=limit,
        beyond_measured_evidence=cells > LARGEST_MEASURED_CELLS,
    )


def read_refusal_reason(estimate: ReadCostEstimate) -> str | None:
    """Return why a read must be refused, or ``None`` if it may proceed."""
    if estimate.permitted:
        return None
    evidence_note = (
        " This input is larger than anything this cost model was measured on "
        f"({LARGEST_MEASURED_CELLS:,} cells), so the estimate is an extrapolation."
        if estimate.beyond_measured_evidence
        else ""
    )
    return (
        f"INPUT_TOO_LARGE: reading {estimate.rows:,} row(s) x {estimate.columns} column(s) "
        f"= {estimate.cells:,} cells is estimated to need "
        f"{estimate.estimated_frame_bytes / 1e9:.2f} GB of memory, above the "
        f"{estimate.limit_bytes / 1e9:.2f} GB limit derived from "
        f"{estimate.available_bytes / 1e9:.2f} GB available. This read path is in-memory with "
        f"no streaming mode, so it would be terminated rather than slowed. Split the input, or "
        f"raise the limit deliberately with {MEMORY_FRACTION_ENV} or {MAX_CELLS_ENV}."
        f"{evidence_note}"
    )


def enforce_read_within_limits(
    path: Path,
    *,
    memory_fraction: float | None = None,
) -> ReadCostEstimate:
    """Raise :class:`InputTooLargeError` if reading ``path`` would not fit; else return cost.

    The estimate is returned on the permitted path too, so a caller can report headroom
    before it becomes a refusal.
    """
    estimate = estimate_read_cost(path, memory_fraction=memory_fraction)
    reason = read_refusal_reason(estimate)
    if reason is not None:
        raise InputTooLargeError(reason)
    return estimate
