"""Unit tests for Causal Determinant Cluster Triage (NEW-06 / D5)."""

from __future__ import annotations

import pandas as pd

from dataforge import cluster_repairs
from dataforge.repairers.base import ProposedFix
from dataforge.transactions.txn import CellFix
from dataforge.verifier.schema import FunctionalDependency, Schema


class TestCausalClusterTriage:
    """Verify massive cell-queue compression into deterministic causal clusters."""

    def test_empty_proposals_returns_unit_compression_report(self) -> None:
        df = pd.DataFrame({"zip": ["35233"], "city": ["BIRMINGHAM"]})
        report = cluster_repairs(df, [])
        assert report.total_proposals == 0
        assert report.cluster_count == 0
        assert report.compression_ratio == 1.0
        assert report.clusters == ()

    def test_hospital_scale_fd_proposals_compress_into_rule_level_clusters(self) -> None:
        rows = []
        proposals: list[ProposedFix] = []
        idx = 0
        for zip_code, clean_city, typos in (
            ("35233", "BIRMINGHAM", ["BIRMINGHHAM", "BIRMINGHM"]),
            ("30303", "ATLANTA", ["ATLNTA", "ATLANTAA"]),
            ("60601", "CHICAGO", ["CHICGO"]),
        ):
            for rep in range(40):
                dirty = typos[rep % len(typos)]
                rows.append({"id": str(idx), "zip": zip_code, "city": dirty})
                proposals.append(
                    ProposedFix(
                        fix=CellFix(
                            row=idx,
                            column="city",
                            old_value=dirty,
                            new_value=clean_city,
                            detector_id="fd_violation",
                        ),
                        reason="FD determinant consensus",
                        confidence=0.95,
                        provenance="deterministic",
                    )
                )
                idx += 1

        df = pd.DataFrame(rows)
        schema = Schema(
            columns={"id": "str", "zip": "str", "city": "str"},
            functional_dependencies=(FunctionalDependency(determinant=("zip",), dependent="city"),),
        )

        report = cluster_repairs(df, proposals, schema)
        assert report.total_proposals == 120
        assert report.cluster_count == 3
        assert report.compression_ratio == 40.0
        assert sum(c.member_count for c in report.clusters) == 120

        by_city = {c.new_value: c for c in report.clusters}
        bhm = by_city["BIRMINGHAM"]
        assert bhm.determinant_columns == ("zip",)
        assert bhm.determinant_values == (("zip", "35233"),)
        assert bhm.distinct_old_values == ("BIRMINGHHAM", "BIRMINGHM")
        assert "where (zip='35233')" in bhm.summary
