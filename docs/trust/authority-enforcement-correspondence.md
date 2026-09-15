# Authority must correspond to enforcement

**Date:** 2026-09-14
**Pre-registration:** [eval/preregistration/authority_enforcement_correspondence.md](../../eval/preregistration/authority_enforcement_correspondence.md)
**Code:** `dataforge/engine/repair.py::authoritative_columns`, `dataforge/domain/vocabulary.py`
**Harness:** `scripts/measure_trust_ledger.py`
**Data:** `eval/results/trust_ledger_adversarial.json`
**Gate:** `tests/unit/test_authority_enforcement_correspondence.py`, `tests/adversarial/test_corpus_gate.py`

## The defect

`authoritative_columns` decides which columns a declared schema has authority over, and through
`verification_strength_for` that decides which untrusted fixes are stamped **`proven`** in the
receipt and the attestation. It granted authority for **ten** `Schema` constraint kinds. The two
verifiers enforce **six**.

| `Schema` field | conferred authority | `SMTVerifier` | `DirectVerifier` |
| --- | --- | --- | --- |
| `columns` (via `type_discriminates`) | yes | yes | yes |
| `not_null_columns` | yes | `smt.py:340` | `direct.py:160` |
| `primary_key_columns` | yes | `smt.py:342` | `direct.py:160,169` |
| `unique_columns` | yes | `smt.py:356` | `direct.py:169` |
| `accepted_values` | yes | `smt.py:358` | `direct.py:181` |
| `regex_constraints` | yes | `smt.py:371` | `direct.py:197` |
| `domain_bounds` | yes | `smt.py:375` | `direct.py:209` |
| `functional_dependencies` | yes | `smt.py:246` | `direct.py:238` |
| **`relationships`** | **yes** | **absent** | **absent** |
| **`aggregate_dependencies`** | **yes** | **absent** | **absent** |
| **`pii_columns`** | **yes** | n/a — policy, not a value predicate | n/a |

`DirectVerifier` already hedged in its accept string — *"satisfied all **tracked** verifier
constraints"* (`direct.py:262`) — but the verdict is `ACCEPT`, and `ACCEPT` on a covered column is
`proven`.

### It was a specification-implementation divergence

`eval/preregistration/entailment_strength.md` lines 29-36 **specified** the discriminating set as
exactly six conditions. `relationships`, `aggregate_dependencies` and `pii_columns` appear nowhere
in that specification; they were in the implementation. The 2026-08-25 change asked *"can this
declaration reject a value?"* of **types** and fixed that case. The same question was never asked
of the other kinds.

One further divergence from that spec is documented and reasoned and was left alone:
`authoritative_columns` covers both sides of a functional dependency where the spec names only the
dependent, because a value in either position is genuinely checked by the FD.

## The measurement

The adversarial corpus already runs under two premises. It gained two more, each
`PERMISSIVE_SCHEMA` **plus exactly one added field**, so any difference is attributable to that
field and nothing else. `build_corpus()` was deliberately **not** extended: its 14 discriminable
attacks are the denominator of the published "10 of 14", and moving a denominator to accommodate a
new finding would restate history rather than add to it.

Subset `discriminable`, n=14:

| premise | applied | corrections | corruptions | held |
| --- | --- | --- | --- | --- |
| `tight` | 1 | 1 | 0 | 13 |
| `permissive` | 0 | 0 | 0 | 14 |
| `unenforceable_relationship` **before the fix** | **11** | 1 | **10** | 3 |
| `unenforceable_aggregate` **before the fix** | **11** | 1 | **10** | 3 |
| `unenforceable_relationship` after | 0 | 0 | 0 | 14 |
| `unenforceable_aggregate` after | 0 | 0 | 0 | 14 |

**Adding one field took a premise from writing nothing to corrupting 10 of 14** — reproducing the
pre-2026-08-25 `str` figure *exactly*. Requiring a declared type to discriminate closed one door
and left an identical one open.

The 10 corrupting attacks were `cyrillic-homoglyph-city`, `empty-string-into-score`,
`newline-injection-into-city`, `out-of-bounds-score`, `quote-injection-into-city`,
`trailing-whitespace-in-zip`, `type-violating-score`, `unlisted-category-in-state`,
`zero-width-space-in-state` and `zip-failing-its-pattern`. The 3 held were blocked for reasons that
have nothing to do with the schema — `stale-precondition`, `nonexistent-column`,
`row-past-the-end`.

### One of those writes changed the shape of the table

`newline-injection-into-city` was **applied**, taking the table from **6 rows to 7** and moving the
column count on two of them. The corpus calls this out as worse than a wrong cell, because it
silently reinterprets every downstream read.

`tests/adversarial/test_corpus_gate.py::test_the_table_shape_is_never_changed` existed and passed
throughout, because **it ran only under `TIGHT_SCHEMA`** — a structural invariant tested solely
under the premise that upholds it. Shape is not a premise-dependent property. It is now asserted
under every premise the corpus defines.

### Why N-version diversity could not catch it

