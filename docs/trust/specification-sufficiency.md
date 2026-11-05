# Specification sufficiency: can a third party verify without trusting DataForge?

`PRODUCT.md`:18-21 ends the product thesis with *"emits a portable attestation that a third party
can verify **without trusting DataForge**."* This measures that clause by building verifiers from
the published artifacts, in a third language, by agents structurally forbidden from reading either
existing implementation, and running them over the committed conformance suite.

Pre-registered in [eval/preregistration/specification_sufficiency.md](../../eval/preregistration/specification_sufficiency.md)
before anything was built. Raw per-vector outcomes in `eval/results/specification_sufficiency.json`;
runner `scripts/bench/measure_specification_sufficiency.py`; the verifiers themselves are committed
under `eval/cleanroom/`.

## Result

Over the 26 vectors committed at the time of measurement:

| Arm | Given | Agrees | Agreement rate | Checks emitted |
| --- | --- | --- | --- | --- |
| **A** | the specification markdown only | 17 of 26 | agreement rate 0.6538 | 11 |
| **B** | that plus the published JSON Schema | 3 of 26 | agreement rate 0.1154 | 12 |

The two arms disagree **with each other on 20 of 26** vectors.

**The finding is not the rate. It is that the arm which followed the specification more faithfully
agreed with us less.** §7 instructs a verifier to *"fail closed on anything unrecognised."* Arm B
obeyed that on `Provenance` — a vocabulary §6.2 claimed was *"published as enums in the JSON
Schema"* and which the schema declared as `{"minLength": 1, "type": "string"}` — and therefore
rejected `valid-deterministic-applied`, `valid-signed` and eighteen more. Arm A disobeyed it,
reporting `skip` for values it could not adjudicate, and scored five times better. Faithfulness was
anti-correlated with conformance, and no amount of additional prose fixes that.

### Direction of error, which matters more than the rate

| Arm | accepts we reject | rejects we accept | same verdict, wrong check named |
| --- | --- | --- | --- |
| **A** | **5** | 1 | 3 |
| **B** | 0 | 5 | 18 |

Arm A's five unsafe accepts are `reject-unknown-review-reason` and all four witness-rejection
vectors. **Four of the five are attestations whose own embedded witness arithmetic refutes the write
it accompanies** — a support of 2 in a group of 5 presented as entailment, a support exceeding its
own group size, a written value absent from its own group's distribution, and counts that hide rows
without declaring truncation. A third party holding a faithful independent implementation built from
the specification would have reported `verified` for every one.

That is the measured failure of the word *without*. It is not a rounding error in a rate; it is the
specific class of document the format exists to catch, passing.

## The six defects that produced it

| # | Defect | Consequence |
| --- | --- | --- |
| 1 | `witness_is_coherent` shipped in both verifiers on 2026-08-29 and §7 listed eleven checks | Arm A accepted all four self-refuting witnesses |
| 2 | `Provenance` and `verdicts.independent_verification` were enforced by the verifier and published nowhere | Arm B rejected 20 of 26 |
| 3 | §7.8 stated one branch of `verdicts_accepting`; the verifier has two | both arms rejected `valid-dry-run` |
| 4 | §7's check 10 read on the *recorded* strength label; the verifier conditions on the *derived* one | both arms added `constraints_present` where the vector expects only `strength_is_earned` |
| 5 | The check **names** were normative and published nowhere | Arm B derived the witness rule correctly and still failed four vectors, because it called the check `witness_coherent` |
| 6 | `verification.checks_available` was a hardcoded ten-name literal | every attestation ever emitted told a third party not to run the witness check |

Defect 2 is the root cause of most of the damage, and its mechanism is a defect class this project
has already recorded four times. `scripts/ci/generate_attestation_schema.py` derived every projected
*value* while hand-enumerating *which* vocabularies to project — four of the seven
`_check_vocabulary` enforces. `Provenance` exists in `dataforge/domain/vocabulary.py` only as a
`Literal` with no companion tuple, so it was the awkward one to import and was omitted by silence.
`PRODUCT.md`:275-278 describes the identical failure in a sibling generator: *"it derived every
projected value and hand-enumerated which vocabularies to project, so adding a constant failed CI
loudly and then resolved by omission."*

Defect 5 is the one nobody predicted. The pre-registration expected a content gap; the binding
constraint was a **naming** gap. Because the vectors assert which named check rejects each document,
a verifier with perfect logic and a different name for it is non-conforming.

## Two claims in the constitution were false

`PRODUCT.md`:104-108 said *"a Python implementation and an independently-written TypeScript one"* and
*"26 committed vectors covering all 11 normative checks."*

**The TypeScript verifier was ported.** Nine user-facing message strings and one code comment are
character-identical apart from renamed local variables, including the comment *"The shipped decision
rule is a STRICT majority, not a plurality."* and the clause *"so the written value was not entailed
by the rule the product implements"* (`dataforge/attestation/__init__.py`:656,658,664,697 against
`playground/web/src/attestation/verify.ts`:213,220,226,232,235,257,464,467,470,510). A comment
carries no behaviour, so two people writing from one document do not converge on it.

