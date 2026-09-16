"""Run the adversarial corpus through the write gate and measure corruption.

The claim under test is the product's central one, stated precisely: an untrusted proposer
cannot write a value that is **not proven against the stated constraints**, and everything
written reverses byte-for-byte. It is NOT the claim that every written value is true -- no
verifier can establish that without ground truth it does not have.

The corpus therefore splits along exactly that line:

* **Discriminable attacks** violate a declared type, bound, pattern, category, or the
  table's structure. The gate must block every one. A write here is a real defect.
* **Undecidable attacks** satisfy every declared constraint and are merely false. The gate
  writes them, labels them proven-against-the-schema, and keeps them reversible. Counting
  these as gate failures would be asserting a guarantee the product explicitly refuses to
  make, which is the error this project has corrected before.

The first run of this suite asserted zero corruptions across the whole corpus and failed on
three undecidable attacks. The assertion was wrong, not the gate -- recorded here because
the distinction is the substance of the result.

Two premises are measured, both covering every column, so the gate labels writes ``proven``
under both. The difference between them is what the label is worth when the premise is
weak.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from dataforge.detectors.base import Schema
from dataforge.engine.repair import ExternalFix, VerifyAndApplyRequest, verify_and_apply
from dataforge.transactions.revert import revert_transaction
from tests.adversarial.corpus import (
    ACCEPTED_VALUES_ONLY_SCHEMA,
    DDL_TYPICAL_SCHEMA,
    NOT_NULL_ONLY_SCHEMA,
    PERMISSIVE_SCHEMA,
    PRIMARY_KEY_ONLY_SCHEMA,
    TIGHT_SCHEMA,
    UNENFORCEABLE_AGGREGATE_SCHEMA,
    UNENFORCEABLE_RELATIONSHIP_SCHEMA,
    UNIQUE_ONLY_SCHEMA,
    Attack,
    CorpusOutcome,
    build_corpus,
    clopper_pearson_upper,
    truth,
    write_table,
)

#: Every premise the corpus defines. Used where an invariant must hold under ALL of them --
#: structural properties such as table shape are not premise-dependent, and testing one only
#: under the premise that upholds it is how the shape check missed an applied newline
#: injection that took the table from 6 rows to 7.
_ALL_PREMISES: tuple[tuple[str, Schema], ...] = (
    ("tight", TIGHT_SCHEMA),
    ("permissive", PERMISSIVE_SCHEMA),
    ("unenforceable_relationship", UNENFORCEABLE_RELATIONSHIP_SCHEMA),
    ("unenforceable_aggregate", UNENFORCEABLE_AGGREGATE_SCHEMA),
    # The per-kind arms, added 2026-09-16. Listed here for the reason the comment above gives:
    # a structural invariant is not premise-dependent, and `not_null_only` is the arm most
    # likely to APPLY the newline injection, which is exactly the case the shape check exists
    # for. See eval/preregistration/per_kind_authority.md.
    ("not_null_only", NOT_NULL_ONLY_SCHEMA),
    ("primary_key_only", PRIMARY_KEY_ONLY_SCHEMA),
    ("unique_only", UNIQUE_ONLY_SCHEMA),
    ("accepted_values_only", ACCEPTED_VALUES_ONLY_SCHEMA),
    ("ddl_typical", DDL_TYPICAL_SCHEMA),
)


def _expected_truth(row: int, column: str) -> str | None:
    try:
        return truth(row, column)
    except (IndexError, ValueError):
        return None


def run_corpus(source: Path, schema: Schema) -> CorpusOutcome:
    """Submit every attack individually and score it against ground truth.

    One request per attack, not one batch: a batch can be rejected wholesale for an
    unrelated reason, which would make the corpus look effective while proving nothing about
    the individual attacks.
    """
    corpus = build_corpus()
    corruptions: list[str] = []
    correct: list[str] = []
    wrongly_blocked: list[str] = []
    reasons: dict[str, str] = {}
    applied_total = 0
    held_total = 0

    for attack in corpus:
        write_table(source)
        if attack.pre_corrupt is not None:
            row, column, wrong = attack.pre_corrupt
            _poke(source, row, column, wrong)

        result = verify_and_apply(
            VerifyAndApplyRequest(
                source_path=source,
                fixes=[attack.fix],
                mode="apply",
                schema=schema,
                confirm_escalations=True,
                proposer="adversarial-corpus",
            )
        )
        receipt = result.receipt

        if receipt.applied_fixes:
            applied_total += len(receipt.applied_fixes)
            for applied_fix in receipt.applied_fixes:
                expected = _expected_truth(applied_fix.row, applied_fix.column)
                if expected is None or applied_fix.new_value != expected:
                    corruptions.append(attack.name)
                else:
                    correct.append(attack.name)
        else:
            held_total += 1
            reason = next(
                (s.review_reason for s in receipt.suggested_fixes if s.review_reason),
                None,
            )
            reasons[attack.name] = reason or "held_without_reason"
            if attack.is_correct_proposal:
                wrongly_blocked.append(attack.name)

    return CorpusOutcome(
        proposed=len(corpus),
        applied=applied_total,
        held=held_total,
        corruptions=tuple(corruptions),
        correct_applications=tuple(correct),
        wrongly_blocked=tuple(wrongly_blocked),
        block_reasons=reasons,
    )


def _poke(source: Path, row: int, column: str, value: str) -> None:
    """Write one wrong cell directly, bypassing the engine, to create a real error."""
    lines = source.read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    index = header.index(column)
    cells = lines[row + 1].split(",")
    cells[index] = value
    lines[row + 1] = ",".join(cells)
    source.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def source(tmp_path: Path) -> Path:
    return write_table(tmp_path / "readings.csv")


def _parsed_rows(source: Path) -> list[list[str]]:
    """Return the file's rows as a CSV reader sees them, header included.

    Parsed rather than split on newlines, because a quoted field may legally contain a newline
    and the shape that matters is the one every downstream reader observes. See
    :func:`test_the_table_shape_is_never_changed` for what counting physical lines cost.
    """
    with source.open(newline="", encoding="utf-8") as handle:
        return [list(row) for row in csv.reader(handle)]


def test_corpus_is_not_vacuous() -> None:
    """A corpus that shrank to a couple of easy cases would prove nothing."""
    corpus = build_corpus()
    assert len(corpus) >= 15
    classes = {attack.attack_class for attack in corpus}
    for required in (
        "plausible_but_wrong",
        "rare_correct_overwrite",
        "stale_precondition",
        "homoglyph",
        "zero_width",
        "boundary",
        "invalid_target",
        "injection",
        "legitimate",
    ):
        assert required in classes, f"corpus no longer covers {required}"
    assert any(attack.is_correct_proposal for attack in corpus), (
        "a corpus with no legitimate proposal cannot detect a gate that blocks everything"
    )
    # Both halves must be populated, or the split is decorative.
    assert sum(1 for a in corpus if a.discriminable) >= 10
    assert sum(1 for a in corpus if not a.discriminable) >= 3


def test_no_discriminable_attack_is_ever_written(source: Path) -> None:
    """The product's actual guarantee, measured.

    Every attack the stated constraints CAN reject must be rejected. This is the assertion
    that would catch a real gate regression.
    """
    outcome = run_corpus(source, TIGHT_SCHEMA)
    corpus = {attack.name: attack for attack in build_corpus()}

    discriminable_corruptions = [name for name in outcome.corruptions if corpus[name].discriminable]
    discriminable_total = sum(1 for attack in corpus.values() if attack.discriminable)
    bound = clopper_pearson_upper(len(discriminable_corruptions), discriminable_total)

    print(
        f"\nADVERSARIAL tight schema, discriminable attacks: n={discriminable_total} "
        f"corruptions={len(discriminable_corruptions)} rate_upper_95={bound:.4f}"
    )
    assert discriminable_corruptions == [], (
        f"the gate wrote a value that violates the stated constraints: {discriminable_corruptions}"
    )
    # And it did not achieve that by refusing everything.
    assert outcome.wrongly_blocked == (), (
        f"a legitimate proposal was blocked: {list(outcome.wrongly_blocked)}"
    )
    assert outcome.correct_applications, "no correct proposal was applied at all"


def test_undecidable_attacks_are_written_but_reversible(source: Path) -> None:
    """The honest limit, stated as a test rather than as a caveat.

    A constraint-satisfying but false value IS written. The guarantee that applies to it is
    not correctness -- it is that the write is recorded, attributed, and reverses to the
    exact prior bytes. This test pins that guarantee, because it is the one being relied on.
    """
    corpus = [attack for attack in build_corpus() if not attack.discriminable]
    assert corpus, "no undecidable attacks left to measure"

    for attack in corpus:
        write_table(source)
        before = source.read_bytes()
        result = verify_and_apply(
            VerifyAndApplyRequest(
                source_path=source,
                fixes=[attack.fix],
                mode="apply",
                schema=TIGHT_SCHEMA,
                confirm_escalations=True,
                proposer="adversarial-corpus",
            )
        )
        receipt = result.receipt
        assert receipt.applied_fixes, (
            f"{attack.name} was blocked; it satisfies every declared constraint, so a "
            "block would mean the schema is doing something other than what it declares"
        )
        # Labelled honestly: proven against the schema, and the schema is named.
        assert all(f.verification_strength == "proven" for f in receipt.applied_fixes)
        assert receipt.authoritative_columns, (
            "a proven untrusted write must name the authority that proved it"
        )
        assert source.read_bytes() != before

        # The guarantee that actually holds for this class.
        assert receipt.txn_id is not None
        revert_transaction(receipt.txn_id, search_root=source.parent)
        assert source.read_bytes() == before, (
            f"{attack.name} did not revert to the exact prior bytes"
        )


def test_without_authority_nothing_untrusted_is_written(source: Path) -> None:
    """With no schema, every external proposal must be HELD -- including the correct one.

    This is the run that exercises the PROVEN-ONLY gate rather than the SMT verifier. The
    first version of this corpus always supplied a schema, so every attack was blocked by
    constraint checking and `enforce_proven_only` was never reached. Mutation testing proved
    it: neutering the proven-only gate entirely, and separately making every provenance
    trusted, left the whole corpus green. It was measuring the verifier and claiming to
    measure the guarantee.

    Without an authoritative schema an `external` value is `plausibility_only` by
    construction, so a correct proposal is held too. That is the intended behaviour: the
    gate refuses to write what it cannot prove, and being right is not the same as being
    provable.
    """
    corpus = build_corpus()
    written: list[str] = []

    for attack in corpus:
        write_table(source)
        if attack.pre_corrupt is not None:
            row, column, wrong = attack.pre_corrupt
            _poke(source, row, column, wrong)
        before = source.read_bytes()

        result = verify_and_apply(
            VerifyAndApplyRequest(
                source_path=source,
                fixes=[attack.fix],
                mode="apply",
                schema=None,
                confirm_escalations=True,
                proposer="adversarial-corpus",
            )
        )
        if result.receipt.applied_fixes or source.read_bytes() != before:
            written.append(attack.name)

    assert written == [], (
        f"an untrusted value was written with no authoritative schema to prove it: {written}"
    )


def test_authority_does_not_leak_across_columns(source: Path) -> None:
    """A schema that speaks about one column must not authorise writes to another.

    The 2026-08-09 defect: one accepted `column_type` constraint on `id` granted blanket
    authority, so a garbage `external` value on the unrelated column `city` was applied and
    stamped `proven`. Mutation testing showed the earlier corpus could not detect it,
    because the tight schema already covered every column.
    """
    partial = Schema(columns={"score": "float"})

    write_table(source)
    before = source.read_bytes()
    result = verify_and_apply(
        VerifyAndApplyRequest(
            source_path=source,
            fixes=[
                # A value that satisfies nothing in particular, on a column the schema
                # never mentions.
                ExternalFix(row=0, column="city", new_value="ZZZ_GARBAGE"),
            ],
            mode="apply",
            schema=partial,
            confirm_escalations=True,
            proposer="adversarial-corpus",
        )
    )
    assert result.receipt.applied_fixes == [], (
        "authority over 'score' authorised a write to 'city'; authority is leaking across columns"
    )
    assert source.read_bytes() == before
    assert "city" not in result.receipt.authoritative_columns


def test_a_permissive_premise_costs_the_ability_to_write_not_the_guarantee(source: Path) -> None:
    """How much of the guarantee comes from the premise rather than the gate.

    This test previously asserted the opposite of what it asserts now, and the change is the
    finding. It used to require ``len(permissive_bad) > 0`` -- pinning as *required behaviour*
    that a schema declaring every column ``str`` admitted 10 of 14 constraint-violating writes,
    because both premises "cover" every column and the gate stamped ``proven`` under both.

    ``eval/preregistration/entailment_strength.md`` predicted that requiring a premise to
    *discriminate* rather than merely *exist* would take that number to zero while leaving the
    tight premise's one legitimate repair intact. It did. So the premise still measurably matters,
    but the axis has moved: a weak premise now loses the ability to **write at all** instead of
    gaining the ability to **corrupt**.

    The non-vacuity teeth are kept and pointed the other way. This fails if a permissive premise
    ever writes anything again, and it fails if the tight premise stops writing -- which would mean
    the fix had destroyed the verification-layer feature rather than corrected it.
    """
    corpus = {attack.name: attack for attack in build_corpus()}
    discriminable_total = sum(1 for attack in corpus.values() if attack.discriminable)

    tight = run_corpus(source, TIGHT_SCHEMA)
    permissive = run_corpus(source, PERMISSIVE_SCHEMA)
    tight_bad = [name for name in tight.corruptions if corpus[name].discriminable]
    permissive_bad = [name for name in permissive.corruptions if corpus[name].discriminable]

    print(
        f"\nADVERSARIAL premise comparison over {discriminable_total} discriminable attacks:"
        f"\n  tight schema (typed, bounded, patterned, enumerated): "
        f"{len(tight_bad)} written, upper95="
        f"{clopper_pearson_upper(len(tight_bad), discriminable_total):.4f}"
        f"\n  permissive schema (every column declared str):        "
        f"{len(permissive_bad)} written, upper95="
        f"{clopper_pearson_upper(len(permissive_bad), discriminable_total):.4f}"
    )

    assert len(tight_bad) == 0
    assert len(tight_bad) <= len(permissive_bad), (
        "a tighter schema admitted more constraint-violating writes, which would mean the "
        "premise is being applied incorrectly"
    )
    assert len(permissive_bad) == 0, (
        "a premise declaring every column str admitted a constraint-violating write again. "
        "authoritative_columns must not count a non-discriminating declared type as authority; "
        "see dataforge.domain.vocabulary.type_discriminates"
    )
    # Non-vacuity, pointed at the fix rather than at the defect: the weak premise must be unable
    # to write, and the strong one must still be able to.
    assert permissive.applied == 0, (
        "a premise that constrains nothing wrote a cell; it has no authority to write anything"
    )
    assert tight.applied > 0, (
        "the tight premise stopped writing its one legitimate repair, so the discriminating-"
        "premise rule is too strict and has destroyed the verification-layer feature rather "
        "than corrected it. Do not relax this assertion; revert the rule"
    )


def test_an_unenforceable_premise_cannot_write_either(source: Path) -> None:
    """The 2026-08-25 rule closed the `str` door; this pins the equivalent one shut.

    Requiring a declared TYPE to discriminate took the permissive premise from 10 of 14
    constraint-violating writes to 0. But `authoritative_columns` granted authority for ten
    constraint kinds while the verifiers enforce six, so naming a column in a `relationships`
    or `aggregate_dependencies` declaration conferred `proven` on a value nothing could reject.

    Each premise here is `PERMISSIVE_SCHEMA` plus exactly ONE added field, so the outcome is
    attributable to that field alone. Measured before the fix, each wrote 11 cells and
    corrupted 10 of 14 -- reproducing the pre-2026-08-25 figure exactly. Recorded in
    `eval/results/trust_ledger_adversarial.json` and
    `docs/trust/authority-enforcement-correspondence.md`.

    The teeth point the same way as the permissive test's: this fails if an unenforceable
    premise ever writes again, and the tight premise's legitimate repair is re-asserted here
    so the rule cannot be satisfied by refusing everything.
    """
    corpus = {attack.name: attack for attack in build_corpus()}
    discriminable_total = sum(1 for attack in corpus.values() if attack.discriminable)
    tight = run_corpus(source, TIGHT_SCHEMA)

    for premise_name, schema in _ALL_PREMISES:
        if not premise_name.startswith("unenforceable"):
            continue
        outcome = run_corpus(source, schema)
        bad = [name for name in outcome.corruptions if corpus[name].discriminable]

        print(
            f"\n{premise_name}: {outcome.applied} written, {len(bad)} of "
            f"{discriminable_total} discriminable attacks corrupted, upper95="
            f"{clopper_pearson_upper(len(bad), discriminable_total):.4f}"
        )

        assert len(bad) == 0, (
            f"the {premise_name} premise admitted a constraint-violating write. A constraint "
            "kind no verifier can reject on must not confer authority; see "
            "dataforge.domain.vocabulary.ENFORCEABLE_CONSTRAINT_KINDS"
        )
        assert outcome.applied == 0, (
            f"the {premise_name} premise wrote a cell. It names every column in a constraint "
            "kind neither SMTVerifier nor DirectVerifier contains a branch for, so it has no "
            "authority to write anything"
        )

    assert tight.applied > 0, (
        "the tight premise stopped writing its one legitimate repair, so the enforceability "
        "rule is too strict and has destroyed the verification-layer feature rather than "
        "corrected it. Do not relax this assertion; revert the rule"
    )


def test_every_blocked_attack_has_an_honest_reason(source: Path) -> None:
    """A block with no reason, or the wrong reason, is not an honest refusal."""
    outcome = run_corpus(source, TIGHT_SCHEMA)
    corpus = {attack.name: attack for attack in build_corpus()}

    unexplained = [
        name for name, reason in outcome.block_reasons.items() if reason == "held_without_reason"
    ]
    assert unexplained == [], f"blocked with no reason: {unexplained}"

    mismatched: list[str] = []
    for name, reason in outcome.block_reasons.items():
        attack: Attack = corpus[name]
        if attack.honest_block_reasons and reason not in attack.honest_block_reasons:
            mismatched.append(
                f"{name}: got {reason!r}, expected one of {sorted(attack.honest_block_reasons)}"
            )
    assert mismatched == [], f"blocked for an unexpected reason: {mismatched}"


def test_the_table_shape_is_never_changed(source: Path) -> None:
    """A structural corruption is worse than a wrong cell.

    An injected newline or quote that changes the row or column count silently reinterprets
    every downstream read, so it is checked separately from value correctness.

    **This ran only under TIGHT_SCHEMA until 2026-09-14, and that was the defect**: a
    structural invariant was tested solely under the premise that holds it. Shape is not a
    premise-dependent property, so it is now asserted under every premise the corpus defines
    -- which is also what makes this test able to fail if the authority rule regresses.

    **Corrected 2026-09-16: it counted PHYSICAL LINES, and that is not the shape.** A
    correctly-quoted CSV field may legally contain a newline and span two physical lines while
    still parsing to one row, so `splitlines()` reports a shape change where none occurred.
    Measured under `not_null_only`, `newline-injection-into-city` is applied and the file
    becomes `1,"springfield\\n9,x,y,z,0",il,62701,10.0` -- valid CSV, six parsed rows before
    and after, five fields in every row, physical lines 6 -> 7.

    So the published sentence *"one applied injection took the table from 6 rows to 7"*
    (`docs/trust/authority-enforcement-correspondence.md`, and the generated `correspondence`
    string in `scripts/measure_trust_ledger.py`) describes a physical-line count and does
    **not** establish that a row was created. The original conditions cannot be reproduced --
    the unenforceable premises now write zero -- so whether that measurement was ever a
    structural corruption is unresolved and is recorded as unresolved.

    The attack remains a genuine **value** corruption and is counted as one; a cell holding an
    embedded newline is hostile to any consumer that splits on newlines rather than parsing.
    What it is not is a change of shape, and asserting the wrong invariant would have hidden a
    real one behind a false alarm.
    """
    for premise_name, schema in _ALL_PREMISES:
        for attack in build_corpus():
            write_table(source)
            if attack.pre_corrupt is not None:
                row, column, wrong = attack.pre_corrupt
                _poke(source, row, column, wrong)
            expected_rows = _parsed_rows(source)

            verify_and_apply(
                VerifyAndApplyRequest(
                    source_path=source,
                    fixes=[attack.fix],
                    mode="apply",
                    schema=schema,
                    confirm_escalations=True,
                    proposer="adversarial-corpus",
                )
            )
            actual_rows = _parsed_rows(source)
            assert len(actual_rows) == len(expected_rows), (
                f"[{premise_name}] {attack.name} changed the parsed row count: "
                f"{len(expected_rows)} -> {len(actual_rows)}"
            )
            for index, row_fields in enumerate(actual_rows):
                assert len(row_fields) == len(expected_rows[index]), (
                    f"[{premise_name}] {attack.name} changed the field count on parsed row "
                    f"{index}: {len(expected_rows[index])} -> {len(row_fields)}"
                )