Both verifiers returned `ACCEPT` on every one of these proposals, so they **agreed**, and
`require_independent_agreement` reads agreement as verification. Diversity cannot detect a
constraint kind absent from the specification the two implementations share: they are both derived
by hand from `Schema`, and they omit the same kinds.

This is PRODUCT.md 1.3's *"two mutually-consistent wrong artifacts reading as verification"*, one
level deeper than the prose-versus-gate case it was written about. The independence that makes the
verifier pair valuable is independence of *implementation*, not of *specification*.

### The realistic path in was dbt, not an adversary

`dataforge/integrations/dbt.py` maps exactly four dbt generic tests. Three are enforced. The
fourth is `relationships` — dbt's built-in referential-integrity test, one of the four that ships
with essentially every dbt project. `_model_columns` only populates `columns` when the manifest
node carries `data_type`, which is frequently absent, so a relationship column could arrive with
**no other constraint at all**.

That module's docstring claimed *"Only dbt generic tests that DataForge can represent as local
constraints are mapped."* Being represented is not being enforced. Corrected.

## The fix

Authority now requires enforceability. The partition lives in
`dataforge.domain.vocabulary.ENFORCEABLE_CONSTRAINT_KINDS` and
`UNENFORCEABLE_CONSTRAINT_KINDS`, beside `type_discriminates`, so the engine, the certificate
verifier and the generated browser code cannot disagree about what `proven` means.

`authoritative_columns` no longer unions a hand-written run of `covered |=` statements. It builds
a map from constraint kind to the columns that kind names, then unions only the enforceable ones —
so a `covered |=` line for an unenforceable kind is not something a future edit can add.

Three kinds lost authority:

* **`relationships`** — referential integrity needs the referenced relation and no verifier loads
  one. Retained for detection and for the constraint IR; it confers no right to write.
* **`aggregate_dependencies`** — a cross-row aggregate cannot be checked by either verifier.
  `_aggregate_sensitive` still escalates, and that is a **different guarantee**; conflating the two
  is what this finding is about.
* **`pii_columns`** — a policy marker, not a value predicate.

## What was measured and found NOT to be a defect

Recorded because a check that came back clean is evidence, and omitting it would leave the
impression that everything examined was broken.

* **Uniqueness and primary keys are genuinely enforced**, in both verifiers. The first hypothesis
  in this investigation was that they were declared and ignored; reading the code refuted it.
  `inferred-guard-gaps.md` gap 6's mitigation is real. Gap 7's was not, and the two sat in the same
  table in the same words.
* **`pii_columns` was mislabelled but not exploitable.** Measured: the write is refused by the PII
  rule (`receipt.applied` False). It loses authority anyway, because that is a fact about a
  different guard rather than a property of the authority rule, and a guarantee that holds by
  accident is not a guarantee.
* **No published number moved.** `eval/premises/hospital_declared.yaml` declares only `columns`
  (all `str`, inert by design) and `functional_dependencies`, so none of the three withdrawn kinds
  appears in it. Verified by reading the premise **before** predicting. The hospital proposal-stage
  tripwire, the oracle fence and the end-to-end declared-premise result are unchanged, and
  `anchor_truth` re-measures the first from code.

## A prediction of mine that the measurement refuted

The plan for this work predicted that `aggregate_dependencies` would behave *differently* from
`relationships`, because `_aggregate_sensitive` escalates a write to an aggregate-source column. It
does escalate — and `confirm_escalations` clears it, which is the same flag an untrusted write
already needs. The two arms came out **identical at 11 writes and 10 corruptions**. I had credited
an escalation as a compensating control when it is not one.

## Honest bound on the claim

Every write in this measurement required `confirm_escalations`, because `external` provenance is
escalated under `NO_UNCONFIRMED_LLM_WRITE`. So the claim is **"unsound under exactly the conditions
the analogous 2026-08-25 defect was measured and fixed under"** — not "writes silently with no
flags". The comparison to the 10-of-14 figure is apples to apples for that reason.

The fix is also **not** a claim that the authority rule is now sound. It is a claim that the rule
no longer confers proof on the strength of a declaration nothing can check. Whether the six
enforceable kinds are checked *correctly* is a different question with different evidence.

## Status

* Defect: closed, and the closure is measured in both directions on the same corpus.
* Gate: `tests/unit/test_authority_enforcement_correspondence.py`, 26 tests. The partition is
  asserted **total** against `dataclasses.fields(Schema)`, so a new constraint kind fails a test
  rather than silently joining either side. Falsified twice before being trusted — re-admitting
  `relationships` to the authority set fails 7 tests including the AST check against both
  verifiers, and planting an unclassified `Schema` field fails the totality check with an
  actionable message.
* Non-vacuity: every enforceable kind has a positive case asserting it **still** confers
  authority, and `test_every_enforceable_kind_has_a_non_vacuity_case` fails if a kind is added
  without one. Without these the whole change would be satisfiable by returning the empty set.
* Not done: referential integrity is still unenforceable. The gap is now honest rather than closed,
  and `test_no_verifier_pretends_to_check_an_unenforceable_kind` fails if a verifier learns to
  check one, so the exemption cannot outlive its reason.
