"""One batch disposition, shared by every write surface.

Until 2026-09-09 the batch safety gate was consumed independently by three call sites and
they did not agree. ``dataforge/engine/repair.py`` held a capped batch in a review queue
with a structured ``ReviewReason``; ``dataforge/agent/controller.py`` emptied its fix lists
and routed the voided fixes **nowhere**; and ``dataforge/stores/repair.py`` did the same
*and* passed no :class:`SafetyContext` at all, so
:meth:`~dataforge.safety.filter.SafetyFilter.evaluate_batch` fell back to a default context
with every flag false -- making ``confirm_escalations`` structurally unreachable on the
warehouse surface even though the caller had it in scope.

That is the shape ``PRODUCT.md`` section 8 forbids -- *"No surface may create parallel write
semantics"* -- and the reason it survived is instructive: the existing parity gate pins the
**per-fix** auto-apply partition, and nothing pinned the **batch-level** disposition. A gate
one level below the defect cannot see it.

The fix follows the pattern this codebase already proved with ``enforce_proven_only`` and
``enforce_constraint_checkable_only``: put the decision somewhere a caller cannot restate it.
:func:`evaluate_batch_disposition` is the *only* place that decides what a non-``ALLOW``
verdict does to a batch, so a surface can no longer invent its own answer -- it consumes
:class:`BatchDisposition` or it does not participate.

**Why this is not inside the write primitive**, which an earlier draft of the plan proposed:
``apply_transaction`` runs only in ``mode == "apply"``, while the batch gate must also run on
a dry run -- reporting what *would* be refused is a dry run's entire purpose. Moving the gate
into the primitive would have silently deleted dry-run reporting, and would have changed the
primitive's contract from *raise on violation* to *return a refusal*. So the shared decision
lives here, and the primitive keeps a raising backstop
(:func:`enforce_batch_disposition`) for a surface that forgets to ask.

Two properties are deliberate:

* **The write set is unchanged.** A non-``ALLOW`` verdict still yields an empty ``applied``
  tuple, exactly as all three surfaces already behaved. This module changes what is
  *reported*, never what is *written*; a change to write authority would need its own
  evidence and its own pre-registration.
* **The remedy is derived, not restated.** ``required_confirm_flags`` comes from
  :meth:`~dataforge.safety.filter.SafetyFilter.confirm_flags_for`, which reads the compiled
  constitution. Hardcoding the flag for a rule is the frozen-population defect
  ``PRODUCT.md`` section 1.3 records twice, and it is precisely the kind of literal that is
  correct on the day it is written.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from dataforge.domain.vocabulary import NextAction, OutcomeCode, ReviewReason
from dataforge.repairers.base import ProposedFix
from dataforge.safety.filter import (
    SafetyContext,
    SafetyFilter,
    SafetyResult,
    SafetyVerdict,
)

#: Schema version for the machine-readable outcome envelope.
MACHINE_OUTCOME_SCHEMA_VERSION: Final[str] = "machine_outcome_v1"

#: Review reason recorded for a batch the constitution refuses outright.
HELD_REASON_DENIED: Final[ReviewReason] = "safety_denied"

#: Review reason recorded for a batch the constitution escalates for confirmation.
HELD_REASON_ESCALATED: Final[ReviewReason] = "safety_escalation"


@dataclass(frozen=True)
class BatchDisposition:
    """What a surface must do with a batch after the constitutional batch gate.

    ``applied`` and ``held`` are always populated coherently: their union is the batch that
    was evaluated and their intersection is empty. A surface that reports ``len(applied)``
    without also surfacing ``held`` loses the fixes a capped batch withheld, which is the
    defect this type exists to make unrepresentable.
    """

    verdict: SafetyVerdict
    reason: str
    rule_ids: tuple[str, ...]
    applied: tuple[ProposedFix, ...]
    held: tuple[ProposedFix, ...]
    held_reason: ReviewReason | None
    required_confirm_flags: frozenset[str]

    @property
    def allowed(self) -> bool:
        """Return whether the batch cleared the gate and may proceed to a write."""
        return self.verdict is SafetyVerdict.ALLOW


class BatchDispositionError(RuntimeError):
    """Raised when a write primitive is handed a batch the constitution would refuse.

    A backstop, not the primary gate. Surfaces consume :class:`BatchDisposition` and should
    never offer a held batch to a write primitive; if one does, failing here converts a
    silent corrupting write into a loud refusal. It mirrors
    :func:`~dataforge.engine.repair.enforce_constraint_checkable_only`, which exists for the
    same reason and should likewise be unreachable from a correct caller.
    """


def evaluate_batch_disposition(
    fixes: list[ProposedFix],
    context: SafetyContext | None = None,
    *,
    safety_filter: SafetyFilter | None = None,
) -> BatchDisposition:
    """Evaluate the batch gate and return the single authoritative disposition.

    ``context`` is optional only to match
    :meth:`~dataforge.safety.filter.SafetyFilter.evaluate_batch`; every shipped surface
    passes one, and ``None`` means *no confirmation flag is set*, which is the restrictive
    direction.

    ``safety_filter`` is injectable so a caller that already built one -- or a test that
    needs a specific constitution -- does not pay to recompile it.
    """
    active_filter = safety_filter if safety_filter is not None else SafetyFilter()
    effective_context = context if context is not None else SafetyContext()
    result: SafetyResult = active_filter.evaluate_batch(fixes, effective_context)

    if result.verdict is SafetyVerdict.ALLOW:
        return BatchDisposition(
            verdict=result.verdict,
            reason=result.reason,
            rule_ids=tuple(result.rule_ids),
            applied=tuple(fixes),
            held=(),
            held_reason=None,
            required_confirm_flags=frozenset(),
        )

    held_reason: ReviewReason = (
        HELD_REASON_DENIED if result.verdict is SafetyVerdict.DENY else HELD_REASON_ESCALATED
    )
    return BatchDisposition(
        verdict=result.verdict,
        reason=result.reason,
        rule_ids=tuple(result.rule_ids),
        applied=(),
        held=tuple(fixes),
        held_reason=held_reason,
        # Derived from the compiled constitution, never restated here.
        required_confirm_flags=active_filter.confirm_flags_for(result.rule_ids),
    )


def enforce_batch_disposition(
    fixes: list[ProposedFix],
    context: SafetyContext | None,
    *,
    safety_filter: SafetyFilter | None = None,
) -> None:
    """Raise if ``fixes`` would not clear the batch gate under ``context``.

    Called by the write primitive so a surface that forgets the gate cannot write anyway.
    ``context`` is a required argument -- even though ``None`` is accepted to mean "no flags
    set" -- because silently defaulting it is exactly the defect that made
    ``confirm_escalations`` unreachable on the warehouse surface: a caller that *had* the flag
    in scope simply did not pass it, and the omission looked deliberate.
    """
    if not fixes:
        return
    disposition = evaluate_batch_disposition(fixes, context, safety_filter=safety_filter)
    if not disposition.allowed:
        raise BatchDispositionError(
            f"Refusing to write a batch the safety constitution did not clear. {disposition.reason}"
        )


@dataclass(frozen=True)
class MachineOutcome:
    """Machine-readable outcome for any non-interactive surface (MCP, warehouse, CLI --json).

    Every field is drawn from a closed vocabulary so a pipeline consumer can branch
    programmatically without parsing prose.  The prose ``reason`` is preserved for
    human-readable logs but is explicitly NOT part of the contract.

    ``schema_version`` is the versioning hook: a consumer that does not recognise
    the version string must refuse rather than guess, exactly as a verifier does
    with an unknown ``VerificationStrength``.
    """

    schema_version: str
    outcome_code: OutcomeCode
    next_actions: tuple[NextAction, ...]
    held_count: int
    reason: str

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-safe dict for embedding in receipts."""
        return {
            "schema_version": self.schema_version,
            "outcome_code": self.outcome_code,
            "next_actions": list(self.next_actions),
            "held_count": self.held_count,
            "reason": self.reason,
        }


