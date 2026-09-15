"""The claim-coverage census must refuse, and must refuse for the right reasons.

`docs_truth.py` verifies every claim in `docs/quantitative_claims.yaml` and opens no other
document, so it is an **allowlist**: a number nobody registered is invisible to it. That is the
direction the hospital anchor drifted through for 54 days with every gate green, and
`tests/unit/test_release_gate.py` says so in as many words -- *"a planted unregistered bolded
numeral passes, which is a coverage direction this gate does not have."*

`scripts/ci/claim_coverage.py` is that direction. These tests pin its **refusals**, because every
harness built in this repository that lacked such a test turned out to have a way of passing
vacuously, and a coverage gate that cannot fail is worse than none: it reports protection.

Pre-registered in `eval/preregistration/claim_coverage_census.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.ci import claim_coverage as census

_ROOT = Path(__file__).resolve().parents[2]


class TestTheCorpusIsDerived:
    """A hand-written list of documents to police is the defect this effort is about."""

    def test_every_trust_document_is_surveyed_or_exempt_with_a_reason(self) -> None:
        """Globbed, not enumerated. Omission must be declared, never silent.

        `test_claim_comparability_guard.py` once policed 2 of 45 trust documents because
        `_TRUST_DOCS` was hand-named, and `readme_truth.py` still uses five hardcoded path lists
        that between them name no `docs/trust` file at all.

        Exemptions are permitted because the DO-178C shape this instrument copies *requires* the
        unlinked remainder to have a name and a reason rather than be absent -- but an exemption
        must be in `EXEMPT_DOCUMENTS`, which a sibling test forces to carry a justification.
        """
        surveyed = {path.resolve() for path in census.live_documents()}
        on_disk = {path.resolve() for path in (_ROOT / "docs" / "trust").glob("*.md")}
        exempt = {path for path in on_disk if path.name in census.EXEMPT_DOCUMENTS}

        assert on_disk, "no trust documents found; this assertion would be vacuous"
        unaccounted = on_disk - surveyed - exempt
        assert unaccounted == set(), (
            f"trust document(s) neither surveyed nor declared exempt: "
            f"{sorted(p.name for p in unaccounted)}"
        )
        assert len(exempt) <= 2, (
            f"{len(exempt)} trust documents are exempt; exemptions are meant to be rare and "
            "principled, and a growing list is how a corpus quietly shrinks"
        )

    def test_the_corpus_is_not_trivially_small(self) -> None:
        assert len(census.live_documents()) >= 40

    def test_every_exemption_states_a_reason(self) -> None:
        """An exemption without a reason is an exemption nobody can review."""
        for name, reason in census.EXEMPT_DOCUMENTS.items():
            assert len(reason.strip()) >= 60, f"{name} has no substantive reason recorded"

    def test_exempt_documents_are_not_also_surveyed(self) -> None:
        surveyed = {path.name for path in census.live_documents()}
        overlap = surveyed & set(census.EXEMPT_DOCUMENTS)

        assert overlap == set(), f"{sorted(overlap)} is both surveyed and exempt"

    def test_the_self_referential_writeup_is_exempt(self) -> None:
        """The census cannot be a subject of itself.

        `claim-coverage-census.md` reports this census's output, so binding its headline
        `bound_share` would increment the bound count that produces `bound_share`. Its numbers are
        still verified -- registered in `docs/quantitative_claims.yaml` against
        `eval/results/claim_coverage.json` and checked by `docs_truth`, a separate gate this
        exemption does not touch. Pinned as a test because the exemption looks like an evasion and
        must be findable as a deliberate choice.
        """
        assert "claim-coverage-census.md" in census.EXEMPT_DOCUMENTS
        assert "SELF-REFERENCE" in census.EXEMPT_DOCUMENTS["claim-coverage-census.md"]


class TestTheExtractorFindsWhatIsAlreadyKnown:
    """K1. An extractor blind to the numbers we registered cannot be trusted about the rest."""

    def test_every_registered_decimal_is_found_in_its_own_document(self) -> None:
        errors = census.instrument_falsification_errors()

        assert errors == [], (
            "the extractor cannot find registered claim values in the documents that register "
            f"them, so no coverage figure may be published: {errors}"
        )

    def test_an_x_suffixed_figure_is_extracted(self) -> None:
        """The concrete bug K1 caught on the first run.

        `wide-table-review-burden.md` registers `25.42` and prints it as `**25.42x**`. The first
        extractor's `(?![\\w.])` lookahead could not see it, so it would have reported that
        document as less covered than it is. `docs_truth.py` allows the same two suffixes.
        """
        assert census._FIGURE.search("ratio of **25.42x** the review rows") is not None
        assert census._FIGURE.search("**25.42x**").group(1) == "25.42"
        assert census._FIGURE.search("a share of 12.50%").group(1) == "12.50"


class TestTheFalsePositiveClassesAreDeclared:
    """K2: publish the confusion rather than a ratio over a junk denominator."""

    def test_an_arxiv_id_is_not_a_measurement(self) -> None:
        figures, excluded = census.extract(_ROOT / "docs" / "trust" / "accuracy-frontier.md")
        values = {figure.value for figure in figures}

        assert "2311.06517" not in values
        assert excluded.get("arxiv_id", 0) >= 1

    def test_a_semantic_version_is_not_a_measurement(self) -> None:
        masked = census._masked_spans("bumped to 5.0.1 this week")

        assert any(label == "semantic_version" for _, _, label in masked)

    def test_the_report_states_its_own_limitations(self) -> None:
        """A lower bound presented as a total is the defect, not the number."""
        report = census.survey()

        assert "LOWER BOUND" in report["limitations"]
        assert "statcheck" in report["limitations"]


class TestTheRatchetHasTeeth:
    """Every one of these was planted and observed to fire before being trusted."""

    def test_a_new_unsourced_figure_raises_the_count(self, tmp_path: Path) -> None:
        """The gate's whole purpose, exercised without touching the real corpus."""
        document = tmp_path / "planted.md"
        document.write_text("A planted result: precision 0.98765 on nothing.\n", encoding="utf-8")
        figures, _ = census.extract(document)

        assert [figure.category for figure in figures] == ["UNSOURCED"]
        assert figures[0].value == "0.98765"

    def test_a_generated_block_is_not_unsourced(self, tmp_path: Path) -> None:
        """The first-best mechanism must not be penalised by the second-best one.

        The marker pair is the one this repository uses. An earlier draft looked for
        `BEGIN GENERATED` and found ZERO generated blocks, which would have reported the repo's
        only drift-proof mechanism as absent.
        """
        document = tmp_path / "generated.md"
        document.write_text(
            "<!-- BENCH:START -->\n| heuristic | 0.3949 |\n<!-- BENCH:END -->\n", encoding="utf-8"
        )
        figures, _ = census.extract(document)

        assert [figure.category for figure in figures] == ["GENERATED"]

    def test_a_fenced_code_block_is_skipped(self, tmp_path: Path) -> None:
        document = tmp_path / "fenced.md"
        document.write_text("```\nthreshold = 0.9999\n```\n", encoding="utf-8")
        figures, _ = census.extract(document)

        assert figures == []

    def test_the_baseline_self_check_fails_a_loosening_merge(self, tmp_path: Path) -> None:
        """K4. A ratchet that silently loosens is worse than none: it looks like protection.

        Committed baseline files conflict on nearly every merge, and a bad resolution is the
        documented way ratchets stop ratcheting. The stated total must agree with the parts.
        """
        original = census.BASELINE
        broken = tmp_path / "baseline.json"
        broken.write_text(
            json.dumps({"unsourced_by_document": {"a.md": 1, "b.md": 2}, "unsourced_total": 999}),
            encoding="utf-8",
        )
        try:
            census.BASELINE = broken  # type: ignore[misc]
            errors = census._baseline_errors({"unsourced_by_document": {}})
        finally:
            census.BASELINE = original  # type: ignore[misc]

        assert any("internally inconsistent" in error for error in errors), errors

    def test_a_missing_baseline_is_not_a_pass(self, tmp_path: Path) -> None:
        """ "Nothing to compare against" and "it checked out" must not read the same."""
        original = census.BASELINE
        try:
            census.BASELINE = tmp_path / "absent.json"  # type: ignore[misc]
            errors = census._baseline_errors({"unsourced_by_document": {}})
        finally:
            census.BASELINE = original  # type: ignore[misc]

        assert errors, "an absent baseline reported no error, so the gate passes on a fresh clone"

    def test_the_committed_baseline_is_internally_consistent(self) -> None:
        payload = json.loads(census.BASELINE.read_text(encoding="utf-8"))

        assert payload["unsourced_total"] == sum(payload["unsourced_by_document"].values())
        assert payload["unsourced_total"] > 0, (
            "a zero baseline would make the ratchet vacuous; if coverage ever reaches total, "
            "replace the ratchet with an equality assertion deliberately"
        )
