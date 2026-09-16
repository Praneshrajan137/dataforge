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
  §9's killing-mutant criterion was unenforceable for a month. All 14 mutants die, covering all 12
  checks.
- The specification now publishes the strength derivation rule, both branches of
  `verdicts_accepting`, which digest `data_identity` compares, `constraints_present`'s actual scope,
  the witness coherence conditions, the check names as normative, and its own normative surface in a
  new §3.1.
- The suite grew from 26 vectors to 30: `data_identity` gained two (the format now carries input
  bytes), a wrong-key signature gained one, and a wrong `_type` gained one. No vector was weakened.

**The mutation harness earned its place on its first run.** `A1-envelope-type-unchecked` SURVIVED:
`envelope_recognised` tests two conditions and only `predicateType` had a vector, so replacing the
`_type` comparison with a constant passed the entire suite. A check with a failure vector is not the
same as a check whose every condition has one.

**One defect was found in the TypeScript verifier while wiring the new vectors.** `verifyStatement`
declared a `dataBytes` option and never read it — line 301 consulted only `dataSha256`. A caller
passing bytes got `data_identity` silently skipped while believing it had been checked, which is the
*"quietly performs fewer checks, reports the same ok"* failure §6.3 warns about, inside the verifier.

## Did the amendments work? Arm C

A third clean-room verifier, built by a fresh agent from the **amended** markdown plus the amended
schema — Arm B's input class, after the fix — and run over the same vectors.

| Arm | Given | Over the original 26 | Over all 30 | Checks |
| --- | --- | --- | --- | --- |
| **B** | markdown + schema, before | 3 of 26, agreement rate 0.1154 | — | 12, one misnamed |
| **C** | markdown + schema, after | 25 of 26, agreement rate 0.9615 | 29 of 30, agreement rate 0.9667 | 12, **all correctly named** |

Both figures are reported because the suite grew from 26 vectors to 30 during this work, and the
four added vectors came out of what Arms A and B exposed. The 26-vector column is the pre-registered
comparison; the 30-vector column is supplementary. Neither is allowed to stand in for the other, and
`scripts/bench/measure_specification_sufficiency.py` names the four added vectors individually so a
fifth cannot silently enlarge the historical baseline.

Arm C emitted all twelve check names correctly, including `witness_is_coherent` — the name that cost
Arm B four vectors on logic it had implemented perfectly.

**P11 is refuted.** It predicted Arm C would pass *all* vectors, and 29 of 30 is not all. The single
residual disagreement is a genuine gap nobody had named: our verifier **short-circuits** on a
signature failure and reports `signature` alone, while Arm C ran all twelve checks on the tampered
payload and additionally reported the subject mismatch. Arm C was right on the letter of §7's *"Every
check is reported individually"*, which says nothing about a signature failure stopping the rest. §7
now states the short-circuit rule explicitly. That amendment is untested by any arm — it closes the
gap for a future one, and saying otherwise would be the reasoning this document exists to refuse.

One instrument defect was found and repaired under the pre-registered carve-out: the runner never
passed `--data`, so Arm C's first run reported it accepting a mismatched-digest document it had
simply never been handed the bytes for. Fixed, re-run, and disclosed as amendment 3 of the
pre-registration. A suspiciously specific failure is a bug in the instrument before it is a finding.

## What this does and does not claim

- **Not that the thesis now holds.** The normative tier checks integrity and coherence. It does not
  re-discharge the SMT obligation, and `PRODUCT.md`:118-121's concession stands unchanged: a third
  party must still trust our verifier that the solver obligation was actually discharged. Nothing
  here touches that.
- **Not that the amendments are sufficient.** Arm C reached 29 of 30, not 30, and the one residual
  gap is named above. The amendment that closes it has not itself been tested by any clean-room arm.
- **Not a clean measurement of specification quality for Arm B.** The JSON Schema is *generated from
  the reference verifier*. Agreement reached through it is agreement with a projection of our
  implementation. Arm B can establish "a third party can verify given what we publish" and can never
  establish "the specification is independently sound."
- **Not a measure of implementer skill.** Each arm is a fixed-effort faithful reader, not a domain
  expert working over days. That makes the arms comparable to each other and makes a *pass* strong
  evidence, but makes a single failure weaker evidence than an expert's failure would be.
- **Not exhaustive over the format.** The vectors are the strongest available proxy and remain
  incomplete: nothing exercises `journal.head_sha256`, which §6.2 describes as binding the hash chain
  into the payload and which `reversibility_complete` does not require.
- **Isolation was structural but not total.** The harness auto-injects `CLAUDE.md` into every
  subagent's context. Arm A disclosed this rather than concealing it. It names no check and no
  vocabulary member, and a grep audit of both arms' sources found zero occurrences of `witness`,
  `witness_is_coherent`, `llm_live`, `verification_strength_for` or the Python's distinctive error
  clause — so the channel existed and was empty. It is not guaranteed empty for a future arm.
- **Arm B's narrative report was lost** when the agent was cut off after its self-tests passed. Its
  instrument, sources and pre-coding check enumeration survived and the vector run is unaffected, but
  the exhaustive markdown-versus-schema divergence list it was asked for does not exist. That list
  was reconstructed by direct reading instead, so it rests on one reading rather than two.

## Open, and named rather than fixed

- **`verdicts.independent_verification` cannot express disagreement.** The verifier accepts
  `{"agreed", "not_run"}`; `dataforge/domain/vocabulary.py` carries a human label for `disagreed` as
  well. An attestation honestly reporting that the second verifier disagreed fails
  `vocabulary_closed` as malformed, and the rejection reads *"unrecognised value"* rather than *"the
  verifiers disagreed"*. Recorded rather than widened: admitting the value raises a separate question
  — whether `verdicts_accepting` should then reject it — and that is a design decision this
  measurement did not ask.
- **Numbers in `specs/` are still policed by nothing.** `spec_correspondence.py` now binds the check
  names and the vocabularies, but `claim_coverage.py`'s corpus still excludes `specs/`,
  `docs/STRATEGY.md` and `THREAT_MODEL.md`. Widening it moves a published denominator and needs its
  own pre-registration.
- **Two mutation harnesses remain outside the population manifest.** `gate_population.py` now
  imports `mutate_attestation` alongside `mutate_autoapply_guards`, but `mutate_domain_vocabulary`
  and `mutate_adversarial_corpus` are still invisible to it, so a mutant deleted from either goes
  unnoticed.
- **`mutate_autoapply_guards.MUTANTS` has 26 entries while four prose sites say 25, 25, 17 and 18.**
  Nothing gates those counts. Unrelated to this work, found while reading it.
