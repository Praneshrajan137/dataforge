# SPEC: repair-attestation

> Status: Accepted
> Owner: dataforge
> Last updated: 2026-09-16

## 1. Purpose

Define `dataforge.repair.attestation/v1`: a portable, versioned, signable statement that
a specific mutation to a specific dataset was verified and is reversible, checkable by a
third party who does not have DataForge installed and does not trust whoever produced
the file.

The product's thesis is that trust is mechanical. That only holds if the proof is
*consumable*. Today it is not: the receipt is dumped to stdout, reprojected lossily over
HTTP, wrapped a third way by the browser, carries no tool version or timestamp, embeds
none of the constraints it was verified against, is joined to the transaction journal by
a bare string, and is unsigned. `docs/STRATEGY.md` states the consequence plainly: *"A
certificate with a named consumer is a product; one without is a log line."*

This spec turns the log line into an artifact.

## 2. Outcomes

- [x] One normative wire format with a published JSON Schema and a stable
      `predicateType` URI. Schema: [repair_attestation.schema.json](repair_attestation.schema.json),
      **generated** from the verifier's own required-field tuples and the closed
      vocabularies by `scripts/ci/generate_attestation_schema.py`, and enforced by
      `make lint`. It was promised here and absent until 2026-08-29, while §6.2 below
      already cited it as the normative source of the enums.
- [x] A **normative** verification tier that is pure-stdlib, solver-free, and
      reimplementable in any language from **the artifacts named in §3.1**. This item read
      "from this document alone" until 2026-09-16, and that was false and measurably so:
      §6.2 declines to restate the closed vocabularies three paragraphs later, so the
      document contradicted itself. A clean-room Java verifier built from the markdown alone
      reached 17 of 26 committed vectors and **accepted five documents this project's own
      verifier rejects** ([docs/trust/specification-sufficiency.md](../docs/trust/specification-sufficiency.md)).
- [ ] Two independent conforming implementations (Python and TypeScript) that agree on
      every committed test vector, including every rejection case. **Unchecked deliberately,
      2026-09-16.** Two implementations agree, but the TypeScript one was *ported* from the
      Python, not written from this document: nine user-facing message strings and one code
      comment are character-identical apart from renamed locals. Their agreement is therefore
      not evidence about this document, which is the property the item was meant to certify.
- [ ] Committed golden vectors covering acceptance and each distinct rejection reason.
- [ ] Fails closed: an unknown enum value, a missing required field, or an unrecognised
      version is a REJECT, never a pass-with-warning.
- [ ] Optional DSSE signing that binds the payload to a keyholder, with unsigned
      attestations reported as `unsigned` and never as authentic.

## 3. Scope

### 3.1 The normative surface

Added 2026-09-16, because "reimplementable from this document alone" was false and nothing
said which artifacts an implementer actually needs. The specification is **these three
files together**, and an implementation is conforming if it agrees with them:

| Artifact | Carries |
|---|---|
| `specs/SPEC_repair_attestation.md` | the envelope, the predicate field table, the normative check list and its conditions |
| [repair_attestation.schema.json](repair_attestation.schema.json) | the required-field sets and **every closed vocabulary**, generated from the verifier so it cannot drift |
| `tests/fixtures/attestation/vectors.json` | the conformance suite, including the exact check name each rejection must report |

The third is normative and was not previously named as such. The vectors assert *which
named checks fail*, not merely accept-or-reject, so an implementation that rejects the right
document via the wrong check is non-conforming — which means **the check names are part of
the wire contract**. A clean-room implementation derived the witness rule correctly from the
schema and still failed four vectors because it called the check `witness_coherent` rather
than `witness_is_coherent`. Names that are load-bearing must be published, and §7 is where
they are published.

The honest bound on this arrangement: the schema is **generated from the reference
verifier**. Agreement reached through it is agreement with a projection of our
implementation, not with a human-authored specification. That is weaker than it sounds and
is stated here rather than in a footnote.

**IN**:

- The statement envelope, the predicate schema, and the normative check list.
- Canonicalisation and signing rules.
- Golden vectors and the cross-implementation conformance requirement.

**OUT**:

- **Key distribution and trust roots.** Signing proves a keyholder produced the payload.
  Deciding *which* keys to trust is deployment policy. No transparency log, no Sigstore
  or Rekor integration, no public root. Stating this is part of the promise: an
  attestation format that implied a trust root it does not have would be the same class
  of overclaim this project has corrected before.
