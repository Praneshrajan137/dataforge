# Pre-registration: authority must correspond to enforcement

Written 2026-09-14, **before** the fix and before the publishable measurement. Nothing below is
edited afterwards; results and deviations are appended as amendments, including amendments that
record my own predictions being refuted.

## The finding this responds to

`dataforge/engine/repair.py::authoritative_columns` decides which columns a declared schema has
authority over, and therefore — through `verification_strength_for` — which untrusted fixes are
stamped **`proven`** in the receipt and the attestation. It grants authority for **ten**
`Schema` constraint kinds. The two verifiers enforce **six**.

| `Schema` field | confers authority | `SMTVerifier` | `DirectVerifier` |
| --- | --- | --- | --- |
| `columns` (via `type_discriminates`) | yes | yes | yes |
| `not_null_columns` | `repair.py:1388` | `smt.py:340` | `direct.py:160` |
| `primary_key_columns` | `repair.py:1387` | `smt.py:342` | `direct.py:160,169` |
| `unique_columns` | `repair.py:1389` | `smt.py:356` | `direct.py:169` |
| `accepted_values` | `repair.py:1390` | `smt.py:358` | `direct.py:181` |
| `regex_constraints` | `repair.py:1391` | `smt.py:371` | `direct.py:197` |
| `domain_bounds` | `repair.py:1392` | `smt.py:375` | `direct.py:209` |
| `functional_dependencies` | `repair.py:1397-1399` | `smt.py:246` | `direct.py:238` |
| **`relationships`** | **`repair.py:1393`** | **absent** | **absent** |
| **`aggregate_dependencies`** | **`repair.py:1394-1396`** | **absent** | **absent** |
| **`pii_columns`** | **`repair.py:1386`** | n/a — policy, not a value predicate | n/a |

`DirectVerifier`'s accept string already hedges — *"satisfied all **tracked** verifier
constraints"* (`direct.py:262`) — but the verdict is `ACCEPT`, and `ACCEPT` on a covered column is
`proven`.

### This is a specification-implementation divergence, not an oversight of scope

`eval/preregistration/entailment_strength.md`, lines 29-36, **specifies** the discriminating set as
exactly six conditions: a non-`str` type, a regex, accepted values, a domain bound, membership of
`not_null`/`unique`/`primary_key`, and being the dependent of a declared functional dependency.

`relationships`, `aggregate_dependencies` and `pii_columns` appear nowhere in that specification.
They are in the implementation. The 2026-08-25 change asked *"can this declaration reject a
value?"* of **types** and fixed that case, measured at 10 of 14 constraint-violating attacks
written before and 0 of 14 after. The same question was never asked of the other kinds.

One divergence from that spec **is** documented and reasoned and is not in scope here:
`authoritative_columns` covers both sides of a functional dependency where the spec names only the
dependent, justified at `repair.py:1370-1371` on the ground that a value in either position is
checked by the FD. That is a defensible reading. The three kinds above have no such justification.

## Full disclosure: a scoping probe ran before this document

This is not a blind prediction and must not be read as one. A throwaway probe
(`$env:TEMP/df_probe/authority_probe.py`, not committed) was run first to decide whether the
finding was "unsound" or merely "mislabelled but not exploitable", because that distinction
determines whether the work is worth doing at all. It reported, on a 5-row table with a premise
whose only statement about column `city` was one unenforceable constraint, and with
`confirm_escalations=True`:

| arm | `city` covered | SMT | Direct | applied | strength | bytes changed |
| --- | --- | --- | --- | --- | --- | --- |
| `relationships` only | yes | accept | accept | **True** | **`proven`** | **yes** |
| `aggregate_dependencies` only | yes (source **and** target) | accept | accept | **True** | **`proven`** | **yes** |
| `pii_columns` only | yes | accept | accept | False | — | no |

The receipt for the first two read: *"Applied 1 **proven** external fix(es) proposed by
'external'."*

**One prediction of mine was already refuted by that probe, and it is recorded here rather than
quietly dropped.** The plan for this work predicted that `aggregate_dependencies` would behave
differently from `relationships` because `safety/constitution.py::_aggregate_sensitive` escalates a
write to an aggregate-source column. It does escalate — and `confirm_escalations=True` clears the
escalation, which is the same flag the attack already requires. So an escalation is not a barrier
here, and I had credited it as a compensating control when it is not one. The `pii_columns` arm
*is* blocked, so the three kinds do not behave alike and must be reported apart.

What the probe does **not** establish is the population figure, because it is one cell on one
table. That is what the measurement below is for.

## The measurement, and why it adds a premise rather than an attack

The publishable arm extends `scripts/measure_trust_ledger.py` and
`eval/results/trust_ledger_adversarial.json`.

**`build_corpus()` is not touched.** Its 17 attacks (14 discriminable, 3 not) are the denominator of
a published claim — "10 of 14" — quoted in `dataforge/domain/vocabulary.py:147`,
`dataforge/engine/repair.py:1374`, `scripts/ci/mutate_autoapply_guards.py:262`,
`scripts/bench/measure_deductive_coverage.py:9` and `tests/unit/test_column_scoped_authority.py:111`.
Adding attacks would move that denominator and silently restate history.

