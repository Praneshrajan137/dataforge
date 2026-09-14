"""The claim gate must report its own coverage, not just its own success.

``docs_truth`` verifies every claim registered in ``docs/quantitative_claims.yaml`` and prints
"Verified N quantitative claims against artifacts". That sentence reads as a population. It is a
sample: the ledger is an **allowlist**, so a claim is policed only if somebody remembered to
register it.

This is not a hypothetical. ``DECISIONS.md:376`` records the project being bitten by exactly this:
"**zero** registered ``docs_truth`` claims, and that gate is an allowlist, so it could not see
the...". A gate whose population is enumerated cannot report what it is missing, and this one's
summary actively invites the reader to believe nothing is missing.

``docs_truth.py:29`` shows the same defect was already caught one level down and fixed: forty-six
claims once had an ``expect`` of two characters or fewer and six were "verifiable in name only",
so "Verified 46 quantitative claims" was itself an overclaim -- "the exact defect this file exists
to prevent, committed by the file that prevents it". That fix addressed claim **quality**. The
**population** half of the same overclaim survived it, and this test closes it.

Measured 2026-09-13 by an independent sweep: the ledger holds 144 claims while the documents carry
an estimated 200-250 quantitative and behavioural claims, so coverage is roughly 55-70%. The fix
asserted here is deliberately NOT a coverage threshold -- a fitted number would need a
pre-registered kill criterion and would invite gaming. What is asserted is **disclosure**: the
summary must state that the ledger is an allowlist, so no reader mistakes the sample for the whole.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GATE = _REPO_ROOT / "scripts" / "ci" / "docs_truth.py"
_LEDGER = _REPO_ROOT / "docs" / "quantitative_claims.yaml"


@pytest.fixture(scope="module")
def summary() -> str:
    """The gate's own passing summary line, captured from a real run."""
    result = subprocess.run(
        [sys.executable, str(_GATE), "--check"],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        timeout=300,
    )
    assert result.returncode == 0, (
        f"docs_truth must pass for this test to be meaningful:\n{result.stderr}"
    )
    return result.stdout


class TestTheGateDisclosesItsOwnPopulation:
    def test_the_summary_names_the_ledger_as_an_allowlist(self, summary: str) -> None:
        """The one assertion that matters: the reader must not mistake a sample for a census."""
        lowered = summary.lower()
        assert "allowlist" in lowered, (
            "the docs_truth summary does not disclose that its claim population is an allowlist. "
            f"It currently reads:\n  {summary.strip()}\n"
            "A reader takes that as 'all quantitative claims are verified'. The ledger is a "
            "registry someone must remember to update, so the gate cannot see -- and cannot "
            "report -- the claims nobody registered."
        )

    def test_the_summary_still_reports_the_verified_count(self, summary: str) -> None:
        """Non-vacuity: disclosure must not be bought by removing the useful number.

        Without this, deleting the count entirely would satisfy the assertion above while making
        the gate's output less informative than before.
        """
        registered = _LEDGER.read_text(encoding="utf-8").count("  - id:")
        assert registered > 0, "could not count registered claims -- the ledger format changed"
        assert str(registered) in summary, (
            f"the summary must still report how many claims were verified (expected "
            f"{registered} from the ledger). Summary:\n  {summary.strip()}"
        )

    def test_the_summary_keeps_the_context_split(self, summary: str) -> None:
        """The earlier fix must survive this one.

        The context/standalone split is how the previous overclaim was corrected: a claim pinned
        to a sentence is stronger evidence than one pinned to a bare token anywhere in a file.
        Regressing it while fixing the population half would trade one honesty defect for another.
        """
        assert "context" in summary.lower(), "the context/standalone split must be preserved"

    def test_the_ledger_is_actually_an_allowlist_not_a_derivation(self) -> None:
        """Pins the premise, so the disclosure cannot silently become false.

        If the ledger were ever derived from the documents rather than hand-registered, the
        disclosure above would be wrong and should be removed. That would be good news, and it
        should fail this test loudly rather than leave a stale warning in CI output.
        """
        gate_source = _GATE.read_text(encoding="utf-8")
        assert "yaml.safe_load(LEDGER" in gate_source, (
            "docs_truth no longer loads a hand-maintained YAML ledger. If claims are now derived "
            "from the documents, the allowlist disclosure is obsolete -- remove it and this test."
        )