- **Re-execution.** Re-running the SMT verifier is the advisory tier (section 7) and is
  explicitly not part of the normative spec.
- **Semantic correctness of the repair.** The attestation says a change was verified
  against stated constraints and is reversible. It does not say the new value is *true*.

## 4. Constraints

- Compatibility: Python `>=3.11,<3.13`. The normative verifier imports only the standard
  library plus `dataforge.domain.vocabulary` (itself stdlib-only).
- Structure: an [in-toto Statement v1] object. `subject` is content-addressed;
  `predicateType` identifies the schema.
- Signing: a [DSSE] envelope. `SIGNATURE = Sign(PAE(UTF8(PAYLOAD_TYPE), SERIALIZED_BODY))`
  where `PAE(type, body) = "DSSEv1" + SP + LEN(type) + SP + type + SP + LEN(body) + SP + body`.
- Safety: producing or verifying an attestation must never mutate user data.

## 5. Prior decisions

- 2026-08-13 (`DECISIONS.md`): the certificate carried a stale copy of the trust
  vocabulary. All closed vocabularies now come from `dataforge/domain/vocabulary.py`, and
  this format embeds them by reference to that single source.
- 2026-08-09 (`docs/trust/authority-is-mutable.md`): authority is per column, never per
  table. The predicate therefore records `authoritative_columns`, and a `proven` label on
  an untrusted provenance is credited only on a covered column.
- `docs/trust/certification-promises.md`: a certified threshold is a claim about a *set*,
  never about one cell. This format inherits that limit and does not soften it.

## 6. The format

### 6.1 Envelope