**That inference has a control group, by accident.** Arm B independently produced *one* short phrase
close to the Python's — `"support N exceeds group_size M"` — over two field names the schema
publishes, and **no** comment. So genuine convergence looks like short phrases over shared
vocabulary; porting looks like long distinctive clauses plus comments. The inference is calibrated
rather than merely plausible.

**And there were never 11 checks to cover.** There were four populations: §7 listed 11, both
implementations ran 12, `checks_available` advertised 10, and `PRODUCT.md`:113-116 enumerated a
*different* 11 that omitted `data_identity`. **Two were numerically equal with different members**,
which is why comparing counts caught nothing. `data_identity` — the only check binding an attestation
to actual bytes — had **zero** vectors from the day it was written, because the vector format carried
no field for input bytes.

## Why no gate could see any of this

**No gate in this repository read any `specs/SPEC_*.md` file.** Every reference to
`SPEC_repair_attestation.md` was a docstring, a hyperlink, or an assertion *message*. So the
highest-authority normative documents were the one category of published prose with an **empty**
policed population — not a narrowed gate, no gate. `scripts/ci/claim_coverage.py` surveys
`docs/trust/*.md` plus three root files; `specs/` is outside it.

The two guards that existed were both of the shape `PRODUCT.md` §1.3 already condemns:

- `tests/unit/test_attestation_vectors.py` iterated a hardcoded **ten**-name tuple against twelve
  implemented checks, under a comment claiming it covered *"every distinct normative check"*.
- `scripts/ci/attestation_conformance.py` asserted `len(vectors) >= 15` against 26 actual.

A lower-bound assertion cannot see a missing member. These are the fifth and sixth instances of that
defect class, in the gate that carries the thesis.

## What changed

Every fix is a derived population or a refusal, not a corrected literal, because a corrected literal
drifts again:

- `dataforge.attestation.NORMATIVE_CHECKS` is the check population, and `AttestationCheck` **raises**
  on a name absent from it — refusal at the construction site, so a thirteenth check cannot reach a
  report unregistered.
- `dataforge.attestation.CLOSED_VOCABULARIES` is the single table `_check_vocabulary` iterates and
  the schema generator projects. The generator **refuses to emit a schema** that omits any closed set
  the verifier enforces, and no longer imports any vocabulary by name.
- `scripts/ci/spec_correspondence.py` derives four populations — specified in §7, implemented,
  exercised by a vector, published as an enum — and refuses on anything in one that is unnameable in
  another. It is the first gate here to read a `specs/SPEC_*.md` at all.
- `scripts/ci/mutate_attestation.py` exists. §8 cited it from 2026-08-13 and it did not exist, so
  §9's killing-mutant criterion was unenforceable for a month. All 15 mutants die, covering all 13
  checks.
- The specification now publishes the strength derivation rule, both branches of
  `verdicts_accepting`, which digest `data_identity` compares, `constraints_present`'s actual scope,
  the witness coherence conditions, the check names as normative, the signature short-circuit rule,
  Check 13 (`authority_is_entailed`), and its own normative surface in §3.1.
- The suite grew from 26 vectors to 30 after Arms A and B (`data_identity` gained two, a wrong-key
  signature gained one, and a wrong `_type` gained one) and to 35 when Check 13 added five premise
  forgery vectors. No vector was weakened.

**The mutation harness earned its place on its first run.** `A1-envelope-type-unchecked` SURVIVED:
`envelope_recognised` tests two conditions and only `predicateType` had a vector, so replacing the
`_type` comparison with a constant passed the entire suite. A check with a failure vector is not the
same as a check whose every condition has one.

**One defect was found in the TypeScript verifier while wiring the new vectors.** `verifyStatement`
declared a `dataBytes` option and never read it — line 301 consulted only `dataSha256`. A caller
passing bytes got `data_identity` silently skipped while believing it had been checked, which is the
*"quietly performs fewer checks, reports the same ok"* failure §6.3 warns about, inside the verifier.

## Did the amendments work? Arms C and D

Two further clean-room verifiers were built by fresh isolated agents from the amended markdown plus
the amended JSON Schema — Arm B's input class, after each wave of specification amendments.

| Arm | Given | Over the original 26 | Over the 30-vector cohort | Over all 35 | Checks |
| --- | --- | --- | --- | --- | --- |
| **B** | markdown + schema, before | 3 of 26, agreement rate 0.1154 | — | — | 12, one misnamed |
| **C** | markdown + schema, after 12-check fix | 25 of 26, agreement rate 0.9615 | 29 of 30, agreement rate 0.9667 | — | 12, **all correctly named** |
| **D** | markdown + schema, with Check 13 & short-circuit rule | 26 of 26, agreement rate 1.0000 | 30 of 30 | 35 of 35, agreement rate 1.0000 | 13, **all correctly named** |

