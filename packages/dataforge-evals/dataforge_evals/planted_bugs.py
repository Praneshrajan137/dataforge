"""Deterministic planted-bug curriculum generator for RLVR and Harbor benchmarks.

Generates non-circular evaluation and training episodes from clean canonical slices
of ``hospital``, ``flights``, ``rayyan``, and ``tax`` using five controlled
corruption operators:

* ``fd_swap`` — corrupts an FD dependent cell to break determinant consensus.
* ``typo_inject`` — injects single-character transposition/duplication typos.
* ``bound_breach`` — perturbs a bounded numeric cell outside ``[min, max]``.
* ``missing_sentinel`` — replaces a populated cell with an unprovable sentinel
  (for example ``"N/A"``) so calibrated agents must abstain when unrecoverable.
* ``scale_shift`` — multiplies a numeric cell by ``100`` to test domain bounds.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

from dataforge_evals.agents.base import GroundTruthCell, InferabilityLabel, Task

__all__ = [
    "CANONICAL_CLEAN_SLICES",
    "CorruptionOperator",
    "PlantedCell",
    "PlantedEpisode",
    "generate_planted_curriculum",
    "plant_episode",
]

CorruptionOperator = Literal[
    "fd_swap",
    "typo_inject",
    "bound_breach",
    "missing_sentinel",
    "scale_shift",
]


@dataclass(frozen=True, kw_only=True)
class PlantedCell:
    """One planted corruption with exact provenance and provability metadata."""

    row: int
    column: str
    clean_value: str
    dirty_value: str
    operator: CorruptionOperator
    provable: bool
    inferability: InferabilityLabel


@dataclass(frozen=True, kw_only=True)
class PlantedEpisode:
    """Self-contained planted-bug episode with clean, dirty, and schema payloads."""

    episode_id: str
    corpus: Literal["hospital", "flights", "rayyan", "tax"]
    clean_df: pd.DataFrame
    dirty_df: pd.DataFrame
    schema_dict: dict[str, Any]
    planted_cells: tuple[PlantedCell, ...]

    def to_eval_task(self) -> Task:
        """Project this planted episode into a standard :class:`Task`."""
        gt = tuple(
            GroundTruthCell(
                row=cell.row,
                column=cell.column,
                dirty_value=cell.dirty_value,
                clean_value=cell.clean_value,
            )
            for cell in self.planted_cells
            if cell.provable
        )
        return Task(
            name=f"{self.corpus}_{self.episode_id}",
            dirty_df=self.dirty_df.copy(),
            canonical_columns=tuple(str(c) for c in self.clean_df.columns),
            metadata={
                "corpus": self.corpus,
                "episode_id": self.episode_id,
                "planted_count": len(self.planted_cells),
                "provable_count": len(gt),
            },
            inferability="context_derivable",
            ground_truth=gt,
        )


def _hospital_slice() -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = [
        {
            "provider_id": "10001",
            "zip": "35233",
            "city": "BIRMINGHAM",
            "state": "AL",
            "score": "92",
        },
        {
            "provider_id": "10002",
            "zip": "35233",
            "city": "BIRMINGHAM",
            "state": "AL",
            "score": "88",
        },
        {
            "provider_id": "10003",
            "zip": "35233",
            "city": "BIRMINGHAM",
            "state": "AL",
            "score": "95",
        },
        {"provider_id": "10004", "zip": "30303", "city": "ATLANTA", "state": "GA", "score": "91"},
        {"provider_id": "10005", "zip": "30303", "city": "ATLANTA", "state": "GA", "score": "87"},
        {"provider_id": "10006", "zip": "30303", "city": "ATLANTA", "state": "GA", "score": "90"},
    ]
    schema: dict[str, Any] = {
        "columns": {
            "provider_id": "str",
            "zip": "str",
            "city": "str",
            "state": "str",
            "score": "int",
        },
        "functional_dependencies": [
            {"determinant": ["zip"], "dependent": "city"},
            {"determinant": ["zip"], "dependent": "state"},
        ],
        "domain_bounds": [{"column": "score", "min_value": 0, "max_value": 100}],
    }
    return pd.DataFrame(rows), schema


def _flights_slice() -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = [
        {"flight_id": "AA101", "carrier": "AA", "hub": "DFW", "delay_min": "12"},
        {"flight_id": "AA102", "carrier": "AA", "hub": "DFW", "delay_min": "5"},
        {"flight_id": "AA103", "carrier": "AA", "hub": "DFW", "delay_min": "18"},
        {"flight_id": "DL201", "carrier": "DL", "hub": "ATL", "delay_min": "8"},
        {"flight_id": "DL202", "carrier": "DL", "hub": "ATL", "delay_min": "15"},
        {"flight_id": "DL203", "carrier": "DL", "hub": "ATL", "delay_min": "4"},
    ]
    schema: dict[str, Any] = {
        "columns": {"flight_id": "str", "carrier": "str", "hub": "str", "delay_min": "int"},
        "functional_dependencies": [{"determinant": ["carrier"], "dependent": "hub"}],
        "domain_bounds": [{"column": "delay_min", "min_value": 0, "max_value": 300}],
    }
    return pd.DataFrame(rows), schema


def _rayyan_slice() -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = [
        {"article_id": "R1", "issn": "0140-6736", "journal": "LANCET", "pages": "14"},
        {"article_id": "R2", "issn": "0140-6736", "journal": "LANCET", "pages": "11"},
        {"article_id": "R3", "issn": "0140-6736", "journal": "LANCET", "pages": "9"},
        {"article_id": "R4", "issn": "0028-0836", "journal": "NATURE", "pages": "7"},
        {"article_id": "R5", "issn": "0028-0836", "journal": "NATURE", "pages": "8"},
        {"article_id": "R6", "issn": "0028-0836", "journal": "NATURE", "pages": "12"},
    ]
    schema: dict[str, Any] = {
        "columns": {"article_id": "str", "issn": "str", "journal": "str", "pages": "int"},
        "functional_dependencies": [{"determinant": ["issn"], "dependent": "journal"}],
        "domain_bounds": [{"column": "pages", "min_value": 1, "max_value": 200}],
    }
    return pd.DataFrame(rows), schema


def _tax_slice() -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = [
        {"record_id": "T1", "area_code": "206", "state": "WA", "rate_pct": "6"},
        {"record_id": "T2", "area_code": "206", "state": "WA", "rate_pct": "6"},
        {"record_id": "T3", "area_code": "206", "state": "WA", "rate_pct": "6"},
        {"record_id": "T4", "area_code": "617", "state": "MA", "rate_pct": "6"},
        {"record_id": "T5", "area_code": "617", "state": "MA", "rate_pct": "6"},
        {"record_id": "T6", "area_code": "617", "state": "MA", "rate_pct": "6"},
    ]
    schema: dict[str, Any] = {
        "columns": {"record_id": "str", "area_code": "str", "state": "str", "rate_pct": "int"},
        "functional_dependencies": [{"determinant": ["area_code"], "dependent": "state"}],
        "domain_bounds": [{"column": "rate_pct", "min_value": 0, "max_value": 20}],
    }
    return pd.DataFrame(rows), schema


CANONICAL_CLEAN_SLICES: dict[
    Literal["hospital", "flights", "rayyan", "tax"],
    tuple[pd.DataFrame, dict[str, Any]],
] = {
    "hospital": _hospital_slice(),
    "flights": _flights_slice(),
    "rayyan": _rayyan_slice(),
    "tax": _tax_slice(),
}


def _inject_typo(value: str) -> str:
    if len(value) >= 2:
        return value + value[-1]
    return value + "X"


def plant_episode(
    corpus: Literal["hospital", "flights", "rayyan", "tax"],
    *,
    operator: CorruptionOperator,
    seed: int = 0,
) -> PlantedEpisode:
    """Deterministically plant one controlled corruption onto a clean corpus slice."""
    if corpus not in CANONICAL_CLEAN_SLICES:
        raise ValueError(
            f"Unsupported corpus {corpus!r}; must be hospital, flights, rayyan, or tax."
        )
    base_df, schema_dict = CANONICAL_CLEAN_SLICES[corpus]
    clean_df = base_df.copy()
    dirty_df = base_df.copy()
    rng = random.Random(seed)

    fds: list[dict[str, Any]] = list(schema_dict.get("functional_dependencies", []))
    bounds: list[dict[str, Any]] = list(schema_dict.get("domain_bounds", []))
    fd_dep_col = str(fds[0]["dependent"])
    num_col = str(bounds[0]["column"])

    target_row = rng.randrange(len(clean_df))
    if operator == "fd_swap":
        col = fd_dep_col
        clean_val = str(clean_df.at[target_row, col])
        other_vals = sorted({str(v) for v in clean_df[col] if str(v) != clean_val})
        dirty_val = other_vals[0] if other_vals else _inject_typo(clean_val)
        provable = True
        inferability: InferabilityLabel = "context_derivable"
    elif operator == "typo_inject":
        col = fd_dep_col
        clean_val = str(clean_df.at[target_row, col])
        dirty_val = _inject_typo(clean_val)
        provable = True
        inferability = "context_derivable"
    elif operator == "bound_breach":
        col = num_col
        clean_val = str(clean_df.at[target_row, col])
        max_v = int(bounds[0]["max_value"])
        dirty_val = str(max_v + 500)
        provable = False
        inferability = "not_inferable_from_prompt"
    elif operator == "missing_sentinel":
        col = num_col
        clean_val = str(clean_df.at[target_row, col])
        dirty_val = "N/A"
        provable = False
        inferability = "not_inferable_from_prompt"
    elif operator == "scale_shift":
        col = num_col
        clean_val = str(clean_df.at[target_row, col])
        dirty_val = str(max(1, int(clean_val)) * 100)
        provable = False
        inferability = "not_inferable_from_prompt"
    else:
        raise ValueError(f"Unknown operator: {operator}")

    dirty_df.at[target_row, col] = dirty_val
    id_digest = hashlib.sha256(
        json.dumps(
            {"corpus": corpus, "operator": operator, "seed": seed, "row": target_row, "col": col},
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:10]
    planted = PlantedCell(
        row=target_row,
        column=col,
        clean_value=clean_val,
        dirty_value=dirty_val,
        operator=operator,
        provable=provable,
        inferability=inferability,
    )
    return PlantedEpisode(
        episode_id=f"{operator}_{seed}_{id_digest}",
        corpus=corpus,
        clean_df=clean_df,
        dirty_df=dirty_df,
        schema_dict=json.loads(json.dumps(schema_dict)),
        planted_cells=(planted,),
    )


def generate_planted_curriculum(*, seeds_per_pair: int = 1) -> list[PlantedEpisode]:
    """Generate a deterministic multi-corpus planted curriculum across all 5 operators."""
    operators: tuple[CorruptionOperator, ...] = (
        "fd_swap",
        "typo_inject",
        "bound_breach",
        "missing_sentinel",
        "scale_shift",
    )
    corpora: tuple[Literal["hospital", "flights", "rayyan", "tax"], ...] = (
        "hospital",
        "flights",
        "rayyan",
        "tax",
    )
    episodes: list[PlantedEpisode] = []
    for corpus in corpora:
        for op in operators:
            for seed in range(max(1, seeds_per_pair)):
                episodes.append(plant_episode(corpus, operator=op, seed=seed))
    return episodes
