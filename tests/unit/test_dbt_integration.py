"""Tests for dbt artifact to DataForge constraint mapping."""

from __future__ import annotations

import json
from pathlib import Path

from dataforge import schema_from_dbt_artifacts, schema_from_dbt_manifest


def _manifest() -> dict[str, object]:
    """Return a minimal dbt manifest payload with generic tests."""
    return {
        "nodes": {
            "model.demo.orders": {
                "resource_type": "model",
                "name": "orders",
                "columns": {
                    "id": {"data_type": "integer"},
                    "status": {"data_type": "string"},
                    "customer_id": {"data_type": "string"},
                },
            },
            "test.demo.not_null_orders_id": {
                "resource_type": "test",
                "test_metadata": {
                    "name": "not_null",
                    "kwargs": {"column_name": "id"},
                },
                "depends_on": {"nodes": ["model.demo.orders"]},
            },
            "test.demo.unique_orders_id": {
                "resource_type": "test",
                "test_metadata": {
                    "name": "unique",
                    "kwargs": {"column_name": "id"},
                },
                "depends_on": {"nodes": ["model.demo.orders"]},
            },
            "test.demo.accepted_orders_status": {
                "resource_type": "test",
                "test_metadata": {
                    "name": "accepted_values",
                    "kwargs": {"column_name": "status", "values": ["placed", "shipped"]},
                },
                "depends_on": {"nodes": ["model.demo.orders"]},
            },
            "test.demo.relationship_orders_customer": {
                "resource_type": "test",
                "test_metadata": {
                    "name": "relationships",
                    "kwargs": {
                        "column_name": "customer_id",
                        "to": "ref('customers')",
                        "field": "id",
                    },
                },
                "depends_on": {"nodes": ["model.demo.orders", "model.demo.customers"]},
            },
            "test.demo.unrelated": {
                "resource_type": "test",
                "test_metadata": {
                    "name": "not_null",
                    "kwargs": {"column_name": "ignored"},
                },
                "depends_on": {"nodes": ["model.demo.other"]},
            },
        }
    }


def test_schema_from_dbt_manifest_maps_supported_generic_tests() -> None:
    schema = schema_from_dbt_manifest(_manifest(), model_name="orders")

    assert schema.columns == {"id": "integer", "status": "string", "customer_id": "string"}
    assert schema.not_null_columns == frozenset({"id"})
    assert schema.unique_columns == frozenset({"id"})
    assert schema.accepted_values[0].column == "status"
    assert schema.accepted_values[0].values == ("placed", "shipped")
    assert schema.relationships[0].column == "customer_id"
    assert schema.relationships[0].reference == "ref('customers')"
    assert schema.relationships[0].reference_column == "id"


def test_schema_from_dbt_artifacts_loads_manifest_file(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")

    schema = schema_from_dbt_artifacts(manifest_path, model_unique_id="model.demo.orders")

    assert schema.not_null_columns == frozenset({"id"})


def test_authoritative_schema_from_dbt_manifest_withholds_weak_kinds() -> None:
    from dataforge.domain.premise import authoritative_columns
    from dataforge.integrations.dbt import authoritative_schema_from_dbt_manifest

    manifest = _manifest()
    # Add a weak-only column (not_null + unique, string type, no accepted_values)
    manifest["nodes"]["model.demo.orders"]["columns"]["weak_col"] = {"data_type": "string"}
    manifest["nodes"]["test.demo.not_null_orders_weak"] = {
        "resource_type": "test",
        "test_metadata": {"name": "not_null", "kwargs": {"column_name": "weak_col"}},
        "depends_on": {"nodes": ["model.demo.orders"]},
    }
    manifest["nodes"]["test.demo.unique_orders_weak"] = {
        "resource_type": "test",
        "test_metadata": {"name": "unique", "kwargs": {"column_name": "weak_col"}},
        "depends_on": {"nodes": ["model.demo.orders"]},
    }

    full_schema = schema_from_dbt_manifest(manifest, model_name="orders")
    assert "weak_col" in authoritative_columns(full_schema)

    strong_schema = authoritative_schema_from_dbt_manifest(manifest, model_name="orders")
    assert strong_schema.not_null_columns == frozenset()
    assert strong_schema.unique_columns == frozenset()
    assert strong_schema.accepted_values == full_schema.accepted_values
    assert authoritative_columns(strong_schema) == frozenset({"id", "status"})
    assert "weak_col" not in authoritative_columns(strong_schema)
