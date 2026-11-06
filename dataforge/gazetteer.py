"""Governed external reference gazetteer for zero-LLM deterministic domain repair.

Mining functional dependencies from a dirty table's own columns risks entrenching
systematic errors when the majority of a group is wrong. A governed external
reference gazetteer (for example USPS ZIP -> City/State, CMS NPI -> Provider, or
ISO/IATA lookup tables) supplies an independent, operator-declared authority:

* **Fail-closed on ambiguous reference data.** If the reference table itself maps
  the same ``key_columns`` tuple to two different values for any ``value_column``,
  construction raises :class:`GazetteerConflictError` rather than guessing.
* **Cryptographically content-addressed.** Every gazetteer computes a canonical
  ``sha256_digest`` over its sorted ``key -> value`` tuples so provenance is
  reproducible across environments.
* **Premise-compatible.** :meth:`ReferenceGazetteer.to_schema` compiles the
  gazetteer into standard :class:`~dataforge.verifier.schema.FunctionalDependency`
  and :class:`~dataforge.verifier.schema.AcceptedValues` rules that round-trip
  through ``dataforge.premise/v1`` without widening the normative wire format.
* **Zero-LLM execution.** :meth:`ReferenceGazetteer.propose_external_fixes` scans
  a table in ``O(N)`` time with ``$0.00`` API spend and emits compare-and-set
  :class:`~dataforge.engine.repair.ExternalFix` proposals ready for
  :func:`~dataforge.engine.repair.verify_and_apply`.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dataforge.domain.premise import premise_to_canonical
from dataforge.engine.repair import ExternalFix
from dataforge.table import TableLike, cell_value, column_names, row_count
from dataforge.verifier.schema import AcceptedValues, FunctionalDependency, Schema

__all__ = [
    "GazetteerConflictError",
    "ReferenceGazetteer",
]


class GazetteerConflictError(ValueError):
    """Raised when a reference gazetteer contains conflicting values for one key."""


def _canonical_digest(
    key_columns: tuple[str, ...],
    value_columns: tuple[str, ...],
    entries: Mapping[tuple[str, ...], dict[str, str]],
) -> str:
    payload = {
        "key_columns": list(key_columns),
        "value_columns": list(value_columns),
        "entries": [
            {"key": list(key), "values": {col: entries[key][col] for col in value_columns}}
            for key in sorted(entries)
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ReferenceGazetteer:
    """Immutable, hash-addressed external lookup authority ``key_columns -> value_columns``."""

    name: str
    key_columns: tuple[str, ...]
    value_columns: tuple[str, ...]
    entries: Mapping[tuple[str, ...], dict[str, str]]
    sha256_digest: str

    @classmethod
    def from_records(
        cls,
        records: Sequence[Mapping[str, object]],
        *,
        key_columns: Sequence[str],
        value_columns: Sequence[str],
        name: str = "inline_gazetteer",
    ) -> ReferenceGazetteer:
        """Build and validate a gazetteer from in-memory mapping records."""
        keys = tuple(str(c).strip() for c in key_columns if str(c).strip())
        vals = tuple(str(c).strip() for c in value_columns if str(c).strip())
        if not keys:
            raise ValueError("key_columns must contain at least one column name.")
        if not vals:
            raise ValueError("value_columns must contain at least one column name.")
        overlap = set(keys) & set(vals)
        if overlap:
            raise ValueError(
                f"key_columns and value_columns must be disjoint; overlap={sorted(overlap)}"
            )

        table: dict[tuple[str, ...], dict[str, str]] = {}
        for idx, record in enumerate(records):
            missing = [col for col in (*keys, *vals) if col not in record]
            if missing:
                raise ValueError(f"Gazetteer record {idx} is missing required columns: {missing}")
            key_tuple = tuple(str(record[col]).strip() for col in keys)
            if any(part == "" for part in key_tuple):
                continue
            val_map = {col: str(record[col]).strip() for col in vals}
            existing = table.get(key_tuple)
            if existing is not None and existing != val_map:
                raise GazetteerConflictError(
                    f"Ambiguous gazetteer key {dict(zip(keys, key_tuple, strict=True))}: "
                    f"conflicting mappings {existing} vs {val_map}"
                )
            table[key_tuple] = val_map

        if not table:
            raise ValueError("Gazetteer contains zero valid reference entries.")

        digest = _canonical_digest(keys, vals, table)
        return cls(
            name=name.strip() or "inline_gazetteer",
            key_columns=keys,
            value_columns=vals,
            entries=table,
            sha256_digest=digest,
        )

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        *,
        key_columns: Sequence[str],
        value_columns: Sequence[str],
        name: str | None = None,
    ) -> ReferenceGazetteer:
        """Load and validate a governed reference gazetteer from a UTF-8 CSV file."""
        csv_path = Path(path)
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            records = list(reader)
        return cls.from_records(
            records,
            key_columns=key_columns,
            value_columns=value_columns,
            name=name or csv_path.stem,
        )

    def lookup(self, key: Sequence[str]) -> dict[str, str] | None:
        """Return a copy of the authoritative values for ``key``, or ``None``."""
        normalized = tuple(str(part).strip() for part in key)
        hit = self.entries.get(normalized)
        return dict(hit) if hit is not None else None

    def to_schema(self, base_schema: Schema | None = None) -> Schema:
        """Compile gazetteer dependencies and closed value domains into a :class:`Schema`."""
        columns = dict(base_schema.columns) if base_schema is not None else {}
        for col in (*self.key_columns, *self.value_columns):
            columns.setdefault(col, "str")

        existing_fds = list(base_schema.functional_dependencies) if base_schema is not None else []
        existing_fd_set = {(fd.determinant, fd.dependent) for fd in existing_fds}
        for val_col in self.value_columns:
            pair = (self.key_columns, val_col)
            if pair not in existing_fd_set:
                existing_fds.append(
                    FunctionalDependency(determinant=self.key_columns, dependent=val_col)
                )

        existing_av = list(base_schema.accepted_values) if base_schema is not None else []
        covered_av_cols = {rule.column for rule in existing_av}
        for val_col in self.value_columns:
            if val_col in covered_av_cols:
                continue
            allowed = tuple(
                sorted({mapping[val_col] for mapping in self.entries.values() if mapping[val_col]})
            )
            if allowed:
                existing_av.append(AcceptedValues(column=val_col, values=allowed))

        if base_schema is None:
            return Schema(
                columns=columns,
                functional_dependencies=tuple(existing_fds),
                accepted_values=tuple(existing_av),
            )
        return Schema(
            columns=columns,
            functional_dependencies=tuple(existing_fds),
            pii_columns=base_schema.pii_columns,
            primary_key_columns=base_schema.primary_key_columns,
            not_null_columns=base_schema.not_null_columns,
            unique_columns=base_schema.unique_columns,
            accepted_values=tuple(existing_av),
            regex_constraints=base_schema.regex_constraints,
            relationships=base_schema.relationships,
            domain_bounds=base_schema.domain_bounds,
            aggregate_dependencies=base_schema.aggregate_dependencies,
        )

    def to_canonical_premise(self, base_schema: Schema | None = None) -> dict[str, Any]:
        """Project the gazetteer's compiled schema into ``dataforge.premise/v1``."""
        return premise_to_canonical(self.to_schema(base_schema))

    def propose_external_fixes(self, df: TableLike) -> list[ExternalFix]:
        """Emit deterministic compare-and-set :class:`ExternalFix` edits for mismatched cells."""
        present_cols = set(column_names(df))
        if not set(self.key_columns).issubset(present_cols):
            return []
        target_cols = [col for col in self.value_columns if col in present_cols]
        if not target_cols:
            return []

        fixes: list[ExternalFix] = []
        total = row_count(df)
        for row_idx in range(total):
            key_tuple = tuple(cell_value(df, row_idx, col).strip() for col in self.key_columns)
            if any(part == "" for part in key_tuple):
                continue
            ref = self.entries.get(key_tuple)
            if ref is None:
                continue
            for val_col in target_cols:
                raw_current = cell_value(df, row_idx, val_col)
                expected = ref[val_col]
                if raw_current != expected:
                    fixes.append(
                        ExternalFix(
                            row=row_idx,
                            column=val_col,
                            new_value=expected,
                            expected_old_value=raw_current,
                        )
                    )
        return fixes
