"""CLI subcommand: ``dataforge quickstart`` - guided demo on a premised fixture.

Runs the full detect -> verified-repair flow on a bundled dataset so a new user
(or a skeptical reviewer) can see DataForge work in seconds, from any install
including a fresh ``pip install`` - the fixture is loaded from packaged data via
``importlib.resources``, not a path relative to the current directory.

**Why this demo ships a schema.** It used to run ``hospital_10rows.csv``, whose only
auto-appliable fix came from ``type_mismatch`` firing with no premise at all. That
detector left ``CONSTRAINT_CHECKABLE_DETECTORS`` on 2026-08-25 for want of a committed
measurement -- 156 flags and zero proposals across three real corpora, see
``docs/trust/bypass-allowlist-evidence.md`` -- so the demo silently began reporting
**zero** repairs while still printing that every fix passed an SMT proof. Two tests
guarded the sentence and neither guarded the number.

Nothing in this product now writes without a declared premise, so an honest
zero-configuration demo is not available and pretending otherwise is the failure this
file caused. ``premised_fd_10rows.csv`` declares ``state -> city`` with a nine-to-one
majority, so the write comes from ``fd_violation``, whose unconditional write precision
is measured rather than assumed. This is the same fixture the release gate migrated to
for the same reason.
"""

from __future__ import annotations

import json
import time
from importlib import resources
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel

_DISASTER_CSV_BYTES = (
    b"zip,city,score\n"
    b"35233,BIRMINGHAM,92\n"
    b"35233,BIRMINGHAM,89\n"
    b"35233,BIRMINGHAM,94\n"
    b"35233,BIRMINGHAM,91\n"
    b"35233,BIRMINGHHAM,88\n"
    b"10001,NEW YORK,95\n"
)

_DISASTER_SCHEMA_BYTES = (
    b"columns:\n"
    b"  zip: string\n"
    b"  city: string\n"
    b"  score: int\n"
    b"domain_bounds:\n"
    b"  score:\n"
    b"    min: 0\n"
    b"    max: 100\n"
    b"functional_dependencies:\n"
    b"  - determinant: [zip]\n"
    b"    dependent: city\n"
)


def _run_disaster_demo(*, json_output: bool) -> None:
    """Run a zero-key guardrail disaster demo in an isolated scratch directory."""
    from dataforge.attestation import verify_attestation
    from dataforge.cli.common import load_schema
    from dataforge.cli.emit import attest_result
    from dataforge.engine.repair import ExternalFix, VerifyAndApplyRequest, verify_and_apply
    from dataforge.transactions.log import sha256_file
    from dataforge.transactions.revert import revert_transaction

    started = time.perf_counter()
    with TemporaryDirectory() as work_dir:
        root = Path(work_dir)
        working_csv = root / "payments.csv"
        working_schema = root / "payments.schema.yaml"
        working_csv.write_bytes(_DISASTER_CSV_BYTES)
        working_schema.write_bytes(_DISASTER_SCHEMA_BYTES)

        source_sha256 = sha256_file(working_csv)
        schema = load_schema(working_schema)

        rogue_agent_batch = [
            ExternalFix(
                row=4,
                column="city",
                new_value="BIRMINGHAM",
                expected_old_value="BIRMINGHHAM",
            ),
            ExternalFix(
                row=0,
                column="score",
                new_value="999",
                expected_old_value="92",
            ),
            ExternalFix(
                row=1,
                column="city",
                new_value="ATLANTA",
                expected_old_value="BIRMINGHAM",
            ),
            ExternalFix(
                row=5,
                column="city",
                new_value="NEW YORK",
                expected_old_value="BOSTON",
            ),
        ]

        result = verify_and_apply(
            VerifyAndApplyRequest(
                source_path=working_csv,
                fixes=rogue_agent_batch,
                mode="apply",
                schema=schema,
                proposer="rogue_llm_agent",
                confirm_escalations=True,
            )
        )
        post_apply_sha256 = sha256_file(working_csv)

        attest_payload = attest_result(
            result,
            source_path=working_csv,
            schema_path=working_schema,
        )
        statement = attest_payload["attestation"]
        verification = verify_attestation(
            statement,
            data_bytes=working_csv.read_bytes(),
        )
        journal_head = str(statement["predicate"]["journal"]["head_sha256"])
        txn_id = result.receipt.txn_id
        assert txn_id is not None

        revert_transaction(txn_id, search_root=root)
        reverted_sha256 = sha256_file(working_csv)

    elapsed = time.perf_counter() - started
    unsat_by_obligation = {
        ob.obligation_id: list(ob.unsat_core) for ob in result.receipt.proof_obligations
    }
    intercepted_details: list[dict[str, Any]] = [
        {
            "row": held.row,
            "column": held.column,
            "proposed_value": held.new_value,
            "review_reason": held.review_reason,
            "unsat_core": unsat_by_obligation.get(f"row_{held.row}_{held.column}", []),
        }
        for held in result.receipt.suggested_fixes
    ]
    payload: dict[str, Any] = {
        "schema_version": "disaster_demo_v1",
        "elapsed_seconds": round(elapsed, 4),
        "zero_api_keys_required": True,
        "submitted_edits": len(rogue_agent_batch),
        "applied_proven_fixes": len(result.fixes),
        "intercepted_corruptions": len(intercepted_details),
        "intercepted_details": intercepted_details,
        "txn_id": txn_id,
        "attestation_verified": verification.ok,
        "journal_head_sha256": journal_head,
        "source_sha256": source_sha256,
        "post_apply_sha256": post_apply_sha256,
        "reverted_sha256": reverted_sha256,
        "byte_identical_revert": reverted_sha256 == source_sha256,
    }

    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        raise typer.Exit(code=0)

    console = Console()
    held_lines = "\n".join(
        f"  - row {item['row']} [bold]{item['column']}[/bold] -> {item['proposed_value']!r}: "
        f"[red]{item['review_reason']}[/red]"
        + (f" (unsat_core={item['unsat_core']})" if item["unsat_core"] else "")
        for item in intercepted_details
    )
    console.print(
        Panel(
            f"Completed zero-key guardrail simulation in [bold]{elapsed:.2f}s[/bold].\n"
            f"Submitted [bold]{len(rogue_agent_batch)}[/bold] agent edits; "
            f"intercepted [red]{len(intercepted_details)}[/red] corrupting edits (no bad writes) "
            f"and applied [green]{len(result.fixes)}[/green] SMT-proven FD repair.\n\n"
            f"Intercepted rogue edits:\n{held_lines}\n\n"
            f"Attestation verified: [green]{verification.ok}[/green] "
            f"(journal head `{journal_head[:16]}...`)\n"
            f"Byte-identical revert: [green]{reverted_sha256 == source_sha256}[/green] "
            f"(`{source_sha256[:16]}...` == `{reverted_sha256[:16]}...`)",
            title="DataForge Disaster Demo (Zero API Keys)",
            style="green",
        )
    )
    raise typer.Exit(code=0)


