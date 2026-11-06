"""Exact Decimal / Z3 RealSort parity and IEEE-754 boundary hazard suite.

Verifies that SMTVerifier (Z3 exact rationals) and DirectVerifier (exact Python Decimal)
reach identical verdicts across IEEE-754 binary64 traps:
- NaN / Infinity / -Infinity fail closed (UNKNOWN) instead of bypassing domain bounds
  or raising uncaught Z3 exceptions;
- high-precision monetary decimals (> 53 bits of significand, e.g. 12345678901234567.89
  vs .88 and 9007199254740993 vs 9007199254740992) are never collapsed by binary64;
- alternative lexical spellings of equal numbers ("100.00" vs "100", "-0.0" vs "0.0",
  "1e2" vs "100", "01" vs "1") are treated identically in UNIQUE, FD, and ACCEPTED_VALUES;
- fractional DomainBounds over integer columns ("int", "integer") agree without truncation.
"""

from __future__ import annotations

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dataforge.repairers.base import ProposedFix
from dataforge.transactions.txn import CellFix
from dataforge.verifier.differential import differential_verify
from dataforge.verifier.direct import DirectVerifier
from dataforge.verifier.result import VerificationVerdict
from dataforge.verifier.schema import (
    AcceptedValues,
    DomainBound,
    FunctionalDependency,
    Schema,
)
from dataforge.verifier.smt import SMTVerifier


def _make_fix(row: int, col: str, old: str, new: str) -> ProposedFix:
    return ProposedFix(
        fix=CellFix(row=row, column=col, old_value=old, new_value=new, detector_id="parity"),
        reason="decimal-z3-parity",
        confidence=1.0,
        provenance="deterministic",
    )


@pytest.mark.parametrize("non_finite", ["nan", "NaN", "inf", "-inf", "Infinity", "-Infinity"])
def test_non_finite_literals_fail_closed_in_both_verifiers(non_finite: str) -> None:
    df = pd.DataFrame({"amount": ["10.00", "20.00"]})
    schema = Schema(
        columns={"amount": "float"},
        domain_bounds=(DomainBound(column="amount", min_value=0.0, max_value=100.0),),
    )
    fix = _make_fix(0, "amount", "10.00", non_finite)
    smt = SMTVerifier().verify(df, [fix], schema)
    direct = DirectVerifier().verify(df, [fix], schema)
    diff = differential_verify(df, [fix], schema)
    assert smt.verdict == VerificationVerdict.UNKNOWN
    assert direct.verdict == VerificationVerdict.UNKNOWN
    assert diff.verdict == VerificationVerdict.REJECT


def test_beyond_ieee754_monetary_precision_detects_collision_and_disagreement() -> None:
    # float("12345678901234567.89") == float("12345678901234567.88") in IEEE-754 binary64!
    # Exact Decimal + Z3 Rational must distinguish them cleanly.
    df = pd.DataFrame(
        {
            "acct": ["A1", "A1"],
            "balance": ["12345678901234567.89", "0.00"],
        }
    )
    schema = Schema(
        columns={"acct": "str", "balance": "decimal"},
        functional_dependencies=(FunctionalDependency(determinant=("acct",), dependent="balance"),),
    )
    wrong_cent = _make_fix(1, "balance", "0.00", "12345678901234567.88")
    exact_cent = _make_fix(1, "balance", "0.00", "12345678901234567.89")

    assert SMTVerifier().verify(df, [wrong_cent], schema).verdict == VerificationVerdict.REJECT
    assert DirectVerifier().verify(df, [wrong_cent], schema).verdict == VerificationVerdict.REJECT
    assert SMTVerifier().verify(df, [exact_cent], schema).verdict == VerificationVerdict.ACCEPT
    assert DirectVerifier().verify(df, [exact_cent], schema).verdict == VerificationVerdict.ACCEPT


@pytest.mark.parametrize(
    ("existing", "candidate", "ctype"),
    [
        ("100.00", "100", "float"),
        ("0.0", "-0.0", "float"),
        ("1e2", "100.0", "decimal"),
        ("01", "1", "int"),
    ],
)
def test_lexical_numeric_aliases_collide_under_unique_in_both_verifiers(
    existing: str, candidate: str, ctype: str
) -> None:
    df = pd.DataFrame({"val": [existing, "999"]})
    schema = Schema(columns={"val": ctype}, unique_columns=frozenset({"val"}))
    fix = _make_fix(1, "val", "999", candidate)
    smt = SMTVerifier().verify(df, [fix], schema)
    direct = DirectVerifier().verify(df, [fix], schema)
    assert smt.verdict == VerificationVerdict.REJECT
    assert direct.verdict == VerificationVerdict.REJECT