Instead the corpus gains **premises**, each identical to `PERMISSIVE_SCHEMA` except for one added
field:

* `UNENFORCEABLE_RELATIONSHIP_SCHEMA` — `PERMISSIVE_SCHEMA` plus a `RelationshipConstraint` on
  every column.
* `UNENFORCEABLE_AGGREGATE_SCHEMA` — `PERMISSIVE_SCHEMA` plus an `AggregateDependency` sourced from
  every column.

One variable changes, so any difference in outcome is attributable to that field and to nothing
else. This is the two-premise design the corpus was built around, extended by one axis.

## Predictions

Subset is `discriminable` (n=14) unless stated. Units are the harness's own
(`cells_applied`, `corrections`, `corruptions`, `cells_held`).

| # | Quantity | Prediction |
| --- | --- | --- |
| **P1** | `authoritative_columns` under either unenforceable premise | All five columns covered, identical to the permissive premise's coverage before 2026-08-25. |
| **P2** | `unenforceable_relationship`, discriminable | `corruptions` **10**, `corrections` **1**, `cells_applied` **11**, `cells_held` **3**. It reproduces the pre-2026-08-25 permissive figure exactly, because the mechanism is identical: blanket authority with no power to reject. The 3 held are the attacks blocked for non-schema reasons — `stale-precondition`, `nonexistent-column`, `row-past-the-end`. |
| **P3** | `unenforceable_aggregate`, discriminable | Identical to P2: **10 / 1 / 11 / 3**. Per the probe, `_aggregate_sensitive` escalates and the escalation is cleared by the flag the run already sets. |
| **P4** | `tight` and `permissive`, all subsets | **Unchanged field-for-field** against the committed artifact. Adding a premise must not perturb an existing arm. |
| **P5** | After the fix, both unenforceable premises | `corruptions` **0**, `cells_applied` **0**, `cells_held` **14** — collapsing onto the permissive premise, which is what they should always have been. |
| **P6** | After the fix, `tight` | `cells_applied` **1**, `corruptions` **0**. The one legitimate repair survives. |
| **P7** | After the fix, every published corpus number | No movement. `eval/premises/hospital_declared.yaml` declares only `columns` (all `str`, inert by design and load-bearing in its own comments) and `functional_dependencies` — none of the three withdrawn kinds. Verified by reading the file before predicting. So the hospital proposal-stage tripwire (tp 451, fp 120, fn 58), the oracle fence, and the end-to-end declared-premise result all hold. |
| **P8** | `pii_columns` arm | Remains **not exploitable**: the PII rule refuses the write. Authority is mislabelled without being reachable. |

## Kill criteria, fixed now

* **K1 — instrument falsification.** Before any new arm is reported, the extended harness must
  reproduce the **existing** arms field-for-field against the committed
  `eval/results/trust_ledger_adversarial.json`: `tight/discriminable` at `corruptions` 0 and
  `cells_applied` 1, and `permissive/discriminable` at `cells_applied` 0. If it cannot, **report
  nothing** and fix the harness first. Bound to the artifact, never to a constant in prose — a
  documented constant is precisely what rotted for 54 days on the hospital anchor.
* **K2 — the claim is withdrawn if the arm is inert.** If an unenforceable premise writes 0, the
  finding downgrades from *unsound* to *authority is mislabelled but not exploitable*, which is a
  weaker and materially different claim. Publish the weaker one; do not restate it as the stronger.
  This is evaluated **per arm**, and P8 already predicts one arm lands there.
* **K3 — the fix must not destroy the feature.** If `tight` stops writing its one legitimate
  repair, the enforceability rule is too strict. Revert it. Do **not** relax the assertion to
  accept the loss. (This is `entailment_strength.md`'s own kill criterion for the analogous case,
  reused deliberately.)
* **K4 — a moved anchor is a finding, not a correction.** If the fix moves the hospital anchor,
  the oracle fence, or the end-to-end declared-premise result, stop and write it up. Do not edit a
  committed number to match a refactor.
* **K5 — no new threshold.** The enforceability rule must be a derivation over constraint kinds
  the schema already carries. If closing this requires inventing a tunable, the approach is wrong
  and stops here. (`entailment_strength.md` refused a fitted constant that looked like a clean win;
  the same standard applies.)
* **K6 — anti-motivated-stopping.** Every result is published even where it embarrasses the
  project or weakens the finding: specifically the `pii_columns` refusal, which reduces the headline
  from three exploitable kinds to two, and the refutation of my aggregate prediction recorded above.

## What is deliberately not being done

