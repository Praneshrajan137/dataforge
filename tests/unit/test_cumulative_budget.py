"""The cumulative cell budget, and the properties that make it safe to consult.

The guard is unusual in that it reads state the product already maintains -- the hash-chained
transaction journal -- rather than a counter of its own. Most of these tests exist to pin the
consequences of that choice, because they are what make it safe:

* it can only ever *withhold* a write, never authorise one;
* a damaged or absent journal degrades to the pre-existing per-batch cap;
* reverting a repair returns the budget it consumed, with no expiry rule to invent.

The last one matters most. A cumulative budget with no reset is a ratchet that eventually
refuses everything, and inventing a time window would have meant fitting a constant to
nothing -- which ``PRODUCT.md`` section 1.4 records this project refusing to do even when the
fitted constant looked like a clean win. Deriving from the journal means the reset already
existed: it is ``dataforge revert``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dataforge.repairers.base import ProposedFix
from dataforge.safety.constitution import HIGH_VOLUME_CELL_BUDGET
from dataforge.safety.cumulative import (
    CUMULATIVE_CONFIRM_FLAG,
    CumulativeExposure,
    cumulative_exposure_for,
    cumulative_refusal_reason,
    cumulative_write_permitted,
)
from dataforge.safety.filter import SafetyContext
from dataforge.transactions.txn import CellFix


def _fixes(count: int) -> list[ProposedFix]:
    return [
        ProposedFix(
            fix=CellFix(
                row=index,
                column="City",
                old_value="old",
                new_value="new",
                detector_id="fd_violation",
            ),
            reason="test fixture",
            confidence=1.0,
            provenance="deterministic",
        )
        for index in range(count)
    ]


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "t.csv"
    path.write_text("ProviderID,City\n1,birmingham\n", encoding="utf-8")
    return path


class TestExposureArithmetic:
    """Pure properties of the exposure record."""

    def test_remaining_never_goes_negative(self) -> None:
        exposure = CumulativeExposure(
            cells_written=500, budget=100, transactions_counted=5, transactions_unreadable=0
        )
        assert exposure.remaining == 0
        assert exposure.exhausted

    def test_would_exceed_is_inclusive_of_the_budget(self) -> None:
        exposure = CumulativeExposure(
            cells_written=0, budget=100, transactions_counted=0, transactions_unreadable=0
        )
        assert not exposure.would_exceed(100), "exactly the budget must be permitted"
        assert exposure.would_exceed(101)

    def test_budget_is_the_constitution_constant_not_a_new_one(self) -> None:
        """No new tuned parameter. This is the point of the design, so it is pinned."""
        assert cumulative_exposure_for(Path("nonexistent.csv")).budget == HIGH_VOLUME_CELL_BUDGET


class TestFreshSourceIsUnconstrained:
    """A file with no history must behave exactly as before this guard existed."""

    def test_absent_journal_is_zero_not_an_error(self, source: Path) -> None:
        exposure = cumulative_exposure_for(source)
        assert exposure.cells_written == 0
        assert exposure.transactions_counted == 0
        assert exposure.transactions_unreadable == 0

    def test_a_batch_within_budget_is_permitted(self, source: Path) -> None:
        permitted, _, reason = cumulative_write_permitted(source, HIGH_VOLUME_CELL_BUDGET, None)
        assert permitted
        assert reason is None

    def test_a_batch_over_budget_is_refused_even_with_no_history(self, source: Path) -> None:
        """The cumulative guard subsumes the single-batch case rather than contradicting it."""
        permitted, _, reason = cumulative_write_permitted(source, HIGH_VOLUME_CELL_BUDGET + 1, None)
        assert not permitted
        assert reason is not None
        assert "NO_CUMULATIVE_HIGH_VOLUME_AUTO_APPLY" in reason


class TestTheRefusalIsActionable:
    """A refusal a caller cannot act on is only marginally better than a silent one."""

    def test_reason_names_the_numbers_and_all_three_remedies(self) -> None:
        exposure = CumulativeExposure(
            cells_written=80, budget=100, transactions_counted=2, transactions_unreadable=0
        )
        reason = cumulative_refusal_reason(exposure, 50)
        assert reason is not None
        assert "80" in reason and "50" in reason and "100" in reason
        assert "revert" in reason.lower()
        assert "split" in reason.lower()
        assert CUMULATIVE_CONFIRM_FLAG in reason

    def test_no_reason_when_the_write_fits(self) -> None:
        exposure = CumulativeExposure(
            cells_written=10, budget=100, transactions_counted=1, transactions_unreadable=0
        )
        assert cumulative_refusal_reason(exposure, 10) is None

    def test_exposure_is_reported_on_the_permitted_path_too(self, source: Path) -> None:
        """So a caller can split its own work before it is refused, not after."""
        permitted, exposure, _ = cumulative_write_permitted(source, 10, None)
        assert permitted
        assert exposure.to_dict()["remaining"] == HIGH_VOLUME_CELL_BUDGET


class TestTheConfirmationEscape:
    """The escape is the existing flag, not a new one."""

    def test_specific_flag_clears_the_budget(self, source: Path) -> None:
        permitted, _, reason = cumulative_write_permitted(
            source,
            HIGH_VOLUME_CELL_BUDGET * 10,
            SafetyContext(**{CUMULATIVE_CONFIRM_FLAG: True}),
        )
        assert permitted
        assert reason is None

    def test_deprecated_blanket_alias_also_clears_it(self, source: Path) -> None:
        """``confirm_escalations`` keeps its documented meaning here as everywhere else."""
        permitted, _, _ = cumulative_write_permitted(
            source, HIGH_VOLUME_CELL_BUDGET * 10, SafetyContext(confirm_escalations=True)
        )
        assert permitted

    def test_an_unrelated_confirmation_does_not_clear_it(self, source: Path) -> None:
        """Confirming PII exposure says nothing about blast radius."""
        permitted, _, _ = cumulative_write_permitted(
            source, HIGH_VOLUME_CELL_BUDGET + 1, SafetyContext(confirm_pii=True, allow_pii=True)
        )
        assert not permitted


class TestItCanOnlyWithholdNeverGrant:
    """The safety property that justifies reading the journal at all."""

    def test_an_unparseable_journal_entry_lowers_the_count(self, source: Path) -> None:
        """A corrupt entry must not be able to raise the total and thus grant nothing.

        Skipping is the only safe direction: an entry we cannot read might have written a
        million cells, but counting it as a million on a guess would refuse legitimate work,
        and counting it as zero merely leaves the per-batch cap in charge -- which is exactly
        where the product was before this guard existed.
        """
        journal = source.parent / ".dataforge" / "transactions"
        journal.mkdir(parents=True, exist_ok=True)
        (journal / "broken.jsonl").write_text("{not json at all\n", encoding="utf-8")

        exposure = cumulative_exposure_for(source)
        assert exposure.cells_written == 0
        assert exposure.transactions_unreadable == 1
        # And the per-batch-sized write is still permitted, i.e. we degraded rather than broke.
        permitted, _, _ = cumulative_write_permitted(source, HIGH_VOLUME_CELL_BUDGET, None)
        assert permitted

    def test_an_empty_journal_directory_is_zero(self, source: Path) -> None:
        (source.parent / ".dataforge" / "transactions").mkdir(parents=True, exist_ok=True)
        assert cumulative_exposure_for(source).cells_written == 0

    def test_never_writes_while_reading(self, source: Path) -> None:
        """Consulting the budget must not change it, or repeated reads would drift."""
        before = sorted(p.name for p in source.parent.rglob("*"))
        cumulative_exposure_for(source)
        cumulative_write_permitted(source, 10, None)
        after = sorted(p.name for p in source.parent.rglob("*"))
        assert before == after
