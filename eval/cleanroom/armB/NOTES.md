# Arm B clean-room notes — normative check enumeration

Inputs: ONLY `specs/SPEC_repair_attestation.md` (MD) and `specs/repair_attestation.schema.json` (JS).

## Constants both documents agree on

- `_type` == `https://in-toto.io/Statement/v1`   (MD §6.1 example; JS `properties._type.const`)
- `predicateType` == `https://dataforge.dev/RepairAttestation/v1` (MD §6.1; JS const)
- `predicate.attestation_version` == `"1"` (MD §6.2; JS const)
- DSSE `payloadType` == `application/vnd.in-toto+json` (MD §6.1 only)
- PAE = `"DSSEv1" SP LEN(type) SP type SP LEN(body) SP body` (MD §4 only)

## Checks (MD §7 order), with rule provenance

| # | name | rule source | condition implemented |
|---|---|---|---|
| 1 | `envelope_recognised` | MD §7.1 + JS consts | `_type` and `predicateType` exactly the two URIs |
| 2 | `version_recognised` | MD §7.2 + JS const (JS does not *require* presence) | `attestation_version` present and == "1" |
| 3 | `schema_complete` | MD §6.2 table + JS `required`/type/pattern | union-of-required present, declared-type union, patterns, conditional `post` |
| 4 | `vocabulary_closed` | JS enums (5) + MD table (independent_verification) | membership in every published closed set; Provenance NOT PUBLISHED -> fail closed |
| 5 | `subject_matches_post_state` | MD §7.5 + MD §6.1 + JS `subject.description` | EVERY subject digest == post digest (applied) / source digest (dry run) |
| 6 | `data_identity` | MD §7.6 | sha256(--data bytes) == designated artifact digest; skip w/o --data |
| 7 | `reversibility_complete` | MD §7.7 (+§6.2 `revert_command` "Required when applied") | applied => reversible && journal.txn_id && revert_command |
| 8 | `verdicts_accepting` | MD §7.8 | verdicts.verifier=="accept" && verdicts.safety=="allow" |
| 9 | `strength_is_earned` | MD §7.9 + §5 + JS `verification_strength.description` + MD App.A | derived from provenance + column authority; recorded>derived REJECT; plausibility_only believed; plausibility_only while applied REJECT |
| 10 | `constraints_present` | MD §7.10 + §6.2 ("Null only when no authority existed") + §6.3 + JS `constraints.description` | proven untrusted fix => embedded constraints; constraints null while authority existed => REJECT |
| 11 | `witness_coherent` | **JS ONLY** (`witness.description`). MD never mentions `witness`. Name is MINE — spec defines the obligation but not the check name. | support*2>group_size; support<=group_size; count(new_value_digest)==support; sum(counts)==group_size unless `truncated` |
| 12 | `signature` | MD §7.11 + §4 + §6.1 + App.A | DSSE Ed25519 over PAE; bare statement or no key => `unsigned`; bad sig => fail |

Total emitted: 12.

## Reading rules adopted where the two documents conflict

- **Presence**: a field required by EITHER document is required (union). Justified by JS's own
  header ("Structural validity is NECESSARY AND NOT SUFFICIENT", `required` arrays are
  *generated from one verifier's tuples*) plus MD §2 "a missing required field is a REJECT".
- **Type**: union of *declared* type sets; a document that declares nothing contributes
  nothing (silence neither permits nor forbids). So `model` = object|string|null;
  `authority.constraints` = object|null (JS declares no type at all).
- **Substrate missing** for a check: `fail` (fail-closed, MD §7 "MUST fail closed on
  anything unrecognised"), except where the spec designates otherwise: `data_identity`
  without `--data` = skip; `signature` unsigned/no-key = `unsigned`; `witness_coherent`
  with no witnesses = skip.
- **Provenance**: the promised closed set is published NOWHERE. Only `external` and
  `entity_consensus` are exhibited as valid (App.A). Anything else is "unrecognised" and
  MD §2/§6.2/§7/§9 + App.A row 6 all demand REJECT. Consequence recorded: App.A row 1
  ("Deterministic fix ... verifies") is unreachable because that provenance token is never
  named, so no genuinely deterministic attestation can pass this leg.
