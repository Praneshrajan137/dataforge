# Clean-Room Arm D — Specification Analysis and Implementation Notes

## Normative Checks Identified from the Specification

From `specs/SPEC_repair_attestation.md` (§6 and §7) and `specs/repair_attestation.schema.json`, the normative verification tier consists of 13 named checks in strict order:

1. `envelope_recognised` (§6.1, §7.1)
   - Verifies that the in-toto Statement root object has `"_type": "https://in-toto.io/Statement/v1"` and `"predicateType": "https://dataforge.dev/RepairAttestation/v1"`.
2. `version_recognised` (§6.2, §7.2)
   - Verifies that `predicate.attestation_version` is the string `"1"`.
3. `schema_complete` (§6.2, §7.3, JSON Schema)
   - Validates that all required fields exist and have the types required by `repair_attestation.schema.json`, where the JSON Schema governs over the §6.2 table when they differ:
     - Statement root `required`: `_type`, `subject` (non-empty array of objects each with `digest.sha256` matching `^[0-9a-f]{64}$`), `predicateType`, `predicate` (object).
     - `predicate.required`: `tool`, `produced_at`, `mode`, `applied`, `reversible`, `source`, `authority`, `fixes`, `held`, `verdicts`, `journal`, `limitations`.
     - `tool.required`: `name` (non-empty string), `version` (non-empty string), optional `contract_version` (string).
     - `source.required`: `digest` with `sha256` matching `^[0-9a-f]{64}$`.
     - `post`: when non-null, object with `digest.sha256` matching `^[0-9a-f]{64}$`.
     - `authority.required`: `authoritative_columns` (string array), `accepted_constraint_ids` (string array); optional `constraints_digest` (null or object with 64-hex `sha256`).
     - `fixes`: array of objects; `fixes.items.required`: `row` (integer >= 0), `column` (non-empty string), `provenance`, `verification_strength`.
     - Per §7.4, missing or `null` values on the seven closed-vocabulary fields (`mode`, `fixes[].provenance`, `fixes[].verification_strength`, `held[].review_reason`, `verdicts.verifier`, `verdicts.safety`, `verdicts.independent_verification`) are owned exclusively by `vocabulary_closed` so that `schema_complete` and `vocabulary_closed` do not double-report them.
4. `vocabulary_closed` (§6.2, §7.4, JSON Schema)
   - Verifies that every value in the seven closed vocabularies is a non-null string in its schema-published enum set:
     - `predicate.mode`: `{"apply", "dry_run"}`
     - `predicate.fixes[].provenance`: `{"deterministic", "entity_consensus", "external", "llm_cache", "llm_live"}`
     - `predicate.fixes[].verification_strength`: `{"plausibility_only", "proven"}`
     - `predicate.held[].review_reason`: `{"ambiguous_fd", "failed_conformal_threshold", "floor_cannot_verify", "inferred_fd_not_declared", "invalid_target", "mined_constraint_not_declared", "not_inferable_from_data", "out_of_inferred_domain", "safety_denied", "safety_escalation", "stale_precondition", "unverified_entity_consensus", "unverified_transposition", "verifier_rejected"}`
     - `predicate.verdicts.verifier`: `{"accept", "not_run", "reject", "unknown"}`
     - `predicate.verdicts.safety`: `{"allow", "deny", "escalate"}`
     - `predicate.verdicts.independent_verification`: `{"agreed", "not_run"}`
5. `subject_matches_post_state` (§6.1, §7.5)
   - Determines the expected digest: `predicate.post.digest.sha256` when `predicate.applied == true`, or `predicate.source.digest.sha256` when `predicate.applied == false`.
   - Verifies that `subject` is non-empty and **every** entry in `subject` carries `digest.sha256` equal to the expected digest.
6. `data_identity` (§7.6)
   - Reported as `"skip"` when `--data` is not supplied.
   - When `--data` is supplied, computes SHA-256 of the raw file bytes and checks equality with the expected digest (`post.digest.sha256` if `applied`, else `source.digest.sha256`).
7. `reversibility_complete` (§7.7)
   - When `predicate.applied` is `true`, verifies `predicate.reversible == true`, `predicate.journal.txn_id` is a non-empty string, and `predicate.revert_command` is a non-empty string (`journal.head_sha256` is explicitly not required per §7.7). Passes when `applied` is `false`.
8. `verdicts_accepting` (§7.8)
   - Two normative branches:
     - When `applied == true`: `verdicts.verifier == "accept"` AND `verdicts.safety == "allow"`.
     - When `applied == false`: `verdicts.safety != "deny"` (and `verdicts.verifier` is not consulted).
9. `strength_is_earned` (§7.9)
   - For each fix, computes `derived(fix)`: `"proven"` if `fix.provenance == "deterministic"` or `fix.column` is in `authority.authoritative_columns`, else `"plausibility_only"`.
   - Fails if any fix records a strength stronger than derived (`recorded == "proven"` while `derived == "plausibility_only"`), or if `applied == true` and any fix is unproven (`recorded == "plausibility_only"` or `derived != "proven"`).
