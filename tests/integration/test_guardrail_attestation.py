"""The guardrail path must emit the portable proof, not just apply the fix.

``dataforge verify-apply`` is the entry point for the declared primary wedge: an untrusted
actor proposes cell edits and DataForge proves each one before it lands. For that wedge's
consumers -- an autonomous agent's operator, an auditor reading after the fact -- the
attestation *is* the product. A guardrail that proves a fix, applies it reversibly and then
discards the evidence has done the expensive half of the job and thrown away the half that
travels.

Until 2026-09-13 this surface emitted no attestation at all while its ``--proposer`` help text
promised "Attribution recorded on the certificate". These tests pin the wiring shut.

Non-circularity: the artifact is verified by ``dataforge attest verify`` from a DIFFERENT
working directory with NO ``--schema`` argument. That is what makes the claim "portable"
falsifiable -- if the constraints were not embedded in the statement, strength could not be
derived and verification would fail. Cross-IMPLEMENTATION non-circularity (the TypeScript
verifier over the same bytes) is covered by the conformance harness.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from dataforge.cli import app

runner = CliRunner()

# `score` is float -- discriminating, so it can reject a value and therefore confers proof.
# `id` is str -- it cannot reject any CSV value, so it confers none (PRODUCT.md C4).
_CSV = "id,score\n1,10\n2,20\n3,30\n"
_SCHEMA = '{"columns": {"id": "str", "score": "float"}}'


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    csv_path = tmp_path / "data.csv"
    schema_path = tmp_path / "schema.json"
    fixes_path = tmp_path / "fixes.json"
    csv_path.write_text(_CSV, encoding="utf-8")
    schema_path.write_text(_SCHEMA, encoding="utf-8")
    # A mixed batch from an untrusted proposer: one provable, one corrupting, one stale.
    fixes_path.write_text(
        json.dumps(
            [
                {"row": 0, "column": "score", "new_value": "15"},
                {"row": 1, "column": "score", "new_value": "not_a_number"},
                {"row": 2, "column": "score", "new_value": "35", "expected_old_value": "999"},
            ]
        ),
        encoding="utf-8",
    )
    return csv_path, schema_path, fixes_path


def _apply(csv_path: Path, schema_path: Path, fixes_path: Path, *extra: str) -> object:
    return runner.invoke(
        app,
        [
            "verify-apply",
            str(csv_path),
            "--fixes",
            str(fixes_path),
            "--schema",
            str(schema_path),
            "--apply",
            "--confirm-escalations",
            *extra,
        ],
    )


def test_guardrail_json_carries_an_attestation(tmp_path: Path) -> None:
    """The receipt is not the proof. A receipt must be trusted; an attestation is checkable."""
    csv_path, schema_path, fixes_path = _fixture(tmp_path)

    result = _apply(csv_path, schema_path, fixes_path, "--json")

    payload = json.loads(result.stdout)
    assert payload["receipt"]["applied"] is True, "the provable fix should have landed"
    assert "attestation" in payload, (
        "verify-apply --json emitted no attestation. The guardrail proved the fix and "
        "discarded the evidence."
    )
    statement = payload["attestation"]
    assert isinstance(statement, dict) and statement, "attestation must be a populated object"


def test_only_the_proven_fix_applies(tmp_path: Path) -> None:
    """A corrupting value and a stale precondition must not survive the gate."""
    csv_path, schema_path, fixes_path = _fixture(tmp_path)

    result = _apply(csv_path, schema_path, fixes_path, "--json")

    payload = json.loads(result.stdout)
    applied = payload["receipt"]["applied_fixes"]
    assert len(applied) == 1, f"expected exactly one proven fix, got {len(applied)}"
    assert applied[0]["row"] == 0
    # The corrupting value must be nowhere in the file.
    assert "not_a_number" not in csv_path.read_text(encoding="utf-8")
    # The stale fix must not have overwritten row 2.
    assert ",35" not in csv_path.read_text(encoding="utf-8")


def test_attest_out_artifact_verifies_elsewhere_without_the_schema(tmp_path: Path) -> None:
    """The artifact must leave the machine and still verify.

    No ``--schema`` is passed to ``attest verify``: if the declared premise were not embedded
    in the statement, strength could not be derived from column authority and this would fail.
    """
    csv_path, schema_path, fixes_path = _fixture(tmp_path)
    artifact = tmp_path / "out" / "attestation.json"
    artifact.parent.mkdir()

    applied = _apply(csv_path, schema_path, fixes_path, "--attest-out", str(artifact))
    assert applied.exit_code == 0, applied.stdout

    assert artifact.exists(), "--attest-out wrote nothing"
    statement = json.loads(artifact.read_text(encoding="utf-8"))
    assert statement, "the written artifact is empty"

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    verified = runner.invoke(
        app,
        ["attest", "verify", str(artifact), "--data", str(csv_path), "--json"],
        catch_exceptions=False,
    )
    assert verified.exit_code == 0, f"the emitted artifact did not verify:\n{verified.stdout}"
    report = json.loads(verified.stdout)
    assert report["ok"] is True, report


def test_dry_run_emits_no_attestation_but_says_why(tmp_path: Path) -> None:
    """Nothing was written, so there is no post-state to certify -- and silence is not enough.

    An attestation over an unchanged file invites being read as a certificate of a repair that
    did not happen. Withholding it is correct; withholding it *silently* would repeat the
    defect this session fixed on the human surface.
    """
    csv_path, schema_path, fixes_path = _fixture(tmp_path)

    result = runner.invoke(
        app,
        [
            "verify-apply",
            str(csv_path),
            "--fixes",
            str(fixes_path),
            "--schema",
            str(schema_path),
            "--dry-run",
            "--confirm-escalations",
            "--json",
        ],
    )

    payload = json.loads(result.stdout)
    assert "attestation" not in payload, "a dry run must not emit a certificate of a repair"
    assert "attestation_unavailable" in payload, "the absence must be explained, not implied"
    assert "--apply" in str(payload["attestation_unavailable"]), "the reason must name the remedy"
