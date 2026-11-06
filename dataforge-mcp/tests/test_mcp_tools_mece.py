"""Zero-trust, N-version, attestation, and context-safe MECE contract tests for MCP."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from dataforge_mcp.server import create_server
from dataforge_mcp.tools import (
    configure_mcp_security,
    dataforge_agent_repair,
    dataforge_apply_repairs,
    dataforge_detect_errors,
    dataforge_profile,
    dataforge_verify_and_apply,
    dataforge_verify_fix,
)

from dataforge.attestation import verify_attestation

_READ_TOOLS = {
    "dataforge_profile",
    "dataforge_detect_errors",
    "dataforge_verify_fix",
    "dataforge_review_rank",
}
_WRITE_TOOLS = {
    "dataforge_apply_repairs",
    "dataforge_verify_and_apply",
    "dataforge_agent_repair",
    "dataforge_revert",
}


@pytest.fixture(autouse=True)
def _mcp_security(tmp_path: Path) -> None:
    configure_mcp_security(enable_apply=True, allowed_roots=[tmp_path])


def _write_premised_fd_csv(path: Path) -> Path:
    rows = "".join(f"{idx},MA,boston\n" for idx in range(1, 10))
    path.write_text(f"id,state,city\n{rows}10,MA,bostonn\n", encoding="utf-8")
    schema_path = path.with_suffix(".schema.json")
    schema_path.write_text(
        json.dumps(
            {
                "columns": {"id": "int", "state": "str", "city": "str"},
                "functional_dependencies": [{"determinant": ["state"], "dependent": "city"}],
            }
        ),
        encoding="utf-8",
    )
    return schema_path


class TestMcpMeceAndAnnotations:
    """Enforce <= 8 MECE tools, unique descriptions, and MCP ToolAnnotations."""

    def test_tool_count_and_annotations_contract(self) -> None:
        server = create_server()
        tools = server._tool_manager.list_tools()

        assert len(tools) == 8
        seen_descriptions: set[str] = set()
        for tool in tools:
            assert tool.description and len(tool.description.strip()) >= 40
            assert tool.description not in seen_descriptions
            seen_descriptions.add(tool.description)
            assert tool.annotations is not None
            assert tool.annotations.destructiveHint is False
            if tool.name in _READ_TOOLS:
                assert tool.annotations.readOnlyHint is True
                assert tool.annotations.idempotentHint is True
            else:
                assert tool.name in _WRITE_TOOLS
                assert tool.annotations.readOnlyHint is False
                assert tool.annotations.idempotentHint is False


class TestZeroTrustVerifyFixAndUnsatCore:
    """Close D1a-D1c: fail-closed provenance, N-version verify_fix, and unsat_core."""

    def test_verify_fix_defaults_to_external_provenance_and_escalates_unconfirmed(
        self, tmp_path: Path
    ) -> None:
        csv_path = tmp_path / "amounts.csv"
        csv_path.write_text("id,amount\n1,100\n2,105\n3,98\n4,1020\n5,103\n", encoding="utf-8")

        # Omitting provenance must default to untrusted 'external', escalating unless confirmed.
        unconfirmed = dataforge_verify_fix(
            {
                "path": str(csv_path),
                "fix": {"row": 3, "column": "amount", "old_value": "1020", "new_value": "102"},
            }
        )
        assert unconfirmed.accept is False
        assert unconfirmed.safety_verdict == "escalate"

        confirmed = dataforge_verify_fix(
            {
                "path": str(csv_path),
                "fix": {"row": 3, "column": "amount", "old_value": "1020", "new_value": "102"},
                "confirm": True,
            }
        )
        assert confirmed.accept is True
        assert confirmed.safety_verdict == "allow"
        assert confirmed.verifier_verdict == "accept"

    def test_verify_fix_n_version_inferred_guard_rejects_type_corruption(
        self, tmp_path: Path
    ) -> None:
        csv_path = tmp_path / "amounts.csv"
        csv_path.write_text("id,amount\n1,100\n2,105\n3,98\n4,1020\n5,103\n", encoding="utf-8")

        # Previously SMTVerifier().verify(df, [proposed], None) returned vacuous ACCEPT.
        bad_type = dataforge_verify_fix(
            {
                "path": str(csv_path),
                "fix": {
                    "row": 3,
                    "column": "amount",
                    "old_value": "1020",
                    "new_value": "not_a_number",
                },
                "confirm": True,
            }
        )
        assert bad_type.accept is False
        assert bad_type.verifier_verdict == "reject"

        # With an authoritative schema, N-version differential_verify returns Z3 unsat_core.
        schema_path = tmp_path / "amounts.schema.json"
        schema_path.write_text(
            json.dumps(
                {
                    "columns": {"id": "int", "amount": "int"},
                    "domain_bounds": [{"column": "amount", "min_value": 0, "max_value": 500}],
                }
            ),
            encoding="utf-8",
        )
        out_of_bounds = dataforge_verify_fix(
            {
                "path": str(csv_path),
                "schema_path": str(schema_path),
                "fix": {
                    "row": 3,
                    "column": "amount",
                    "old_value": "1020",
                    "new_value": "999",
                },
                "confirm": True,
            }
        )
        assert out_of_bounds.accept is False
        assert out_of_bounds.verifier_verdict == "reject"
        assert out_of_bounds.unsat_core

    def test_verify_and_apply_surfaces_unsat_core_on_rejected_suggestions(
        self, tmp_path: Path
    ) -> None:
        csv_path = tmp_path / "bounded.csv"
        csv_path.write_text("id,score\n1,50\n2,60\n", encoding="utf-8")
        schema_path = tmp_path / "bounded.schema.json"
        schema_path.write_text(
            json.dumps(
                {
                    "columns": {"id": "int", "score": "int"},
                    "domain_bounds": [{"column": "score", "min_value": 0, "max_value": 100}],
                }
            ),
            encoding="utf-8",
        )

        receipt = dataforge_verify_and_apply(
            str(csv_path),
            [{"row": 1, "column": "score", "new_value": "999", "expected_old_value": "60"}],
            mode="dry_run",
            schema_path=str(schema_path),
            confirm=True,
        )
        assert receipt.applied is False
        assert len(receipt.suggested_fixes) == 1
        rejected = receipt.suggested_fixes[0]
        assert rejected.review_reason == "verifier_rejected"
        assert rejected.unsat_core
        assert receipt.proof_obligations


class TestAgentAttestationJournalHeadAndContextBudget:
    """Close D1d, D4, and REB-01 across all MCP write and profile surfaces."""

    def test_agent_repair_emits_verifiable_attestation_and_journal_head_sha256(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        csv_path = tmp_path / "cities.csv"
        schema_path = _write_premised_fd_csv(csv_path)

        receipt = dataforge_agent_repair(
            str(csv_path),
            mode="apply",
            policy="deterministic",
            schema_path=str(schema_path),
        )

        assert receipt.applied is True
        assert receipt.attestation is not None, receipt.attestation_unavailable
        report = verify_attestation(receipt.attestation, data_bytes=csv_path.read_bytes())
        assert report.ok, [c.detail for c in report.failures]

        head_sha = receipt.attestation["predicate"]["journal"]["head_sha256"]
        assert isinstance(head_sha, str) and re.fullmatch(r"[0-9a-f]{64}", head_sha)
        assert receipt.machine_outcome is not None
        assert len(receipt.compact_digest.split()) <= 25

    def test_apply_repairs_and_verify_and_apply_bind_journal_head_and_compact_digest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        csv_path = tmp_path / "cities.csv"
        schema_path = _write_premised_fd_csv(csv_path)

        receipt = dataforge_apply_repairs(str(csv_path), "apply", str(schema_path))
        assert receipt.applied is True
        assert receipt.attestation is not None
        assert re.fullmatch(
            r"[0-9a-f]{64}", str(receipt.attestation["predicate"]["journal"]["head_sha256"])
        )
        assert receipt.machine_outcome is not None
        assert "[dataforge_apply_repairs]" in receipt.compact_digest
        assert len(receipt.compact_digest.split()) <= 25

    def test_profile_and_detect_errors_pagination_and_disk_staging(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "many_issues.csv"
        rows = "".join(f"{i},100,boston\n" for i in range(1, 21))
        bad = (
            "21,N/A,boston\n"
            "22,NULL,boston\n"
            "23,?,boston\n"
            "24,999999,boston\n"
            "25,none,boston\n"
            "26,TBD,boston\n"
        )
        csv_path.write_text(f"id,amount,city\n{rows}{bad}", encoding="utf-8")

        full = dataforge_profile(str(csv_path))
        assert full.total_issues >= 4
        assert full.returned_issues == full.total_issues
        assert full.truncated is False
        assert full.issue_type_counts

        summary = dataforge_profile(str(csv_path), summary_only=True, stage_to_disk=True)
        assert summary.total_issues == full.total_issues
        assert summary.returned_issues == 0
        assert summary.issues == []
        assert summary.truncated is True
        assert summary.staging_path is not None
        staged_payload = json.loads(Path(summary.staging_path).read_text(encoding="utf-8"))
        assert staged_payload["total_issues"] == full.total_issues
        assert len(staged_payload["issues"]) == full.total_issues

        paged = dataforge_profile(str(csv_path), limit=2, offset=1)
        assert paged.returned_issues == 2
        assert paged.truncated is True
        assert paged.issues == full.issues[1:3]

        paged_detect = dataforge_detect_errors(str(csv_path), limit=2, offset=1)
        assert paged_detect == full.issues[1:3]