def quickstart(
    disaster_demo: Annotated[
        bool,
        typer.Option(
            "--disaster-demo",
            help="Simulate a rogue agent batch: intercept 3 corruptions, apply 1 proven FD fix, "
            "verify portable attestation, and revert byte-for-byte with zero API keys.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Emit machine-readable JSON output (supported with --disaster-demo).",
        ),
    ] = False,
) -> None:
    """Run a guided demo: profile and verify repairs on bundled, premised data."""
    if disaster_demo:
        _run_disaster_demo(json_output=json_output)
    console = Console()
    from dataforge.engine.repair import RepairPipelineRequest, run_repair_pipeline

    started = time.perf_counter()
    fixtures = resources.files("dataforge").joinpath("fixtures")
    with (
        resources.as_file(fixtures.joinpath("premised_fd_10rows.csv")) as packaged_csv,
        resources.as_file(fixtures.joinpath("premised_fd_10rows.schema.yaml")) as packaged_schema,
        TemporaryDirectory() as work_dir,
    ):
        # Copy packaged fixture into a writable temp dir (dry-run mutates nothing,
        # but this keeps the demo identical to a real working-file flow).
        working = Path(work_dir) / "readings.csv"
        working.write_bytes(Path(packaged_csv).read_bytes())

        from dataforge.cli.common import load_schema

        schema = load_schema(Path(packaged_schema))
        result = run_repair_pipeline(
            RepairPipelineRequest(source_path=working, mode="dry_run", schema=schema)
        )

    elapsed = time.perf_counter() - started
    issues = len(result.issues)
    fixes = len(result.fixes)
    console.print(
        Panel(
            f"Profiled a bundled dataset in [bold]{elapsed:.2f}s[/bold].\n"
            f"Detected [bold]{issues}[/bold] data-quality issue(s); "
            f"[green]{fixes}[/green] have a verified, reversible repair.\n\n"
            "The repair is earned by a declared functional dependency shipped alongside "
            "the data. Every proposed fix passed an SMT proof and the safety constitution, "
            "and would be applied inside a byte-for-byte reversible transaction.",
            title="DataForge Quickstart",
            style="green",
        )
    )
    console.print(
        Panel(
            "Try it on your own data:\n"
            "  [bold]dataforge profile your.csv[/bold]            # detect issues\n"
            "  [bold]dataforge repair your.csv --dry-run[/bold]   # preview verified repairs\n"
            "  [bold]dataforge repair your.csv --apply[/bold]     # apply (reversible)\n"
            "  [bold]dataforge revert <txn-id>[/bold]             # undo, byte-for-byte\n\n"
            "See honest per-error-class coverage on real benchmarks:\n"
            "  [bold]dataforge bench --quick[/bold]\n\n"
            "DataForge auto-applies only what it can prove correct, and it proves nothing "
            "without a declared premise: pass --schema to earn repairs. Everything else "
            "is flagged for review, never silently changed.",
            title="Next steps",
            style="cyan",
        )
    )
    raise typer.Exit(code=0)
