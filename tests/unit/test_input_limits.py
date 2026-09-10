"""The input-size guard, and the binding between its constant and the measured artifact.

The important test here is :meth:`TestTheConstantIsArtifactBound.test_bytes_per_cell_covers_the_measured_range`.
``MEASURED_BYTES_PER_CELL`` is a published claim about this product's memory cost, and
``PRODUCT.md`` requires such a number to be bound to the artifact that produced it rather than
maintained by hand -- ``docs_truth.py`` and ``test_user_facing_numbers.py`` exist for exactly
that reason. Re-measuring on different hardware must fail this test rather than leave the
constant quietly disagreeing with the evidence.

The rest pin the guard's failure direction. Every ambiguity is resolved toward *refusing*,
because the alternative to a refusal here is not a slow run -- it is a process killed by the
kernel, with no receipt, no reason and no exit code for a caller to branch on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dataforge.limits import (
    LARGEST_MEASURED_CELLS,
    MAX_CELLS_ENV,
    MEASURED_BYTES_PER_CELL,
    MEMORY_FRACTION_ENV,
    InputTooLargeError,
    enforce_read_within_limits,
    estimate_csv_shape,
    estimate_read_cost,
    read_refusal_reason,
)

_ARTIFACT = Path(__file__).resolve().parents[2] / "eval" / "results" / "read_path_ceiling.json"


def _write_csv(path: Path, rows: int, columns: int) -> Path:
    header = ",".join(f"c{index}" for index in range(columns))
    line = ",".join("v" * 8 for _ in range(columns))
    path.write_text(header + "\n" + "\n".join([line] * rows) + "\n", encoding="utf-8")
    return path


class TestTheConstantIsArtifactBound:
    """The published cost figure must match the committed measurement."""

    def test_artifact_exists_and_declares_its_schema(self) -> None:
        assert _ARTIFACT.is_file(), (
            "eval/results/read_path_ceiling.json is missing. Regenerate with "
            "scripts/bench/measure_read_path_ceiling.py -- the constant in dataforge/limits.py "
            "is a published claim and must not float free of its evidence."
        )
        payload = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "read_path_ceiling_v1"

    def test_bytes_per_cell_covers_the_measured_range(self) -> None:
        """The constant must be at or above the measured maximum.

        At-or-above rather than equal: rounding up is safe, rounding down is the failure this
        guard exists to prevent. If a re-measurement exceeds the constant, this fails and the
        constant must be raised -- deliberately, with the artifact as the reason.
        """
        payload = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
        measured_max = payload["observed_bytes_per_cell_max"]
        assert measured_max > 0, "artifact recorded no successful measurement"
        assert measured_max <= MEASURED_BYTES_PER_CELL, (
            f"MEASURED_BYTES_PER_CELL={MEASURED_BYTES_PER_CELL} is below the measured maximum "
            f"{measured_max:.1f} B/cell. Raise the constant; do not lower the measurement."
        )

    def test_evidence_horizon_matches_the_artifact(self) -> None:
        """``LARGEST_MEASURED_CELLS`` must not claim more evidence than exists."""
        payload = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
        assert payload["largest_successful_cells"] >= LARGEST_MEASURED_CELLS

    def test_the_artifact_records_no_failures(self) -> None:
        """A failed grid point means the ceiling is inside the measured range."""
        payload = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
        assert payload["failures"] == [], (
            "the measurement grid contains failures, so the real ceiling is lower than "
            f"{LARGEST_MEASURED_CELLS:,} cells and LARGEST_MEASURED_CELLS overstates the evidence"
        )


class TestShapeEstimation:
    """Cheap shape estimation, and its stated inaccuracies."""

    def test_counts_rows_and_columns(self, tmp_path: Path) -> None:
        path = _write_csv(tmp_path / "t.csv", rows=25, columns=4)
        rows, columns = estimate_csv_shape(path)
        assert rows == 25
        assert columns == 4

    def test_empty_file_is_zero_not_an_error(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.csv"
        path.write_text("", encoding="utf-8")
        assert estimate_csv_shape(path) == (0, 0)

    def test_header_only_file_has_no_data_rows(self, tmp_path: Path) -> None:
        path = tmp_path / "header.csv"
        path.write_text("a,b,c\n", encoding="utf-8")
        rows, columns = estimate_csv_shape(path)
        assert rows == 0
        assert columns == 3

    def test_embedded_newline_overcounts_which_is_the_safe_direction(self, tmp_path: Path) -> None:
        """A quoted newline inflates the row count, so the guard errs toward refusing."""
        path = tmp_path / "quoted.csv"
        path.write_text('a,b\n"x\ny",2\n', encoding="utf-8")
        rows, _ = estimate_csv_shape(path)
        assert rows >= 2, "must not undercount a file containing quoted newlines"


class TestTheGuardPermitsOrdinaryInput:
    """A guard that refuses normal work is worse than no guard."""

    def test_small_file_is_permitted(self, tmp_path: Path) -> None:
        path = _write_csv(tmp_path / "t.csv", rows=100, columns=5)
        estimate = enforce_read_within_limits(path)
        assert estimate.permitted
        assert read_refusal_reason(estimate) is None

    def test_estimate_is_returned_on_the_permitted_path(self, tmp_path: Path) -> None:
        """So a caller can see headroom before it becomes a refusal."""
        path = _write_csv(tmp_path / "t.csv", rows=100, columns=5)
        estimate = enforce_read_within_limits(path)
        assert estimate.cells == 500
        assert estimate.estimated_frame_bytes == 500 * MEASURED_BYTES_PER_CELL
        assert estimate.limit_bytes > 0

    def test_the_shipped_fixture_is_permitted(self) -> None:
        fixture = Path(__file__).resolve().parents[2] / "fixtures" / "hospital_10rows.csv"
        if not fixture.is_file():
            pytest.skip("fixture not present")
        assert enforce_read_within_limits(fixture).permitted


class TestTheGuardRefusesAndSaysWhy:
    """A refusal must be actionable, and reachable without allocating a huge file."""

    def test_refuses_when_the_cell_cap_is_exceeded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(MAX_CELLS_ENV, "10")
        path = _write_csv(tmp_path / "t.csv", rows=100, columns=5)
        with pytest.raises(InputTooLargeError, match="INPUT_TOO_LARGE"):
            enforce_read_within_limits(path)

    def test_the_reason_names_the_numbers_and_the_remedies(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(MAX_CELLS_ENV, "10")
        path = _write_csv(tmp_path / "t.csv", rows=100, columns=5)
        reason = read_refusal_reason(estimate_read_cost(path))
        assert reason is not None
        assert "500" in reason, "must state the cell count it refused"
        assert "in-memory" in reason, "must say why slowing down is not an option"
        assert MEMORY_FRACTION_ENV in reason and MAX_CELLS_ENV in reason, (
            "a refusal that does not name the override is not actionable"
        )

    def test_an_operator_can_raise_the_limit_deliberately(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = _write_csv(tmp_path / "t.csv", rows=100, columns=5)
        monkeypatch.setenv(MAX_CELLS_ENV, "10")
        with pytest.raises(InputTooLargeError):
            enforce_read_within_limits(path)
        monkeypatch.setenv(MAX_CELLS_ENV, "1000000")
        assert enforce_read_within_limits(path).permitted

    def test_extrapolation_beyond_the_evidence_is_disclosed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Above the measured horizon the estimate is a model, and must say so."""
        monkeypatch.setenv(MAX_CELLS_ENV, "1")
        path = _write_csv(tmp_path / "t.csv", rows=2, columns=2)
        estimate = estimate_read_cost(path)
        assert not estimate.beyond_measured_evidence, "4 cells is well inside the evidence"
        reason = read_refusal_reason(estimate)
        assert reason is not None
        assert "extrapolation" not in reason.lower()


class TestTheCliBoundaryEnforcesIt:
    """The guard must be on the path user input actually takes."""

    def test_cli_read_csv_refuses_an_oversized_input(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from dataforge.cli.common import read_csv

        monkeypatch.setenv(MAX_CELLS_ENV, "10")
        path = _write_csv(tmp_path / "t.csv", rows=100, columns=5)
        with pytest.raises(InputTooLargeError):
            read_csv(path)

    def test_library_read_csv_is_deliberately_unguarded(self, tmp_path: Path) -> None:
        """The limit is a CLI-boundary policy, not a library primitive restriction.

        Pinned because the distinction is a design decision rather than an oversight: the
        engine builds frames for itself, and a hard cap inside the primitive would fire on
        internal work the user never asked about.
        """
        from dataforge.table import read_csv as library_read_csv

        path = _write_csv(tmp_path / "t.csv", rows=10, columns=3)
        assert library_read_csv(path) is not None