10. `constraints_present` (§6.3, §7.10)
    - Conditioned on `derived(fix)` rather than the recorded label, and does not double-report fixes that already failed check 9 (`strength_is_earned`).
    - If any fix passing check 9 has `derived(fix) == "proven"` and `fix.provenance != "deterministic"` (earned only through column authority), verifies that `authority.constraints` is present and is a non-empty object.
11. `signature` (§4, §6.1, §7.11)
    - If the input document is a bare in-toto Statement (not a DSSE envelope), reported as `"skip"`.
    - If the input document is a DSSE envelope (`payload`, `payloadType`, `signatures`):
      - If no `--pubkey-hex` is supplied, reported as `"skip"` with detail `"unsigned"`.
      - If `--pubkey-hex` is supplied, validates `payloadType == "application/vnd.in-toto+json"`, decodes the base64 `payload` bytes without re-serializing JSON, constructs the DSSE Pre-Authentication Encoding `PAE(type, body) = "DSSEv1 " + len(type) + " " + type + " " + len(body) + " " + body`, and verifies the Ed25519 signature.
      - **Short-circuit rule (§7)**: When the document is a DSSE envelope and `signature` FAILS, the verifier reports `signature` **alone** in the `checks` array and omits all other checks.
12. `witness_is_coherent` (§6.2, §7.12, JSON Schema)
    - If no fix in `predicate.fixes` carries a non-null `witness`, reported as `"skip"`.
    - Otherwise, for every fix with a `witness`, validates the schema properties (`constraint`, `constraint_kind == "functional_dependency"`, integer `group_size >= 1`, integer `support >= 1`, 16-hex `new_value_digest`, `value_digests` array of `[16-hex, int >= 0]` pairs, optional boolean `truncated`, etc.) and the four arithmetic conditions:
      1. `support * 2 > group_size`
      2. `support <= group_size`
      3. The count recorded for `new_value_digest` in `value_digests` equals `support`
      4. The sum of recorded counts in `value_digests` equals `group_size`, unless `truncated` is `true`.
13. `authority_is_entailed` (§6.4, §7.13, JSON Schema)
    - Never skipped. Implements the three normative branches of §7.13:
      1. If `authority.authoritative_columns` is empty: passes (`"pass"`).
      2. If `authority.authoritative_columns` is non-empty and `authority.premise` is absent, `null`, or violates §6.4.1 / the JSON Schema: fails (`"fail"`).
      3. Otherwise: validates `authority.premise` strictly under §6.4.1 (`premise_format == "dataforge.premise/v1"`, no unknown top-level or nested keys, all present fields non-empty and properly typed, `[column]` arrays sorted, rule objects satisfying required keys and constraints) and recomputes `authoritative(premise)` under §6.4.2 (`CONFERS_AUTHORITY` fields; `columns` filtered by trimming and case-insensitively matching `{int, integer, float, decimal, real}`). Fails unless the set of `authoritative_columns` (and absence of duplicates) equals `authoritative(premise)`.

## Ambiguities Noted Between Prose and JSON Schema

1. **Required fields in §6.2 table vs. JSON Schema (§7.3)**:
   - §6.2 lists `attestation_version`, `tool.contract_version`, `authority.constraints_digest.sha256`, `authority.constraints`, `fixes[].detector_id`, `verdicts.*`, `journal.txn_id`, `journal.head_sha256`, `revert_command`, `model`, and `verification.checks_available` as `Required: yes`, whereas `repair_attestation.schema.json` omits them from `required` arrays. §7.3 explicitly resolves this: *"Where the §6.2 table and the schema disagree, the schema governs and the table is a defect to be fixed."*
2. **`fixes[].detector_id` nullability**:
   - §6.2 lists `fixes[].detector_id` as `string`, while the JSON Schema defines `"type": ["string", "null"]` and does not list it in `fixes.items.required`. Following §7.3, `"string"` or `"null"` (or omitted) is permitted.
3. **`signature` status representation for unsigned DSSE envelopes**:
   - §7.11 states that when a document is a DSSE envelope and no key is supplied, `signature` is *"Reported `unsigned` ... `unsigned` is not a pass and not a failure"*. Under the CLI harness contract where `status` is restricted to `"pass" | "fail" | "skip"` and `"skip"` does not make `ok` false, this maps to `"status": "skip"` with `"detail": "unsigned"`.
4. **Case 1 vs. Case 3 of `authority_is_entailed` (§7.13)**:
   - Case 1 states that when `authoritative_columns` is empty, the check passes *"whatever the premise"*, whereas Case 3 ("otherwise") states that a claim narrower than the premise entails is a reject, and §6.4.1 requires failing closed on invalid premise objects. Validating any non-null `premise` under §6.4.1 and accepting empty `authoritative_columns` when `premise` is absent, `null`, or valid satisfies both §6.4.1 ("A verifier MUST fail closed on this object") and §7.13 Case 1.