def _next_actions_for_escalation(
    disposition: BatchDisposition,
) -> tuple[NextAction, ...]:
    """Derive next-actions from a non-ALLOW disposition.

    Derived from ``required_confirm_flags``, which comes from the compiled constitution, so a
    new confirm flag added to a batch rule produces a next-action without editing this
    function.

    **Corrected on introduction.** The first version tested
    ``"confirm_escalations" in disposition.required_confirm_flags``, which is *always false*:
    :meth:`~dataforge.safety.filter.SafetyFilter.confirm_flags_for` returns the SPECIFIC rule
    flags -- ``confirm_high_volume`` for the cell budget -- and never the deprecated blanket
    alias. So ``needs_confirm_escalations`` was unreachable and every refused batch reported
    only ``needs_review``: a machine consumer was told to escalate to a human when a flag it
    could set itself would have cleared the gate. That is the frozen-population defect
    ``PRODUCT.md`` section 1.3 records -- a literal that looks like a derivation. The
    condition is now "the constitution named a flag that would clear this", whatever that
    flag is called.
    """
    actions: list[NextAction] = []
    if disposition.required_confirm_flags:
        actions.append("needs_confirm_escalations")
    if len(disposition.held) > 1:
        actions.append("retry_smaller_batch")
    if not actions:
        actions.append("needs_review")
    return tuple(actions)


