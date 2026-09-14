"""Human rendering for the machine outcome a run already computes.

**Why this module exists, with the measurement.** Every repair run has produced a
``machine_outcome`` on its receipt since the ``MachineOutcome`` contract landed
(``dataforge.safety.disposition.outcome_for_batch`` is the single derivation point, and
``engine/repair.py`` records the result on the receipt). Human-readable English for every
member of both vocabularies has existed just as long, in
``dataforge.domain.vocabulary.OUTCOME_CODE_HUMAN`` and ``NEXT_ACTION_HUMAN``.

Nothing rendered either one. A grep for ``OUTCOME_CODE_HUMAN`` across ``dataforge/``,
``tests/`` and ``playground/`` returned **no consumers**, and
``scripts/ci/generate_domain_vocabulary.py`` says so explicitly: the labels are "withheld
for the same reason: no browser consumer renders them yet".

That is the defect ``PRODUCT.md`` §1.3 names -- *"Before hardening a component, name its
consumer. If nothing reads it, rigour there buys correctness of a report, not of the
product. The check is one grep for the type name."* -- and §10 records what the project
decided the remedy is: **reallocation, not disclosure.** Knowing an output is unconsumed
and leaving it unconsumed is the pattern that got the training subsystem excised.

The user-visible consequence was measured on 2026-09-12, against a schema-less CSV with
three detected issues:

* the JSON surface reported ``next_actions = ["needs_declared_premise"]`` and
  ``outcome_code = "no_repairable_errors"``;
* the human surface printed ``No fixes proposed.`` and never used the word *schema*.

So the product computed the exact remedy the operator needed and handed it only to
machines. ``PRODUCT.md`` §1.5 claims a user gets "detection, a named refusal reason, and a
one-line way to authorise the writes deliberately"; on the human CLI the reason was
suppressed by an equality check and the one-line authorisation was never printed. This
module is what makes that sentence true.

**Derived, not restated.** ``vocabulary.py`` instructs every consumer to derive the
population via ``get_args()`` rather than hardcode it, because a frozen literal is the
defect §1.3 records twice. This module derives both populations, and
``tests/unit/test_outcome_render.py`` fails if any vocabulary member lacks human text --
so adding a code without its label breaks CI rather than silently rendering nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, get_args

from rich.panel import Panel

from dataforge.domain.vocabulary import (
    NEXT_ACTION_HUMAN,
    OUTCOME_CODE_HUMAN,
    NextAction,
    OutcomeCode,
)
from dataforge.ui.trust_vocab import humanize_review_reason

if TYPE_CHECKING:
    from rich.console import Console

#: Every outcome code the vocabulary declares, derived from the Literal.
KNOWN_OUTCOME_CODES: Final[frozenset[str]] = frozenset(get_args(OutcomeCode))

#: Every next-action the vocabulary declares, derived from the Literal.
KNOWN_NEXT_ACTIONS: Final[frozenset[str]] = frozenset(get_args(NextAction))

#: Actions that carry no instruction, so rendering them as guidance would be noise.
_SILENT_ACTIONS: Final[frozenset[str]] = frozenset({"none"})


def _describe_outcome(code: object) -> str:
    """Return human text for one outcome code.

    An unrecognised code is reported verbatim rather than dropped. A renderer must not
    crash a run that already succeeded, but it must also not silently swallow a code it
    does not know -- that would reproduce the frozen-population defect at display time.
    Completeness is enforced by test, which is where a missing label should fail.
    """
    if not isinstance(code, str) or code not in KNOWN_OUTCOME_CODES:
        return f"Unrecognised outcome code {code!r} (this is a DataForge defect; please report it)."
    return OUTCOME_CODE_HUMAN.get(code, f"Outcome {code} has no human description.")


def _describe_action(action: object) -> str:
    """Return human guidance for one next-action, or the empty string to omit it."""
    if not isinstance(action, str) or action not in KNOWN_NEXT_ACTIONS:
        return (
            f"Unrecognised next action {action!r} (this is a DataForge defect; please report it)."
        )
    if action in _SILENT_ACTIONS:
        return ""
    return NEXT_ACTION_HUMAN.get(action, f"Next action {action} has no human description.")


def outcome_lines(machine_outcome: object) -> list[str]:
    """Build the human lines for a ``machine_outcome`` mapping.

    Split out from the rendering so tests can assert on content without a terminal, and so
    other surfaces can reuse the wording rather than inventing their own. Returns an empty
    list when there is no outcome to describe, which keeps the caller's control flow simple.

    Args:
        machine_outcome: The receipt's ``machine_outcome`` mapping, or ``None``.

    Returns:
        Zero or more display lines. The first is the outcome; the rest are guidance.
    """
    if not isinstance(machine_outcome, dict):
        return []
    code = machine_outcome.get("outcome_code")
    if code is None:
        return []

    lines = [_describe_outcome(code)]

    raw_actions = machine_outcome.get("next_actions") or ()
    # A bare string is accepted as a single action rather than discarded. The first version
    # tested `isinstance(raw_actions, (list, tuple))` and fell through to `[]`, so a
    # `next_actions` that arrived as `"needs_declared_premise"` -- a plausible serialisation
    # of a one-element list, and what a hand-built payload looks like -- dropped the guidance
    # SILENTLY. That is the exact defect this module was written to fix, reproduced inside the
    # fix; caught by an independent reviewer, not by its author. Iterating a string would be
    # worse than dropping it (one line per character), so it is wrapped, not iterated.
    if isinstance(raw_actions, str):
        actions: list[object] = [raw_actions]
    elif isinstance(raw_actions, (list, tuple)):
        actions = list(raw_actions)
    else:
        actions = []
    for action in actions:
        guidance = _describe_action(action)
        if guidance:
            lines.append(f"-> {guidance}")

    held = machine_outcome.get("held_count")
    if isinstance(held, int) and held > 0:
        lines.append(f"{held} fix(es) held for review.")

    return lines


def render_machine_outcome(
    machine_outcome: object,
    console: Console,
    *,
    title: str = "Outcome",
) -> bool:
    """Render the outcome and its next actions to ``console``.

    Args:
        machine_outcome: The receipt's ``machine_outcome`` mapping, or ``None``.
        console: Destination console.
        title: Panel title.

    Returns:
        ``True`` if anything was rendered, so a caller can decide whether it still needs a
        fallback message of its own.
    """
    lines = outcome_lines(machine_outcome)
    if not lines:
        return False
    console.print(Panel("\n".join(lines), title=title, style="yellow"))
    return True


def held_fix_lines(suggested_fixes: object) -> list[str]:
    """Summarise held fixes by review reason.

    Withheld fixes are the product's primary honest output when nothing is written -- a
    refusal is only actionable if the operator can see *what* was refused and *why*. They
    were reachable only through ``--json``.

    Grouped rather than listed per cell, deliberately: ``CLAUDE.md`` records that Rich output
    is slow beyond a few hundred rows, and a flooded queue printed one line per cell is
    unreadable anyway. The count is the actionable part; the cells are in ``--json``.

    Args:
        suggested_fixes: The receipt's ``suggested_fixes`` sequence, or ``None``.

    Returns:
        One line per distinct review reason, most frequent first.
    """
    if not isinstance(suggested_fixes, (list, tuple)) or not suggested_fixes:
        return []

    counts: dict[str | None, int] = {}
    for candidate in suggested_fixes:
        reason = getattr(candidate, "review_reason", None)
        if reason is None and isinstance(candidate, dict):
            raw = candidate.get("review_reason")
            reason = raw if isinstance(raw, str) else None
        counts[reason] = counts.get(reason, 0) + 1

    ordered = sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))
    return [f"{count} x {humanize_review_reason(reason)}" for reason, count in ordered]


def render_held_fixes(
    suggested_fixes: object,
    console: Console,
    *,
    title: str = "Held For Review",
) -> bool:
    """Render the held-fix summary to ``console``.

    Args:
        suggested_fixes: The receipt's ``suggested_fixes`` sequence, or ``None``.
        console: Destination console.
        title: Panel title.

    Returns:
        ``True`` if anything was rendered.
    """
    lines = held_fix_lines(suggested_fixes)
    if not lines:
        return False
    console.print(Panel("\n".join(lines), title=title, style="yellow"))
    return True
