"""Unit tests for t_0 table conservation invariants (row, column, and non-null mass)."""

from __future__ import annotations

import pandas as pd

from dataforge.safety import check_table_conservation


def test_legitimate_value_repair_conserves_structure_and_mass() -> None:
    before = pd.DataFrame({"zip": ["36274", "36274"], "city": ["ROANOKE", "ROANOK"]})
    after = pd.DataFrame({"zip": ["36274", "36274"], "city": ["ROANOKE", "ROANOKE"]})
    report = check_table_conservation(before, after)
    assert report.ok is True
    assert report.nulls_introduced == 0
    assert report.violations == ()


def test_zero_row_truncation_hack_is_rejected() -> None:
    before = pd.DataFrame({"zip": ["36274", "36274"], "city": ["ROANOKE", "ROANOK"]})
    after = pd.DataFrame({"zip": pd.Series(dtype="str"), "city": pd.Series(dtype="str")})
    report = check_table_conservation(before, after)
    assert report.ok is False
    assert any("row_count_changed" in v for v in report.violations)


def test_column_deletion_hack_is_rejected() -> None:
    before = pd.DataFrame({"zip": ["36274"], "city": ["ROANOK"]})
    after = pd.DataFrame({"zip": ["36274"]})
    report = check_table_conservation(before, after)
    assert report.ok is False
    assert any("column_schema_changed" in v for v in report.violations)


def test_null_flooding_erasure_is_rejected_by_default() -> None:
    before = pd.DataFrame({"zip": ["36274", "36274"], "city": ["ROANOKE", "ROANOK"]})
    after = pd.DataFrame({"zip": ["36274", "36274"], "city": ["ROANOKE", "NULL"]})
    report = check_table_conservation(before, after)
    assert report.ok is False
    assert report.nulls_introduced == 1
    assert any("null_flooding_detected" in v for v in report.violations)


def test_bounded_null_allowance_respects_budget() -> None:
    before = pd.DataFrame({"a": ["1", "2", "3", "4"]})
    after_one = pd.DataFrame({"a": ["1", "", "3", "4"]})
    after_two = pd.DataFrame({"a": ["1", "", "", "4"]})
    assert check_table_conservation(
        before, after_one, allow_new_nulls=True, max_new_null_fraction=0.25
    ).ok
    refused = check_table_conservation(
        before, after_two, allow_new_nulls=True, max_new_null_fraction=0.25
    )
    assert not refused.ok
    assert any("null_budget_exceeded" in v for v in refused.violations)
