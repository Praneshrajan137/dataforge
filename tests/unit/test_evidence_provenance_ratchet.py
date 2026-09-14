"""Provenance coverage over committed evidence artifacts, as a ratchet.

First principle #3 is *"A benchmark you cannot reproduce byte-for-byte is an anecdote, not a
result."* Measured 2026-09-12: of **962** JSON artifacts under ``eval/results/``, **22**
carry a ``git_commit`` anywhere in their payload. The remaining 940 record numbers with no
machine-readable statement of what produced them.

That includes load-bearing evidence. ``bypass_allowlist_hospital.json`` backs
``docs/trust/bypass-allowlist-evidence.md``, which ``CLAUDE.md`` names as the replacement for
the retired 0.7926 anchor and which ``PRODUCT.md`` §1.4 cites for per-detector write
authority. ``capability_measurement_stage.json`` backs the stage-gap figure quoted in
``PRODUCT.md`` §1.1. Neither carries provenance.

**Why this file is a ratchet and not a backfill.** The mechanism already exists and is good:
:class:`dataforge.bench.core.BenchmarkEvidenceMetadata` records schema version, git commit and
dirty flag, seeds, dependency versions, platform, a generator command, a *reproduction*
command, per-dataset evidence and artifact digests. The 22 covered artifacts are the ones
written through it. So the gap is not a missing capability -- it is a mechanism with too few
consumers, the same shape as the human-label vocabulary that ``dataforge/ui/outcome.py``
exists to fix.

Backfilling the other 940 is impossible and would be *wrong* to attempt: nobody knows which
commit produced a 2026-04 run, and writing a plausible hash into an old artifact would
manufacture evidence, which the honesty doctrine forbids outright. What can be done honestly
is make the gap **visible and monotonically shrinking**: coverage may rise, never fall. A new
measurement script that skips provenance now fails a test instead of quietly joining 940
others.

To raise the floor: write artifacts through ``BenchmarkEvidenceMetadata`` (or include an
equivalent ``git_commit``), then raise :data:`_COVERAGE_FLOOR` in the same commit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

_RESULTS_DIR: Final[Path] = Path("eval/results")

#: Artifacts carrying a ``git_commit`` as measured on 2026-09-12. Raise this when you improve
#: coverage; never lower it to make a change pass.
_COVERAGE_FLOOR: Final[int] = 22

#: Total artifacts at the same measurement, recorded so the RATIO is legible in failures. Not
#: asserted as an upper bound -- new evidence is welcome, it just has to carry provenance.
_TOTAL_AT_MEASUREMENT: Final[int] = 962


def _has_git_commit(payload: object, depth: int = 0) -> bool:
    """Return whether ``git_commit`` appears anywhere within a shallow traversal.

    Deliberately structure-agnostic. Different harnesses nest their provenance differently
    (top level, under ``metadata``, under ``evidence_metadata``), and a checker that
    hardcoded one layout would police only the harnesses it already knew about -- the
    frozen-population defect ``PRODUCT.md`` §1.3 records twice.
    """
    if depth > 4:
        return False
    if isinstance(payload, dict):
        if "git_commit" in payload:
            return True
        return any(_has_git_commit(value, depth + 1) for value in payload.values())
    if isinstance(payload, list):
        return any(_has_git_commit(item, depth + 1) for item in payload[:5])
    return False


def _coverage() -> tuple[int, int, list[Path]]:
    """Return (covered, total, uncovered_paths) for committed evidence artifacts."""
    if not _RESULTS_DIR.is_dir():
        return 0, 0, []
    covered = 0
    total = 0
    uncovered: list[Path] = []
    for path in sorted(_RESULTS_DIR.rglob("*.json")):
        total += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            uncovered.append(path)
            continue
        if _has_git_commit(payload):
            covered += 1
        else:
            uncovered.append(path)
    return covered, total, uncovered


def test_provenance_coverage_does_not_regress() -> None:
    """Coverage may rise, never fall. A new artifact must carry provenance."""
    covered, total, _ = _coverage()
    assert covered >= _COVERAGE_FLOOR, (
        f"provenance coverage fell to {covered} of {total} artifacts, below the recorded "
        f"floor of {_COVERAGE_FLOOR}. An evidence artifact lost its git_commit, which means "
        f"a published number can no longer be traced to the code that produced it. "
        f"First principle #3 forbids that. Restore the provenance rather than lowering the "
        f"floor."
    )


def test_the_gap_is_recorded_rather_than_hidden() -> None:
    """The uncovered majority is a known, quantified gap -- assert it is still quantified.

    If coverage ever reaches every artifact this test should be deleted, not weakened. Until
    then it exists so nobody reads the ratchet above as "provenance is handled".
    """
    covered, total, uncovered = _coverage()
    if total == 0:
        return
    assert uncovered, (
        "every artifact now carries provenance -- delete this test and the gap section of "
        "the module docstring rather than leaving a stale claim that a gap exists"
    )
    assert covered < total, "coverage is complete; see the message above"


def test_provenance_mechanism_exists_and_is_the_one_to_reuse() -> None:
    """Name the vetted path, so a new harness does not reimplement provenance badly.

    ``PRODUCT.md`` §1.4: "A reimplementation of a measurement reproduces the defect the vetted
    path exists to avoid." The same applies to provenance -- a hand-rolled block that omits
    the dirty flag or the reproduction command is worse than reusing this model.
    """
    from dataforge.bench.core import BenchmarkEvidenceMetadata

    fields = set(BenchmarkEvidenceMetadata.model_fields)
    for required in ("git_commit", "git_dirty", "generated_at_utc", "reproduction_command"):
        assert required in fields, (
            f"BenchmarkEvidenceMetadata lost {required!r}; it is the field that makes an "
            "artifact reproducible rather than merely dated"
        )
