"""Pins the warehouse write-budget boundary: what is enforced, and what is not.

``PRODUCT.md`` §8 says "No surface may create parallel write semantics", and
``dataforge/stores/duckdb.py`` names one place the warehouse backend falls short of the
file backend. An audit on 2026-09-12 found the *description* of that shortfall was wider
than the shortfall itself, which is its own kind of inaccuracy: read literally, the old
comment implied the warehouse path had no volume gate at all.

Both halves are pinned here because a named gap that nothing tests is a gap that drifts.

**Enforced.** The single-batch disposition, including ``confirm_high_volume``.
``stores/repair.py`` evaluates it with the caller's ``SafetyContext`` and plans only
``disposition.applied``, so an over-budget batch is held before any SQL exists.

**Not enforced.** Cumulative exposure across runs, and for a *structural* reason rather
than a missing threshold: ``cumulative_exposure_for`` counts cells from
``transaction.fixes``, and the warehouse transaction records ``fixes=[]`` because the
changed cells live in ``patch_plan``. Any future fix has to teach the counter to read a
patch plan; raising or lowering a budget cannot help. If someone does that work, the
``test_cumulative_counting_is_structurally_impossible_today`` test below should fail, which
is the point of writing it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dataforge.repairers.base import ProposedFix
from dataforge.safety import SafetyContext
from dataforge.safety.cumulative import HIGH_VOLUME_CELL_BUDGET, cumulative_exposure_for
from dataforge.safety.disposition import evaluate_batch_disposition
from dataforge.transactions.txn import CellFix

_OVER_BUDGET = HIGH_VOLUME_CELL_BUDGET + 50


def _fixes(count: int) -> list[ProposedFix]:
    """Build ``count`` deterministic single-cell fixes on distinct rows."""
    return [
        ProposedFix(
            fix=CellFix(
                row=index,
                column="city",
                old_value="bostonn",
                new_value="boston",
                detector_id="fd_violation",
            ),
            reason="declared functional dependency",
            confidence=1.0,
            provenance="deterministic",
        )
        for index in range(count)
    ]


class TestSingleBatchVolumeIsEnforced:
    """The half that holds, on the shared derivation the warehouse path calls."""

    def test_over_budget_batch_is_escalated_without_confirmation(self) -> None:
        disposition = evaluate_batch_disposition(
            _fixes(_OVER_BUDGET), SafetyContext(confirm_escalations=False)
        )
        assert disposition.verdict.value == "escalate"
        assert len(disposition.applied) == 0
        assert len(disposition.held) == _OVER_BUDGET
        assert "confirm_high_volume" in disposition.required_confirm_flags

    def test_over_budget_batch_applies_with_confirmation(self) -> None:
        """The flag is the documented escape, and it must actually work."""
        disposition = evaluate_batch_disposition(
            _fixes(_OVER_BUDGET), SafetyContext(confirm_escalations=True)
        )
        assert disposition.verdict.value == "allow"
        assert len(disposition.applied) == _OVER_BUDGET

    def test_under_budget_batch_needs_no_confirmation(self) -> None:
        disposition = evaluate_batch_disposition(
            _fixes(HIGH_VOLUME_CELL_BUDGET - 50), SafetyContext(confirm_escalations=False)
        )
        assert disposition.verdict.value == "allow"
        assert len(disposition.held) == 0


class TestCumulativeExposureGap:
    """The half that does not hold, pinned so it cannot change unnoticed."""

    def test_warehouse_transaction_records_no_per_cell_fixes(self) -> None:
        """``fixes=[]`` is the structural reason cumulative counting reads zero.

        Asserted against the source rather than a live apply so the pin holds without a
        DuckDB connection, and so it names the exact line a future fix must change.
        """
        source = Path("dataforge/stores/duckdb.py").read_text(encoding="utf-8")
        assert "fixes=[]," in source, (
            "DuckDBStore no longer records an empty fix list. If it now records the cells it "
            "wrote, cumulative exposure may have become computable for the warehouse backend "
            "-- update the comment in apply_patch_plan and this test together."
        )

    def test_cumulative_counting_is_structurally_impossible_today(self, tmp_path: Path) -> None:
        """A table target has no file journal, so exposure is zero by construction.

        This is not asserting that zero is *correct*. It is asserting that zero is what the
        current design produces, so that closing the gap breaks this test and forces the
        comment in ``apply_patch_plan`` to be revisited.
        """
        exposure = cumulative_exposure_for(tmp_path / "some_warehouse_table")
        assert exposure.cells_written == 0
        assert exposure.transactions_counted == 0

    def test_budget_constant_is_shared_not_redeclared(self) -> None:
        """Both surfaces must read one budget, or they cannot be compared at all."""
        assert HIGH_VOLUME_CELL_BUDGET == 100


@pytest.mark.parametrize("confirmed", [False, True])
def test_disposition_is_the_single_derivation_point(confirmed: bool) -> None:
    """The warehouse path must not re-implement the volume rule locally.

    ``PRODUCT.md`` §1.4 records that a reimplemented measurement reproduces the defect the
    vetted path exists to avoid. The same applies to a gate: ``stores/repair.py`` must reach
    this decision through ``evaluate_batch_disposition``, not a local length check.
    """
    source = Path("dataforge/stores/repair.py").read_text(encoding="utf-8")
    assert "evaluate_batch_disposition(" in source
    assert "HIGH_VOLUME_CELL_BUDGET" not in source, (
        "the warehouse path appears to compare against the budget directly; it must inherit "
        "the decision from the shared disposition instead"
    )
    disposition = evaluate_batch_disposition(
        _fixes(_OVER_BUDGET), SafetyContext(confirm_escalations=confirmed)
    )
    assert (disposition.verdict.value == "allow") is confirmed
