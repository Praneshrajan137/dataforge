"""Cumulative write exposure across invocations, derived from the transaction journal.

``dataforge/safety/constitution.py`` names this gap in ``_high_volume_batch``'s docstring:

    *"No cross-batch accumulation. A sequence of batches each just under budget still
    passes... the agent path issues many batches and can walk under the budget
    indefinitely."*

**Two corrections to how that gap was understood, both established by reading the code.**

First, the agent surface does *not* issue many batches per run. ``run_agent_repair`` evaluates
the batch gate once (``dataforge/agent/controller.py``) and calls ``apply_transaction`` once,
in a top-level branch rather than a loop; ``max_steps`` bounds the executor's *reasoning*
steps, which feed a single fix set. So a per-run accumulator -- the obvious reading, and the
one an earlier plan for this module specified -- would protect nothing at all. The real
evasion vector is **repeated invocation**: an MCP client calling ``dataforge_agent_repair``
twenty times writes twenty budgets' worth of cells, each invocation individually compliant.

Second, closing that does **not** require new persistent state, which was the cost this
change was expected to carry. Every applied write is already recorded in the hash-chained
transaction journal under ``.dataforge/transactions/``, because that journal is what makes a
repair reversible. Cumulative exposure is therefore *derivable* from state the product
already maintains and already treats as authoritative. Introducing a second counter would
have created a new authority-bearing artifact that could disagree with the journal -- and
``docs/trust/authority-is-mutable.md`` is about exactly that class of risk.

Three properties make this safe to consult before a write:

* **It can only withhold, never grant.** The count is a floor: a missing, truncated or
  unreadable journal yields a *smaller* number, so the worst case degrades to the per-batch
  cap that already applied. Nothing here can authorise a write that ``_high_volume_batch``
  would refuse.
* **Reset is already defined, and was not invented here.** ``dataforge revert`` marks a
  transaction reverted, and reverted transactions are excluded, so undoing a repair returns
  the budget it consumed. There is no new expiry rule and no new tuned constant: the budget
  is ``HIGH_VOLUME_CELL_BUDGET``, the same constant ``PRODUCT.md`` declines to re-fit.
* **The escape is the existing one.** The same confirmation flag that clears a capped batch
  clears a cumulative overrun, so an operator who has already accepted blast radius is not
  asked a second, differently-worded question.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dataforge.safety.constitution import HIGH_VOLUME_CELL_BUDGET
from dataforge.safety.filter import SafetyContext
from dataforge.transactions.log import load_transaction, transactions_dir_for

#: The confirmation flag that clears a cumulative overrun.
#:
#: Deliberately the *same* flag as the per-batch cell budget rather than a new one. Both
#: guards protect one quantity -- how many cells this tool may rewrite without a human
#: saying so -- and splitting the confirmation would let an operator clear one while
#: believing they had cleared both.
CUMULATIVE_CONFIRM_FLAG = "confirm_high_volume"


@dataclass(frozen=True)
class CumulativeExposure:
    """Cells already written to a source path, and what that permits next.

    ``cells_written`` is a floor rather than an exact figure, and callers must treat it as
    one: an unreadable journal entry is skipped rather than guessed at.
    """

    cells_written: int
    budget: int
    transactions_counted: int
    transactions_unreadable: int

    @property
    def remaining(self) -> int:
        """Return cells still writable under the budget, never negative."""
        return max(0, self.budget - self.cells_written)

    @property
    def exhausted(self) -> bool:
        """Return whether the budget is already spent."""
        return self.cells_written >= self.budget

    def would_exceed(self, additional_cells: int) -> bool:
        """Return whether writing ``additional_cells`` more would breach the budget."""
        return self.cells_written + additional_cells > self.budget

    def to_dict(self) -> dict[str, object]:
        """Serialize for a receipt so a machine caller can budget for itself.

        Reported even when the guard permits the write. A caller that can see it is
        approaching the budget can split its own work; one that only learns at the refusal
        has already wasted the round trip. This is the field that makes the guard cooperative
        rather than merely obstructive.
        """
        return {
            "cells_written": self.cells_written,
            "budget": self.budget,
            "remaining": self.remaining,
            "transactions_counted": self.transactions_counted,
            "transactions_unreadable": self.transactions_unreadable,
        }


def cumulative_exposure_for(
    source_path: Path,
    *,
    budget: int = HIGH_VOLUME_CELL_BUDGET,
) -> CumulativeExposure:
    """Return cells already written to ``source_path`` by applied, unreverted transactions.

    Reads the existing journal. Never writes, so consulting the budget cannot itself change
    it, and a read-only or absent ``.dataforge`` directory is a zero rather than an error.
    """
    journal_dir = transactions_dir_for(source_path)
    if not journal_dir.is_dir():
        return CumulativeExposure(
            cells_written=0,
            budget=budget,
            transactions_counted=0,
            transactions_unreadable=0,
        )

    cells = 0
    counted = 0
    unreadable = 0
    resolved_source = source_path.resolve()
    for log_path in sorted(journal_dir.glob("*.jsonl")):
        try:
            transaction = load_transaction(log_path)
        except Exception:
            # A journal entry this module cannot parse is skipped, not guessed at. Skipping
            # lowers the count, which is the direction that cannot manufacture authority.
            unreadable += 1
            continue
        if not transaction.applied or transaction.reverted_at is not None:
            continue
        # The journal is keyed by directory, and two files can share one `.dataforge`, so the
        # recorded source path is checked rather than assumed.
        if Path(transaction.source_path).resolve() != resolved_source:
            continue
        cells += len({(fix.row, fix.column) for fix in transaction.fixes})
        counted += 1

    return CumulativeExposure(
        cells_written=cells,
        budget=budget,
        transactions_counted=counted,
        transactions_unreadable=unreadable,
    )


def cumulative_refusal_reason(
    exposure: CumulativeExposure,
    additional_cells: int,
) -> str | None:
    """Return why a cumulative write must be withheld, or ``None`` if it may proceed.

    Phrased like the constitution's own rule identifiers so a caller sees the same shape of
    reason from both budgets.
    """
    if not exposure.would_exceed(additional_cells):
        return None
    return (
        "NO_CUMULATIVE_HIGH_VOLUME_AUTO_APPLY: this source has already had "
        f"{exposure.cells_written} cell(s) written by earlier invocations and {additional_cells} "
        f"more would exceed the {exposure.budget}-cell budget. Revert an earlier repair to "
        f"return its budget, split the work, or pass the {CUMULATIVE_CONFIRM_FLAG} "
        "confirmation."
    )


def cumulative_write_permitted(
    source_path: Path,
    additional_cells: int,
    context: SafetyContext | None,
    *,
    budget: int = HIGH_VOLUME_CELL_BUDGET,
) -> tuple[bool, CumulativeExposure, str | None]:
    """Return whether a cumulative write is permitted, with its exposure and reason.

    The exposure is returned on the permitted path too, so a surface can report it whether or
    not it refused.
    """
    exposure = cumulative_exposure_for(source_path, budget=budget)
    if context is not None and context.confirms(CUMULATIVE_CONFIRM_FLAG):
        return True, exposure, None
    reason = cumulative_refusal_reason(exposure, additional_cells)
    return reason is None, exposure, reason
