"""The spec-correspondence gate, shown failing on cases it newly covers.

`PRODUCT.md`:280-283 requires this rather than suggesting it:

    A gate nobody has seen fail on a case it newly covers has not been shown to cover it, so a
    fix of this kind must ship with a planted claim that fails against the frozen version and
    passes against the derived one.

Each test below plants exactly one defect that was REAL in this repository before 2026-09-15 and
that every pre-existing gate reported green on. The frozen artifacts they replace are named in
each docstring, so a reader can check the claim rather than take it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "ci"))

import spec_correspondence as gate  # noqa: E402

from dataforge.attestation import (  # noqa: E402
    CLOSED_VOCABULARIES,
    NORMATIVE_CHECKS,
    AttestationCheck,
)

ALL_CHECKS = tuple(NORMATIVE_CHECKS)
ALL_VOCABULARIES = set(CLOSED_VOCABULARIES)
SPEC_TEXT = (PROJECT_ROOT / "specs" / "SPEC_repair_attestation.md").read_text(encoding="utf-8")


def _errors(
    *,
    specified: list[str] | None = None,
    implemented: tuple[str, ...] | None = None,
    exercised: set[str] | None = None,
    vocabularies: set[str] | None = None,
    published: set[str] | None = None,
) -> list[str]:
    """Run the correspondence comparison over a fully-corresponding baseline, minus one thing."""
    return gate._correspondence_errors(
        specified if specified is not None else list(ALL_CHECKS),
        implemented if implemented is not None else ALL_CHECKS,
        exercised if exercised is not None else set(ALL_CHECKS),
        vocabularies if vocabularies is not None else ALL_VOCABULARIES,
        published if published is not None else ALL_VOCABULARIES,
        SPEC_TEXT,
    )


class TestTheGateIsNotVacuous:
    """The baseline must pass, or every planted failure below proves nothing."""

    def test_the_real_repository_corresponds(self) -> None:
        assert gate.check() == 0

    def test_a_fully_corresponding_population_produces_no_errors(self) -> None:
        assert _errors() == []


class TestItCatchesTheDefectsThatWereReal:
    def test_a_check_implemented_but_not_specified(self) -> None:
        """The `witness_is_coherent` defect, exactly.

        It shipped in both verifiers on 2026-08-29 and section 7 listed eleven checks until
        2026-09-15. A clean-room verifier built from the specification accepted all four
        attestations whose own witness arithmetic refutes them.
        """
        errors = _errors(specified=[name for name in ALL_CHECKS if name != "witness_is_coherent"])

        assert any("CHECK NOT SPECIFIED" in error for error in errors)
        assert any("witness_is_coherent" in error for error in errors)

    def test_a_check_with_no_failure_vector(self) -> None:
        """The `data_identity` defect.

        It had zero vectors from the day it was written, because the vector format carried no
        field for input bytes. The guard that should have caught it -- the ten-name tuple in
        `test_attestation_vectors.py` -- did not contain it, and a lower-bound assertion cannot
        see a missing member.
        """
        errors = _errors(exercised={name for name in ALL_CHECKS if name != "data_identity"})

        assert any("CHECK NOT EXERCISED" in error for error in errors)
        assert any("data_identity" in error for error in errors)

    def test_a_closed_vocabulary_that_is_enforced_but_unpublished(self) -> None:
        """The `Provenance` defect, which cost a clean-room verifier 20 of 26 vectors.

        `generate_attestation_schema.py` projected four of the seven closed sets the verifier
        enforces, so section 6.2's claim that the vocabularies are "published as enums in the
        JSON Schema" was false for the one vocabulary a committed vector tests.
        """
        errors = _errors(published=ALL_VOCABULARIES - {"fixes[].provenance"})

        assert any("VOCABULARY NOT PUBLISHED" in error for error in errors)
        assert any("provenance" in error for error in errors)

    def test_a_check_specified_but_never_implemented(self) -> None:
        """The other direction: a document promising a check nothing performs."""
        errors = _errors(specified=[*ALL_CHECKS, "referential_integrity_holds"])

        assert any("CHECK NOT IMPLEMENTED" in error for error in errors)

    def test_an_exemption_that_outlived_its_reason(self) -> None:
        """A stale exemption widens what goes unchecked, silently."""
        gate.NO_FAILURE_VECTOR_EXEMPT["a_check_that_no_longer_exists"] = "reason"
        try:
            errors = _errors()
        finally:
            del gate.NO_FAILURE_VECTOR_EXEMPT["a_check_that_no_longer_exists"]

        assert any("STALE EXEMPTION" in error for error in errors)

    def test_an_exemption_for_a_check_that_does_have_a_vector(self) -> None:
        """An exemption that changes nothing is the same defect as a gate that checks nothing."""
        gate.NO_FAILURE_VECTOR_EXEMPT["signature"] = "reason"
        try:
            errors = _errors()
        finally:
            del gate.NO_FAILURE_VECTOR_EXEMPT["signature"]

        assert any("NEEDLESS EXEMPTION" in error for error in errors)


class TestItRefusesRatherThanReportingAnEmptyPopulation:
    """A parser that silently matches nothing makes every comparison pass by emptiness.

    This is the failure mode the whole gate is about, so the gate must not be able to have it.
    """

    def test_a_missing_normative_block_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot find"):
            gate.specified_checks("# A document with no normative section\n")

    def test_a_block_that_parses_too_few_checks_raises(self) -> None:
        text = "**Normative.**\n\n1. `only_one` - not a real list.\n\n**Advisory.**\n"

        with pytest.raises(ValueError, match="parsed to only 1 checks"):
            gate.specified_checks(text)

    def test_a_duplicated_check_raises(self) -> None:
        names = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india"]
        body = "\n".join(
            f"{index}. `{name}` - a check." for index, name in enumerate(names, start=1)
        )
        text = f"**Normative.**\n\n{body}\n10. `alpha` - the same one again.\n\n**Advisory.**\n"

        with pytest.raises(ValueError, match="more than once"):
            gate.specified_checks(text)

    def test_an_empty_vector_file_raises(self) -> None:
        with pytest.raises(ValueError, match="no vectors"):
            gate.exercised_checks({"vectors": {}})


class TestTheCheckNameRegistryRefusesTheUnnameable:
    """Refusal at the construction site, which is what mutant A14 removes.

    Before this, a check name was a bare string literal at every emission site, so nothing could
    enumerate the population -- which is how four different populations coexisted, two of them
    numerically equal with different members.
    """

    def test_an_unregistered_check_name_cannot_be_constructed(self) -> None:
        with pytest.raises(ValueError, match="not in NORMATIVE_CHECKS"):
            AttestationCheck("looks_plausible_but_unregistered", True, "detail")

    def test_every_registered_name_can_be_constructed(self) -> None:
        for name in NORMATIVE_CHECKS:
            assert AttestationCheck(name, True, "detail").name == name

    def test_the_population_has_no_duplicates(self) -> None:
        assert len(NORMATIVE_CHECKS) == len(set(NORMATIVE_CHECKS))