All three cohort columns are reported because the suite grew from 26 vectors to 30 after Arms A and B
and to 35 when Check 13 (`authority_is_entailed`) was added. `scripts/bench/measure_specification_sufficiency.py`
names every post-baseline vector individually (`VECTORS_ADDED_AFTER_MEASUREMENT` and
`VECTORS_ADDED_AFTER_ARM_C`) so no added vector can silently move an earlier arm's figure.

**P11 (Arm C) was refuted by one vector; P12 (Arm D) is confirmed on all 35.** Arm C reached 29 of 30
because the reference verifier short-circuits on a DSSE `signature` failure and reports `signature`
alone, whereas Arm C ran all twelve checks on the tampered payload and additionally reported
`subject_matches_post_state`. §7 was amended to state the short-circuit rule explicitly, and §6.4 /
check 13 were added to specify `authority_is_entailed`. Arm D — pre-registered in Amendment 4
of `eval/preregistration/specification_sufficiency.md` and built from `specs/SPEC_repair_attestation.md`
and `specs/repair_attestation.schema.json` alone — agreed with the reference verifier on **35 of 35**
vectors (`1.0000`) on its first run, emitting all 13 normative check names and preserving its full
narrative analysis in `eval/cleanroom/armD/NOTES.md`.

One instrument defect was found and repaired during Arm C under the pre-registered carve-out: the
runner never passed `--data`, so Arm C's first run reported it accepting a mismatched-digest document
it had simply never been handed the bytes for. Fixed, re-run, and disclosed as amendment 3 of the
pre-registration.

## What this does and does not claim

- **Not that the thesis now holds in full.** The normative tier checks integrity, coherence, and that
  the claimed `authoritative_columns` follow from the embedded `authority.premise`. It does not
  re-discharge the SMT obligation against the dataset, and `PRODUCT.md`:118-121's concession stands
  unchanged: a third party must still trust our verifier that the solver obligation was actually
  discharged. Nothing here touches that.
- **Not a clean measurement of prose-only quality for Arms B, C, or D.** The JSON Schema is *generated
  from the reference verifier*. Agreement reached through it is agreement with a projection of our
  implementation. Arms C and D establish *"a third party can build a 100%-conforming verifier given
  the two specification artifacts we publish (`SPEC_repair_attestation.md` and
  `repair_attestation.schema.json`)."*
- **Not a measure of implementer skill.** Each arm is a fixed-effort faithful reader, not a domain
  expert working over days. That makes the arms comparable to each other and makes Arm D's 35 of 35
  pass strong evidence that the specification surface is unambiguous across all 35 vectors.
- **Not exhaustive over the format.** The vectors are the strongest available proxy and remain
  incomplete: nothing exercises `journal.head_sha256`, which §6.2 describes as binding the hash chain
  into the payload and which `reversibility_complete` does not require.
- **Isolation was audited both by transcript and by source grep.** For Arm D, the subagent transcript
  confirms only two `view_file` calls (`specs/SPEC_repair_attestation.md` and
  `specs/repair_attestation.schema.json`), and a grep audit of `eval/cleanroom/armD/Verify.java`
  found zero occurrences of implementation-only symbols (`verification_strength_for`,
  `AttestationCheck`, `verify_attestation`, `NORMATIVE_CHECKS`, `CLOSED_VOCABULARIES`,
  `premise_from_canonical`, or the Python's distinctive error clause).

## Open, and named rather than fixed

- **`verdicts.independent_verification` cannot express disagreement.** The verifier accepts
  `{"agreed", "not_run"}`; `dataforge/domain/vocabulary.py` carries a human label for `disagreed` as
  well. An attestation honestly reporting that the second verifier disagreed fails
  `vocabulary_closed` as malformed, and the rejection reads *"unrecognised value"* rather than *"the
  verifiers disagreed"*. Recorded rather than widened: admitting the value raises a separate question
  — whether `verdicts_accepting` should then reject it — and that is a design decision this
  measurement did not ask.
- **Numbers in `specs/` are still policed by `spec_correspondence.py`, not `claim_coverage.py`.**
  `spec_correspondence.py` binds the check names and the vocabularies, while `claim_coverage.py`'s
  corpus excludes `specs/`, `docs/STRATEGY.md` and `THREAT_MODEL.md` because widening it moves a
  published denominator and needs its own pre-registration.
- **Resolved in 2026-10-20:** All four mutation harnesses (`mutate_autoapply_guards` [26],
  `mutate_attestation` [15], `mutate_domain_vocabulary` [10], `mutate_adversarial_corpus` [4]) are now
  registered in `gate_population.py` with a structural glob check over `scripts/ci/mutate_*.py`, and
  the stale mutant counts in `Makefile` and `backend_gate.py` have been reconciled to 26.
