"""Tests for rendering the machine outcome a repair run already computes.

Two kinds of test live here, and they guard different failures:

* **Population completeness** -- every member of ``OutcomeCode`` and ``NextAction`` must
  have human text. These derive the population via ``get_args()``, so adding a vocabulary
  member without its label fails here rather than silently rendering nothing to a user.
  This is the frozen-population defect ``PRODUCT.md`` §1.3 records twice, applied to the
  display layer.
* **The end-to-end guarantee** -- a run that writes nothing must tell the operator *why*
  and *what would change it*. Measured on 2026-09-12, the human CLI printed
  ``No fixes proposed.`` and never used the word *schema*, while the ``--json`` surface on
  the same run reported ``next_actions = ["needs_declared_premise"]``. The test named
  ``test_zero_write_run_names_the_remedy`` fails against that behaviour.
"""

from __future__ import annotations

from pathlib import Path
from typing import get_args

from rich.console import Console
from typer.testing import CliRunner

from dataforge.cli import app
from dataforge.domain.vocabulary import (
    NEXT_ACTION_HUMAN,
    OUTCOME_CODE_HUMAN,
    NextAction,
    OutcomeCode,
)
from dataforge.ui.outcome import (
    held_fix_lines,
    outcome_lines,
    render_held_fixes,
    render_machine_outcome,
)
from dataforge.ui.trust_vocab import humanize_review_reason

runner = CliRunner()


def test_every_outcome_code_has_human_text() -> None:
    """Derived from the Literal, so a new code without a label fails here."""
    for code in get_args(OutcomeCode):
        assert code in OUTCOME_CODE_HUMAN, f"OutcomeCode {code!r} has no human text"
        assert OUTCOME_CODE_HUMAN[code].strip(), f"OutcomeCode {code!r} has empty human text"


def test_every_next_action_has_human_text() -> None:
    """Derived from the Literal, so a new action without a label fails here."""
    for action in get_args(NextAction):
        assert action in NEXT_ACTION_HUMAN, f"NextAction {action!r} has no human text"
        assert NEXT_ACTION_HUMAN[action].strip(), f"NextAction {action!r} has empty human text"


def test_declared_premise_guidance_does_not_recommend_trusting_mined_constraints() -> None:
    """The remedy for a missing premise must not point at the corrupting opt-in.

    ``--trust-mined-constraints`` is measured at 116 already-correct cells corrupted on
    hospital (``PRODUCT.md`` §1.4). Guidance that nudges an operator toward it to escape a
    zero-write run would trade the product's safety result for apparent helpfulness.
    """
    guidance = NEXT_ACTION_HUMAN["needs_declared_premise"]
    assert "--schema" in guidance
    assert "trust-mined-constraints" not in guidance


def test_outcome_lines_renders_code_and_actions() -> None:
    """The mapping is turned into an outcome line plus one guidance line per action."""
    lines = outcome_lines(
        {
            "outcome_code": "no_repairable_errors",
            "next_actions": ["needs_declared_premise"],
            "held_count": 0,
        }
    )
    assert lines
    assert OUTCOME_CODE_HUMAN["no_repairable_errors"] in lines[0]
    assert any("--schema" in line for line in lines[1:])


def test_outcome_lines_omits_none_action() -> None:
    """``none`` carries no instruction, so it must not be rendered as guidance."""
    lines = outcome_lines({"outcome_code": "clean", "next_actions": ["none"], "held_count": 0})
    assert lines == [OUTCOME_CODE_HUMAN["clean"]]


def test_outcome_lines_reports_held_count() -> None:
    """A held count is the product's primary honest output and must be visible."""
    lines = outcome_lines(
        {"outcome_code": "all_fixes_held", "next_actions": ["needs_review"], "held_count": 4}
    )
    assert any("4 fix(es) held for review." in line for line in lines)


def test_outcome_lines_empty_without_outcome() -> None:
    """Absent or malformed input renders nothing rather than raising."""
    assert outcome_lines(None) == []
    assert outcome_lines({}) == []
    assert outcome_lines("not a mapping") == []


def test_unknown_code_is_reported_not_swallowed() -> None:
    """An unrecognised code must surface, not vanish -- silence is the defect."""
    lines = outcome_lines({"outcome_code": "some_future_code", "next_actions": []})
    assert "some_future_code" in lines[0]


