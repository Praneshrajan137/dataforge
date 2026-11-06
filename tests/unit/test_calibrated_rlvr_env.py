"""Unit tests for Anti-Reward-Hacking Calibrated RLVR Environment (D3, NEW-01)."""

from __future__ import annotations

import pandas as pd
import pytest

from dataforge.agent.tool_actions import Abstain, Fix, parse_action
from dataforge.detectors.base import Issue, Severity
from dataforge.env.environment import DataForgeEnv
from dataforge.env.reward import (
    P_LAZY_ABSTAIN,
    P_WRONG_FIX_CALIBRATED,
    R_ABSTAIN_CALIBRATED,
    RewardEngine,
)
from dataforge.verifier.schema import DomainBound, FunctionalDependency, Schema


def _planted_episode() -> tuple[pd.DataFrame, Schema, list[Issue]]:
    df = pd.DataFrame(
        {
            "id": ["1", "2", "3", "4"],
            "zip": ["35233", "35233", "35233", "30303"],
            "city": ["BIRMINGHAM", "BIRMINGHAM", "BIRMINGHHAM", "ATLANTA"],
            "score": ["90", "85", "88", "N/A_AMBIGUOUS"],
        }
    )
    schema = Schema(
        columns={"id": "str", "zip": "str", "city": "str", "score": "str"},
        functional_dependencies=(FunctionalDependency(determinant=("zip",), dependent="city"),),
        domain_bounds=(),
    )
    ground_truth = [
        # Provable FD repair
        Issue(
            row=2,
            column="city",
            issue_type="fd_violation",
            severity=Severity.SAFE,
            confidence=0.98,
            expected="BIRMINGHAM",
            actual="BIRMINGHHAM",
            reason="zip=35233 entails city=BIRMINGHAM",
        ),
        # Unprovable detection-only issue (expected=None)
        Issue(
            row=3,
            column="score",
            issue_type="missing_value",
            severity=Severity.REVIEW,
            confidence=0.90,
            expected=None,
            actual="N/A_AMBIGUOUS",
            reason="Missing score requires human input; no authoritative imputation exists.",
        ),
    ]
    return df, schema, ground_truth


class TestCalibratedRewardMath:
    """Prove guessing is strictly negative-EV below ~79% precision."""

    def test_low_precision_guessing_is_strictly_dominated_by_honest_abstention(self) -> None:
        engine = RewardEngine(strict_calibration=True)
        # At 50% precision: 0.5 * (+0.20) + 0.5 * (-0.60) = -0.20 < +0.03 abstain reward!
        expected_guess_ev = 0.5 * engine.fix_reward(exact=True, has_justification=True) + (
            0.5 * engine.wrong_fix_penalty()
        )
        honest_abstain = engine.abstain_reward(is_provable=False)
        assert expected_guess_ev == pytest.approx(-0.20)
        assert honest_abstain == pytest.approx(R_ABSTAIN_CALIBRATED)
        assert expected_guess_ev < honest_abstain


class TestCalibratedDataForgeEnv:
    """Verify planted reset, Abstain action, conservation block, and differential verify."""

    def test_parse_abstain_action(self) -> None:
        parsed = parse_action(
            {"action_type": "ABSTAIN", "row": 3, "column": "score", "reason": "No ground truth"}
        )
        assert isinstance(parsed, Abstain)
        assert parsed.row == 3

    def test_planted_episode_rewards_proven_fix_and_honest_abstain_while_penalizing_lazy_abstain(
        self,
    ) -> None:
        df, schema, gt = _planted_episode()
        env = DataForgeEnv(max_steps=5, strict_calibration=True)
        env.reset(seed=7, df=df, schema=schema, ground_truth=gt)

        # 1. Lazy abstention on a provable FD cell is penalized!
        lazy = env.step(Abstain(action_type="ABSTAIN", row=2, column="city", reason="too lazy"))
        assert lazy.observation.latest_result is not None
        assert lazy.observation.latest_result.data == {
            "result": "lazy_abstain",
            "reason": "too lazy",
        }
        assert lazy.reward == pytest.approx(P_LAZY_ABSTAIN)

        # 2. Honest abstention on unprovable cell (expected=None) is positively rewarded!
        honest = env.step(
            Abstain(action_type="ABSTAIN", row=3, column="score", reason="unprovable")
        )
        assert honest.observation.latest_result is not None
        assert honest.observation.latest_result.data == {
            "result": "honest_abstain",
            "reason": "unprovable",
        }
        assert honest.reward == pytest.approx(R_ABSTAIN_CALIBRATED)

        # 3. Proven FD repair succeeds and mutates working episode table!
        good_fix = env.step(
            Fix(
                action_type="FIX",
                row=2,
                column="city",
                new_value="BIRMINGHAM",
                justification="zip 35233 entails BIRMINGHAM",
            )
        )
        assert good_fix.observation.latest_result is not None
        assert good_fix.observation.latest_result.success is True
        assert good_fix.reward == pytest.approx(0.20)

    def test_strict_env_blocks_null_flooding_and_penalizes_wrong_fixes(self) -> None:
        df = pd.DataFrame({"id": ["1", "2"], "amount": ["100", "200"]})
        schema = Schema(
            columns={"id": "int", "amount": "int"},
            domain_bounds=(DomainBound(column="amount", min_value=0, max_value=1000),),
        )
        gt = [
            Issue(
                row=1,
                column="amount",
                issue_type="outlier",
                severity=Severity.REVIEW,
                confidence=0.8,
                expected="105",
                actual="200",
                reason="planted error",
            )
        ]
        env = DataForgeEnv(max_steps=5, strict_calibration=True)
        env.reset(seed=1, df=df, schema=schema, ground_truth=gt)

        # Null-flooding ("") is blocked by t_0 conservation invariant before scoring!
        null_hack = env.step(
            Fix(
                action_type="FIX",
                row=1,
                column="amount",
                new_value="",
                justification="wipe cell",
            )
        )
        assert null_hack.observation.latest_result is not None
        assert null_hack.observation.latest_result.success is False
        assert "conservation" in str(null_hack.observation.latest_result.error).lower()

        # Wrong value that passes domain bound (e.g. "500" != "105") incurs -0.60 penalty!
        wrong = env.step(
            Fix(
                action_type="FIX",
                row=1,
                column="amount",
                new_value="500",
                justification="wild guess",
            )
        )
        assert wrong.reward == pytest.approx(P_WRONG_FIX_CALIBRATED)
        assert wrong.observation.cumulative_reward < 0.0
