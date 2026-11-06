"""Tests for the accountable-spend layer (``dataforge.spend``).

These are the regression locks for the three independent guards: the pre-flight
USD estimate, the in-flight hard stop, and the after-the-fact receipt ledger.
Every test is offline -- no provider is contacted.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dataforge.cli.bench import _write_spend_receipt
from dataforge.spend import (
    PRICES,
    CostCapExceededError,
    ModelPrice,
    SpendMeter,
    append_receipt,
    cap_from_env,
    estimate_usd,
    load_ledger,
    meter_from_env,
    price_for,
    total_estimated_usd,
)

_PRICE = ModelPrice(usd_per_1k_input=0.005, usd_per_1k_output=0.015)


class TestModelPrice:
    """Per-call cost arithmetic."""

    def test_usd_for_charges_input_and_output_separately(self) -> None:
        # 1000 prompt tokens at $0.005/1k + 1000 completion at $0.015/1k.
        assert _PRICE.usd_for(1000, 1000) == pytest.approx(0.020)

    def test_usd_for_is_zero_without_tokens(self) -> None:
        assert _PRICE.usd_for(0, 0) == 0.0

    def test_price_for_is_case_insensitive(self) -> None:
        assert price_for("AZURE") == PRICES["azure"]

    def test_unpriced_provider_returns_none(self) -> None:
        # Groq/Cerebras are free-tier: a missing entry disables the USD guard
        # rather than inventing a number.
        assert price_for("groq") is None
        assert price_for("cerebras") is None


class TestEstimateUsd:
    """The pre-flight guard that was missing: prices x planned calls."""

    def test_estimate_multiplies_calls_by_per_call_cost(self) -> None:
        estimate = estimate_usd(
            calls=1000,
            avg_prompt_tokens=350,
            avg_completion_tokens=100,
            price=_PRICE,
        )
        # 350/1k*0.005 + 100/1k*0.015 = 0.00325 per call.
        assert estimate == pytest.approx(3.25)

    def test_unpriced_provider_yields_no_estimate(self) -> None:
        # No estimate means no refusal: we never fabricate a price to block on.
        assert (
            estimate_usd(
                calls=1000,
                avg_prompt_tokens=350,
                avg_completion_tokens=100,
                price=None,
            )
            is None
        )


class TestSpendMeter:
    """The single in-flight guard that replaced three duplicated copies."""

    def test_records_tokens_and_accumulates_cost(self) -> None:
        meter = SpendMeter(provider="azure", model="m", price=_PRICE)
        meter.record(prompt_tokens=1000, completion_tokens=1000)
        meter.record(prompt_tokens=1000, completion_tokens=1000)
        assert meter.calls == 2
        assert meter.cumulative_usd == pytest.approx(0.040)

    def test_hard_stops_when_cap_exceeded(self) -> None:
        meter = SpendMeter(provider="azure", model="m", price=_PRICE, max_usd=0.05)
        meter.record(prompt_tokens=1000, completion_tokens=1000)  # $0.020
        meter.record(prompt_tokens=1000, completion_tokens=1000)  # $0.040
        with pytest.raises(CostCapExceededError, match="azure spend guard tripped"):
            meter.record(prompt_tokens=1000, completion_tokens=1000)  # $0.060

    def test_cap_is_exclusive_so_landing_exactly_on_it_is_allowed(self) -> None:
        meter = SpendMeter(provider="azure", model="m", price=_PRICE, max_usd=0.020)
        meter.record(prompt_tokens=1000, completion_tokens=1000)
        assert meter.cumulative_usd == pytest.approx(0.020)

    def test_unpriced_meter_counts_but_never_trips(self) -> None:
        # This is the free-tier path: accounting without a USD guard, matching
        # the previous no-op behavior for Groq and Cerebras exactly.
        meter = SpendMeter(provider="groq", model="m", price=None, max_usd=0.0001)
        for _ in range(50):
            meter.record(prompt_tokens=10_000, completion_tokens=10_000)
        assert meter.calls == 50
        assert meter.cumulative_usd == 0.0

    def test_reasoning_tokens_are_recorded_for_visibility(self) -> None:
        meter = SpendMeter(provider="azure", model="m", price=_PRICE)
        meter.record(prompt_tokens=10, completion_tokens=200, reasoning_tokens=180)
        receipt = meter.receipt(run_id="r1")
        assert receipt.reasoning_tokens == 180
        # Reasoning tokens are billed inside completion_tokens, never added twice.
        assert receipt.completion_tokens == 200

    def test_missing_usage_fails_closed_on_a_metered_run(self) -> None:
        # A provider omitting usage would otherwise silently zero the guard and
        # let a capped run overspend undetected.
        meter = SpendMeter(
            provider="azure",
            model="m",
            price=_PRICE,
            max_usd=10.0,
            fail_on_missing_usage=True,
        )
        with pytest.raises(CostCapExceededError, match="no usage payload"):
            meter.record(prompt_tokens=0, completion_tokens=0, usage_present=False)

    def test_missing_usage_is_tolerated_when_not_metered(self) -> None:
        meter = SpendMeter(provider="groq", model="m", price=None)
        meter.record(prompt_tokens=0, completion_tokens=0, usage_present=False)
        assert meter.calls == 1


class TestCapFromEnv:
    """Cap resolution: provider-specific wins, global is the floor."""

    def test_provider_specific_cap_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATAFORGE_AZURE_MAX_USD", "15")
        monkeypatch.setenv("DATAFORGE_MAX_USD", "3")
        assert cap_from_env("azure") == 15.0

    def test_global_cap_applies_when_no_specific_cap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATAFORGE_AZURE_MAX_USD", raising=False)
        monkeypatch.setenv("DATAFORGE_MAX_USD", "7.5")
        assert cap_from_env("azure") == 7.5

    def test_no_cap_configured_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATAFORGE_AZURE_MAX_USD", raising=False)
        monkeypatch.delenv("DATAFORGE_MAX_USD", raising=False)
        assert cap_from_env("azure") is None

    def test_non_positive_disables_the_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The established convention for "run unmetered".
        monkeypatch.setenv("DATAFORGE_AZURE_MAX_USD", "0")
        assert cap_from_env("azure") is None

    def test_malformed_value_falls_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATAFORGE_AZURE_MAX_USD", "not-a-number")
        monkeypatch.setenv("DATAFORGE_MAX_USD", "2")
        assert cap_from_env("azure") == 2.0

    def test_meter_from_env_wires_price_and_cap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATAFORGE_AZURE_MAX_USD", "1")
        meter = meter_from_env(provider="azure", model="dep")
        assert meter.max_usd == 1.0
        meter.record(prompt_tokens=1000, completion_tokens=0)
        assert meter.cumulative_usd == pytest.approx(0.005)


class TestLedger:
    """Receipts are append-only and auditable."""

    def test_append_creates_ledger_with_schema(self, tmp_path: Path) -> None:
        path = tmp_path / "spend_ledger.json"
        meter = SpendMeter(provider="azure", model="dep", price=_PRICE, max_usd=5.0)
        meter.record(prompt_tokens=1000, completion_tokens=1000)
        append_receipt(path, meter.receipt(run_id="probe", method="llm_corrector"))

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema"] == "dataforge_spend_ledger_v1"
        assert len(payload["receipts"]) == 1
        receipt = payload["receipts"][0]
        assert receipt["run_id"] == "probe"
        assert receipt["provider"] == "azure"
        assert receipt["method"] == "llm_corrector"
        assert receipt["cap_usd"] == 5.0
        assert receipt["estimated_usd"] == pytest.approx(0.020)

    def test_append_is_additive_not_destructive(self, tmp_path: Path) -> None:
        path = tmp_path / "spend_ledger.json"
        for run_id in ("a", "b", "c"):
            meter = SpendMeter(provider="azure", model="dep", price=_PRICE)
            meter.record(prompt_tokens=1000, completion_tokens=0)
            append_receipt(path, meter.receipt(run_id=run_id))
        assert [r["run_id"] for r in load_ledger(path)] == ["a", "b", "c"]

    def test_total_sums_every_receipt(self, tmp_path: Path) -> None:
        path = tmp_path / "spend_ledger.json"
        for _ in range(4):
            meter = SpendMeter(provider="azure", model="dep", price=_PRICE)
            meter.record(prompt_tokens=1000, completion_tokens=0)  # $0.005 each
            append_receipt(path, meter.receipt(run_id="r"))
        assert total_estimated_usd(path) == pytest.approx(0.020)

    def test_absent_ledger_reads_as_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.json"
        assert load_ledger(path) == []
        assert total_estimated_usd(path) == 0.0

    def test_corrupt_ledger_reads_as_empty_rather_than_crashing(self, tmp_path: Path) -> None:
        path = tmp_path / "spend_ledger.json"
        path.write_text("{not json", encoding="utf-8")
        assert load_ledger(path) == []


class TestLedgerSummary:
    """A ledger total that is mostly reconstruction must not read as a measurement.

    The split is derived from ``calls == 0`` rather than a flag, because a receipt with
    no token counts cannot have had its USD observed -- and a flag is something a caller
    can forget to set.
    """

    def test_splits_measured_from_reconstructed(self, tmp_path: Path) -> None:
        from dataforge.spend import ledger_summary

        path = tmp_path / "ledger.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "dataforge_spend_ledger_v1",
                    "receipts": [
                        {"run_id": "a", "calls": 10, "estimated_usd": 4.0},
                        {"run_id": "b", "calls": 0, "estimated_usd": 6.0},
                    ],
                }
            ),
            encoding="utf-8",
        )
        summary = ledger_summary(path)
        assert summary.measured_usd == pytest.approx(4.0)
        assert summary.estimated_usd == pytest.approx(6.0)
        assert summary.measured_receipts == 1
        assert summary.estimated_receipts == 1
        assert summary.total_usd == pytest.approx(10.0)
        assert summary.measured_fraction == pytest.approx(0.4)

    def test_missing_calls_key_counts_as_reconstruction(self, tmp_path: Path) -> None:
        from dataforge.spend import ledger_summary

        path = tmp_path / "ledger.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "dataforge_spend_ledger_v1",
                    "receipts": [{"run_id": "a", "estimated_usd": 2.0}],
                }
            ),
            encoding="utf-8",
        )
        summary = ledger_summary(path)
        assert summary.estimated_receipts == 1
        assert summary.measured_usd == pytest.approx(0.0)

    def test_describe_states_the_measured_fraction(self, tmp_path: Path) -> None:
        from dataforge.spend import ledger_summary

        path = tmp_path / "ledger.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "dataforge_spend_ledger_v1",
                    "receipts": [
                        {"run_id": "a", "calls": 5, "estimated_usd": 1.0},
                        {"run_id": "b", "calls": 0, "estimated_usd": 3.0},
                    ],
                }
            ),
            encoding="utf-8",
        )
        described = ledger_summary(path).describe()
        assert "measured" in described and "reconstructed" in described
        assert "25%" in described

    def test_empty_ledger_is_fully_measured_by_convention(self, tmp_path: Path) -> None:
        """No spend means nothing unverified; the fraction must not divide by zero."""
        from dataforge.spend import ledger_summary

        path = tmp_path / "ledger.json"
        path.write_text(
            json.dumps({"schema": "dataforge_spend_ledger_v1", "receipts": []}),
            encoding="utf-8",
        )
        summary = ledger_summary(path)
        assert summary.total_usd == pytest.approx(0.0)
        assert summary.measured_fraction == pytest.approx(1.0)

    def test_total_matches_total_estimated_usd(self, tmp_path: Path) -> None:
        """The split must not change the headline number, only explain it."""
        from dataforge.spend import ledger_summary, total_estimated_usd

        path = tmp_path / "ledger.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "dataforge_spend_ledger_v1",
                    "receipts": [
                        {"run_id": "a", "calls": 3, "estimated_usd": 1.25},
                        {"run_id": "b", "calls": 0, "estimated_usd": 2.5},
                        {"run_id": "c", "calls": 9, "estimated_usd": 0.75},
                    ],
                }
            ),
            encoding="utf-8",
        )
        assert ledger_summary(path).total_usd == pytest.approx(total_estimated_usd(path))


class TestBenchSpendReceipt:
    """The bench CLI must record what a paid run cost.

    `docs/trust/spend-accountability.md` presents the ledger as the after-the-fact record, but
    `append_receipt` was called from one place only -- the Azure capability probe -- so the bench
    path spent real money silently. A 270-call gpt-5.6-sol run costing ~$0.98 left no trace.
    """

    @staticmethod
    def _record(**kwargs: object) -> SimpleNamespace:
        base = {
            "provider": "azure",
            "model": "gpt-5.6-sol",
            "llm_calls": 3,
            "prompt_tokens": 1000,
            "completion_tokens": 200,
        }
        base.update(kwargs)
        return SimpleNamespace(**base)

    def test_writes_one_receipt_per_provider_model_pair(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        output = SimpleNamespace(
            records=[
                self._record(),
                self._record(),
                self._record(model="gpt-5-mini", llm_calls=1),
            ]
        )
        _write_spend_receipt(output)

        payload = json.loads((tmp_path / "eval" / "results" / "spend_ledger.json").read_text())
        receipts = payload["receipts"]
        by_model = {r["model"]: r for r in receipts}
        assert set(by_model) == {"gpt-5.6-sol", "gpt-5-mini"}
        # Summed within a pair, never across pairs: two deployments have different prices, so
        # merging them would attribute spend to whichever appeared first.
        assert by_model["gpt-5.6-sol"]["calls"] == 6
        assert by_model["gpt-5.6-sol"]["prompt_tokens"] == 2000
        assert by_model["gpt-5-mini"]["calls"] == 1

    def test_uses_env_prices_so_the_receipt_matches_the_enforced_cap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DATAFORGE_AZURE_USD_PER_1K_INPUT", "1.0")
        monkeypatch.setenv("DATAFORGE_AZURE_USD_PER_1K_OUTPUT", "2.0")
        _write_spend_receipt(SimpleNamespace(records=[self._record()]))

        payload = json.loads((tmp_path / "eval" / "results" / "spend_ledger.json").read_text())
        # 1000/1000*1.0 + 200/1000*2.0 = 1.4, not the provider-table figure.
        assert payload["receipts"][0]["estimated_usd"] == pytest.approx(1.4)

    def test_writes_nothing_when_no_llm_calls_were_made(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _write_spend_receipt(
            SimpleNamespace(records=[self._record(llm_calls=0), self._record(provider=None)])
        )
        assert not (tmp_path / "eval" / "results" / "spend_ledger.json").exists()


class TestAnthropicOllamaAndStrictSpendGuard:
    """Accountable metering for Anthropic Claude models, local Ollama, and strict caps."""

    def test_anthropic_models_have_conservative_per_model_prices(self) -> None:
        from dataforge.spend import is_model_priced, require_price_for

        opus = require_price_for("anthropic", "claude-opus-4-7")
        sonnet = require_price_for("anthropic", "claude-sonnet-4-6")
        haiku = require_price_for("anthropic", "claude-haiku-4-5")
        assert opus.usd_per_1k_input == pytest.approx(0.005)
        assert opus.usd_per_1k_output == pytest.approx(0.025)
        assert sonnet.usd_per_1k_input == pytest.approx(0.003)
        assert sonnet.usd_per_1k_output == pytest.approx(0.015)
        assert haiku.usd_per_1k_input == pytest.approx(0.001)
        assert haiku.usd_per_1k_output == pytest.approx(0.005)
        assert is_model_priced("anthropic", "claude-opus-5-5")

    def test_anthropic_fallback_uses_conservative_opus_ceiling(self) -> None:
        fallback = price_for("anthropic", "claude-future-unknown")
        assert fallback == ModelPrice(usd_per_1k_input=0.005, usd_per_1k_output=0.025)

    def test_ollama_is_unpriced_local_tier_even_under_strict_cap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DATAFORGE_MAX_USD", "1.0")
        monkeypatch.setenv("DATAFORGE_STRICT_SPEND_CAP", "1")
        meter = meter_from_env(provider="ollama", model="qwen2.5:7b-instruct")
        meter.record(prompt_tokens=5000, completion_tokens=1000)
        assert meter.calls == 1
        assert meter.cumulative_usd == 0.0

    def test_strict_spend_cap_refuses_unknown_paid_provider_with_active_cap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DATAFORGE_MAX_USD", "1.0")
        monkeypatch.setenv("DATAFORGE_STRICT_SPEND_CAP", "1")
        meter = meter_from_env(provider="mystery-paid-cloud", model="m1")
        with pytest.raises(CostCapExceededError, match="no token price is registered"):
            meter.record(prompt_tokens=100, completion_tokens=50)

    def test_anthropic_and_ollama_provider_adapters_mocked_offline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asyncio

        import httpx

        from dataforge.agent import providers

        providers.reset_spend_meter()
        monkeypatch.setenv("DATAFORGE_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-offline")
        monkeypatch.setenv("DATAFORGE_ANTHROPIC_MAX_USD", "0.01")

        async def mock_post_anthropic(self: object, url: str, **kwargs: object) -> httpx.Response:
            assert url.endswith("/v1/messages")
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "ATLANTA"}],
                    "usage": {
                        "input_tokens": 200,
                        "cache_creation_input_tokens": 50,
                        "cache_read_input_tokens": 50,
                        "output_tokens": 100,
                    },
                },
                request=request,
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_anthropic)
        res = asyncio.run(
            providers.complete_with_usage(
                [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
                model="claude-sonnet-4-6",
            )
        )
        assert res.text == "ATLANTA"
        assert res.usage.prompt_tokens == 300
        assert res.usage.completion_tokens == 100
        active = providers.spend_meter()
        assert active is not None
        # 300/1k * 0.003 + 100/1k * 0.015 = 0.0009 + 0.0015 = 0.0024
        assert active.cumulative_usd == pytest.approx(0.0024)

        # Now verify local Ollama ($0, no API key needed)
        providers.reset_spend_meter()
        monkeypatch.setenv("DATAFORGE_LLM_PROVIDER", "ollama")
        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)

        async def mock_post_ollama(self: object, url: str, **kwargs: object) -> httpx.Response:
            assert "11434" in url
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "BOSTON"}}],
                    "usage": {"prompt_tokens": 120, "completion_tokens": 4},
                },
                request=request,
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_ollama)
        ollama_res = asyncio.run(
            providers.complete_with_usage([{"role": "user", "content": "fix"}])
        )
        assert ollama_res.text == "BOSTON"
        assert ollama_res.provider == "ollama"
        ollama_meter = providers.spend_meter()
        assert ollama_meter is not None
        assert ollama_meter.cumulative_usd == 0.0
