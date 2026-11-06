"""t_0 table conservation invariants: row count, column order, and non-null cell mass.

Autonomous agents and RL policies routinely discover degenerate reward hacks when a
verifier checks only local constraints: truncating rows to zero, dropping a constrained
column, or overwriting conflicting cells with empty/null sentinels so vacuously fewer
violations remain. This module makes table-wide structural and cell-mass conservation
an explicit, deterministic check.
"""

from __future__ import annotations

from dataclasses import dataclass

from dataforge.table import TableLike, column_names, column_values, row_count

_NULL_SENTINELS: frozenset[str] = frozenset({"", "null", "none", "nan", "n/a", "na", "<na>"})


def _is_populated(raw: object) -> bool:
    if raw is None:
        return False
    text = str(raw).strip()
    return text.lower() not in _NULL_SENTINELS


@dataclass(frozen=True, slots=True)
class ConservationReport:
    """Deterministic conservation audit comparing post-state against t_0 pre-state."""

    ok: bool
    rows_before: int
    rows_after: int
    columns_before: tuple[str, ...]
    columns_after: tuple[str, ...]
    non_null_before: int
    non_null_after: int
    nulls_introduced: int
    violations: tuple[str, ...]


def check_table_conservation(
    before: TableLike,
    after: TableLike,
    *,
    allow_new_nulls: bool = False,
    max_new_null_fraction: float = 0.0,
) -> ConservationReport:
    """Verify row-count, column-set, and populated-cell conservation from ``before`` to ``after``."""
    cols_before = tuple(column_names(before))
    cols_after = tuple(column_names(after))
    r_before = row_count(before)
    r_after = row_count(after)

    violations: list[str] = []
    if r_after != r_before:
        violations.append(
            f"row_count_changed: expected {r_before} rows from t_0, observed {r_after}"
        )
    if cols_after != cols_before:
        violations.append(
            f"column_schema_changed: expected {list(cols_before)}, observed {list(cols_after)}"
        )

    non_null_before = 0
    non_null_after = 0
    nulls_introduced = 0

    shared_cols = (
        cols_before
        if cols_before == cols_after
        else tuple(c for c in cols_before if c in set(cols_after))
    )
    shared_rows = min(r_before, r_after)

    for col in cols_before:
        vals_b = column_values(before, col)
        non_null_before += sum(1 for v in vals_b if _is_populated(v))

    for col in cols_after:
        vals_a = column_values(after, col)
        non_null_after += sum(1 for v in vals_a if _is_populated(v))

    for col in shared_cols:
        vals_b = column_values(before, col)
        vals_a = column_values(after, col)
        for idx in range(shared_rows):
            if _is_populated(vals_b[idx]) and not _is_populated(vals_a[idx]):
                nulls_introduced += 1

    if nulls_introduced > 0:
        if not allow_new_nulls:
            violations.append(
                f"null_flooding_detected: {nulls_introduced} populated cell(s) were erased to null/empty"
            )
        else:
            denominator = max(non_null_before, 1)
            fraction = nulls_introduced / denominator
            if fraction > max_new_null_fraction:
                violations.append(
                    f"null_budget_exceeded: {nulls_introduced}/{denominator} ({fraction:.4f}) "
                    f"exceeds max_new_null_fraction={max_new_null_fraction:.4f}"
                )

    return ConservationReport(
        ok=not violations,
        rows_before=r_before,
        rows_after=r_after,
        columns_before=cols_before,
        columns_after=cols_after,
        non_null_before=non_null_before,
        non_null_after=non_null_after,
        nulls_introduced=nulls_introduced,
        violations=tuple(violations),
    )
