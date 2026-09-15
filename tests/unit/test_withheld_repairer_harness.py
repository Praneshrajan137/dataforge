"""Tests for the withheld-repairer harness extension.

Why this file exists, dated 2026-08-26. `scripts/bench/measure_bypass_allowlist.py` was extended to
score two repairers that are **unreachable through the product** -- absent from `build_repairers`'
deterministic registry -- so the harness constructs them directly. Two things about that extension
need pinning, because both could silently invalidate the published measurement.

1. The harness now memoises `FormatViolationRepairer._dominant_profile` so the tax arm (200,000 rows)
   is reachable at all: unmemoised it costs 632 ms per flag across 20,018 flags, which is 211
   minutes. A memo that changed even one proposal would make the published numbers fiction. The
   equivalence is verified here rather than argued in a comment.

2. Scoring a non-allowlist detector must not quietly widen what the *product* may write. The harness
   deliberately measures a superset of the allowlist; that superset must stay confined to the
   harness.

These are cheap tests guarding an expensive measurement. See
`docs/trust/withheld-repairer-result.md`.
"""

from __future__ import annotations

import pytest

from dataforge.detectors.format_violation import FormatViolationDetector
from dataforge.domain.vocabulary import CONSTRAINT_CHECKABLE_DETECTORS
from dataforge.repairers.format_violation import FormatViolationRepairer
from scripts.bench import measure_bypass_allowlist as harness

pytest.importorskip("pandas")
import pandas as pd  # noqa: E402


def _padding_frame() -> pd.DataFrame:
    """A column whose dominant shape is 5 digits, with two shorter legitimate values.

    This is the exact failure mode measured on all three corpora that produced writes: hospital's
    `index`, rayyan's `id` and tax's `salary` are all all-digit columns with legitimate width
    variation, and the leading-zero branch pads them.
    """
    return pd.DataFrame({"id": [f"{n:05d}" for n in range(10, 28)] + ["5000", "1"]})


class TestTheProfileMemoChangesNoProposal:
    """The memo is a speed change or the published numbers are fiction."""

    def test_memoised_and_direct_repairers_agree_cell_for_cell(self) -> None:
        """Compared proposal by proposal, not by count.

        A count comparison would pass if the memo swapped two proposals, which is exactly the kind
        of error a per-column cache could introduce on a multi-column frame.
        """
        frame = pd.DataFrame(
            {
                "id": [f"{n:05d}" for n in range(10, 28)] + ["5000", "1"],
                "code": [f"{n:03d}" for n in range(100, 118)] + ["7", "88"],
            }
        )
        issues = FormatViolationDetector().detect(frame, None)
        assert issues, "fixture must flag something or this test is vacuous"

        direct = FormatViolationRepairer()
        memoised = harness._ProfileMemoRepairer()

        for issue in issues:
            expected = direct.propose(issue, frame, None, None)
            actual = memoised.propose(issue, frame, None, None)
            if expected is None:
                assert actual is None, f"memo proposed where the repairer abstained: {issue.row}"
                continue
            assert actual is not None
            assert actual.fix.new_value == expected.fix.new_value
            assert actual.fix.row == expected.fix.row
            assert actual.fix.column == expected.fix.column

    def test_the_memo_restores_a_working_staticmethod(self) -> None:
        """The memo patches a staticmethod. Leaking it would corrupt every later measurement.

        Asserted BEHAVIOURALLY, and that distinction is the whole point of this test. The first
        version compared ``FormatViolationRepairer._dominant_profile is original`` and PASSED while
        the restoration was broken: accessing a staticmethod attribute yields the underlying
        function, so assigning it back produced an instance method whose next call received ``self``
        as its first argument. Identity held; the descriptor did not. Only calling it caught that.
        """
        frame = _padding_frame()
        issues = FormatViolationDetector().detect(frame, None)

        harness._ProfileMemoRepairer().propose(issues[0], frame, None, None)

        # Two positional arguments, via an instance, exactly as the repairer calls it internally.
        shape, examples = FormatViolationRepairer()._dominant_profile(frame, "id")
        assert shape == "99999"
        assert examples

    def test_the_memo_survives_an_exception(self) -> None:
        """Restoration is in a ``finally``; pinned because the leak would be invisible."""
        memoised = harness._ProfileMemoRepairer()

        with pytest.raises(Exception):  # noqa: B017 - any failure must still restore
            memoised.propose(None, None, None, None)  # type: ignore[arg-type]

        shape, _examples = FormatViolationRepairer()._dominant_profile(_padding_frame(), "id")
        assert shape == "99999"


