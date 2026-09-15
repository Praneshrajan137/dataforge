"""Claim coverage: enumerate the published numbers, not the registered ones.

Why this exists
---------------
``scripts/ci/docs_truth.py`` verifies every claim in ``docs/quantitative_claims.yaml`` against a
JSON artifact, in both directions. It is an **allowlist**: it opens only the documents its claims
name, so a number nobody registered is invisible to it. The repository says so about itself --
``tests/unit/test_release_gate.py``: *"a planted unregistered bolded numeral passes, which is a
coverage direction this gate does not have."* That direction is how the hospital anchor was stale
for 54 days with every gate green.

This is that direction. It enumerates the ARTIFACT -- the decimal figures actually printed in the
published prose -- and requires every one to fall into a named category.

The pattern is not novel and is credited rather than reinvented
--------------------------------------------------------------
DO-178C, ISO 26262 and IEC 62304 require bidirectional traceability, and they achieve completeness
by enumerating the artifact rather than the links: a requirement with no parent is a *derived
requirement*, a named category with an obligation, and untraceable code is *dead* or *deactivated
code* with an explicit verification objective. The artifact is a **traceability matrix** and
auditing its completeness is **coverage analysis**. ``UNSOURCED`` below is the derived-requirement
analogue: not an error, but named, counted and ratcheted rather than silent.

What this deliberately does NOT do
----------------------------------
* **It does not claim to find every claim.** ``statcheck``, doing the same job on statistics in
  academic prose -- the most format-standardised reporting domain there is -- reports recognising
  ~60% of tests and cannot read numbers that appear only in tables. An extractor claiming total
  recall would be lying. Coverage here is ``BOUND / extracted``, and ``extracted`` is a lower bound
  on the true population.
* **It does not register anything.** Choosing which artifact pointer backs a sentence is a human
  judgement, and a machine guess would manufacture exactly the false binding this apparatus exists
  to prevent.
* **It is second-best by construction.** The first-best mechanism is to GENERATE the number into
  the prose, as Quarto and knitr do with inline code and as ``BENCHMARK_REPORT.md`` and the README
  benchmark block already do here. A number inside a generated block cannot drift, which is why
  ``GENERATED`` is a category rather than a failure.

Pre-registered in ``eval/preregistration/claim_coverage_census.md``.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEDGER = PROJECT_ROOT / "docs" / "quantitative_claims.yaml"
BASELINE = PROJECT_ROOT / "eval" / "results" / "claim_coverage_baseline.json"
ARTIFACT = PROJECT_ROOT / "eval" / "results" / "claim_coverage.json"


#: Documents whose numbers are LIVE claims. Derived, never restated: the trust corpus is globbed,
#: because a hand-written list of documents to police is the defect this whole effort is about --
#: ``test_claim_comparability_guard.py`` policed 2 of 45 that way, and ``readme_truth.py`` still
#: uses five hardcoded path lists that between them name no ``docs/trust`` file at all.
def live_documents() -> list[Path]:
    """Return every document whose numbers are treated as live published claims."""
    documents = sorted((PROJECT_ROOT / "docs" / "trust").glob("*.md"))
    for name in ("README.md", "PRODUCT.md", "ARCHITECTURE.md"):
        candidate = PROJECT_ROOT / name
        if candidate.exists():
            documents.append(candidate)
    # The exemption list is applied HERE, not only where claims are checked. Until it was, a
    # document could be declared exempt and surveyed anyway -- an exemption that changes nothing is
    # the same defect as a gate that checks nothing.
    return [document for document in documents if document.name not in EXEMPT_DOCUMENTS]


#: Documents exempt by PRINCIPLE, not convenience, each with the reason. ``PRODUCT.md`` section 5
#: forbids rewriting frozen historical evidence, so a number in an append-only log is a record of
#: what was believed on its date rather than a live claim. Registering them would invite editing
#: them.
EXEMPT_DOCUMENTS: Final[dict[str, str]] = {
    "DECISIONS.md": (
        "Append-only decision log. PRODUCT.md section 5 forbids rewriting it, so its numbers are "
        "historical record rather than live claims, and its own standing notice says reading an "
        "old entry as a current claim is a mistake."
    ),
    "CHANGELOG.md": (
        "Generated release history. Its numbers are version identifiers and dates, not "
        "measurements."
    ),
    "BENCHMARK_REPORT.md": (
        "Fully generated from eval/results/ by scripts/bench/generate_report.py, which is the "
        "first-best mechanism: a generated number cannot drift from its artifact, so binding it "
        "with a ledger entry would add a second place for the same fact to live."
    ),
    "claim-coverage-census.md": (
        "SELF-REFERENCE. Its content is a report OF this census, so surveying it makes the output "
        "an input: binding its headline bound_share would increment the bound count that produces "
        "bound_share. Its numbers are still verified -- they are registered in "
        "docs/quantitative_claims.yaml and bound to eval/results/claim_coverage.json by "
        "docs_truth, which is a separate gate and unaffected by this exemption. This is the same "
        "category error docs/trust/measure-on-my-table-result.md records its egress scan making "
        "when it scanned its own commentary."
    ),
}

#: A decimal with at least two fractional digits, optionally carrying an ``x`` or ``%`` suffix.
#: Deliberately narrow, trading recall for precision: this is the shape every measured figure in
#: this repository takes (0.8352, 0.4599, 0.7954), and admitting one-place decimals would sweep in
#: thresholds, ratios and prose like "1.5x" while adding little.
#:
#: The suffix allowance was added because K1 fired on the first run: ``wide-table-review-burden.md``
#: registers ``25.42`` and prints it as ``**25.42x**``, so a bare ``(?![\w.])`` lookahead could not
#: see it. ``docs_truth.py`` allows the same two suffixes when matching prose, and an extractor
#: stricter than the gate it complements would under-report coverage while looking precise. This is
#: what the instrument-falsification criterion is for.
_FIGURE = re.compile(r"(?<![\w.])(\d+\.\d{2,})(?:[x%])?(?![\w.])")

#: Patterns whose matches are not measurements. Each is a stated false-positive class rather than a
#: silent filter, because the pre-registration's K2 requires the confusion be published.
_NOT_A_MEASUREMENT: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("semantic_version", re.compile(r"\d+\.\d+\.\d+")),
    ("arxiv_id", re.compile(r"(?:arXiv:)?\d{4}\.\d{4,5}")),
    ("iso_date", re.compile(r"\d{4}-\d{2}-\d{2}")),
)

_FENCE = re.compile(r"^\s*```")

#: Markers delimiting machine-generated regions. ``<!-- BENCH:START -->`` / ``<!-- BENCH:END -->``
#: is the pair this repository actually uses (``README.md``, ``docs/docs/index.md``), written by
#: ``scripts/bench/refresh_benchmark_truth.py``. Derived from a grep rather than guessed: the first
#: draft looked for ``BEGIN GENERATED`` and found ZERO generated blocks, which would have reported
#: the repository's one first-best mechanism as absent.
#:
#: **Anchored to the whole line**, and that matters. Unanchored, a document that MENTIONS the marker
#: in prose -- as ``docs/trust/claim-coverage-census.md`` does when explaining this very category --
#: flipped the extractor into generated mode and mis-categorised everything up to the next mention,
#: inflating GENERATED from 12 to 17. That is the same category error
#: ``docs/trust/measure-on-my-table-result.md`` records its egress scan making when it scanned its
#: own commentary for the user's values. A generator emits its markers alone on a line; prose does
#: not.
_GENERATED_OPEN = re.compile(r"^\s*(?:<!--\s*[A-Z_]+:(?:START|BEGIN)\s*-->|BEGIN GENERATED)\s*$")
_GENERATED_CLOSE = re.compile(r"^\s*(?:<!--\s*[A-Z_]+:END\s*-->|END GENERATED)\s*$")


@dataclass(frozen=True)
class Figure:
    """One decimal figure found in prose, with where it was found and how it is sourced."""

    document: str
    line: int
    value: str
    category: str
    detail: str


def _load_ledger() -> list[dict[str, Any]]:
    payload = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    claims = payload.get("claims", []) if isinstance(payload, dict) else []
    return [claim for claim in claims if isinstance(claim, dict)]


def _ledger_index(claims: Iterable[dict[str, Any]]) -> tuple[dict[str, set[str]], dict[str, str]]:
    """Return (doc -> expected values) and (value -> a claim id that binds it anywhere)."""
    by_document: dict[str, set[str]] = {}
    anywhere: dict[str, str] = {}
    for claim in claims:
        document = str(claim.get("doc", ""))
        expect = str(claim.get("expect", ""))
        if not document or not expect:
            continue
        by_document.setdefault(document.replace("\\", "/"), set()).add(expect)
        anywhere.setdefault(expect, str(claim.get("id", "?")))
    return by_document, anywhere


def _masked_spans(line: str) -> list[tuple[int, int, str]]:
    """Return spans of the line that are known not to be measurements, with the class name."""
    spans: list[tuple[int, int, str]] = []
    for label, pattern in _NOT_A_MEASUREMENT:
        for match in pattern.finditer(line):
            spans.append((match.start(), match.end(), label))
    return spans


def _document_key(document: Path) -> str:
    """Return the repo-relative POSIX path, or the bare name for a document outside the tree.

    Defensive rather than decorative: ``relative_to`` raises on any path outside
    ``PROJECT_ROOT``, so an extractor that assumed containment crashed on a temp file. A gate that
    cannot be exercised on a fixture is a gate whose refusals cannot be tested.
    """
    try:
        return document.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return document.name


def extract(document: Path) -> tuple[list[Figure], dict[str, int]]:
    """Return the figures in a document plus a tally of the false-positive classes excluded.

    Skips fenced code blocks: a number in a command or a JSON sample is an illustration, and
    ``docs_truth`` does not bind those either.
    """
    relative = _document_key(document)
    by_document, anywhere = _ledger_index(_load_ledger())
    bound_values = by_document.get(relative, set())

    figures: list[Figure] = []
    excluded: dict[str, int] = {}
    in_fence = False
    in_generated = False

    for number, raw in enumerate(document.read_text(encoding="utf-8").splitlines(), start=1):
        if _FENCE.match(raw):
            in_fence = not in_fence
            continue
        if _GENERATED_OPEN.search(raw):
            in_generated = True
        if _GENERATED_CLOSE.search(raw):
            in_generated = False
            continue
        if in_fence:
            continue

        masked = _masked_spans(raw)
        for match in _FIGURE.finditer(raw):
            start, end = match.span(1)
            overlap = next(
                (label for left, right, label in masked if left <= start and end <= right), None
            )
            if overlap is not None:
                excluded[overlap] = excluded.get(overlap, 0) + 1
                continue
            value = match.group(1)
            if in_generated:
                category, detail = "GENERATED", "inside a generated block"
            elif value in bound_values:
                category, detail = "BOUND", "registered for this document"
            elif value in anywhere:
                category, detail = "RESTATED", f"bound elsewhere as {anywhere[value]}"
            else:
                category, detail = "UNSOURCED", "no ledger entry binds this value"
            figures.append(Figure(relative, number, value, category, detail))
    return figures, excluded


def survey() -> dict[str, Any]:
    """Categorise every figure in the live corpus and return the report payload."""
    figures: list[Figure] = []
    excluded: dict[str, int] = {}
    for document in live_documents():
        found, skipped = extract(document)
        figures.extend(found)
        for label, count in skipped.items():
            excluded[label] = excluded.get(label, 0) + count

    tally: dict[str, int] = {}
    for figure in figures:
        tally[figure.category] = tally.get(figure.category, 0) + 1

    unsourced_by_document: dict[str, int] = {}
    for figure in figures:
        if figure.category == "UNSOURCED":
            unsourced_by_document[figure.document] = (
                unsourced_by_document.get(figure.document, 0) + 1
            )

    extracted = len(figures)
    return {
        "measurement": "claim_coverage",
        "extracted_figures": extracted,
        "by_category": dict(sorted(tally.items())),
        "bound_share": round(tally.get("BOUND", 0) / extracted, 4) if extracted else None,
        "documents_surveyed": len(live_documents()),
        "documents_with_no_bound_figure": sorted(
            _document_key(document)
            for document in live_documents()
            if not any(figure.category == "BOUND" for figure in extract(document)[0])
        ),
        "unsourced_by_document": dict(sorted(unsourced_by_document.items())),
        "unsourced_total": sum(unsourced_by_document.values()),
        "excluded_false_positive_classes": dict(sorted(excluded.items())),
        "exempt_documents": dict(sorted(EXEMPT_DOCUMENTS.items())),
        "limitations": (
            "extracted_figures is a LOWER BOUND on the published claim population, not a count of "
            "it. Only decimals with two or more fractional digits are extracted, fenced code is "
            "skipped, and integers, percentages and one-place decimals are not counted at all. "
            "statcheck, doing this job on academic statistics, reports ~60% recall in a stricter "
            "domain. bound_share is therefore a coverage figure over the extracted population and "
            "must never be quoted as coverage of all published claims."
        ),
    }


def instrument_falsification_errors() -> list[str]:
    """K1: the extractor must find every already-registered claim value in its own document.

    An extractor blind to the numbers we know about cannot be trusted about the ones we do not, so
    a failure here suppresses the coverage figure entirely rather than lowering it.
    """
    by_document, _ = _ledger_index(_load_ledger())
    errors: list[str] = []
    for document, expected in sorted(by_document.items()):
        path = PROJECT_ROOT / document
        if not path.exists() or path.suffix != ".md":
            continue  # Python-file claims are policed by test_user_facing_numbers.py.
        if path.name in EXEMPT_DOCUMENTS:
            continue
        found = {figure.value for figure in extract(path)[0]}
        for value in sorted(expected):
            if not _FIGURE.fullmatch(value):
                continue  # integers and percentages are outside this extractor by design
            if value not in found:
                errors.append(f"{document}: registered value {value!r} not found by the extractor")
    return errors


def _baseline_errors(report: dict[str, Any]) -> list[str]:
    """Compare against the committed baseline. Ratchets DOWN only, and self-checks its own total."""
    if not BASELINE.exists():
        return [f"{BASELINE.name} is absent; run --emit to record the current state."]
    committed = json.loads(BASELINE.read_text(encoding="utf-8"))
    recorded: dict[str, int] = committed.get("unsourced_by_document", {})
    errors: list[str] = []

    # K4: a botched merge must FAIL rather than silently loosen the ratchet.
    stated_total = committed.get("unsourced_total")
    if stated_total != sum(recorded.values()):
        errors.append(
            f"baseline is internally inconsistent: unsourced_total is {stated_total} but its "
            f"per-document counts sum to {sum(recorded.values())}. A conflict resolution that "
            "loosens the ratchet must fail, not pass."
        )

    current: dict[str, int] = report["unsourced_by_document"]
    for document, count in sorted(current.items()):
        allowed = recorded.get(document, 0)
        if count > allowed:
            errors.append(
                f"{document}: {count} unsourced figures, baseline allows {allowed}. A new number "
                "in published prose must be registered in docs/quantitative_claims.yaml, placed "
                "in a generated block, or -- if it genuinely cannot be bound -- added to the "
                "baseline with the reason, deliberately and in review."
            )
    return errors


def main() -> int:
    """Report or check claim coverage."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Fail if unsourced figures increased.")
    group.add_argument("--emit", action="store_true", help="Record the current state as baseline.")
    group.add_argument("--report", action="store_true", help="Print the survey and exit 0.")
    args = parser.parse_args()

    falsifications = instrument_falsification_errors()
    if falsifications:
        print("INSTRUMENT FALSIFIED (K1). Reporting no coverage figure; fix the extractor first:")
        for error in falsifications:
            print(f"  - {error}")
        return 1

    report = survey()
    print(
        f"Claim coverage: {report['by_category'].get('BOUND', 0)} bound, "
        f"{report['by_category'].get('GENERATED', 0)} generated, "
        f"{report['by_category'].get('RESTATED', 0)} restated elsewhere, "
        f"{report['by_category'].get('UNSOURCED', 0)} unsourced, "
        f"of {report['extracted_figures']} decimal figures across "
        f"{report['documents_surveyed']} live documents."
    )
    print(f"  bound share of extracted figures: {report['bound_share']}")
    print(f"  documents with no bound figure:   {len(report['documents_with_no_bound_figure'])}")
    print(f"  excluded false-positive classes:  {report['excluded_false_positive_classes']}")

    if args.report:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    if args.emit:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        # The survey artifact is written alongside the baseline so this document's own headline can
        # be BOUND like any other claim. A write-up announcing a coverage gate whose own numbers are
        # unsourced would fail its own standard, which is the failure mode this whole instrument is
        # about.
        ARTIFACT.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        payload = {
            "measurement": "claim_coverage_baseline",
            "note": (
                "Grandfathered unsourced figures per document. The gate fails when any count "
                "RISES, so every new number in published prose must be bound, generated, or "
                "deliberately exempted. Ratcheting on unsourced-decreasing rather than "
                "bound-increasing is deliberate: a ratchet on the latter is satisfiable by "
                "registering the easiest numbers, which measures compliance instead of coverage."
            ),
            "unsourced_by_document": report["unsourced_by_document"],
            "unsourced_total": report["unsourced_total"],
        }
        BASELINE.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"wrote {BASELINE.relative_to(PROJECT_ROOT)}")
        print(f"wrote {ARTIFACT.relative_to(PROJECT_ROOT)}")
        return 0

    errors = _baseline_errors(report)
    if errors:
        print("\nClaim coverage check FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("\nClaim coverage check passed: no document gained an unsourced figure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