Unsigned, the artifact is a bare in-toto Statement:

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    { "name": "hospital.csv", "digest": { "sha256": "<post-state hex>" } }
  ],
  "predicateType": "https://dataforge.dev/RepairAttestation/v1",
  "predicate": { }
}
```

Signed, that Statement becomes the DSSE `SERIALIZED_BODY`:

```json
{
  "payload": "<base64(statement JSON)>",
  "payloadType": "application/vnd.in-toto+json",
  "signatures": [{ "keyid": "<hex>", "sig": "<base64>" }]
}
```

`subject` names the artifact the attestation is *about*: for an applied repair, the
repaired bytes; for a dry run, the unchanged source. Subjects are matched by digest, so
a renamed file still verifies.

**Why signing bytes and not canonical JSON.** DSSE signs the payload bytes it carries,
so there is no canonical-JSON rule to agree on. This is not incidental. The transaction
journal already demonstrates the failure mode: `dataforge/transactions/log.py` computes
its hash preimage with compact separators but writes the on-disk line with default
separators, so the bytes on disk are not the bytes hashed, and a reimplementation must
rediscover that by experiment. A format whose integrity depends on two parties
independently producing byte-identical JSON has a latent interoperability bug. Verifiers
MUST NOT re-parse the envelope after signature verification to obtain the payload.

### 6.2 Predicate

| Field | Type | Required | Notes |
|---|---|---|---|
| `attestation_version` | `"1"` | yes | Unrecognised value is a REJECT, not a warning. |
| `tool.name` | string | yes | `"dataforge"`. |
| `tool.version` | string | yes | The receipt has never carried this. Without it a reader cannot tell which verifier's semantics applied. |
| `tool.contract_version` | string | yes | The repair contract, distinct from this format's version. |
| `produced_at` | RFC 3339 UTC | yes | The receipt has no timestamp today. |
| `mode` | `"apply" \| "dry_run"` | yes | A dry run attests intent, not a mutation. |
| `applied` | bool | yes | |
| `reversible` | bool | yes | |
| `source.digest.sha256` | hex(64) | yes | Pre-state. |
| `post.digest.sha256` | hex(64) | when `applied` | Post-state; MUST equal the subject digest. |
| `authority.authoritative_columns` | string[] | yes | May be empty. Empty means only a deterministic fix can honestly be `proven`. |
| `authority.accepted_constraint_ids` | string[] | yes | |
| `authority.constraints_digest.sha256` | hex(64) \| null | yes | Digest of the constraint set. |
| `authority.constraints` | object \| null | yes | **The constraint set embedded in full.** Null only when no authority existed. |
| `fixes[]` | object[] | yes | One entry per applied cell; empty for a dry run. |
| `fixes[].row` | int >= 0 | yes | |
| `fixes[].column` | string | yes | |
| `fixes[].provenance` | `Provenance` | yes | Closed vocabulary. Unknown value is a REJECT. |
| `fixes[].verification_strength` | `VerificationStrength` | yes | **Not nullable.** Absent was previously read as proven. |
| `fixes[].detector_id` | string | yes | |
| `fixes[].witness` | object | no | **Added to this table 2026-09-16; it was emitted from 2026-08-29 and documented only in the JSON Schema.** The evidence a constraint-derived write rested on, as data: the entailing constraint, the determinant group's value distribution, and the written value — all values as `sha256(value)[:16]`, never plaintext. Structure and coherence conditions in [the JSON Schema](repair_attestation.schema.json) and in §7.12. |
| `held[]` | object[] | yes | Held proposals, each with a `review_reason` from the closed vocabulary. |
| `verdicts.verifier` | `VerifierVerdict` | yes | |
| `verdicts.safety` | `SafetyVerdict` | yes | |
| `verdicts.independent_verification` | `"agreed" \| "not_run"` | yes | |
| `journal.txn_id` | string \| null | yes | |
| `journal.head_sha256` | hex(64) \| null | yes | Binds the hash chain INTO the signed payload. Previously the receipt referenced the journal only by name. |
| `revert_command` | string \| null | yes | Required when `applied`. |
| `model` | object \| null | yes | Provider and model identity when any fix is LLM-origin; null otherwise. |
| `limitations` | string[] | yes | Durable record of every downgrade. |
| `verification.checks_available` | string[] | yes | The producer's implemented normative-check **population**, not the subset runnable on this document. Derived from `dataforge.attestation.NORMATIVE_CHECKS`; it was a hardcoded ten-name literal until 2026-09-16 and omitted `signature` and `witness_is_coherent`, so every attestation ever emitted told a third party not to run the one check that breaks the strength circularity. |

Vocabularies (`Provenance`, `VerificationStrength`, `ReviewReason`, `VerifierVerdict`,
`SafetyVerdict`, and the two stated inline above — `mode` and
`verdicts.independent_verification`) are exactly those in `dataforge/domain/vocabulary.py`,
published as enums in [the JSON Schema](repair_attestation.schema.json) and generated into
TypeScript. They are not restated here, because restating a closed vocabulary is how three
drifts shipped.

**That claim was false for `Provenance` until 2026-09-16, and it was the single most
expensive defect this specification has had.** `scripts/ci/generate_attestation_schema.py`
derived every projected *value* while hand-enumerating *which* vocabularies to project —
four of the seven the normative tier enforces — so `provenance` was published as
`{"minLength": 1, "type": "string"}` and `independent_verification` as any string, boolean
or null. `Provenance` is the one vocabulary a committed vector tests. A clean-room verifier
obeying §7's instruction to *"fail closed on anything unrecognised"* therefore rejected
**20 of 26** vectors, including `valid-deterministic-applied` and `valid-signed`. The
generator now projects `dataforge.attestation.CLOSED_VOCABULARIES` and **refuses to emit a
schema** that omits any closed set the verifier enforces, so this sentence is now
mechanically true rather than aspirational. This was the fourth instance of the defect
`PRODUCT.md` §1.3 records, and the first one caught by an outside reader rather than by us.

Structural validity is **necessary and not sufficient**. The schema cannot express the
checks that carry the guarantee: re-deriving trust strength from provenance and column
authority, comparing the subject digest against the data, requiring every subject to name
the artifact the predicate describes, and verifying the DSSE signature. A document that
satisfies the schema and fails `verify_attestation` is expected, and the schema's own
`description` says so — a published schema otherwise invites "it validates, therefore it
is proven", which is the over-claim this spec exists to retire.

### 6.3 Constraints must be embedded, not referenced

`authority.constraints` carries the constraint set itself. A digest and an id list are
dangling pointers: today `reverify_certificate` must be handed the schema out-of-band as
`object | None`, and when it is absent the verifier **re-infers constraints from the
repaired data** and silently skips its cross-check. Inferring constraints from data that
was repaired to satisfy those constraints is circular, and a verifier that quietly
performs fewer checks reports the same `ok` for a weaker result. Embedding is what makes
independent verification possible at all.

### 6.4 The premise, published so authority can be recomputed

**Added 2026-09-16, and it closes the largest remaining gap in this document's central claim.**

Embedding the constraint set (§6.3) was necessary and not sufficient. Until this section existed,
`authority.constraints` was the operator's `--schema` file re-read from disk, or — via
`attest build --constraints` — any JSON object at all, and the only check that read it,
§7's check 10, asserted that it was **non-empty**. Meanwhile `authority.authoritative_columns`,
which §7's check 9 derives every fix's strength from, was accepted as given. Nothing compared the
two. **A producer could therefore emit any authoritative column list beside any constraint payload
and pass every check in §7.** `authority.constraints_digest` did not help: it digests the payload
sitting beside it, so an editor of one recomputes the other for free, and no implementation —
neither reference, nor the TypeScript verifier, nor any of the three clean-room verifiers — ever
recomputed it.

`authority.premise` fixes that. It is the declared schema **authority was actually computed from**,
projected into a format that round-trips, so a third party can apply the rule below and compare the
result to the claim. That is arithmetic on published data, which is what §1 means by verifying
without trusting the producer.

#### 6.4.1 The premise format

`authority.premise` is an object carrying `premise_format: "dataforge.premise/v1"` and any subset of
the eleven constraint fields below. **A field whose value is empty is omitted**, so a premise
declaring only column types is exactly `{"premise_format": "dataforge.premise/v1", "columns": {...}}`.

| field | shape | meaning |
| --- | --- | --- |
| `columns` | `{column: type_name}` | declared type per column |
| `pii_columns` | `[column]`, sorted | columns holding personal data |
| `primary_key_columns` | `[column]`, sorted | declared key |
| `not_null_columns` | `[column]`, sorted | must not be empty |
| `unique_columns` | `[column]`, sorted | values distinct |
| `functional_dependencies` | `[{determinant: [column], dependent: column}]` | determinant fixes dependent |
| `accepted_values` | `[{column, values: [string]}]` | closed value set |
| `regex_constraints` | `[{column, pattern}]` | value must match |
| `relationships` | `[{column, reference, reference_column}]` | referential constraint |
| `domain_bounds` | `[{column, min_value, max_value, inclusive_min, inclusive_max}]` | numeric range; bounds may be `null` |
| `aggregate_dependencies` | `[{source_column, target_column, aggregate, group_by: [column]}]` | `aggregate` is `"sum"` or `"avg"` |

The four `[column]` fields are **sorted**, because they represent unordered sets and sorting is the
only canonical form of one. The six rule arrays are **in the producer's own order and are not
sorted**, because the projection must reproduce the object it was given; rule order affects no
verdict, since the rule below unions across rules.

**A verifier MUST fail closed on this object.** Specifically it MUST reject, rather than ignore:

- a missing or unrecognised `premise_format`;
- any top-level key not in the table above;
- any key inside a rule object not in that rule's row;
- a value of the wrong shape — notably, `accepted_values` and `regex_constraints` MUST be arrays of
  objects here, even though DataForge's own convenience loader also accepts a mapping, and a
  `[column]` field MUST be an array and not a bare string;
- a rule that violates its own stated constraint, such as an `accepted_values` entry with an empty
  `values` array.

Tolerating any of these would let a premise confer authority through a channel this document cannot
express, which is the same defect as granting authority for a constraint kind no verifier enforces.

#### 6.4.2 The authority rule, published rather than described

Two sets, given here in full because a reimplementation must not have to infer them.

**The constraint kinds that may confer write authority** — eight of the eleven fields:

```
CONFERS_AUTHORITY = { columns, primary_key_columns, not_null_columns, unique_columns,
                      accepted_values, regex_constraints, domain_bounds,
                      functional_dependencies }

