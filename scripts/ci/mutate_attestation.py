"""Mutation harness for the attestation's normative tier.

`specs/SPEC_repair_attestation.md` section 8 has cited this file since 2026-08-13, and section 9
required *"Every normative check has a killing mutant"*. **The file did not exist until
2026-09-15**, so that acceptance criterion was unenforceable for a month -- the second artifact
the specification cited before it existed. Section 2 records the first.

Each mutant reverts one normative check to a plausible weaker form and asserts the suite notices.
A check whose mutant SURVIVES is a check nothing tests: the conformance vectors would pass while
the guarantee is gone, which is precisely how `witness_is_coherent` could have been deleted
without a red build before the vectors covered it.

Shape borrowed wholesale from ``scripts/ci/mutate_autoapply_guards.py``, including the parts that
look paranoid and are not:

* **A kill is pytest exit 1 and nothing else.** ``returncode != 0`` once scored 18 of 18 while
  every mutant had died of ``ModuleNotFoundError``.
* **Four NOT_APPLIED guards before trusting a mutation**, because a mutant whose anchor text has
  drifted silently applies nothing and then reports a pass.
* **A baseline run first**, and a refusal to score at all if the unmutated suite is not green. A
  mutation score against a red baseline is noise.

Usage:
    python scripts/ci/mutate_attestation.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PYTEST_ALL_PASSED = 0
PYTEST_TESTS_FAILED = 1

RUN_TIMEOUT_SECONDS = 900


def _python() -> str:
    """Resolve the interpreter, preferring an explicit override then the venv.

    ``mutate_autoapply_guards.py`` records why this is not simply ``sys.executable``: a hardcoded
    Windows venv path meant that harness had never executed on Linux CI.
    """
    override = os.environ.get("DATAFORGE_MUTATE_PYTHON")
    if override:
        return override
    for candidate in (
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / ".venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


PYTHON = _python()

ATTESTATION = "dataforge/attestation/__init__.py"
VECTOR_TESTS = "tests/unit/test_attestation_vectors.py"
UNIT_TESTS = "tests/unit/test_attestation.py"
CORRESPONDENCE = "tests/unit/test_spec_correspondence.py"


@dataclass(frozen=True)
class Mutant:
    """One weakening of the normative tier, and the tests that must notice it."""

    name: str
    target: str
    old: str
    new: str
    tests: tuple[str, ...]
    why: str
    check: str
    """Which normative check this mutant disables. Used to report per-check coverage."""


MUTANTS: tuple[Mutant, ...] = (
    Mutant(
        name="A1-envelope-type-unchecked",
        target=ATTESTATION,
        old='statement.get("_type") == STATEMENT_TYPE',
        new="True",
        tests=(VECTOR_TESTS,),
        why="any document claiming our predicateType is accepted whatever its _type",
        check="envelope_recognised",
    ),
    Mutant(
        name="A2-version-accepts-anything",
        target=ATTESTATION,
        old="            version == ATTESTATION_VERSION,",
        new="            True,",
        tests=(VECTOR_TESTS,),
        why="a v2 attestation is read with v1 semantics instead of being refused",
        check="version_recognised",
    ),
    Mutant(
        name="A3-vocabulary-fails-open",
        target=ATTESTATION,
        old="if item.get(field) not in members:",
        new="if False:",
        tests=(VECTOR_TESTS,),
        why="an unknown provenance or review_reason passes as a published member",
        check="vocabulary_closed",
    ),
    Mutant(
        name="A4-subject-any-instead-of-every",
        target=ATTESTATION,
        old="bool(subject_digests) and not unexpected and _is_hex64(expected)",
        new="bool(subject_digests) and _is_hex64(expected)",
        tests=(VECTOR_TESTS,),
        why=(
            "the subject rule reverts to accepting a statement that also names an artifact "
            "nobody attested -- the smuggling hole both verifiers had until 2026-08-29"
        ),
        check="subject_matches_post_state",
    ),
    Mutant(
        name="A5-data-identity-always-passes",
        target=ATTESTATION,
        old="actual == expected,",
        new="True,",
        tests=(VECTOR_TESTS,),
        why=(
            "bytes that do not hash to the attested digest verify anyway, so the only check "
            "binding an attestation to real data stops binding"
        ),
        check="data_identity",
    ),
    Mutant(
        name="A6-reversibility-not-required",
        target=ATTESTATION,
        old='if not predicate.get("applied"):\n        return [\n            AttestationCheck(\n                "reversibility_complete",',
        new='if True:\n        return [\n            AttestationCheck(\n                "reversibility_complete",',
        tests=(VECTOR_TESTS,),
        why="an applied repair with no revert command reports reversible",
        check="reversibility_complete",
    ),
    Mutant(
        name="A7-verdicts-ignore-the-verifier",
        target=ATTESTATION,
        old='ok = verifier == "accept" and safety == "allow"',
        new='ok = safety == "allow"',
        tests=(VECTOR_TESTS,),
        why="a repair the verifier REJECTED still verifies, so long as safety allowed it",
        check="verdicts_accepting",
    ),
    Mutant(
        name="A8-strength-not-re-derived",
        target=ATTESTATION,
        old='if derived != "proven":',
        new="if False:",
        tests=(VECTOR_TESTS,),
        why=(
            "the recorded strength is believed instead of re-derived, so an untrusted value on "
            "an uncovered column is proven because it says so"
        ),
        check="strength_is_earned",
    ),
    Mutant(
        name="A9-constraints-need-not-be-embedded",
        target=ATTESTATION,
        old="has_constraints = isinstance(constraints, Mapping) and bool(constraints)",
        new="has_constraints = True",
        tests=(VECTOR_TESTS,),
        why=(
            "a write proven only by schema authority no longer has to carry that schema, so the "
            "third party is back to a dangling pointer"
        ),
        check="constraints_present",
    ),
    Mutant(
        name="A10-signature-not-verified",
        target=ATTESTATION,
        old='return AttestationCheck("signature", False, "no signature verified against the key"), None',
        new='return AttestationCheck("signature", True, "no signature verified against the key"), statement',
        tests=(VECTOR_TESTS,),
        why="a forged or wrong-key signature reports verified",
        check="signature",
    ),
    Mutant(
        name="A11-witness-majority-becomes-plurality",
        target=ATTESTATION,
        old="if support * 2 <= group_size:",
        new="if support * 2 < 0:",
        tests=(VECTOR_TESTS,),
        why=(
            "the strict-majority rule becomes a plurality, which is the difference mutant M16 "
            "measures at 731 corrupted clean cells on hospital"
        ),
        check="witness_is_coherent",
    ),
    Mutant(
        name="A12-witness-count-need-not-match-support",
        target=ATTESTATION,
        old="if counts.get(str(new_digest)) != support:",
        new="if False:",
        tests=(VECTOR_TESTS,),
        why=(
            "a witness may claim support its own distribution does not show, including for a "
            "value absent from the group entirely"
        ),
        check="witness_is_coherent",
    ),
    Mutant(
        name="A13-schema-completeness-unchecked",
        target=ATTESTATION,
        old="for field in REQUIRED_TOOL_FIELDS:",
        new="for field in ():",
        tests=(VECTOR_TESTS, UNIT_TESTS),
        why="an attestation with no tool version verifies, so nobody can tell which semantics applied",
        check="schema_complete",
    ),
    Mutant(
        name="A14-check-names-unregistered",
        target=ATTESTATION,
        old="if name not in _NORMATIVE_CHECK_NAMES:",
        new="if False:",
        tests=(CORRESPONDENCE,),
        why=(
            "a check name can be emitted without being registered, which is how twelve checks "
            "ran against a specification listing eleven"
        ),
        check="__registry__",
    ),
    Mutant(
        name="A15-authority-claim-taken-on-trust",
        target=ATTESTATION,
        old="if entailed == claimed:",
        new="if True:",
        tests=(VECTOR_TESTS,),
        why=(
            "the authority claim stops being compared to the premise it came from, which restores "
            "the state in which a producer could emit any authoritative_columns beside any premise "
            "and pass every check -- so `proven` returns to being an assertion a reader must "
            "accept rather than arithmetic a reader can repeat"
        ),
        check="authority_is_entailed",
    ),
)


def _run(command: list[str]) -> int:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=RUN_TIMEOUT_SECONDS,
    )
    return completed.returncode


def _pytest(paths: tuple[str, ...]) -> int:
    return _run(
        [
            PYTHON,
            "-m",
            "pytest",
            *paths,
            "-x",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:randomly",
        ]
    )


def baseline_verdict() -> tuple[bool, str]:
    """Refuse to score anything if the unmutated suite is not green."""
    paths = tuple(sorted({path for mutant in MUTANTS for path in mutant.tests}))
    code = _pytest(paths)
    if code == PYTEST_ALL_PASSED:
        return True, f"baseline green over {len(paths)} test path(s)"
    return False, f"baseline is NOT green (pytest exit {code}) over {paths}"


def _verdict_for(returncode: int) -> str:
    """Only pytest's "tests failed" exit code counts as a kill."""
    if returncode == PYTEST_TESTS_FAILED:
        return "KILLED"
    if returncode == PYTEST_ALL_PASSED:
        return "SURVIVED"
    return f"HARNESS_ERROR (pytest exit {returncode} -- not a kill)"