class TestTheMeasuredMechanism:
    """The leading-zero branch, which produced 10,356 of 10,356 harmful writes."""

    def test_a_shorter_legitimate_number_is_padded(self) -> None:
        """The mechanism behind every write the measurement classified as corruption.

        Pinned as a unit test so the published finding does not depend on a corpus download. If this
        ever abstains instead, `docs/trust/withheld-repairer-result.md` is out of date and must be
        amended rather than this assertion edited.
        """
        frame = _padding_frame()
        issues = [i for i in FormatViolationDetector().detect(frame, None) if i.column == "id"]
        proposals = [
            p
            for p in (FormatViolationRepairer().propose(i, frame, None, None) for i in issues)
            if p is not None
        ]

        written = {p.fix.old_value: p.fix.new_value for p in proposals}
        assert written["5000"] == "05000"
        assert written["1"] == "00001"


class TestHarnessScopeDoesNotWidenProductScope:
    """Measuring a non-member must not make it a member."""

    @staticmethod
    def _registrable_repairer_keys() -> frozenset[str]:
        """Every key ``build_repairers`` can register, derived by AST.

        Static rather than by calling it with every flag on, because ``allow_llm=True``
        constructs an ``LLMCorrectorRepairer`` and a unit test must not depend on that being
        constructible. Reads the dict literal's keys and every ``registry[...] = `` assignment.
        """
        import ast
        import inspect
        import textwrap

        from dataforge.repairers import build_repairers

        tree = ast.parse(textwrap.dedent(inspect.getsource(build_repairers)))
        keys: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key in node.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        keys.add(key.value)
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
                value = node.slice.value
                if isinstance(value, str):
                    keys.add(value)
        return frozenset(keys)

    def test_the_measurable_scope_is_total_over_registrable_repairers(self) -> None:
        """Every repairer the product can register is measured or excluded WITH A REASON.

        This replaces a pair of lower-bound assertions (``CONSTRAINT_CHECKABLE_DETECTORS <
        measurable`` plus two named members) that structurally could not see a missing member.
        Three were missing: ``decimal_shift``, ``entity_consensus`` and ``outlier``. `CLAUDE.md`
        names this harness as what replaces the retired 0.7926 headline, so an unseen hole in its
        population is a hole in the evidence that replaced a headline.

        The shape is the one `PRODUCT.md` 1.3 asks for and that
        ``ENFORCEABLE_CONSTRAINT_KINDS`` uses: enumerate the artifact, and give the remainder a
        name and a reason rather than letting it be absence.
        """
        registrable = self._registrable_repairer_keys()
        measured = set(harness.MEASURABLE_DETECTORS)
        excluded = set(harness.UNMEASURED_DETECTORS)

        assert len(registrable) >= 8, (
            f"only {len(registrable)} registrable repairer keys parsed from build_repairers; the "
            "AST derivation has stopped working and this assertion is now vacuous"
        )
        unaccounted = registrable - measured - excluded
        assert unaccounted == set(), (
            f"repairer(s) {sorted(unaccounted)} can be registered by build_repairers but are "
            "neither measured by this harness nor listed in UNMEASURED_DETECTORS with a reason. "
            "A repairer that is silently unmeasured is a write path with no committed figure."
        )
        assert measured & excluded == set(), (
            f"{sorted(measured & excluded)} is both measured and excluded; the scope is incoherent"
        )

    def test_every_exclusion_states_a_reason(self) -> None:
        """An exemption without a reason is an exemption nobody can review."""
        for name, reason in harness.UNMEASURED_DETECTORS.items():
            assert len(reason.strip()) >= 80, f"{name} has no substantive reason recorded"

    def test_the_measurable_set_is_a_strict_superset_of_the_allowlist(self) -> None:
        """Non-vacuity for the measurement: it must reach detectors the product cannot.

        Kept alongside the totality test above, not replaced by it: totality would be satisfied by
        excluding everything, and this is what forbids that.
        """
        measurable = set(harness.MEASURABLE_DETECTORS)

        assert set(CONSTRAINT_CHECKABLE_DETECTORS) < measurable
        assert {"format_violation", "categorical_normalization"} <= measurable

    def test_the_two_measured_repairers_gained_no_write_authority(self) -> None:
        """The pre-committed outcome, asserted so it cannot drift.

        `eval/preregistration/withheld_repairer_coverage.md` pre-committed that neither repairer
        enters the allowlist in the session that measured them, even if no kill criterion fires --
        and `categorical_normalization` did pass both. Passing a REMOVAL criterion is not earning
        admission, and 38% of its writes are harmful.
        """
        assert "format_violation" not in CONSTRAINT_CHECKABLE_DETECTORS
        assert "categorical_normalization" not in CONSTRAINT_CHECKABLE_DETECTORS

    def test_neither_repairer_is_in_the_deterministic_registry(self) -> None:
        """The second, independent mechanism holding them: they cannot even propose.

        Asserted separately from the allowlist because the two are different acts. Proposing for
        review is much weaker than writing unsupervised without a threshold, and conflating them is
        how a measurement becomes a permission.
        """
        from dataforge.repairers import build_repairers

        registry = build_repairers(cache_dir=None, allow_llm=False)

        assert "format_violation" not in registry
        assert "categorical_normalization" not in registry
