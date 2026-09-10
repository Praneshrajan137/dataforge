"""The batch disposition is shared, and a surface cannot restate it.

These tests exist because of a defect that survived an existing parity gate. Three call
sites consumed the constitutional batch gate independently and disagreed: the engine held a
capped batch for review, the agent surface emptied its lists and routed the voided fixes
nowhere, and the warehouse surface did the same *and* passed no ``SafetyContext``, making
``confirm_escalations`` structurally unreachable there.

The reason it survived is the interesting part, and it dictates what is tested here: the
existing decision-table gate pins the **per-fix** auto-apply partition, and nothing pinned
the **batch-level** disposition. So the important test in this file is not a behavioural
one -- it is :func:`test_no_surface_calls_evaluate_batch_directly`, which fails if any
product module reintroduces its own call to
:meth:`~dataforge.safety.filter.SafetyFilter.evaluate_batch`. Behaviour tests show the
current surfaces agree today; that structural test is what keeps a *fourth* surface from
disagreeing tomorrow.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from dataforge.repairers.base import ProposedFix
from dataforge.safety.disposition import (
    BatchDispositionError,
    enforce_batch_disposition,
    evaluate_batch_disposition,
)
from dataforge.safety.filter import SafetyContext, SafetyFilter, SafetyVerdict
from dataforge.transactions.txn import CellFix

#: Modules that consume the batch gate. Kept as paths rather than imported symbols so the
#: structural test reads source, which is what a future divergence would live in.
_PRODUCT_ROOT = Path(__file__).resolve().parents[2] / "dataforge"

#: The one module allowed to call ``SafetyFilter.evaluate_batch``.
_DISPOSITION_MODULE = _PRODUCT_ROOT / "safety" / "disposition.py"


def _fixes(count: int, *, column: str = "City") -> list[ProposedFix]:
    """Return ``count`` distinct-cell proposals, all deterministic and provable."""
    return [
        ProposedFix(
            fix=CellFix(
                row=index,
                column=column,
                old_value="old",
                new_value="new",
                detector_id="fd_violation",
            ),
            reason="test fixture",
            confidence=1.0,
            provenance="deterministic",
        )
        for index in range(count)
    ]


def _budget() -> int:
    """Read the cell budget from source of truth rather than restating it."""
    from dataforge.safety.constitution import HIGH_VOLUME_CELL_BUDGET

    return HIGH_VOLUME_CELL_BUDGET


class TestDispositionInvariants:
    """Properties that must hold for every disposition, whatever the verdict."""

    def test_allowed_batch_applies_everything_and_holds_nothing(self) -> None:
        disposition = evaluate_batch_disposition(_fixes(_budget()))

        assert disposition.allowed
        assert disposition.verdict is SafetyVerdict.ALLOW
        assert len(disposition.applied) == _budget()
        assert disposition.held == ()
        assert disposition.held_reason is None
        assert disposition.required_confirm_flags == frozenset()

    def test_capped_batch_holds_everything_and_applies_nothing(self) -> None:
        over = _budget() + 1
        disposition = evaluate_batch_disposition(_fixes(over))

        assert not disposition.allowed
        assert disposition.verdict is SafetyVerdict.ESCALATE
        assert disposition.applied == ()
        assert len(disposition.held) == over
        assert disposition.held_reason == "safety_escalation"

    @pytest.mark.parametrize("count", [0, 1, 50, 100, 101, 250])
    def test_applied_and_held_partition_the_batch(self, count: int) -> None:
        """Union is the batch and intersection is empty, at every size.

        This is the property that makes losing a fix unrepresentable: a surface reporting
        both collections cannot silently drop one.
        """
        batch = _fixes(count)
        disposition = evaluate_batch_disposition(batch)

        assert len(disposition.applied) + len(disposition.held) == count
        applied_ids = {id(fix) for fix in disposition.applied}
        held_ids = {id(fix) for fix in disposition.held}
        assert applied_ids.isdisjoint(held_ids)
        assert applied_ids | held_ids == {id(fix) for fix in batch}

    def test_held_reason_is_set_exactly_when_the_batch_is_not_allowed(self) -> None:
        assert evaluate_batch_disposition(_fixes(1)).held_reason is None
        assert evaluate_batch_disposition(_fixes(_budget() + 1)).held_reason is not None


class TestRemedyIsDerived:
    """``required_confirm_flags`` must come from the constitution, never a literal."""

    def test_capped_batch_names_the_flag_that_would_clear_it(self) -> None:
        disposition = evaluate_batch_disposition(_fixes(_budget() + 1))

        assert disposition.rule_ids  # the gate names which rule fired
        assert disposition.required_confirm_flags == SafetyFilter().confirm_flags_for(
            disposition.rule_ids
        )
        assert disposition.required_confirm_flags

    def test_the_named_flag_actually_clears_the_batch(self) -> None:
        """The remedy is not merely reported, it works.

        A ``required_confirm_flags`` value that did not clear the gate would be worse than
        no field at all: a machine consumer would act on it and be refused again.
        """
        over = _fixes(_budget() + 1)
        refused = evaluate_batch_disposition(over)

        for flag in refused.required_confirm_flags:
            cleared = evaluate_batch_disposition(over, SafetyContext(**{flag: True}))
            assert cleared.allowed, f"{flag} was reported as the remedy but did not clear"

    def test_blanket_alias_also_clears_the_batch(self) -> None:
        """The deprecated ``confirm_escalations`` alias keeps its meaning."""
        over = _fixes(_budget() + 1)
        assert evaluate_batch_disposition(over, SafetyContext(confirm_escalations=True)).allowed


class TestPrimitiveBackstop:
    """``enforce_batch_disposition`` refuses what a surface should never have offered."""

    def test_raises_on_a_batch_the_gate_would_refuse(self) -> None:
        with pytest.raises(BatchDispositionError, match="did not clear"):
            enforce_batch_disposition(_fixes(_budget() + 1), None)

    def test_permits_a_confirmed_batch(self) -> None:
        enforce_batch_disposition(_fixes(_budget() + 1), SafetyContext(confirm_escalations=True))

    def test_permits_a_batch_within_budget(self) -> None:
        enforce_batch_disposition(_fixes(_budget()), None)

    def test_empty_batch_is_not_an_error(self) -> None:
        enforce_batch_disposition([], None)


class TestNoSurfaceRestatesTheDecision:
    """The structural guard. This is the test the old parity gate was missing."""

    def test_no_surface_calls_evaluate_batch_directly(self) -> None:
        """Only ``safety/disposition.py`` may call ``SafetyFilter.evaluate_batch``.

        A surface that calls it directly is free to invent its own answer for a non-ALLOW
        verdict, which is precisely how three call sites came to disagree. Reintroducing
        such a call fails here regardless of whether the reintroduced behaviour happens to
        match today's, because the *ability* to diverge is the defect.
        """
        offenders: list[str] = []
        for path in _PRODUCT_ROOT.rglob("*.py"):
            if path == _DISPOSITION_MODULE:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "evaluate_batch"
                ):
                    offenders.append(f"{path.relative_to(_PRODUCT_ROOT)}:{node.lineno}")

        assert not offenders, (
            "These modules call SafetyFilter.evaluate_batch directly instead of consuming "
            "evaluate_batch_disposition, and can therefore diverge on what a refused batch "
            f"means: {offenders}"
        )

    def test_warehouse_surface_passes_a_safety_context(self) -> None:
        """The warehouse call site must pass a context, not rely on the default.

        Structural because the defect was structural: ``confirm_escalations`` was a parameter
        of the enclosing function, was threaded into ``propose_repairs`` on the line above,
        and was simply not passed to the batch gate -- so the all-flags-false default looked
        deliberate and the product's only measured end-to-end result was unreachable here.
        """
        source = (_PRODUCT_ROOT / "stores" / "repair.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "evaluate_batch_disposition"
        ]
        assert calls, "the warehouse surface no longer evaluates the batch gate at all"
        for call in calls:
            passes_context = len(call.args) >= 2 or any(
                keyword.arg == "context" for keyword in call.keywords
            )
            assert passes_context, (
                f"stores/repair.py:{call.lineno} evaluates the batch gate without a "
                "SafetyContext, so no confirmation flag can ever reach it"
            )


class TestAgentSurfaceReportsHeldBatch:
    """The agent surface must return the fixes a capped batch withheld.

    The gate is forced rather than provoked with real data: making the deterministic
    repairer emit more than ``HIGH_VOLUME_CELL_BUDGET`` proposals requires a declared
    premise, and threading one here would test premise acquisition rather than the wiring
    this change touched. Forcing the disposition isolates the property under test -- that a
    non-ALLOW verdict reaches ``held_fixes`` instead of being dropped.
    """

    def test_batch_voided_fixes_reach_held_fixes(self, monkeypatch, tmp_path) -> None:
        from dataforge.agent import AgentRepairRequest
        from dataforge.agent import controller as controller_module
        from dataforge.safety.disposition import BatchDisposition

        source = tmp_path / "t.csv"
        source.write_text("ProviderID,City\n1,birmingham\n2,BIRMINGHAM\n", encoding="utf-8")

        withheld = _fixes(3, column="City")
        forced = BatchDisposition(
            verdict=SafetyVerdict.ESCALATE,
            reason="NO_HIGH_VOLUME_AUTO_APPLY: forced for test.",
            rule_ids=("NO_HIGH_VOLUME_AUTO_APPLY",),
            applied=(),
            held=tuple(withheld),
            held_reason="safety_escalation",
            required_confirm_flags=frozenset({"confirm_high_volume"}),
        )
        monkeypatch.setattr(
            controller_module,
            "evaluate_batch_disposition",
            lambda *args, **kwargs: forced,
        )

        result = controller_module.run_agent_repair(
            AgentRepairRequest(source_path=source, mode="dry_run", policy="deterministic")
        )

        assert result.safety_verdict == "escalate"
        assert result.fixes_count == 0, "a refused batch must still write nothing"
        assert len(result.held_fixes) >= len(withheld), (
            "batch-voided fixes were dropped instead of being returned in held_fixes -- "
            "this is the defect the shared disposition exists to prevent"
        )
        assert any(
            "NO_HIGH_VOLUME_AUTO_APPLY" in str(payload.verifier_reason)
            for payload in result.held_fixes
        ), "a held fix must carry the batch reason, not only the unproven reason"
