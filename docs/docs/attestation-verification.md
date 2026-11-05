# Attestation Verification for Third-Party Auditors

Every `dataforge repair` run can emit a portable `in-toto` v1 / DSSE attestation (`dataforge.repair.attestation/v1`) stating what changed, why it was permitted, which schema premise conferred authority, and how to reverse the write.

The attestation is designed so that **an independent party can verify the repair without trusting DataForge, running a solver, or making network calls**.

---

## What you hold and what you can prove

| What the verifier holds | Command | Checks executed | Strongest honest reading of `ok: true` |
| --- | --- | --- | --- |
| **Attestation + CSV bytes + Ed25519 public key** | `dataforge attest verify attestation.json --data repaired.csv --public-key-hex <64-hex>` | All 13 normative checks (`signature` and `data_identity` active) | The statement was signed by the holder of the key, its subject SHA-256 matches `repaired.csv` byte-for-byte, and every applied write is backed by trusted provenance or an entailed schema premise. |
| **Attestation + CSV bytes (unsigned)** | `dataforge attest verify attestation.json --data repaired.csv` | 12 active checks (`signature` reported as `skipped`) | The statement is internally coherent and matches `repaired.csv` byte-for-byte, but authorship is unverified because no cryptographic signature was checked. |
| **Attestation only (no CSV bytes)** | `dataforge attest verify attestation.json` | 11 active checks (`signature` and `data_identity` reported as `skipped`) | **Internal coherence only.** The statement's vocabulary, verdicts, reversibility metadata, entailment witnesses, and authority premise are self-consistent, and it names a SHA-256 digest of a file you have not inspected. |

!!! warning "`skipped` is not `passed`"
    Both the Python reference verifier (`dataforge/attestation/__init__.py`), the browser TypeScript verifier (`playground/web/src/attestation/verify.ts`), and the clean-room Java 17 verifier (`eval/cleanroom/armD/Verify.java`) report `data_identity` and `signature` in a separate `skipped` list whenever `--data` or a DSSE signature is absent.
    An auditor holding only the attestation JSON must **never** summarize `ok: true` with `data_identity` skipped as "the file was verified." Without `--data`, the verifier has not seen the table bytes; it has verified only that the statement is internally coherent and claims a specific SHA-256 digest (`subject[].digest.sha256`).

---

## The 13 normative checks

A conforming verifier executes thirteen named checks in order:

1. `signature` — If the document is a DSSE envelope, verifies the Ed25519 signature over `PAE(payloadType, payload)`. Reported as `skipped` on bare `in-toto` Statements. Short-circuits remaining checks on failure.
2. `envelope_recognised` — `_type` equals `https://in-toto.io/Statement/v1` and `predicateType` equals `https://dataforge.dev/RepairAttestation/v1`.
3. `version_recognised` — `predicate.attestation_version` equals `"1"`.
4. `schema_complete` — All required top-level `subject` and `predicate` fields (`tool.name`, `tool.version`, `tool.contract_version`, `produced_at`, `mode`, `applied`, `reversible`, `source`, `post`, `authority`, `fixes`, `held`, `verdicts`, `journal`, `revert_command`, `limitations`, `verification`) are present and structurally well-typed.
5. `vocabulary_closed` — Every enum value (`mode`, `verdicts.*`, `fixes[].provenance`, `fixes[].verification_strength`, `held[].review_reason`) belongs to its published closed vocabulary. Unknown strings fail closed.
6. `subject_matches_post_state` — Every entry in `subject[]` carries a 64-character lowercase hex SHA-256 equal to `post.digest.sha256` (when `applied: true`) or `source.digest.sha256` (when `applied: false`). Multi-subject statements naming a second artifact are rejected.
7. `data_identity` — When `--data` bytes are supplied, `sha256(data)` equals the expected subject digest. Reported as `skipped` when no bytes are supplied.
8. `reversibility_complete` — When `applied: true`, requires `reversible: true`, a non-empty `journal.txn_id`, and a non-empty `revert_command`.
9. `verdicts_accepting` — When `applied: true`, requires `verdicts.verifier == "accept"` and `verdicts.safety == "allow"`. On a dry run (`applied: false`), requires `verdicts.safety != "deny"`.
10. `strength_is_earned` — Re-derives each fix's verification strength from `fixes[].provenance` and membership of `fixes[].column` in `authority.authoritative_columns`. Any applied fix whose recorded or derived strength is `"plausibility_only"` is rejected.
11. `constraints_present` — When any applied fix is proven solely by schema authority (its provenance is not in `TRUSTED_PROVENANCE`), requires `authority.constraints` to be a non-empty object.
12. `witness_is_coherent` — Inspects `fixes[].witness` for functional-dependency repairs: verifies `1 <= support <= group_size`, strict majority (`support * 2 > group_size`), digest count consistency, and non-identity replacement (`new_value_digest != old_value_digest`). Reported as `skipped` when no fix carries a witness.
13. `authority_is_entailed` — Parses `authority.premise` (`dataforge.premise/v1`) and recomputes the authoritative column set from `DISCRIMINATING_COLUMN_TYPES` and `ENFORCEABLE_CONSTRAINT_KINDS`. Rejects if the recomputed set does not equal `authority.authoritative_columns` as a set.

---

## Strong vs. weak schema authority (`weak_only_columns`)

Not all enforceable schema constraints narrow a cell's value space equally:

- **Strong authority kinds** (`STRONG_AUTHORITY_CONSTRAINT_KINDS`: discriminating `columns`, `primary_key_columns`, `accepted_values`, `regex_constraints`, `domain_bounds`, `functional_dependencies`) constrain the value itself.
- **Weak authority kinds** (`WEAK_AUTHORITY_CONSTRAINT_KINDS`: `not_null_columns`, `unique_columns`) check only presence or distinctness. Declared alone, they admit arbitrary non-empty / non-colliding strings.

When a column in `authority.authoritative_columns` is covered **only** by `not_null_columns` or `unique_columns`, the `authority_is_entailed` check detail explicitly appends `weak_only_columns=[...]` so an auditor or downstream consumer can see that the column's schema authority rests solely on presence/uniqueness rather than value-domain restriction. When importing dbt manifests for repair authority, use `authoritative_schema_from_dbt_artifacts(...)` (`authority_mode="strong_only"`) to withhold weak kinds from conferring write authority.

---

## Reproducing three-language conformance

The normative specification (`specs/SPEC_repair_attestation.md`), JSON Schema (`specs/repair_attestation.schema.json`), and 35-vector golden suite (`tests/fixtures/attestation/vectors.json`) are verified continuously across three independent implementations:

1. **Python** (`dataforge/attestation/__init__.py`)
2. **TypeScript** (`playground/web/src/attestation/verify.ts`)
3. **Clean-room Java 17** (`eval/cleanroom/armD/Verify.java`, written strictly from the specification and JSON Schema without reading any repository code)

Run the three-language conformance gate locally:

```bash
python scripts/ci/attestation_conformance.py --check
```