CONFERS_NOTHING   = { pii_columns, relationships, aggregate_dependencies }
```

`relationships` and `aggregate_dependencies` confer nothing because **no verifier can reject on
them**; `pii_columns` is a handling label, not a value constraint. Declaring a relationship on every
column once took a premise from 0 writes to 11, corrupting 10 of 14 adversarial writes, every one
stamped `proven` (`docs/trust/authority-enforcement-correspondence.md`).

**The declared types that may confer write authority** — a closed allowlist:

```
CONFERS_AUTHORITY_TYPES = { int, integer, float, decimal, real }
```

Compared case-insensitively after trimming whitespace. **Everything else confers nothing**, and this
allowlist fails closed by design. `str`, `string`, `text`, `object`, `any` and `""` are encodable but
constrain nothing. `date`, `datetime`, `timestamp`, `bool`, `uuid`, `varchar`, `numeric` and every
unrecognised spelling do narrow a value space but **no verifier can encode them**, so a proposal on
such a column returns UNKNOWN and the authority could never be acted on. Until 2026-09-16 this was a
denylist of the non-constraining spellings, which granted authority to `date` and to anything
unrecognised; an implementation built on the older reading **over-credits**, which is why the set is
given here as an allowlist rather than as prose.

**The recomputation.** A column is authoritative when any conferring kind names it:

```
named(premise, kind) =
    kind == columns                 -> { c : premise.columns[c] normalises into CONFERS_AUTHORITY_TYPES }
    kind in the four [column] sets  -> the set itself
    kind == accepted_values         -> { r.column for r in premise.accepted_values }
    kind == regex_constraints       -> { r.column for r in premise.regex_constraints }
    kind == domain_bounds           -> { r.column for r in premise.domain_bounds }
    kind == relationships           -> { r.column for r in premise.relationships }
    kind == aggregate_dependencies  -> { r.source_column, r.target_column for r in ... }
    kind == functional_dependencies -> { r.determinant... , r.dependent for r in ... }

