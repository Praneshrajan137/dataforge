"""Unit tests for Governed External Reference Gazetteer (NEW-03)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from dataforge import (
    GazetteerConflictError,
    ReferenceGazetteer,
    VerifyAndApplyRequest,
    read_csv,
    verify_and_apply,
)
from dataforge.domain.premise import premise_from_canonical


class TestReferenceGazetteer:
    """Verify fail-closed loading, premise round-trip, and zero-LLM 1.0-precision repair."""

    def test_conflicting_reference_rows_fail_closed(self) -> None:
        with pytest.raises(GazetteerConflictError, match="Ambiguous gazetteer key"):
            ReferenceGazetteer.from_records(
                [
                    {"zip": "35233", "city": "BIRMINGHAM", "state": "AL"},
                    {"zip": "35233", "city": "HUNTSVILLE", "state": "AL"},
                ],
                key_columns=["zip"],
                value_columns=["city", "state"],
            )

    def test_canonical_premise_round_trip_and_digest_stability(self, tmp_path: Path) -> None:
        ref_csv = tmp_path / "usps_zip.csv"
        ref_csv.write_text(
            "zip,city,state\n35233,BIRMINGHAM,AL\n30303,ATLANTA,GA\n",
            encoding="utf-8",
        )
        g1 = ReferenceGazetteer.from_csv(
            ref_csv, key_columns=["zip"], value_columns=["city", "state"]
        )
        g2 = ReferenceGazetteer.from_records(
            [
                {"zip": "30303", "city": "ATLANTA", "state": "GA"},
                {"zip": "35233", "city": "BIRMINGHAM", "state": "AL"},
            ],
            key_columns=["zip"],
            value_columns=["city", "state"],
        )
        assert g1.sha256_digest == g2.sha256_digest
        assert g1.lookup(["35233"]) == {"city": "BIRMINGHAM", "state": "AL"}
        assert g1.lookup(["99999"]) is None

        premise = g1.to_canonical_premise()
        assert premise["premise_format"] == "dataforge.premise/v1"
        reconstructed = premise_from_canonical(premise)
        assert reconstructed == g1.to_schema()

    def test_zero_llm_gazetteer_repairs_majority_corrupted_group_via_verify_and_apply(
        self, tmp_path: Path
    ) -> None:
        """Even when 100% of dirty rows for zip=35233 say BIRMINGHHAM, the external
        gazetteer repairs every row to BIRMINGHAM with 0 LLM calls and 1.0 precision."""
        gazetteer = ReferenceGazetteer.from_records(
            [
                {"zip": "35233", "city": "BIRMINGHAM", "state": "AL"},
                {"zip": "30303", "city": "ATLANTA", "state": "GA"},
            ],
            key_columns=["zip"],
            value_columns=["city", "state"],
            name="usps_zip_authority",
        )
        dirty_csv = tmp_path / "providers.csv"
        dirty_csv.write_text(
            "id,zip,city,state\n1,35233,BIRMINGHHAM,AL\n2,35233,BIRMINGHM,AL\n3,30303,ATLANTA,GA\n",
            encoding="utf-8",
        )

        df = read_csv(dirty_csv)
        fixes = gazetteer.propose_external_fixes(df)
        assert len(fixes) == 2

        result = verify_and_apply(
            VerifyAndApplyRequest(
                source_path=dirty_csv,
                fixes=fixes,
                mode="apply",
                schema=gazetteer.to_schema(),
                proposer=f"gazetteer:{gazetteer.name}",
                confirm_escalations=True,
            )
        )
        assert result.receipt.applied is True
        assert result.receipt.fixes_count == 2
        repaired = pd.read_csv(dirty_csv, dtype=str)
        assert list(repaired["city"]) == ["BIRMINGHAM", "BIRMINGHAM", "ATLANTA"]
