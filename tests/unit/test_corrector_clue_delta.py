"""Offline unit tests for Z3 clue-delta retries, causal JSON ordering, and prompt diet."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from dataforge.detectors.base import Issue
from dataforge.repairers.base import ProposedFix, RepairAttempt, RetryContext
from dataforge.repairers.llm_corrector import _ABSTAIN_TOKEN, LLMCorrectorRepairer
from dataforge.transactions.txn import CellFix


def _frame() -> pd.DataFrame:
    cities = ["ATLANTA"] * 6 + ["BIRMINGHAM"] * 5 + ["MOBILE"] * 4
    return pd.DataFrame(
        {
            "provider": [f"P{i:03d}" for i in range(len(cities) + 1)],
            "city": [*cities, "ATLNTA"],
        }
    )


def _issue(df: pd.DataFrame) -> Issue:
    row = len(df) - 1
    return Issue(
        row=row,
        column="city",
        issue_type="categorical_normalization",
        severity="review",
        reason="value not in vocabulary",
        actual=str(df.at[row, "city"]),
        confidence=0.6,
    )


class TestClueDeltaRetryLoop:
    """Verify CHG-01: Z3 unsat_core clue-delta, enum pruning, and max_retries cap."""

    def test_retry_context_prunes_rejected_values_from_enum_and_embeds_unsat_core(
        self, tmp_path: Path
    ) -> None:
        df = _frame()
        issue = _issue(df)
        seen_prompts: list[list[dict[str, str]]] = []
        seen_formats: list[dict[str, object] | None] = []

        def structured_fn(
            messages: list[dict[str, str]], response_format: dict[str, object] | None
        ) -> str:
            seen_prompts.append([dict(m) for m in messages])
            seen_formats.append(response_format)
            return json.dumps({"value": "ATLANTA", "confidence": 0.92})

        corrector = LLMCorrectorRepairer(
            cache_dir=tmp_path,
            allow_llm=True,
            model="test-model",
            samples=1,
            structured_completion_fn=structured_fn,  # type: ignore[arg-type]
            structured=True,
        )

        failed_fix = ProposedFix(
            fix=CellFix(
                row=issue.row,
                column="city",
                old_value="ATLNTA",
                new_value="BIRMINGHAM",
                detector_id=issue.issue_type,
            ),
            reason="first try",
            confidence=0.8,
            provenance="llm_live",
        )
        attempt = RepairAttempt(
            issue=issue,
            attempt_number=1,
            fix=failed_fix,
            status="rejected",
            reason="FD state->city mismatch",
            unsat_core=("fd_state_city_row_15",),
        )
        retry_ctx = RetryContext(
            issue=issue,
            previous_attempts=(attempt,),
            rejected_values=frozenset({"BIRMINGHAM"}),
            hints=("Determinant peer rows require ATLANTA.",),
        )

        proposal = corrector.propose(issue, df, None, retry_context=retry_ctx)
        assert proposal is not None
        assert proposal.fix.new_value == "ATLANTA"
        assert proposal.confidence == pytest.approx(0.92)

        # Decode-time enum must exclude BIRMINGHAM!
        schema_spec = seen_formats[0]
        assert schema_spec is not None
        enum_vals = schema_spec["json_schema"]["schema"]["properties"]["value"]["enum"]  # type: ignore[index]
        assert "BIRMINGHAM" not in enum_vals
        assert enum_vals == ["ATLANTA", "MOBILE", _ABSTAIN_TOKEN]

        # User prompt must carry structured clue_delta with unsat_core and hints!
        user_msg = seen_prompts[0][1]["content"]
        assert "fd_state_city_row_15" in user_msg
        assert "BIRMINGHAM" in user_msg
        assert "Determinant peer rows require ATLANTA." in user_msg

    def test_retry_context_rejects_blacklisted_value_even_in_free_text_mode(self) -> None:
        df = _frame()
        issue = _issue(df)
        corrector = LLMCorrectorRepairer(
            cache_dir=None,
            allow_llm=True,
            model="test-model",
            samples=1,
            completion_fn=lambda _msgs: "BIRMINGHAM",
            structured=False,
        )
        retry_ctx = RetryContext(
            issue=issue,
            rejected_values=frozenset({"BIRMINGHAM"}),
        )
        assert corrector.propose(issue, df, None, retry_context=retry_ctx) is None

    def test_max_retries_hard_cap_halts_runaway_loops(self) -> None:
        df = _frame()
        issue = _issue(df)
        calls = {"n": 0}

        def count_fn(_msgs: list[dict[str, str]]) -> str:
            calls["n"] += 1
            return "ATLANTA"

        corrector = LLMCorrectorRepairer(
            cache_dir=None,
            allow_llm=True,
            model="test-model",
            samples=1,
            completion_fn=count_fn,  # type: ignore[arg-type]
            max_retries=2,
        )
        attempts = tuple(
            RepairAttempt(
                issue=issue,
                attempt_number=idx,
                status="rejected",
                reason="failed",
            )
            for idx in (1, 2, 3)
        )
        retry_ctx = RetryContext(issue=issue, previous_attempts=attempts)
        assert corrector.propose(issue, df, None, retry_context=retry_ctx) is None
        assert calls["n"] == 0


class TestCausalJsonAndSimplePromptDiet:
    """Verify CHG-02 (causal JSON property order) and CHG-04 (>=50% prompt diet)."""

    def test_causal_json_orders_constraint_check_before_value_and_confidence(self) -> None:
        df = _frame()
        issue = _issue(df)
        payload = json.dumps(
            {
                "constraint_check": "ATLNTA is 1 edit from ATLANTA in pool.",
                "value": "ATLANTA",
                "confidence": 0.87,
            }
        )
        corrector = LLMCorrectorRepairer(
            cache_dir=None,
            allow_llm=True,
            model="test-model",
            samples=2,
            completion_fn=lambda _msgs: payload,
            structured=True,
            causal_json=True,
        )
        spec = corrector._response_format(df, issue)
        assert spec is not None
        schema = spec["json_schema"]["schema"]  # type: ignore[index]
        assert list(schema["properties"].keys()) == [
            "constraint_check",
            "value",
            "confidence",
        ]
        assert schema["required"] == ["constraint_check", "value", "confidence"]

        proposal = corrector.propose(issue, df, None)
        assert proposal is not None
        assert proposal.fix.new_value == "ATLANTA"
        assert proposal.confidence == pytest.approx(0.87)

    def test_simple_prompt_reduces_prompt_length_by_over_fifty_percent(self) -> None:
        df = _frame()
        issue = _issue(df)
        default_seen: list[list[dict[str, str]]] = []
        diet_seen: list[list[dict[str, str]]] = []

        default_corrector = LLMCorrectorRepairer(
            cache_dir=None,
            allow_llm=True,
            model="test-model",
            samples=1,
            completion_fn=lambda msgs: default_seen.append(msgs) or "ATLANTA",  # type: ignore[arg-type,func-returns-value]
            structured=False,
            simple_prompt=False,
        )
        diet_corrector = LLMCorrectorRepairer(
            cache_dir=None,
            allow_llm=True,
            model="test-model",
            samples=1,
            completion_fn=lambda msgs: diet_seen.append(msgs) or "ATLANTA",  # type: ignore[arg-type,func-returns-value]
            structured=False,
            simple_prompt=True,
        )

        assert default_corrector.propose(issue, df, None) is not None
        assert diet_corrector.propose(issue, df, None) is not None

        default_chars = sum(len(m["content"]) for m in default_seen[0])
        diet_chars = sum(len(m["content"]) for m in diet_seen[0])
        assert diet_chars <= 0.5 * default_chars
