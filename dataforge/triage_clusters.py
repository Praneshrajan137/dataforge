"""Causal determinant cluster triage for compact human and orchestrator review.

Cell-by-cell review queues suffer severe alert fatigue on real-world tables:
399 individual FD/categorical repair proposals on ``hospital`` collapse to a
handful of recurring determinant rules (for example ``zip='35233' -> city='birmingham'``).
Grouping proposals by ``(detector_id, column, determinant_signature, new_value)``
preserves 100% of row-level traceability while letting operators and parent
agents inspect, approve, or hold coherent causal rules.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from dataforge.engine.repair import CandidateFix
from dataforge.repairers.base import ProposedFix
from dataforge.table import TableLike, cell_value, column_names, row_count
from dataforge.verifier.schema import Schema

__all__ = [
    "CausalCluster",
    "ClusterCompressionReport",
    "cluster_repairs",
]


class CausalCluster(BaseModel):
    """One causal rule-level cluster aggregating identical determinant/target proposals."""

    cluster_id: str = Field(min_length=12, max_length=12)
    detector_id: str = Field(min_length=1)
    column: str = Field(min_length=1)
    determinant_columns: tuple[str, ...] = Field(default_factory=tuple)
    determinant_values: tuple[tuple[str, str], ...] = Field(default_factory=tuple)
    distinct_old_values: tuple[str, ...] = Field(default_factory=tuple)
    new_value: str
    member_rows: tuple[int, ...] = Field(min_length=1)
    member_count: int = Field(ge=1)
    min_confidence: float = Field(ge=0.0, le=1.0)
    max_confidence: float = Field(ge=0.0, le=1.0)
    provenances: tuple[str, ...] = Field(default_factory=tuple)
    summary: str = Field(min_length=1)

    model_config = ConfigDict(frozen=True, extra="forbid")


class ClusterCompressionReport(BaseModel):
    """Aggregated causal cluster report over a batch of candidate repairs."""

    total_proposals: int = Field(ge=0)
    cluster_count: int = Field(ge=0)
    compression_ratio: float = Field(ge=1.0)
    clusters: tuple[CausalCluster, ...] = Field(default_factory=tuple)

    model_config = ConfigDict(frozen=True, extra="forbid")


def _normalize_item(item: ProposedFix | CandidateFix) -> CandidateFix:
    if isinstance(item, ProposedFix):
        return CandidateFix.from_proposed(item)
    return item


def _determinant_signature(
    df: TableLike,
    row: int,
    target_column: str,
    schema: Schema | None,
    present_cols: set[str],
    total_rows: int,
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    if schema is None or row < 0 or row >= total_rows:
        return (), ()
    for fd in schema.functional_dependencies:
        if fd.dependent != target_column:
            continue
        if all(col in present_cols for col in fd.determinant):
            det_cols = tuple(fd.determinant)
            det_vals = tuple((col, str(cell_value(df, row, col)).strip()) for col in det_cols)
            return det_cols, det_vals
    return (), ()


def _cluster_id(
    detector_id: str,
    column: str,
    det_vals: tuple[tuple[str, str], ...],
    new_value: str,
) -> str:
    raw = json.dumps(
        {
            "detector_id": detector_id,
            "column": column,
            "determinant": list(det_vals),
            "new_value": new_value,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def cluster_repairs(
    df: TableLike,
    proposals: Sequence[ProposedFix | CandidateFix],
    schema: Schema | None = None,
) -> ClusterCompressionReport:
    """Group cell-level repair proposals into compact causal determinant clusters."""
    if not proposals:
        return ClusterCompressionReport(
            total_proposals=0,
            cluster_count=0,
            compression_ratio=1.0,
            clusters=(),
        )

    present_cols = set(column_names(df))
    total_rows = row_count(df)
    buckets: dict[
        tuple[str, str, tuple[tuple[str, str], ...], str],
        tuple[tuple[str, ...], list[CandidateFix]],
    ] = {}

    for raw_item in proposals:
        item = _normalize_item(raw_item)
        det_cols, det_vals = _determinant_signature(
            df, item.row, item.column, schema, present_cols, total_rows
        )
        key = (item.detector_id, item.column, det_vals, item.new_value)
        if key not in buckets:
            buckets[key] = (det_cols, [item])
        else:
            buckets[key][1].append(item)

    built: list[CausalCluster] = []
    for (detector_id, column, det_vals, new_value), (det_cols, members) in buckets.items():
        cid = _cluster_id(detector_id, column, det_vals, new_value)
        rows = tuple(sorted({m.row for m in members}))
        old_vals = tuple(sorted({m.old_value for m in members}))
        confs = [m.confidence for m in members]
        provs = tuple(sorted({m.provenance for m in members}))
        if det_vals:
            where_clause = ", ".join(f"{col}={val!r}" for col, val in det_vals)
            summary = (
                f"{detector_id} on {column!r} where ({where_clause}): "
                f"{len(members)} edit(s) {list(old_vals[:3])} -> {new_value!r}"
            )
        else:
            summary = (
                f"{detector_id} on {column!r}: "
                f"{len(members)} edit(s) {list(old_vals[:3])} -> {new_value!r}"
            )
        built.append(
            CausalCluster(
                cluster_id=cid,
                detector_id=detector_id,
                column=column,
                determinant_columns=det_cols,
                determinant_values=det_vals,
                distinct_old_values=old_vals,
                new_value=new_value,
                member_rows=rows,
                member_count=len(members),
                min_confidence=min(confs),
                max_confidence=max(confs),
                provenances=provs,
                summary=summary,
            )
        )

    built.sort(key=lambda c: (-c.member_count, c.column, c.cluster_id))
    ratio = round(max(1.0, len(proposals) / max(1, len(built))), 4)
    return ClusterCompressionReport(
        total_proposals=len(proposals),
        cluster_count=len(built),
        compression_ratio=ratio,
        clusters=tuple(built),
    )
