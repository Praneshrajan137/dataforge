"""Batch-disposition parity gate: every surface agrees on what a refused batch means.

This gate exists because the F1 defect survived an existing parity gate. The existing
``test_autoapply_decision_table`` and non-regression gate pin the **per-fix** auto-apply
partition, but nothing pinned the **batch-level** disposition -- so three surfaces invented
three different answers for a capped batch and the suite was green. A gate one level below
the defect cannot see it.

Properties enforced, each with demonstrated failure evidence:

1. **Structural (bidirectional registry)**: every call site of
   ``evaluate_batch_disposition`` is registered here, and every registry entry still has a
   live call site. An unregistered consumer can invent its own interpretation of the
   disposition, which is the defect this gate exists to prevent.

2. **Behavioral (cross-surface parity)**: when given a capped batch, every registered
   surface reports the verdict, produces a non-empty held set, and writes nothing.
   Parametrised over surfaces so adding a surface inherits the requirement.

3. **Mutation evidence (planted divergence)**: a per-surface divergence that silently drops
   held fixes -- the exact pre-W1 agent behavior -- makes the parity assertion fire. Per
   ``PRODUCT.md`` section 1.3: a gate nobody has seen fail on a case it newly covers has
   not been shown to cover it.

The surface list is DERIVED from source (AST scan for calls to
``evaluate_batch_disposition``), not hardcoded, following the write-primitive registry
pattern from ``tests/integration/test_surface_uniformity.py``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from dataforge.repairers.base import ProposedFix
from dataforge.safety.disposition import BatchDisposition
from dataforge.safety.filter import SafetyVerdict
from dataforge.transactions.txn import CellFix

# ── Constants ──────────────────────────────────────────────────────────────────
_PRODUCT_ROOT = Path(__file__).resolve().parents[2] / "dataforge"
_DISPOSITION_MODULE = _PRODUCT_ROOT / "safety" / "disposition.py"


# ── Batch-disposition consumer registry ────────────────────────────────────────
#
# Keyed by MODULE, not by surface function, because the AST scan finds call sites
# in source files. The same module may contain more than one call site (engine/repair.py
# has two: run_repair_pipeline and verify_and_apply); that is fine -- the property under
# test is that every module CONSUMING the disposition does so uniformly, and the
# disposition type's immutability ensures that within a module.


@dataclass(frozen=True)
class BatchDispositionConsumer:
    """One registered module that calls ``evaluate_batch_disposition``."""

    module: str  # relative to _PRODUCT_ROOT, e.g. "engine/repair.py"
    note: str


_BATCH_DISPOSITION_CONSUMERS: tuple[BatchDispositionConsumer, ...] = (
    BatchDispositionConsumer(
        "engine/repair.py",
        "Pipeline (run_repair_pipeline) and external-fix (verify_and_apply) paths.",
    ),
    BatchDispositionConsumer(
        "agent/controller.py",
        "Verified agent repair (run_agent_repair).",
    ),
    BatchDispositionConsumer(
        "stores/repair.py",
        "Warehouse/table-store repair (run_table_store_repair).",
    ),
)


def _discover_disposition_consumers() -> dict[str, list[int]]:
    """AST-scan ``dataforge/`` for call sites of ``evaluate_batch_disposition``.

    Returns ``{relative_module_path: [line_numbers]}``. The disposition module
    itself is excluded -- it DEFINES the function; calling it there is not a
    consumer.
    """
    consumers: dict[str, list[int]] = {}
    for path in _PRODUCT_ROOT.rglob("*.py"):
        if path == _DISPOSITION_MODULE:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "evaluate_batch_disposition"
            ):
                rel = path.relative_to(_PRODUCT_ROOT).as_posix()
                consumers.setdefault(rel, []).append(node.lineno)
    return consumers


# ── Forced disposition for behavioral tests ────────────────────────────────────


def _fixes(count: int, *, column: str = "city") -> list[ProposedFix]:
    return [
        ProposedFix(
            fix=CellFix(
                row=i,
                column=column,
                old_value="old",
                new_value="new",
                detector_id="fd_violation",
            ),
            reason="parity gate fixture",
            confidence=1.0,
            provenance="deterministic",
        )
        for i in range(count)
    ]


def _forced_escalated_disposition(count: int = 5) -> BatchDisposition:
    """A capped batch that the constitution would refuse."""
    withheld = _fixes(count)
    return BatchDisposition(
        verdict=SafetyVerdict.ESCALATE,
        reason="NO_HIGH_VOLUME_AUTO_APPLY: forced for parity gate test.",
        rule_ids=("NO_HIGH_VOLUME_AUTO_APPLY",),
        applied=(),
        held=tuple(withheld),
        held_reason="safety_escalation",
        required_confirm_flags=frozenset({"confirm_high_volume"}),
    )


# ── Parity assertion (the gate itself) ────────────────────────────────────────
#
# This is the shared assertion that every behavioral test invokes. A planted
# divergence test calls it on a divergent result and shows it fires.


def _assert_batch_parity(
    *,
    surface_name: str,
    safety_verdict: str,
    held_count: int,
    applied_count: int,
) -> None:
    """Assert a surface's output is consistent with an escalated batch disposition.

    Three properties must hold on EVERY surface when the batch gate escalates:

    1. The verdict is forwarded (not swallowed or defaulted to "allow").
    2. The held set is non-empty (voided fixes are surfaced, not dropped).
    3. No write happens (applied count is zero).

    Calling this function IS the gate. The behavioral tests call it on each
    surface's real output; the planted-divergence test calls it on a divergent
    output and shows it fires.
    """
    assert safety_verdict == "escalate", (
        f"{surface_name}: reported verdict {safety_verdict!r} instead of 'escalate' -- "
        "the batch disposition verdict is not forwarded to the caller"
    )
    assert held_count > 0, (
        f"{surface_name}: held_count is 0 for a capped batch -- "
        "batch-voided fixes were silently dropped instead of being surfaced. "
        "This is the exact defect the shared BatchDisposition exists to prevent."
    )
    assert applied_count == 0, (
        f"{surface_name}: applied {applied_count} fix(es) despite a refused batch -- "
        "a capped batch must write nothing"
    )


# ── 1. Structural tests (bidirectional registry) ─────────────────────────────


class TestBatchDispositionConsumerRegistry:
    """The consumer list is derived from source and must be bidirectionally sound."""

    def test_no_unregistered_consumers(self) -> None:
        """Every module calling ``evaluate_batch_disposition`` must be registered."""
        found = _discover_disposition_consumers()
        registered_modules = {c.module for c in _BATCH_DISPOSITION_CONSUMERS}
        unregistered = sorted(found.keys() - registered_modules)
        assert not unregistered, (
            "Unregistered batch-disposition consumer(s): "
            + "; ".join(f"{mod} at lines {found[mod]}" for mod in unregistered)
            + ". Every module that calls evaluate_batch_disposition must be registered "
            "in _BATCH_DISPOSITION_CONSUMERS so the parity gate covers it."
        )

    def test_no_stale_registry_entries(self) -> None:
        """A registry entry with no live call site must be deleted."""
        found = _discover_disposition_consumers()
        registered_modules = {c.module for c in _BATCH_DISPOSITION_CONSUMERS}
        stale = sorted(registered_modules - found.keys())
        assert not stale, (
            f"Stale batch-disposition registry entries (no live call site): {stale}. "
            "Delete them; a stale entry hides a missing gate."
        )


# ── 2. Behavioral parity tests (parametrised over surfaces) ──────────────────


class TestBatchDispositionBehavioralParity:
    """Every surface reports the same structured outcome for a capped batch.

    The forced disposition is injected via monkeypatch so the test isolates the
    SURFACE WIRING, not the detector or the safety filter. Whether the filter
    fires correctly is tested in ``test_batch_disposition.py``; this file tests
    that each surface forwards the result faithfully.
    """

    def test_pipeline_surface(self, monkeypatch, tmp_path) -> None:
        from dataforge.engine import repair as repair_module
        from dataforge.engine.repair import RepairPipelineRequest, run_repair_pipeline
        from tests.support.tables import build_premised_repairable_table

        table = build_premised_repairable_table(tmp_path / "t.csv")
        forced = _forced_escalated_disposition()
        monkeypatch.setattr(repair_module, "evaluate_batch_disposition", lambda *a, **kw: forced)

        result = run_repair_pipeline(
            RepairPipelineRequest(source_path=table.csv_path, mode="dry_run", schema=table.schema)
        )
        # Pipeline exposes verdict on receipt.safety_verdict, held fixes in
        # receipt.suggested_fixes (with review_reason "safety_escalation"), and
        # applied count as receipt.fixes_count.
        batch_held = [
            s for s in result.receipt.suggested_fixes if s.review_reason == "safety_escalation"
        ]
        _assert_batch_parity(
            surface_name="pipeline (run_repair_pipeline)",
            safety_verdict=result.receipt.safety_verdict,
            held_count=len(batch_held),
            applied_count=result.receipt.fixes_count,
        )

    def test_agent_surface(self, monkeypatch, tmp_path) -> None:
        from dataforge.agent import AgentRepairRequest
        from dataforge.agent import controller as controller_module

        source = tmp_path / "t.csv"
        source.write_text("ProviderID,City\n1,birmingham\n2,BIRMINGHAM\n", encoding="utf-8")
        forced = _forced_escalated_disposition()
        monkeypatch.setattr(
            controller_module, "evaluate_batch_disposition", lambda *a, **kw: forced
        )

        result = controller_module.run_agent_repair(
            AgentRepairRequest(source_path=source, mode="dry_run", policy="deterministic")
        )
        _assert_batch_parity(
            surface_name="agent (run_agent_repair)",
            safety_verdict=result.safety_verdict,
            held_count=len(result.held_fixes),
            applied_count=result.fixes_count,
        )

    def test_warehouse_surface(self, monkeypatch, tmp_path) -> None:
        from dataforge.stores import repair as stores_repair_module
        from dataforge.stores.csv import CSVStore
        from dataforge.stores.repair import run_table_store_repair
        from tests.support.tables import build_premised_repairable_table

        table = build_premised_repairable_table(tmp_path / "t.csv")
        store = CSVStore(table.csv_path)
        forced = _forced_escalated_disposition()
        monkeypatch.setattr(
            stores_repair_module,
            "evaluate_batch_disposition",
            lambda *a, **kw: forced,
        )

        result = run_table_store_repair(store, mode="dry_run", schema=table.schema)
        _assert_batch_parity(
            surface_name="warehouse (run_table_store_repair)",
            safety_verdict=result.patch_plan.safety_verdict,
            held_count=len(result.held_fixes),
            applied_count=len(result.fixes),
        )


# ── 3. Planted divergence (mutation evidence) ────────────────────────────────


class TestPlantedDivergence:
    """Demonstrate the parity assertion catches the pre-W1 defect pattern.

    Pre-W1, the agent surface received a non-ALLOW verdict and responded by
    emptying ``all_fixes``, ``agent_fixes``, and ``floor_fixes`` -- then routed
    the voided fixes **nowhere**. The MCP caller saw ``fixes_count=0`` alongside
    an empty held set, with the cause only in ``receipt.reason`` (which no
    harness read). The warehouse surface did the same AND passed no
    ``SafetyContext``, so ``confirm_escalations`` was structurally unreachable.

    This test does NOT revert W1. It constructs a result object that exhibits the
    pre-W1 symptom and shows the parity assertion fires on it.
    """

    def test_dropped_held_fixes_detected(self) -> None:
        """Verdict forwarded but held set empty -- the pre-W1 agent pattern."""
        with pytest.raises(AssertionError, match="silently dropped"):
            _assert_batch_parity(
                surface_name="agent (planted divergence)",
                safety_verdict="escalate",
                held_count=0,
                applied_count=0,
            )

    def test_swallowed_verdict_detected(self) -> None:
        """Verdict defaulted to 'allow' instead of forwarding 'escalate'."""
        with pytest.raises(AssertionError, match="not forwarded"):
            _assert_batch_parity(
                surface_name="agent (planted divergence)",
                safety_verdict="allow",
                held_count=3,
                applied_count=0,
            )

    def test_write_despite_refusal_detected(self) -> None:
        """Surface applied fixes despite a non-ALLOW verdict."""
        with pytest.raises(AssertionError, match="refused batch"):
            _assert_batch_parity(
                surface_name="agent (planted divergence)",
                safety_verdict="escalate",
                held_count=3,
                applied_count=5,
            )

    def test_all_three_violations_present_in_pre_w1_agent(self) -> None:
        """The pre-W1 agent surface exhibited exactly one of the three violations.

        Its verdict WAS forwarded (via ``safety_verdict``), and its applied count
        WAS zero. But its held set was empty -- so the gate catches it on the
        held-count assertion specifically. This confirms the gate covers the EXACT
        failure mode, not just a plausible variant.
        """
        # The pre-W1 agent surface: verdict correct, writes zero, held empty.
        # Exactly one of the three parity assertions fires.
        try:
            _assert_batch_parity(
                surface_name="agent (pre-W1 simulation)",
                safety_verdict="escalate",
                held_count=0,
                applied_count=0,
            )
            raise RuntimeError(
                "BUG IN THE GATE: the pre-W1 agent pattern passed all parity "
                "assertions. This gate does not cover the defect it was built for."
            )
        except AssertionError as e:
            # The assertion must fire on the held-count check specifically.
            assert "silently dropped" in str(e), (
                f"The assertion fired but on the wrong check: {e}. "
                "The pre-W1 defect is about dropped held fixes, not verdict or writes."
            )