def test_string_next_actions_is_not_silently_dropped() -> None:
    """A string ``next_actions`` is a plausible serialisation mistake. Drop it and the user
    never sees the remedy the engine computed — the exact defect this module exists to fix."""
    lines = outcome_lines(
        {"outcome_code": "no_repairable_errors", "next_actions": "needs_declared_premise"}
    )
    assert any("--schema" in line for line in lines), (
        f"next_actions was a string and the guidance was silently dropped. Lines: {lines}"
    )


def test_render_machine_outcome_writes_to_console() -> None:
    """The renderer reports whether it produced output, so callers can fall back."""
    console = Console(record=True, width=100)
    assert render_machine_outcome(
        {"outcome_code": "no_repairable_errors", "next_actions": ["needs_declared_premise"]},
        console,
    )
    assert "--schema" in console.export_text()
    assert not render_machine_outcome(None, console)


def _write_detectable_but_unrepairable(path: Path) -> None:
    """A CSV with issues no premise-free repairer will fix.

    Duplicate rows and unparseable dates are detected without a declared schema, and
    neither has a repairer that can propose a proven value -- so the run reaches
    ``no_repairable_errors`` with ``needs_declared_premise``, which is exactly the default
    zero-configuration outcome after C4 removed write authority from mined constraints.
    """
    path.write_text(
        "id,name,amount,joined\n"
        "1,Alice,100,2020-01-15\n"
        "2,Bob,,2020-02-20\n"
        "3,Carol,105,15/03/2020\n"
        "4,Dave,98,2020-04-10\n"
        "5,Eve,999999,2020-05-12\n"
        "5,Eve,999999,2020-05-12\n"
        "7,Frank,,not a date\n",
        encoding="utf-8",
    )


def test_zero_write_run_names_the_remedy(tmp_path: Path) -> None:
    """A run that writes nothing must name the reason AND the way forward.

    This is the end-to-end guarantee behind ``PRODUCT.md`` §1.5's claim that a user gets
    "detection, a named refusal reason, and a one-line way to authorise the writes
    deliberately". Before 2026-09-12 the human surface printed only ``No fixes proposed.``
    and this test failed.
    """
    source = tmp_path / "dirty.csv"
    _write_detectable_but_unrepairable(source)

    result = runner.invoke(app, ["repair", str(source), "--dry-run"])

    output = result.stdout
    assert "No fixes proposed." in output, "the existing outcome line should be preserved"
    assert "--schema" in output, (
        "a zero-write run must name the remedy the engine already computed "
        f"(next_actions carried needs_declared_premise). Got:\n{output}"
    )


class _Candidate:
    """Minimal stand-in for a held candidate repair."""

    def __init__(self, review_reason: str | None) -> None:
        self.review_reason = review_reason


def test_held_fix_lines_groups_by_reason() -> None:
    """Held fixes are summarised per reason, most frequent first."""
    lines = held_fix_lines(
        [
            _Candidate("failed_conformal_threshold"),
            _Candidate("failed_conformal_threshold"),
            _Candidate("floor_cannot_verify"),
        ]
    )
    assert len(lines) == 2
    assert lines[0].startswith("2 x ")
    assert lines[1].startswith("1 x ")


def test_held_fix_lines_humanizes_reason() -> None:
    """The reason is rendered as a sentence, never as a raw machine token."""
    lines = held_fix_lines([_Candidate("floor_cannot_verify")])
    assert lines == [f"1 x {humanize_review_reason('floor_cannot_verify')}"]
    assert "floor_cannot_verify" not in lines[0]


def test_held_fix_lines_accepts_mappings() -> None:
    """A JSON-decoded receipt yields dicts, not objects, and must still summarise."""
    assert held_fix_lines([{"review_reason": "floor_cannot_verify"}]) == [
        f"1 x {humanize_review_reason('floor_cannot_verify')}"
    ]


def test_held_fix_lines_handles_missing_reason() -> None:
    """A candidate with no recorded reason still gets an honest held sentence."""
    lines = held_fix_lines([_Candidate(None)])
    assert lines == [f"1 x {humanize_review_reason(None)}"]


def test_held_fix_lines_empty_inputs() -> None:
    """Nothing held renders nothing."""
    assert held_fix_lines(None) == []
    assert held_fix_lines([]) == []


def test_render_held_fixes_writes_to_console() -> None:
    """The held summary reaches a terminal and reports that it rendered."""
    console = Console(record=True, width=100)
    assert render_held_fixes([_Candidate("floor_cannot_verify")], console)
    assert "1 x" in console.export_text()
    assert not render_held_fixes([], console)
