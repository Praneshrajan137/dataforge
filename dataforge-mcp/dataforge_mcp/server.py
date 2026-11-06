"""Executable MCP server for DataForge."""

from __future__ import annotations

import argparse
from typing import Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from dataforge_mcp.tools import (
    configure_mcp_security,
    dataforge_agent_repair,
    dataforge_apply_repairs,
    dataforge_detect_errors,
    dataforge_profile,
    dataforge_revert,
    dataforge_review_rank,
    dataforge_verify_and_apply,
    dataforge_verify_fix,
)

TransportLiteral = Literal["stdio", "streamable-http"]


_READ_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
_REVERSIBLE_WRITE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)


def create_server(*, host: str = "127.0.0.1", port: int = 8000) -> FastMCP:
    """Create a FastMCP server with all DataForge tools registered."""
    mcp = FastMCP(
        "DataForge",
        instructions=(
            "DataForge is a neuro-symbolic tabular verification and repair guardrail. "
            "Use read-only tools (profile, detect_errors, review_rank, verify_fix) to inspect "
            "and dry-check candidate edits, and reversible transaction tools "
            "(verify_and_apply, apply_repairs, agent_repair, revert) to commit proven repairs "
            "with offline-verifiable in-toto/DSSE attestations."
        ),
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
    )
    mcp.tool(
        name="dataforge_profile",
        description=(
            "Read-only table overview: row/column shape, issue counts by type, and optional "
            "paged or disk-staged (.dataforge/staging/) issue lists."
        ),
        annotations=_READ_ANNOTATIONS,
    )(dataforge_profile)
    mcp.tool(
        name="dataforge_detect_errors",
        description=(
            "Read-only issue scan: return detected tabular anomalies with optional "
            "limit/offset pagination."
        ),
        annotations=_READ_ANNOTATIONS,
    )(dataforge_detect_errors)
    mcp.tool(
        name="dataforge_verify_fix",
        description=(
            "Read-only single-cell dry check: run SafetyFilter and N-version (Z3 + Direct) "
            "verification on one proposed fix without mutating disk."
        ),
        annotations=_READ_ANNOTATIONS,
    )(dataforge_verify_fix)
    mcp.tool(
        name="dataforge_review_rank",
        description=(
            "Read-only triage queue ordering: rank detected cells highest-error-likelihood "
            "first without proposing or writing repair values."
        ),
        annotations=_READ_ANNOTATIONS,
    )(dataforge_review_rank)
    mcp.tool(
        name="dataforge_apply_repairs",
        description=(
            "Run DataForge's deterministic repair pipeline (dry_run or reversible journaled "
            "apply) under an optional authoritative schema, emitting an in-toto attestation."
        ),
        annotations=_REVERSIBLE_WRITE_ANNOTATIONS,
    )(dataforge_apply_repairs)
    mcp.tool(
        name="dataforge_verify_and_apply",
        description=(
            "External agent guardrail: verify caller-supplied cell edits and journal-commit "
            "only schema-proven fixes with an offline-verifiable DSSE attestation."
        ),
        annotations=_REVERSIBLE_WRITE_ANNOTATIONS,
    )(dataforge_verify_and_apply)
    mcp.tool(
        name="dataforge_agent_repair",
        description=(
            "Autonomous multi-step repair: apply the deterministic floor then run a bounded "
            "residual agent policy under verified reversible transactions and attestation."
        ),
        annotations=_REVERSIBLE_WRITE_ANNOTATIONS,
    )(dataforge_agent_repair)
    mcp.tool(
        name="dataforge_revert",
        description=(
            "Byte-identical rollback: verify the append-only hash-chain journal and restore "
            "a CSV to its exact pre-transaction bytes by txn_id."
        ),
        annotations=_REVERSIBLE_WRITE_ANNOTATIONS,
    )(dataforge_revert)
    return mcp


def serve(
    *,
    transport: TransportLiteral = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
    enable_apply: bool = False,
    allowed_roots: list[str] | None = None,
) -> None:
    """Run the DataForge MCP server."""
    configure_mcp_security(enable_apply=enable_apply, allowed_roots=allowed_roots)
    server = create_server(host=host, port=port)
    server.run(transport=transport)


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the console script."""
    parser = argparse.ArgumentParser(prog="dataforge-mcp")
    subparsers = parser.add_subparsers(dest="command")
    serve_parser = subparsers.add_parser("serve", help="Start the MCP server.")
    serve_parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport to use.",
    )
    serve_parser.add_argument("--host", default="127.0.0.1", help="HTTP host.")
    serve_parser.add_argument("--port", default=8000, type=int, help="HTTP port.")
    serve_parser.add_argument(
        "--enable-apply",
        action="store_true",
        help="Allow MCP clients to mutate CSV files through reversible transactions.",
    )
    serve_parser.add_argument(
        "--allowed-root",
        action="append",
        dest="allowed_roots",
        help="Filesystem root that MCP tools may read or mutate. May be repeated.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Console entry point for ``dataforge-mcp``."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        raise SystemExit(0)
    if args.command == "serve":
        serve(
            transport=args.transport,
            host=args.host,
            port=args.port,
            enable_apply=args.enable_apply,
            allowed_roots=args.allowed_roots,
        )
        return
    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