def run(mutant: Mutant) -> str:
    target = PROJECT_ROOT / mutant.target
    original = target.read_text(encoding="utf-8")

    if mutant.old not in original:
        return f"NOT_APPLIED (anchor absent in {mutant.target})"
    mutated = original.replace(mutant.old, mutant.new, 1)
    if mutated == original:
        return "NOT_APPLIED (replacement was a no-op)"

    try:
        target.write_text(mutated, encoding="utf-8", newline="\n")
        if target.read_text(encoding="utf-8") == original:
            return "NOT_APPLIED (file unchanged on disk)"
        return _verdict_for(_pytest(mutant.tests))
    finally:
        target.write_text(original, encoding="utf-8", newline="\n")


def main() -> int:
    from dataforge.attestation import NORMATIVE_CHECKS

    green, note = baseline_verdict()
    print(f"baseline: {note}")
    if not green:
        print(
            "REFUSING TO SCORE MUTANTS: a mutation score against a red baseline measures "
            "nothing. Fix the suite first."
        )
        return 1

    results: list[tuple[Mutant, str]] = []
    for mutant in MUTANTS:
        verdict = run(mutant)
        results.append((mutant, verdict))
        print(f"{verdict:12s} {mutant.name}  -- {mutant.why}")

    problems = [(mutant, verdict) for mutant, verdict in results if verdict != "KILLED"]

    # Enumerate the artifact, name the remainder, refuse on anything unnameable. A mutation
    # harness that covers ten of twelve checks and says "all mutants killed" is the same defect
    # class the checks themselves had.
    covered = {mutant.check for mutant in MUTANTS}
    uncovered = sorted(set(NORMATIVE_CHECKS) - covered)

    if problems:
        print("\nPROBLEMS:")
        for mutant, verdict in problems:
            print(f"  {verdict}: {mutant.name} ({mutant.target})")
        return 1

    if uncovered:
        print(
            f"\nUNMUTATED CHECKS: {uncovered}. Every normative check needs a killing mutant "
            "(specs/SPEC_repair_attestation.md section 9). Add one, or name the shortfall here."
        )
        return 1

    print(
        f"\nAll {len(results)} mutants killed, covering every one of the "
        f"{len(NORMATIVE_CHECKS)} normative checks."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