def outcome_for_batch(
    disposition: BatchDisposition,
    *,
    issues_count: int = 0,
    fixes_count: int = 0,
) -> MachineOutcome:
    """Derive a :class:`MachineOutcome` from a batch disposition and run counters.

    This is the SINGLE derivation point: every surface (CLI, agent, warehouse, MCP)
    calls this rather than building its own outcome, just as every surface calls
    :func:`evaluate_batch_disposition` rather than calling ``evaluate_batch`` directly.
    """
    if disposition.allowed and fixes_count > 0:
        return MachineOutcome(
            schema_version=MACHINE_OUTCOME_SCHEMA_VERSION,
            outcome_code="repairs_applied",
            next_actions=("none",),
            held_count=0,
            reason=disposition.reason,
        )

    if issues_count == 0:
        return MachineOutcome(
            schema_version=MACHINE_OUTCOME_SCHEMA_VERSION,
            outcome_code="clean",
            next_actions=("none",),
            held_count=0,
            reason=disposition.reason,
        )

    if disposition.allowed and fixes_count == 0:
        if len(disposition.held) > 0:
            return MachineOutcome(
                schema_version=MACHINE_OUTCOME_SCHEMA_VERSION,
                outcome_code="all_fixes_held",
                next_actions=("needs_review",),
                held_count=len(disposition.held),
                reason=disposition.reason,
            )
        return MachineOutcome(
            schema_version=MACHINE_OUTCOME_SCHEMA_VERSION,
            outcome_code="no_repairable_errors",
            next_actions=("needs_declared_premise",),
            held_count=0,
            reason=disposition.reason,
        )

    # Non-ALLOW verdict: batch was refused by the constitution.
    # Compared by identity against the enum member. The first version tested
    # ``disposition.verdict == "deny"`` against a string, which mypy flagged as a
    # non-overlapping comparison: it was always False, so `batch_safety_denied` was
    # unreachable and a hard denial was reported to callers as a soft escalation.
    if disposition.verdict is SafetyVerdict.DENY:
        return MachineOutcome(
            schema_version=MACHINE_OUTCOME_SCHEMA_VERSION,
            outcome_code="batch_safety_denied",
            next_actions=_next_actions_for_escalation(disposition),
            held_count=len(disposition.held),
            reason=disposition.reason,
        )

    # escalate
    return MachineOutcome(
        schema_version=MACHINE_OUTCOME_SCHEMA_VERSION,
        outcome_code="batch_safety_escalated",
        next_actions=_next_actions_for_escalation(disposition),
        held_count=len(disposition.held),
        reason=disposition.reason,
    )


def outcome_for_run(
    *,
    issues_count: int,
    fixes_count: int,
    held_count: int,
    safety_verdict: str,
    reason: str,
    required_confirm_flags: frozenset[str] = frozenset(),
) -> MachineOutcome:
    """Derive a :class:`MachineOutcome` from aggregate run statistics.

    Used by surfaces (agent, warehouse) that accumulate multiple batch dispositions
    and report a single run-level outcome.
    """
    if fixes_count > 0:
        code: OutcomeCode = "repairs_applied"
        actions: tuple[NextAction, ...] = ("none",)
    elif issues_count == 0:
        code = "clean"
        actions = ("none",)
    elif held_count > 0 and safety_verdict in ("escalate", "deny"):
        code = "batch_safety_denied" if safety_verdict == "deny" else "batch_safety_escalated"
        action_list: list[NextAction] = []
        if "confirm_escalations" in required_confirm_flags:
            action_list.append("needs_confirm_escalations")
        if held_count > 1:
            action_list.append("retry_smaller_batch")
        if not action_list:
            action_list.append("needs_review")
        actions = tuple(action_list)
    elif held_count > 0:
        code = "all_fixes_held"
        actions = ("needs_review",)
    else:
        code = "no_repairable_errors"
        actions = ("needs_declared_premise",)

    return MachineOutcome(
        schema_version=MACHINE_OUTCOME_SCHEMA_VERSION,
        outcome_code=code,
        next_actions=actions,
        held_count=held_count,
        reason=reason,
    )
