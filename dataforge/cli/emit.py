"""Result serialisation and attestation emission, shared by every write surface.

Why this module exists rather than a private helper on one command.

``dataforge`` has three CLI surfaces that write to a user's data -- ``repair``, ``verify-apply``
and ``watch``, derivable as the commands exposing ``--apply``. Until 2026-09-13 only ``repair``
emitted the portable attestation; the other two proved each fix, applied it reversibly, and
discarded the evidence. ``verify-apply`` did so while its ``--proposer`` help text promised
"Attribution recorded on the certificate", and it is the entry point for the declared primary
wedge, whose consumers -- an agent's operator, an auditor reading after the fact -- exist only
for that evidence.

That gap survived a test suite containing ``test_attestation_reaches_consumers.py`` because
that test imports the emitter and calls it directly. It proves the artifact is correct. It
cannot see a surface that never calls it. Keeping these functions in one module with a derived
population gate (``TestEveryWriteSurfaceCanEmitProof``) is what makes the omission detectable
instead of invisible.

The functions are deliberately import-cheap: every heavy dependency is imported inside the
function body, because ``tests/unit/test_cli_import_cost.py`` forbids loading the engine on
``dataforge --version``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from dataforge.engine.repair import RepairPipelineResult

__all__ = ["attest_result", "result_json", "write_attestation"]


def result_json(result: RepairPipelineResult, *, attestation: dict[str, Any] | None = None) -> str:
    """Serialize a repair result for CLI/MCP/CI consumers.

    ``attestation`` is merged as a SIBLING of the receipt rather than a receipt field:
    ``tests/integration/test_surface_uniformity.py`` asserts the pipeline, agent and
    external-guardrail certificates share one schema and one field set, so adding to the
    receipt would break the parity that makes those three surfaces comparable.
    """
    payload = result.model_dump(mode="json")
    if attestation is not None:
        payload.update(attestation)
    return json.dumps(payload, indent=2, sort_keys=True)


def attest_result(
    result: RepairPipelineResult,
    *,
    source_path: Path,
    schema_path: Path | None,
) -> dict[str, Any]:
    """Attest a completed repair, or say why not.

    Called on every ``--json`` run so the portable proof reaches a consumer without a second
    command. ``dataforge attest build`` remains for attesting a receipt saved earlier.

    Only an APPLIED repair is attested. A dry run has written nothing, so its subject digest
    would be the source rather than a result, and an attestation over an unchanged file
    invites being read as a certificate of a repair that did not happen. The absence is
    reported with its remedy rather than left implicit -- an unexplained missing field is the
    same defect as an unrendered outcome code.

    The declared premise is embedded from the schema FILE rather than from the parsed
    ``Schema`` object, because the dataclass has no JSON projection and inventing one would
    put an unreviewed wire format on the critical path of a normative artifact. Embedding it
    is not optional in general: ``_check_strength`` requires the constraints for any fix whose
    provenance is untrusted and which is proven by schema rather than by construction, which
    is precisely the external-proposer case -- that is, precisely ``verify-apply``, the surface
    that until 2026-09-13 never called this function.
    """
    from datetime import UTC, datetime

    from dataforge import __version__
    from dataforge.attestation import attest_repair
    from dataforge.cli.common import load_schema, load_schema_mapping
    from dataforge.witness import witnesses_for_applied_fixes

    if not result.receipt.applied:
        return {
            "attestation_unavailable": (
                "nothing was applied, so there is no post-state to attest. Re-run with "
                "--apply to obtain a portable attestation."
            )
        }

    applied = [fix.model_dump(mode="json") for fix in result.receipt.applied_fixes]
    emission = attest_repair(
        result.receipt.model_dump(mode="json"),
        subject_name=source_path.name,
        tool_version=__version__,
        produced_at=datetime.now(UTC).isoformat(),
        constraints=load_schema_mapping(schema_path) if schema_path is not None else None,
        journal_head_sha256=None,
        data_bytes=source_path.read_bytes() if source_path.is_file() else None,
        witnesses=witnesses_for_applied_fixes(
            source_path,
            applied,
            load_schema(schema_path) if schema_path is not None else None,
        ),
    )
    return emission.as_dict()


def write_attestation(payload: dict[str, Any], destination: Path) -> str | None:
    """Write the statement to ``destination``; return an error message, or None on success.

    Returns rather than raises because an unwritable attestation path must not undo a repair
    that already landed correctly. The write is the last step; the data is already committed
    and reversible via the journal. Failing the whole command here would leave the user with a
    correct file, a correct receipt, and a nonzero exit code -- inviting them to "retry" a
    mutation that already succeeded.

    Only a real statement is ever written. When the emission was withheld, the reason is
    surfaced instead: a file named ``attestation.json`` containing an explanation of why there
    is no attestation is worse than no file, because it will be archived and later read as one.
    """
    from dataforge.transactions.files import atomic_write_bytes

    statement = payload.get("attestation")
    if statement is None:
        return str(payload.get("attestation_unavailable", "no attestation was produced"))
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(
            destination,
            (json.dumps(statement, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
    except OSError as exc:
        return f"could not write the attestation to '{destination}': {exc}"
    return None
