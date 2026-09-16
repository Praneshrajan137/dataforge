"""The adversarial corpus: proposals designed to defeat the proven-only gate.

Why this exists
---------------
The guardrail claim -- "an untrusted agent proposes fixes and nothing incorrect is
silently written" -- was previously evidenced by a run that recorded ``agent_fix_count:
0``. Zero proposals reached the gate, so "zero corruptions" was a statement about an empty
set. ``docs/trust/write-surface-uniformity.md`` says so directly: *"n=1, 150 rows, one
dataset, one model, dry-run."*

This corpus gives the claim a denominator. Every entry is a proposal built specifically to
slip past a naive gate, paired with the ground-truth value it is attacking, so a
**corruption** is measurable rather than assumed: a corruption is a fix that was APPLIED
and whose applied value differs from ground truth.

What it is designed to reveal
-----------------------------
Not a comfortable zero. The corpus is run under TWO premises:

* a **tight** schema (typed, bounded, pattern-constrained, enumerated), and
* a **permissive** schema that merely declares every column ``str``.

Both cover every column, so under both the gate reports the writes as ``proven``. The
difference in measured corruption between them is the quantity nobody had measured: how
much of the guarantee comes from the gate, and how much comes from the quality of the
premise it was handed. ``docs/trust/authority-is-mutable.md`` predicts the answer in prose
-- *"Covering a column is not the same as constraining the value ... The strength of a
proof is still the strength of its premise"* -- and this turns that sentence into a number.

A corpus that only ever reported zero would be measuring its own optimism.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from dataforge.detectors.base import (
    AcceptedValues,
    AggregateDependency,
    DomainBound,
    RegexConstraint,
    RelationshipConstraint,
    Schema,
)
from dataforge.engine.repair import ExternalFix

# Imported rather than reimplemented: the bound that appears in published claims must be
# the same function the product ships, or the corpus is measuring something else.
from dataforge.metrics import clopper_pearson_upper

__all__ = [
    "ACCEPTED_VALUES_ONLY_SCHEMA",
    "COLUMNS",
    "DDL_TYPICAL_SCHEMA",
    "GROUND_TRUTH",
    "NON_ENCODABLE_TYPE_SCHEMA",
    "NOT_NULL_ONLY_SCHEMA",
    "PERMISSIVE_SCHEMA",
    "PRIMARY_KEY_ONLY_SCHEMA",
    "TIGHT_SCHEMA",
    "UNENFORCEABLE_AGGREGATE_SCHEMA",
    "UNENFORCEABLE_RELATIONSHIP_SCHEMA",
    "UNIQUE_ONLY_SCHEMA",
    "Attack",
    "CorpusOutcome",
    "build_corpus",
    "clopper_pearson_upper",
    "truth",
    "write_table",
]

# --- The table under attack ---------------------------------------------------
# Ground truth is committed here so "corruption" is decidable rather than inferred.

COLUMNS = ("id", "city", "state", "zip", "score")

GROUND_TRUTH: tuple[tuple[str, ...], ...] = (
    ("1", "springfield", "il", "62701", "10.0"),
    ("2", "chicago", "il", "60601", "20.0"),
    ("3", "peoria", "il", "61602", "30.0"),
    ("4", "chicago", "il", "60601", "40.0"),
    ("5", "springfield", "il", "62701", "50.0"),
)


def write_table(path: Path) -> Path:
    """Write the ground-truth table. The corpus attacks a correct file on purpose."""
    lines = [",".join(COLUMNS)]
    lines.extend(",".join(row) for row in GROUND_TRUTH)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def truth(row: int, column: str) -> str:
    return GROUND_TRUTH[row][COLUMNS.index(column)]


# --- The two premises ---------------------------------------------------------

TIGHT_SCHEMA = Schema(
    columns={"id": "str", "city": "str", "state": "str", "zip": "str", "score": "float"},
    accepted_values=(
        AcceptedValues(column="city", values=("springfield", "chicago", "peoria")),
        AcceptedValues(column="state", values=("il",)),
    ),
    regex_constraints=(RegexConstraint(column="zip", pattern=r"^\d{5}$"),),
    domain_bounds=(DomainBound(column="score", min_value=0.0, max_value=100.0),),
)

# Covers every column, constrains almost nothing. This is not a straw man: it is what
# schema inference produces from dirty data, and what a hurried operator accepts.
PERMISSIVE_SCHEMA = Schema(
    columns={"id": "str", "city": "str", "state": "str", "zip": "str", "score": "str"},
)

# --- The premises that cover every column via a constraint NOTHING CAN CHECK -------
#
# Each is ``PERMISSIVE_SCHEMA`` plus exactly ONE added field, so any difference in outcome
# is attributable to that field and to nothing else. That is the whole design: the corpus
# already isolates "how much of the guarantee comes from the premise", and these isolate
# "how much comes from the premise being CHECKABLE".
#
# Why they exist. The 2026-08-25 rule (``dataforge.domain.vocabulary.type_discriminates``)
# established that a declared type must be able to reject a value before it confers proof,
# and took the permissive premise from 10 of 14 constraint-violating writes to 0. But
# ``authoritative_columns`` grants authority for ten constraint kinds and the verifiers
# enforce six, so the rule closed the ``str`` door and left an equivalent one open: a
# relationship or an aggregate dependency names a column, confers authority over it, and
# neither ``SMTVerifier`` nor ``DirectVerifier`` contains any branch that can reject on it.
#
# ``relationships`` is the one that matters in practice rather than adversarially:
# ``dataforge/integrations/dbt.py`` maps dbt's built-in ``relationships`` test onto this
# field, so a user importing a dbt manifest arrives here without doing anything unusual.
#
# See ``eval/preregistration/authority_enforcement_correspondence.md``.
#
# ``build_corpus()`` is deliberately NOT extended to reach this. Its 14 discriminable
# attacks are the denominator of the published "10 of 14", and moving a denominator to
# accommodate a new finding would restate history rather than add to it.

_REFERENCE_RELATION = "ref_dimension"

UNENFORCEABLE_RELATIONSHIP_SCHEMA = Schema(
    columns={"id": "str", "city": "str", "state": "str", "zip": "str", "score": "str"},
    relationships=tuple(
        RelationshipConstraint(
            column=column,
            reference=_REFERENCE_RELATION,
            reference_column="name",
        )
        for column in COLUMNS
    ),
)

UNENFORCEABLE_AGGREGATE_SCHEMA = Schema(
    columns={"id": "str", "city": "str", "state": "str", "zip": "str", "score": "str"},
    aggregate_dependencies=tuple(
        AggregateDependency(
            source_column=column,
            aggregate="sum",
            target_column=f"{column}_total",
        )
        for column in COLUMNS
    ),
)

# --- The premises that isolate ONE ENFORCEABLE KIND EACH ----------------------------
#
# Added 2026-09-16. The block above isolates kinds nothing can check. These isolate kinds
# that CAN be checked, one at a time, to measure HOW MUCH each one can reject. That question
# has never been asked: ``authoritative_columns`` confers identical authority for all eight
# enforceable kinds, and ``strength_for_fix`` keys on nothing but column-name membership, so
# a column named by ``not_null_columns`` and one named by ``accepted_values`` are equally
# authoritative and a fix on either is equally eligible to be labelled ``proven``.
#
# Why it is urgent rather than academic. ``TIGHT_SCHEMA``'s 0-of-14 is a BUNDLE result --
# types, ``accepted_values``, ``regex_constraints`` and ``domain_bounds`` together -- so it
# attributes strength to none of its members. The two external premise sources worth wiring
# up supply a characteristic SUBSET: a dbt manifest gives ``not_null``, ``unique`` and
# ``accepted_values``; database DDL gives ``not_null``, ``primary_key`` and ``unique``. Three
# of those four are ABSENT from ``TIGHT_SCHEMA``. So a realistic externally-derived premise
# is the tight bundle minus everything that might be doing the work, and until these arms
# existed nobody knew what that scores.
#
# Same discipline as above: each is ``PERMISSIVE_SCHEMA`` plus exactly ONE added field.
# ``ddl_typical`` is the single declared exception and says so in its own comment.
#
# See ``eval/preregistration/per_kind_authority.md``.

NOT_NULL_ONLY_SCHEMA = Schema(
    columns={"id": "str", "city": "str", "state": "str", "zip": "str", "score": "str"},
    not_null_columns=frozenset(COLUMNS),
)

# `direct.py`:160 tests membership of `not_null_columns` OR `primary_key_columns` with one
# predicate, so this arm exists to confirm the two are indistinguishable rather than to
# discover something new. An arm that merely confirms is still worth running: the claim
# "these are the same" is currently an inference from reading, not a measurement.
PRIMARY_KEY_ONLY_SCHEMA = Schema(
    columns={"id": "str", "city": "str", "state": "str", "zip": "str", "score": "str"},
    primary_key_columns=frozenset(COLUMNS),
)

# Declaring `unique` over every column is FALSE of this table -- `chicago` and `springfield`
# each appear twice. That is deliberate and realistic: Snowflake documents PRIMARY KEY,
# FOREIGN KEY and UNIQUE as "Optional, not enforced", so a warehouse can and does carry
# uniqueness declarations its data violates.
UNIQUE_ONLY_SCHEMA = Schema(
    columns={"id": "str", "city": "str", "state": "str", "zip": "str", "score": "str"},
    unique_columns=frozenset(COLUMNS),
)

# The enumerations are the table's own value sets, which is the strongest honest form of this
# declaration. If one kind alone reproduces the whole tight bundle's result, this is it.
ACCEPTED_VALUES_ONLY_SCHEMA = Schema(
    columns={"id": "str", "city": "str", "state": "str", "zip": "str", "score": "str"},
    accepted_values=tuple(
        AcceptedValues(
            column=column,
            values=tuple(sorted({row[COLUMNS.index(column)] for row in GROUND_TRUTH})),
        )
        for column in COLUMNS
    ),
)

# THE PRODUCT QUESTION, and the one arm that breaks the one-field rule on purpose.
#
# What a DDL importer would actually emit for a typical production table: NOT NULL on the
# columns that declare it, a PRIMARY KEY, and types that carry no domain information --
# `Get Real` (DBTest'18) measured 48.8% of real BI tuple values stored as Text, and an
# unconstrained VARCHAR narrows nothing. It has two added fields rather than one because it
# models a real source rather than attributing a delta, and its composition is fixed in the
# pre-registration so it cannot be tuned to a result.
DDL_TYPICAL_SCHEMA = Schema(
    columns={"id": "str", "city": "str", "state": "str", "zip": "str", "score": "str"},
    not_null_columns=frozenset(COLUMNS),
    primary_key_columns=frozenset({"id"}),
)

#: Axis 2: a declared type that CONFERS authority but that no verifier can ENCODE.
#:
#: `type_discriminates` is a denylist -- authority goes to any spelling absent from
#: NON_DISCRIMINATING_COLUMN_TYPES -- while `direct.py`:148 returns UNKNOWN for any type outside
#: {int, integer, float, decimal, real, str, string}. `date` sits in the gap: authoritative and
#: uncheckable. This arm exists to measure what that gap costs, on both sides of the rule change,
#: because the change looks obviously safe and that is when this repository has shipped the same
#: defect three times. See eval/preregistration/per_kind_authority.md amendment 2 (P9, P10, K8-K10).
NON_ENCODABLE_TYPE_SCHEMA = Schema(
    columns=dict.fromkeys(COLUMNS, "date"),
)


# --- The taxonomy -------------------------------------------------------------


@dataclass(frozen=True)
class Attack:
    """One adversarial proposal, and why it is dangerous.

    ``discriminable`` is the load-bearing field. It records whether the STATED CONSTRAINTS
    can tell this proposal apart from the truth:

    * ``True``  -- the value violates a declared type, bound, pattern, category, or the
      table's structure. The gate must block it. Anything written here is a real defect.
    * ``False`` -- the value satisfies every declared constraint and is merely FALSE. No
      verifier can reject it without ground truth it does not have, so the gate writes it,
      labels it proven-against-the-schema, and keeps it reversible. Calling this a gate
      failure would be claiming a guarantee the product explicitly refuses to make; see
      ``docs/trust/accuracy-frontier.md`` on ABSTENTION and
      ``docs/trust/certification-promises.md`` on the strength of a premise.

    Separating the two is the whole point. A corpus that lumped them together would either
    report a false failure or hide a real one.
    """

    name: str
    attack_class: str
    why_dangerous: str
    fix: ExternalFix
    discriminable: bool = True
    # Reasons that would be an HONEST block for this attack. Empty means the proposal is
    # legitimately correct and SHOULD apply.
    honest_block_reasons: frozenset[str] = field(default_factory=frozenset)
    is_correct_proposal: bool = False
    # Corrupt the table before proposing, so a legitimate repair has something to repair.
    pre_corrupt: tuple[int, str, str] | None = None


def build_corpus() -> tuple[Attack, ...]:
    """Every attack class from the plan, as concrete proposals against the table above."""
    return (
        # --- Legitimate proposals: the corpus must not block everything ---------
        Attack(
            name="correct-score-repair",
            attack_class="legitimate",
            why_dangerous="A gate that blocks everything is useless; this must apply.",
            fix=ExternalFix(row=0, column="score", new_value="10.0"),
            is_correct_proposal=True,
            # The table is ground truth, so a legitimate repair needs an error to repair.
            pre_corrupt=(0, "score", "999.0"),
        ),
        # --- Plausible but wrong ------------------------------------------------
        # These satisfy every declared constraint. No verifier can reject them without
        # ground truth, so they are marked NOT discriminable: the guarantee they fall under
        # is reversibility and honest labelling, not correctness.
        Attack(
            name="fd-consistent-but-wrong-city",
            attack_class="plausible_but_wrong",
            why_dangerous=(
                "chicago is a real value in this column and consistent with state=il, so "
                "every categorical and FD check passes. Only the ground truth disagrees."
            ),
            fix=ExternalFix(row=0, column="city", new_value="chicago"),
            discriminable=False,
        ),
        Attack(
            name="in-range-but-wrong-score",
            attack_class="plausible_but_wrong",
            why_dangerous=(
                "77.0 is inside the declared domain bound, so a bounds check cannot "
                "distinguish it from the correct 10.0."
            ),
            fix=ExternalFix(row=0, column="score", new_value="77.0"),
            discriminable=False,
        ),
        # --- Rare-but-correct overwrite ----------------------------------------
        Attack(
            name="rare-but-correct-overwrite",
            attack_class="rare_correct_overwrite",
            why_dangerous=(
                "peoria appears once, so a frequency or nearest-valid heuristic reads it "
                "as a typo and 'corrects' it to the majority. This is the measured NO-GO "
                "that produced 25 corruptions to fix 23. The proposed value is itself a "
                "declared category, so the schema cannot object."
            ),
            fix=ExternalFix(row=2, column="city", new_value="chicago"),
            discriminable=False,
        ),
        # --- Stale precondition -------------------------------------------------
        Attack(
            name="stale-precondition",
            attack_class="stale_precondition",
            why_dangerous="A lost update: the proposer read a value that is no longer there.",
            fix=ExternalFix(
                row=1, column="score", new_value="21.0", expected_old_value="NOT_THE_VALUE"
            ),
            honest_block_reasons=frozenset({"stale_precondition"}),
        ),
        # --- Confusables --------------------------------------------------------
        Attack(
            name="cyrillic-homoglyph-city",
            attack_class="homoglyph",
            why_dangerous=(
                "The 'c' is Cyrillic U+0441. Visually identical to the correct value, "
                "different bytes. Any check that only asks 'is this a string?' passes it."
            ),
            fix=ExternalFix(row=1, column="city", new_value="\u0441hicago"),
            honest_block_reasons=frozenset({"verifier_rejected", "invalid_target"}),
        ),
        Attack(
            name="zero-width-space-in-state",
            attack_class="zero_width",
            why_dangerous=(
                "A U+200B zero-width space renders as nothing, so the value looks correct "
                "to a human reviewer and compares unequal to every downstream join."
            ),
            fix=ExternalFix(row=0, column="state", new_value="i\u200bl"),
            honest_block_reasons=frozenset({"verifier_rejected", "invalid_target"}),
        ),
        Attack(
            name="trailing-whitespace-in-zip",
            attack_class="whitespace",
            why_dangerous="Trailing space survives most validation and breaks exact matches.",
            fix=ExternalFix(row=0, column="zip", new_value="62701 "),
            honest_block_reasons=frozenset({"verifier_rejected", "invalid_target"}),
        ),
        # --- Boundary values ----------------------------------------------------
        Attack(
            name="empty-string-into-score",
            attack_class="boundary",
            why_dangerous="Empty string is neither null nor a number; many checks skip it.",
            fix=ExternalFix(row=0, column="score", new_value=""),
            honest_block_reasons=frozenset({"verifier_rejected", "invalid_target"}),
        ),
        Attack(
            name="out-of-bounds-score",
            attack_class="boundary",
            why_dangerous="Above the declared maximum; a tight schema must catch this.",
            fix=ExternalFix(row=0, column="score", new_value="1000000.0"),
            honest_block_reasons=frozenset(
                {"verifier_rejected", "invalid_target", "out_of_inferred_domain"}
            ),
        ),
        Attack(
            name="type-violating-score",
            attack_class="boundary",
            why_dangerous="Non-numeric into a float column: the classic type attack.",
            fix=ExternalFix(row=0, column="score", new_value="not-a-number"),
            honest_block_reasons=frozenset(
                {"verifier_rejected", "invalid_target", "out_of_inferred_domain"}
            ),
        ),
        Attack(
            name="zip-failing-its-pattern",
            attack_class="boundary",
            why_dangerous="Six digits against a five-digit pattern.",
            fix=ExternalFix(row=0, column="zip", new_value="627011"),
            honest_block_reasons=frozenset(
                {"verifier_rejected", "invalid_target", "out_of_inferred_domain"}
            ),
        ),
        Attack(
            name="unlisted-category-in-state",
            attack_class="boundary",
            why_dangerous="A value outside the enumerated set.",
            fix=ExternalFix(row=0, column="state", new_value="zz"),
            honest_block_reasons=frozenset(
                {"verifier_rejected", "invalid_target", "out_of_inferred_domain"}
            ),
        ),
        # --- Structural attacks -------------------------------------------------
        Attack(
            name="nonexistent-column",
            attack_class="invalid_target",
            why_dangerous="A column that does not exist must never be created by a write.",
            fix=ExternalFix(row=0, column="ghost_column", new_value="x"),
            honest_block_reasons=frozenset({"invalid_target"}),
        ),
        Attack(
            name="row-past-the-end",
            attack_class="invalid_target",
            why_dangerous="An out-of-range row index must not extend the table.",
            fix=ExternalFix(row=9999, column="score", new_value="1.0"),
            honest_block_reasons=frozenset({"invalid_target"}),
        ),
        Attack(
            name="newline-injection-into-city",
            attack_class="injection",
            why_dangerous=(
                "An embedded newline can split one CSV row into two, changing the shape of "
                "the table rather than one cell."
            ),
            fix=ExternalFix(row=0, column="city", new_value="springfield\n9,x,y,z,0"),
            honest_block_reasons=frozenset({"verifier_rejected", "invalid_target"}),
        ),
        Attack(
            name="quote-injection-into-city",
            attack_class="injection",
            why_dangerous="An unbalanced quote can swallow subsequent fields on reparse.",
            fix=ExternalFix(row=0, column="city", new_value='springfield"'),
            honest_block_reasons=frozenset({"verifier_rejected", "invalid_target"}),
        ),
    )


# --- Scoring ------------------------------------------------------------------


@dataclass(frozen=True)
class CorpusOutcome:
    """What the gate did with the corpus, in terms that permit a corruption count."""

    proposed: int
    applied: int
    held: int
    corruptions: tuple[str, ...]
    correct_applications: tuple[str, ...]
    wrongly_blocked: tuple[str, ...]
    block_reasons: dict[str, str]

    @property
    def corruption_count(self) -> int:
        return len(self.corruptions)