authoritative(premise) = union of named(premise, kind) for kind in CONFERS_AUTHORITY
```

`functional_dependencies` names **both** sides: a value in either position is checked by the
dependency, so both are genuinely constrained. `aggregate_dependencies` likewise names both, though
it confers nothing.

An absent `authority.premise` yields the empty set. That is not the same as passing: see check 13.

## 7. Two tiers, named and separated


**Normative.** Pure stdlib, no solver, no inference, reimplementable from the artifacts in
§3.1. The checks, in order:

1. `envelope_recognised` - `_type` and `predicateType` are exactly the expected URIs.
2. `version_recognised` - `attestation_version` is `"1"`.
3. `schema_complete` - every required field present and well-typed. The required sets are
   `predicate.required`, `tool.required`, `authority.required` and `fixes.items.required` in
   [the JSON Schema](repair_attestation.schema.json), which are generated from the verifier's
   own tuples. Where the §6.2 table and the schema disagree, **the schema governs** and the
   table is a defect to be fixed.
4. `vocabulary_closed` - every enum value is a member of its published set. There are
   **seven** such sets, all published as enums in the JSON Schema:
   `fixes[].provenance`, `fixes[].verification_strength`, `held[].review_reason`,
   `verdicts.verifier`, `verdicts.safety`, `verdicts.independent_verification`, and `mode`.
   A value absent from its set is a REJECT. **A missing or null value is also a REJECT here**,
   not under `schema_complete`: `null` is not a member of any published set, and this check
   owns that rejection so the two do not double-report it.
5. `subject_matches_post_state` - **every** entry in `subject` carries the expected digest:
   `post.digest` when `applied`, `source.digest` otherwise. Duplicates naming the same
   artifact are permitted; one entry naming a different artifact is a REJECT, whatever its
   position. Reading only `subject[0]` let a valid attestation be extended with a subject
   nobody attested.
6. `data_identity` - SHA-256 of the supplied bytes equals **the same digest check 5 expects**:
   `post.digest` when `applied`, `source.digest` otherwise. Reported `skipped` when no bytes
   are supplied, never `passed`. (§7.6 read only "the expected digest" until 2026-09-16, which
   named neither field and left the applied and dry-run cases indistinguishable.)
7. `reversibility_complete` - `applied` implies `reversible`, `txn_id`, `revert_command`.
   `journal.head_sha256` is deliberately **not** required by this check even though §6.2
   describes it as binding the hash chain into the payload; that gap is real and recorded in
   [docs/trust/specification-sufficiency.md](../docs/trust/specification-sufficiency.md).
8. `verdicts_accepting` - **two branches, and both are normative.** When `applied`: verifier
   is `accept` **and** safety is `allow`. When not `applied`: safety is not `deny`, and the
   verifier verdict is **not consulted at all**, because a dry run reaches no verifier. Until
   2026-09-16 this item read only "verifier `accept`, safety `allow`", which made the
   committed `valid-dry-run` vector — whose verifier verdict is `not_run` — unreachable for
   any faithful implementation. Both clean-room arms rejected it.
9. `strength_is_earned` - for every fix, the recorded strength must not exceed the derived
   one. **The derivation, published here rather than described (2026-09-16):**

   ```
   derived(fix) = "proven"  if fix.provenance in TRUSTED_PROVENANCE = {"deterministic"}
                            or fix.column in authority.authoritative_columns
                = "plausibility_only"  otherwise
   ```

   A fix is *unproven* when its recorded strength is `plausibility_only` — an honest
   downgrade is always believed and never re-derived upward — or when `derived(fix)` is not
   `proven`. The check FAILS when `applied` and any fix is unproven; on a dry run it passes,
   because nothing was written. This is what Appendix A row 5 means by "REJECT while
   `applied`", and this check is the one that reports it.

   Note what this cannot do: it re-derives strength with the same rule the producer used to
   stamp it, so within one implementation it validates field consistency rather than the rule.
   Check 12 exists because of that.
10. `constraints_present` - a fix whose `proven` strength is **earned only through column
    authority** — that is, `derived(fix) == "proven"` while `fix.provenance` is not in
    `TRUSTED_PROVENANCE` — requires non-empty embedded `authority.constraints`. It is
    conditioned on the **derived** strength, not on the recorded label. A fix that already
    fails check 9 does not additionally fail this one, because that would report one defect
    twice. Until 2026-09-16 this item read "a `proven` untrusted fix requires embedded
    constraints", which reads on the recorded label; **both clean-room arms independently
    implemented that reading** and both diverged from the reference verifier on
    `reject-entity-consensus-claimed-proven`. Two isolated faithful readers agreeing against
    the implementation is evidence about the sentence, not about the readers.
11. `signature` - when signed, DSSE verification against a supplied public key. Reported
    `unsigned` when the document is a DSSE envelope and no key was supplied; `unsigned` is
    not a pass and not a failure, and an overall verdict of "no check failed" therefore does
    **not** mean authentic.
12. `witness_is_coherent` - **added to this document 2026-09-16.** It shipped in both
    implementations from 2026-08-29 and was documented only in the JSON Schema's `witness`
    description, so this list said eleven while both verifiers ran twelve.

    For every fix carrying a `witness`, all four conditions hold, over the witness's own
    stated arithmetic and **without recomputing anything from the data**:

    1. `support * 2 > group_size` — a strict majority, not a plurality;
    2. `support <= group_size`;
    3. the count recorded for `new_value_digest` in `value_digests` equals `support`;
    4. the recorded counts sum to `group_size`, unless `truncated` is true.

    Reported `skipped` when no fix carries a witness — absence of evidence must not read as
    evidence. This check is the only one that can contradict a write **without re-running the
    labelling rule that produced it**, which is what makes it the check a third party most
    needs and the one whose absence from this document mattered most: a clean-room verifier
    built from the markdown alone accepted all four attestations whose own witness arithmetic
    refutes them.
13. `authority_is_entailed` - **added 2026-09-16.** `authority.authoritative_columns` must equal
    `authoritative(authority.premise)` under §6.4.2's rule, recomputed by the verifier from the
    embedded premise. A claim naming a column the premise does not entail is a REJECT.

    This is the check that makes check 9 mean something. Check 9 derives strength from membership in
    `authoritative_columns` and therefore, as it says itself, "validates field consistency rather
    than the rule". It reads the claim as trusted input. Before this check existed, a producer could
    emit any column list beside any premise and pass all twelve preceding checks — so `proven` was an
    assertion a reader had to accept, not arithmetic a reader could repeat.

    Three cases, and the distinction is normative:

    1. `authoritative_columns` is empty — **passes**, whatever the premise. An empty claim asserts no
       authority and is entailed by anything, including an absent premise.
    2. `authoritative_columns` is non-empty and `authority.premise` is absent, unreadable, or
       violates §6.4.1 — **REJECT**. This is the case a permissive reading would get wrong by
       treating an unreadable premise as an empty one and then finding, correctly, that the empty set
       does not equal the claim. Reaching REJECT is right; reaching it by that route is not, because
       an implementation that swallows the parse error cannot tell the operator why.
    3. otherwise — **REJECT unless the two sets are equal.** Equality, not containment. A claim
       *narrower* than the premise entails is also a REJECT: it means the producer and the reader
       disagree about the rule, and a disagreement that happens to be conservative today is still a
       disagreement.

    Never `skipped`. Case 1 is a genuine pass, and reporting it as skipped would let a document with
    no authority claim look partially unverified.

    What this cannot do, stated as plainly as check 9's own limit: it verifies that the claim follows
    from the **published** premise, not that the published premise is the one the operator meant. A
    producer that embeds a premise it never repaired against produces a self-consistent document.
    Binding the premise to the data is what `data_identity` and the journal do, and neither is
    complete; `docs/trust/premise-binding.md` names the residual gap.

Every check is reported individually. A verifier MUST NOT collapse "passed" and "skipped"
into one status, and MUST fail closed on anything unrecognised.

**One exception, and it is the only place a check may stop the others (added 2026-09-16).** When
the document is a DSSE envelope and `signature` FAILS, a verifier MUST report `signature` alone
and MUST NOT report the remaining checks. The payload of a document whose signature does not
verify is unauthenticated, and reporting detailed findings about unauthenticated content invites
a reader to act on assertions nobody stands behind. The same reasoning is why §6.1 forbids
re-parsing the envelope after verification.

This was unstated until a clean-room verifier reported `signature` **and**
`subject_matches_post_state` on `reject-tampered-signed-payload` — correctly, on the letter of
"every check is reported individually", and in disagreement with the reference implementation.
It was the single residual defect after the other amendments on this page
([docs/trust/specification-sufficiency.md](../docs/trust/specification-sufficiency.md)).

**The check names above are normative.** The conformance vectors assert which named check
rejects each document, so a verifier that reaches the right verdict under a different name is
non-conforming. `dataforge.attestation.NORMATIVE_CHECKS` is the same population in executable
form, `scripts/ci/spec_correspondence.py` refuses when the two disagree, and
`AttestationCheck` refuses to construct a name absent from it.

**Advisory.** Today's `reverify_certificate`: re-runs the real SMT and Direct verifiers
to re-derive ACCEPT per cell. Strictly stronger, and strictly **not** a spec — it depends
on z3, on `infer_verification_schema`, on two specific checkers, and on DataForge's CSV
round-trip. It is labelled advisory so nobody mistakes "DataForge agrees with itself" for
independent verification.

## 8. Verification

- `tests/unit/test_attestation.py` - build, sign, verify, and every rejection path.
- `tests/fixtures/attestation/*.json` - golden vectors, machine-independent (no absolute
  paths inside any signed payload; the journal's path-dependent hashes are a known
  weakness recorded in `docs/trust/`).
- `playground/web/src/attestation/verify.test.ts` - the TypeScript implementation over
  the same vectors.
- `scripts/ci/attestation_conformance.py --check` - runs both implementations over every
  vector and fails on any disagreement. This is the gate that makes this a spec rather
  than one program's behaviour.
- `scripts/ci/mutate_attestation.py` - mutation harness; every normative check must have
  a mutant that kills it, or the shortfall is named and counted. **This file was cited here
  from 2026-08-13 and did not exist until 2026-09-16**, so §9's killing-mutant criterion was
  unenforceable for a month. That was the second artifact this document cited before it
  existed; §2 records the first.
- `scripts/ci/spec_correspondence.py --check` - derives the normative check population from
  this document's §7, from `dataforge.attestation.NORMATIVE_CHECKS`, and from the committed
  vectors, and refuses when any member of one is unnameable in the others. It is the first
  gate in this repository to read a `specs/SPEC_*.md` file at all; before it, the four false
  claims this section's siblings carried were invisible to CI by construction.

## 9. Acceptance gate

Checked against measured evidence 2026-09-16. Eleven of these twelve boxes were unchecked for
a month while the format was described elsewhere as complete; the ticks below are the ones
that now have a gate or an artifact behind them, and the crosses are named rather than left
blank.

- [x] Both implementations agree on every vector, acceptance and rejection. Enforced by
      `scripts/ci/attestation_conformance.py --check`. **But see §2: they agree because one was
      ported from the other, so this box certifies less than it appears to.**
- [x] Every normative check has a killing mutant, or the shortfall is named and counted.
      Enforced by `scripts/ci/mutate_attestation.py`.
- [x] Unknown enum, unknown version, and missing field all REJECT. Vectors
      `reject-unknown-provenance`, `reject-unknown-review-reason`, `reject-unrecognised-version`,
      `reject-missing-tool-version`.
- [x] An unsigned attestation reports `unsigned`, never `verified`.
- [x] A wrong-key signature REJECTS. Vector `reject-signature-from-a-different-key`, added
      2026-09-16 — this box was ticked by no vector for a month, because the only signature
      rejection vector tampered with the payload and verified against the *correct* key.
- [x] Supplied bytes that do not hash to the attested digest REJECT. Vectors
      `valid-data-identity-with-matching-bytes` and `reject-data-identity-mismatched-bytes`,
      added 2026-09-16. `data_identity` had **zero** vectors from the day it was written,
      because the vector format carried no field for input bytes.
- [x] Every normative check is named in §7, registered in
      `dataforge.attestation.NORMATIVE_CHECKS`, and exercised by a vector or declared exempt
      with a reason. Enforced by `scripts/ci/spec_correspondence.py --check`.
- [x] Every closed vocabulary the normative tier enforces is published as an enum in the JSON
      Schema. Enforced by `scripts/ci/generate_attestation_schema.py`, which refuses to emit a
      schema that omits one.
- [x] **The authority claim is derivable from published data rather than taken on trust.** Added and
      measured 2026-09-16. `authority.authoritative_columns` is now recomputed from
      `authority.premise` by both implementations under §6.4.2's rule, and a document whose premise
      does not entail its claim REJECTS — vectors `reject-authority-wider-than-the-premise-entails`,
      `reject-authority-from-a-non-discriminating-type`,
      `reject-authority-from-a-type-no-verifier-can-encode`,
      `reject-premise-with-an-unrecognised-key`, `reject-premise-without-a-recognised-format`.
      **This box did not exist until the gap it covers was measured, and the measurement is the
      reason to trust the tick**: on the forged document every one of the other twelve checks
      passes, and the TypeScript verifier accepted all five vectors above until check 13 was
      written. Before that, a producer could publish any column list beside any premise, so the
      most load-bearing field in the certificate was unfalsifiable.
- [ ] **A conforming implementation written from §3.1's artifacts alone, by someone who has not
      read ours.** Measured 2026-09-16 and this is the box that matters: two clean-room Java
      verifiers reached 17 of 26 and 3 of 26. Re-measurement after the amendments above is in
      [docs/trust/specification-sufficiency.md](../docs/trust/specification-sufficiency.md).
- [ ] **A named consumer.** `docs/STRATEGY.md`: *"A certificate with a named consumer is a
      product; one without is a log line."* See
      [docs/trust/attestation-consumer.md](../docs/trust/attestation-consumer.md).
- [x] `hospital` correction F1 unchanged, checked by `scripts/ci/anchor_truth.py` against the
      committed artifact. (This item read "unchanged at 0.7926" until 2026-09-07; a checklist
      that names a literal cannot notice when the literal stops being reproducible.)

## Appendix A - Toy cases

| Case | Expected |
|---|---|
| Deterministic fix, applied, no schema | verifies; `strength_is_earned` passes on provenance alone |
| `external` fix on a column in `authoritative_columns` | verifies |
| Same fix, column absent from `authoritative_columns` | REJECT (`strength_is_earned`) |
| `entity_consensus` fix, no authority, recorded `proven` | REJECT (`strength_is_earned`, and **not** `constraints_present` — see §7.10) |
| Any fix recorded `plausibility_only` | REJECT (`strength_is_earned`) while `applied` |
| `provenance: "some_future_corrector"` | REJECT (`vocabulary_closed`) |
| `attestation_version: "2"` | REJECT (`version_recognised`) |
| Payload byte flipped after signing | REJECT (`signature`) |
| Signed, no public key supplied | `signature` reported `unsigned`, overall not authentic |
| Subject digest not equal to `post.digest` | REJECT (`subject_matches_post_state`) |
| Dry run, verifier `not_run` | verifies; `verdicts_accepting` does not consult the verifier verdict (§7.8) |
| Witness whose `support` is a plurality, not a majority | REJECT (`witness_is_coherent`) |
| Signature verified against a key other than the signer's | REJECT (`signature`) |

[in-toto Statement v1]: https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md
[DSSE]: https://github.com/secure-systems-lab/dsse/blob/master/protocol.md