def test_numeric_determinant_lexical_aliases_enforce_fd_in_both_verifiers() -> None:
    df = pd.DataFrame({"rate": ["100.00", "50.0"], "tier": ["GOLD", "SILVER"]})
    schema = Schema(
        columns={"rate": "float", "tier": "str"},
        functional_dependencies=(FunctionalDependency(determinant=("rate",), dependent="tier"),),
    )
    # Moving row 1's rate to "100" puts it in row 0's determinant group ("100.00"),
    # which conflicts because tier is "SILVER" != "GOLD".
    fix = _make_fix(1, "rate", "50.0", "100")
    smt = SMTVerifier().verify(df, [fix], schema)
    direct = DirectVerifier().verify(df, [fix], schema)
    assert smt.verdict == VerificationVerdict.REJECT
    assert direct.verdict == VerificationVerdict.REJECT


@pytest.mark.parametrize("int_spelling", ["int", "integer"])
def test_fractional_domain_bounds_on_integer_columns_do_not_truncate(int_spelling: str) -> None:
    df = pd.DataFrame({"qty": ["5", "10"]})
    schema = Schema(
        columns={"qty": int_spelling},
        domain_bounds=(DomainBound(column="qty", min_value=1.5, max_value=9.5),),
    )
    below = _make_fix(0, "qty", "5", "1")
    above = _make_fix(0, "qty", "5", "10")
    inside = _make_fix(0, "qty", "5", "9")
    for candidate, expected in [
        (below, VerificationVerdict.REJECT),
        (above, VerificationVerdict.REJECT),
        (inside, VerificationVerdict.ACCEPT),
    ]:
        assert SMTVerifier().verify(df, [candidate], schema).verdict == expected
        assert DirectVerifier().verify(df, [candidate], schema).verdict == expected


_FLOAT_LITERALS = [
    "-1.5",
    "-0.0",
    "0",
    "0.0",
    "0.1",
    "0.2",
    "0.3",
    "1",
    "1.0",
    "1.5",
    "10",
    "10.00",
    "1e1",
    "12345678901234567.89",
    "12345678901234567.88",
]


@settings(max_examples=120, deadline=None)
@given(
    v0=st.sampled_from(_FLOAT_LITERALS),
    v1=st.sampled_from(_FLOAT_LITERALS),
    candidate=st.sampled_from(_FLOAT_LITERALS),
    use_unique=st.booleans(),
    use_enum=st.booleans(),
    lo=st.sampled_from([-1.5, 0.0, 0.1, 1.5]),
    hi=st.sampled_from([1.5, 10.0, 1e18]),
    inc_lo=st.booleans(),
    inc_hi=st.booleans(),
)
def test_hypothesis_float_decimal_equivalence(
    v0: str,
    v1: str,
    candidate: str,
    use_unique: bool,
    use_enum: bool,
    lo: float,
    hi: float,
    inc_lo: bool,
    inc_hi: bool,
) -> None:
    df = pd.DataFrame({"x": [v0, v1]})
    schema = Schema(
        columns={"x": "float"},
        domain_bounds=(
            DomainBound(
                column="x",
                min_value=lo,
                max_value=hi,
                inclusive_min=inc_lo,
                inclusive_max=inc_hi,
            ),
        ),
        accepted_values=(
            (AcceptedValues(column="x", values=("0", "0.3", "10", "12345678901234567.89")),)
            if use_enum
            else ()
        ),
        unique_columns=frozenset({"x"}) if use_unique else frozenset(),
    )
    fix = _make_fix(0, "x", v0, candidate)
    smt = SMTVerifier().verify(df, [fix], schema)
    direct = DirectVerifier().verify(df, [fix], schema)
    assert smt.verdict == direct.verdict, (
        f"Decimal/Z3 mismatch: smt={smt.verdict} ({smt.reason}) vs "
        f"direct={direct.verdict} ({direct.reason})"
    )