**Referential integrity is not implemented.** Making `relationships` enforceable requires loading
the referenced relation, which no verifier does and which is a genuine design question — the
warehouse path may be the route, since `verifier/constraint_ir.py:125-136` already compiles a
relationship into a SQL proof query. Withdrawing authority is the safe, reversible half and is
strictly more refusing. Granting authority back is the half that needs evidence, and it gets its
own pre-registration.

**`aggregate_dependencies` keeps its safety escalation.** Withdrawing authority does not withdraw
`_aggregate_sensitive`. Escalation and proof are different guarantees, and the finding above is
precisely that they had been conflated.

**`pii_columns` loses authority despite P8.** A policy marker is not a value predicate. That its
mislabelling is currently unreachable is a fact about another guard, not a property of the
authority rule, and PRODUCT.md's own doctrine is that a guarantee holding by accident is not a
guarantee.

## Scope

**Does not** touch `is_trusted_provenance`, `TRUSTED_PROVENANCE`, the repairer's abstain rule, the
100-cell volume budget, or `type_discriminates`. Deterministic provenance keeps conferring proof by
construction; that is a different weakness with a different remedy.

**Does not** claim the resulting authority rule is sound. It claims the rule stops conferring proof
on the strength of a declaration nothing can check, and the before-and-after arms give the numbers
that show whether that claim holds.

---

## AMENDMENT 1 (2026-09-14): results

Appended, not edited. Every prediction above stands as written.

**K1 satisfied.** The extended harness reproduced `tight` and `permissive` field-for-field against
the committed artifact. The check is now baked into `scripts/measure_trust_ledger.py`, which
refuses to report a new arm at all if a pre-existing arm has moved, and treats a missing artifact
as a failure rather than a pass.

### Predictions, resolved

| # | Prediction | Outcome |
| --- | --- | --- |
| P1 | all five columns covered | **CONFIRMED** |
| P2 | relationship arm 10 / 1 / 11 / 3 | **CONFIRMED EXACTLY** � corruptions 10, corrections 1, applied 11, held 3 |
| P3 | aggregate arm identical to P2 | **CONFIRMED EXACTLY** � 10 / 1 / 11 / 3 |
| P4 | existing arms unperturbed | **CONFIRMED** � the artifact diff is purely additive; no `-` line touches `tight` or `permissive` |
| P5 | after the fix, both arms 0 / 0 / 14 | **CONFIRMED** � both collapse onto the permissive premise |
| P6 | after the fix, `tight` keeps 1 write, 0 corruptions | **CONFIRMED** |
| P7 | no published number moves | **CONFIRMED** � `anchor_truth` re-measures hospital at F1 0.8352 (tp 451, fp 120) and flights at 0.0 (tp 0, fp 9) from code |
| P8 | `pii_columns` not exploitable | **CONFIRMED** � `receipt.applied` False; the PII rule refuses the write |

The 10 corrupting attacks were `cyrillic-homoglyph-city`, `empty-string-into-score`,
`newline-injection-into-city`, `out-of-bounds-score`, `quote-injection-into-city`,
`trailing-whitespace-in-zip`, `type-violating-score`, `unlisted-category-in-state`,
`zero-width-space-in-state`, `zip-failing-its-pattern`. The 3 held were blocked for non-schema
reasons, exactly as P2 named them: `stale-precondition`, `nonexistent-column`, `row-past-the-end`.

### One finding NOT predicted, and it is larger than what was

`newline-injection-into-city` was among the applied writes, and it **changed the shape of the
table** � 6 rows to 7, with the column count moving on two of them. The corpus's own docstring
ranks a structural corruption above a wrong cell, because it silently reinterprets every
downstream read.

`tests/adversarial/test_corpus_gate.py::test_the_table_shape_is_never_changed` existed and passed
throughout, because **it ran only under `TIGHT_SCHEMA`**. A structural invariant was being tested
solely under the premise that upholds it. Shape is not premise-dependent; the test now runs under
every premise the corpus defines.

This was not in any prediction because the pre-registration reasoned about *authority* and not
about what the authorised writes would then *do*. Worth recording as a method lesson: predicting
the gate's verdict is not the same as predicting the blast radius of the verdict being wrong.

### The refutation recorded before the fact, confirmed

The disclosure section above records that my prediction about `aggregate_dependencies` behaving
differently was already refuted by the scoping probe. The population measurement confirms it: the
two arms are **identical at every number**. `_aggregate_sensitive` escalates, and
`confirm_escalations` � the flag an untrusted write already needs � clears it.

### Kill criteria not fired

K2 did not fire for `relationships` or `aggregate_dependencies` (both exploitable, so the strong
claim stands) and **did** fire for `pii_columns`, exactly as P8 predicted; that arm is published as
the weaker "mislabelled but not exploitable" claim per K2's own instruction. K3 did not fire �
`tight` still writes its 1 legitimate repair. K4 did not fire � no anchor moved. K5 was honoured: no
threshold was invented, the rule is a partition over kinds the schema already carries. K6 was
honoured: the `pii_columns` result is published though it reduces the headline from three
exploitable kinds to two, and my own refuted prediction is recorded in the body rather than dropped.
