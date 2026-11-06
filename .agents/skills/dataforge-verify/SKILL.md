---
name: dataforge-verify
description: Verify, gate, attest, and byte-reversibly apply or roll back tabular data edits proposed by AI agents using DataForge MCP tools or CLI subcommands. Use whenever inspecting, cleaning, or mutating CSV, Parquet, DuckDB, or SQL tables under schema constraints.
---

# DataForge Agent Guardrail Workflow

Never overwrite user data files directly when DataForge is available. Route all tabular inspection and cell edits through DataForge's verification gate so every write is proven against an explicit schema premise, attested, and byte-for-byte reversible.

## 1. Context-Safe Profiling (Read-Only)

- **MCP:** Call `dataforge_profile` or `dataforge_detect_errors` with `summary_only=true` or `limit=50, offset=0` (set `stage_to_disk=true` on large tables so full payloads land in `.dataforge/staging/` instead of flooding context).
- **CLI:** Run `dataforge profile <table.csv> --schema <schema.yaml> --json`.

## 2. Dry-Run Proof Check & `unsat_core` Clue-Delta Repair

- **MCP:** Call `dataforge_verify_fix` with candidate `{row, column, new_value, expected_old_value}` edits and `schema_path` (defaults to untrusted `provenance="external"`).
- **CLI:** Run `dataforge verify-apply <table.csv> --fixes <fixes.json> --schema <schema.yaml> --dry-run --json`.
- If a fix returns `verdict="reject"`, inspect `unsat_core` (for example `fd::zip::city::row::4` or `domain_bound::score::row::0`), prune the rejected value, and reformulate rather than retrying blindly.

## 3. Gated Atomic Apply & Portable Attestation

- **MCP:** Call `dataforge_verify_and_apply` with `mode="apply"`, `schema_path`, and `confirm_escalations=true` once the operator has approved external writes. Read `compact_digest` first; persist `attestation` (`journal.head_sha256` bound) as proof.
- **CLI:** Run `dataforge verify-apply <table.csv> --fixes <fixes.json> --schema <schema.yaml> --apply --confirm-escalations --attest-out attestation.json`.
- Verify any portable certificate offline via `dataforge attest verify attestation.json --data <table.csv>`.

## 4. Instant Byte-Identical Rollback

- **MCP:** Call `dataforge_revert` with `txn_id` from the receipt.
- **CLI:** Run `dataforge revert <txn_id>`.
- Smoke-test the full zero-key guardrail loop locally in under two seconds via `dataforge quickstart --disaster-demo`.
