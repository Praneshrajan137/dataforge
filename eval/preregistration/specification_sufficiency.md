# Pre-registration: is the attestation specification sufficient for an independent implementation?

Written 2026-09-15, **before** building or running anything. Nothing below is edited afterwards;
results, deviations and refutations are appended as amendments at the bottom.

## The claim under test

`PRODUCT.md`:18-21 states the product thesis, and its last clause is the subject of this document:

> **DataForge is the reference implementation of a verifiable data-mutation protocol: it changes only
> what it can prove correct, honestly flags everything it cannot, never silently corrupts data, and
> emits a portable attestation that a third party can verify without trusting DataForge.**

`specs/SPEC_repair_attestation.md`:31-32 and :183 make the operative promise concrete twice — a
verification tier that is *"reimplementable in any language from this document alone"*. That promise
is what makes the word **without** mean anything: if the only way to check an attestation is to run
code we wrote, a third party is trusting us at one remove.

Two implementations exist and agree on every committed vector. That agreement is presented as
evidence of specification quality. It is not, if the second implementation was derived from the first
rather than from the document, because a port inherits the original's blind spots by construction.
This project has already measured that exact failure one layer down and named it:

> The independence that makes the verifier pair valuable is independence of *implementation*, not of
> *specification*.
> — `PRODUCT.md`:161-162, on `authoritative_columns` conferring authority for ten constraint kinds
> while both verifiers enforced six, agreeing with each other and both being wrong.

So the question is not whether two programs agree. It is whether the **document** determines the
behaviour they agree on.

## The hand count, recorded before any implementation was opened

Fixed here because it is destroyed the moment I read the verifier, and because it is the datum P2
is scored against.

`specs/SPEC_repair_attestation.md` §7 enumerates **11** normative checks: `envelope_recognised`,
`version_recognised`, `schema_complete`, `vocabulary_closed`, `subject_matches_post_state`,
`data_identity`, `reversibility_complete`, `verdicts_accepting`, `strength_is_earned`,
`constraints_present`, `signature`.

Three further observations from the same reading, all made before opening either verifier:

1. **Appendix A case 5** — *"Any fix recorded `plausibility_only` → REJECT while `applied`"* — names no
   enforcing check, and §7.9 states the seemingly opposite *"a recorded `plausibility_only` is always
   believed"*. An implementer must guess which check reports it.
2. **§7.9 supplies no derivation rule.** *"strength derived from provenance and the column's
   authority"* names the inputs and omits the function. Appendix A gives four examples, which
   underdetermines a mapping over `Provenance` × {covered, uncovered} → `VerificationStrength`.
3. **§7.6 does not say which digest.** *"SHA-256 of the supplied bytes equals the expected digest"* —
   `source.digest` or `post.digest` is undefined, and the two differ on every applied repair.

Derived from `tests/fixtures/attestation/vectors.json` and its generator alone, still without opening
either verifier: the committed vectors reference **11 distinct check names**, of which `data_identity`
is not one, and one of which — `witness_is_coherent` — is absent from §7. So the implementations run
**12**. `PRODUCT.md`:113-116 enumerates a **third** set of eleven that includes `witness_is_coherent`
and omits `data_identity`.

**There are therefore four check sets in play, and two of them are both "11" while containing
different members.** An equal count concealing unequal membership is the same defect class as the
lower-bound assertion that could not see a missing member (`PRODUCT.md`:288-289), and it is the reason
no reader caught this by comparing numbers.

## The second normative document, and why this needs two arms

`specs/repair_attestation.schema.json` is not an implementation detail. §2 links it as the published
schema, and §6.2 declares it the publication point for the closed vocabularies and *explicitly
declines to restate them* on the grounds that restating a closed vocabulary is how three drifts
shipped. A stranger following the specification is therefore **directed** to it.

That schema's `witness` description states the coherence rule the prose never mentions:

> The normative verifier checks this block's INTERNAL COHERENCE (support is a strict majority of
> group_size, the written value's count equals its support, counts sum to group_size unless
> truncation is declared).

Traced by hand against the five witness vectors before any code was run, that one sentence appears to
determine all five verdicts. So *"a check the specification never mentions"* is true of the prose and
false of the published surface — and a single clean-room arm cannot distinguish "the specification is
insufficient" from "the prose is insufficient but the published surface is adequate". Those two
findings have different fixes, and the difference is the entire question.

Hence two arms, and a third after the amendment:

| Arm | Inputs | What it measures |
| --- | --- | --- |
| **A** | `specs/SPEC_repair_attestation.md` only | §7's literal claim, *"from this document alone"* |
| **B** | that plus `specs/repair_attestation.schema.json` | what a third party actually gets from what we publish |
| **C** | the **amended** prose only, fresh agent, after the fix | whether the amendment achieved sufficiency |

**Arm B's bound, stated before it runs so it cannot be quietly dropped afterwards.** The schema is
*generated from the verifier* — its own `description` says so. Agreement reached via the schema is
agreement with a projection of our implementation, not with a human-authored specification. Arm B can
therefore establish "a third party can verify given what we publish" and can never establish "the
specification is independently sound". Where Arm B succeeds and Arm A fails, the honest reading is
that the specification's normative content lives in a generated artifact.

Comparison is three-way: A against ours, B against ours, and **A against B**. The third is not
redundant. Two faithful readers of overlapping documents disagreeing *with each other* is direct
evidence of ambiguity that does not depend on our verifier being right about anything.

## Method

Both arms are built by subagents in **Java 17, standard library only** — `Signature.getInstance("Ed25519")`,
`MessageDigest`, `java.util.Base64`, and a hand-written JSON scanner. A third language is chosen so
that byte-level porting is impossible and accidental convergence on an identical error string is
unlikely; a character-identical error string is the evidence that exposed the second implementation as
a port, so the instrument must not be able to produce that artefact by copying.

Isolation is **structural, not intentional**. Each arm's prompt forbids opening, reading, grepping,
listing or inferring the contents of `dataforge/attestation/**`,
`playground/web/src/attestation/**`, `tests/fixtures/attestation/**`, `tests/unit/test_attestation*.py`,
`scripts/ci/generate_attestation_*.py`, `scripts/ci/attestation_conformance.py`,
`dataforge/domain/vocabulary.py`, `dataforge/witness*` and `dataforge/cli/attest.py`, and forbids
searching the repository for `verify_attestation`, `witness_is_coherent` or any check name. The arms do
not receive the vectors: vector *names* and `expect_failures` enumerate the check list, so handing them
over would let an arm fit the answers and would destroy the only measurement the exercise produces.

Each arm must **report what it could not determine** rather than guessing. That declaration is a
primary output, not a footnote — it is the direct evidence for P3.

## Pre-committed hypothesis and predictions

**H1** and **P1-P4** are copied verbatim from `HANDOFF_earn_the_word_without.md` §3, where they were
fixed by the previous session before this work began. They are reproduced unaltered and are not
edited under any result.

**H1.** `specs/SPEC_repair_attestation.md` is insufficient for an independent implementation. A
clean-room verifier built from it alone will fail at least one committed vector.

| # | Prediction |
| --- | --- |
| **P1** | It fails **at least 4** vectors — the `witness_is_coherent` set — since that check appears nowhere in the document. |
| **P2** | It implements **11** checks rather than 12, matching spec section 7 and diverging from both existing implementations. |
| **P3** | It **cannot implement `vocabulary_closed`** without reading `dataforge/domain/vocabulary.py`, because spec section 6.2 deliberately declines to restate the enums. |
| **P4** | It passes `data_identity` **vacuously**, because no vector exercises it. |

The following are added 2026-09-15 by the current session, before any arm was launched and before any
vector was run. They are frozen on the same terms. Where P1-P4 speak of "it", they are scored against
**Arm A**, which is the arm matching their premise.

| # | Prediction |
| --- | --- |
| **P5** | Arm A fails **at least 4** vectors of the witness set; Arm B fails **at most 1** of them, because `repair_attestation.schema.json` states the coherence rule in prose. The delta between arms is the specification value carried by a generated artifact. |
| **P6** | **Both** arms fail `reject-unknown-provenance`. `Provenance` is published as an enum nowhere in `specs/`: the schema declares it `{"minLength": 1, "type": "string"}`, so §6.2's claim that the vocabularies are "published as enums in the JSON Schema" is false for the one vocabulary a committed vector tests. |
| **P7** | **Both** arms fail `valid-dry-run`, reporting a `verdicts_accepting` failure on `verifier: "not_run"`, because §7.8 is unqualified — *"verifier `accept`, safety `allow`"* — and carves out no dry-run case. |
| **P8** | At least one arm fails `reject-missing-verification-strength` by reporting `schema_complete` in addition to `vocabulary_closed`, because §6.2 marks the field required and **"Not nullable."** while the committed vector expects `vocabulary_closed` alone. |
| **P9** | The two arms disagree **with each other** on at least 2 vectors. Faithful readers diverging is evidence of ambiguity independent of whether either matches our verifier. |
| **P10** | Neither arm reports `constraints_present` on `reject-entity-consensus-claimed-proven`, even though a literal §7.10 reading — *"a `proven` untrusted fix requires embedded constraints"* — requires it of an `entity_consensus` fix recorded `proven` with `constraints: null`. The committed vector expects `strength_is_earned` alone, so §7.10's scope is underdetermined. |
| **P11** | Arm C, given the amended prose alone, passes **all** committed vectors. If it does not, the amendment did not achieve sufficiency and that is the published result. |

## Pre-committed kill criteria

**K1-K5** are copied verbatim from the handoff and are not edited.

- **K1 — instrument falsification, and it outranks every finding.** If the clean-room agent is found
  to have read either existing implementation, **the entire result is void** and must be re-run with a
  fresh agent. Independence is the only thing being measured; a single glance destroys the only
  evidence the exercise produces.
- **K2 — the inversion holds.** Every vector the clean-room verifier fails is scored as a
  specification defect until proven otherwise. If you find yourself patching the new implementation to
  make a vector pass, the exercise has been inverted and its output is worthless.
- **K3 — anti-motivated-stopping.** If H1 is refuted and a faithful reading passes all 26 vectors,
  **publish that.** It is the strongest possible result for the thesis and must not be buried for being
  unexciting.
- **K4 — no vector may be weakened.** Vectors may be added. None may be relaxed to accommodate the
  third implementation.
- **K5 — no new tunables.** This is a measurement of a document, not an opportunity to redesign the
  attestation format.

Added 2026-09-15, on the same terms:

- **K6 — the instrument carve-out, fenced before any result is seen.** K2 makes every clean-room
  failure a specification defect. That rule needs exactly one exception, and the exception needs a
  boundary drawn *now*, because an unbounded version of it is a laundering route for "I patched the
  verifier until it passed".

  A clean-room failure is an **instrument** defect — repairable, then re-run — only when the arm
  produced **no well-formed verdict at all**, specifically: (a) a crash or a non-terminating run;
  (b) a JSON lexing or parsing error; (c) a base64 or Ed25519 API misuse; (d) output that does not
  parse as a verdict.

  It is **never** an instrument defect when the arm emitted a well-formed verdict that disagrees about
  which check fires, or about whether the document is accepted. Every semantic disagreement is a
  specification defect under K2. Any repair made under this carve-out is recorded as an amendment
  naming the category, with the diff, before the arm is re-run.

- **K7 — the arms are the instrument; the specification is the subject.** No amendment to the
  specification may be made before all of Arm A and Arm B's results are recorded. Amending first would
  measure a document already repaired, and the temptation to do so is strongest exactly when a result
  is embarrassing.

## What this does not claim

- **Not that a passing clean-room arm makes the thesis true.** The normative tier checks integrity and
  coherence. It does not re-discharge the SMT obligation, and `PRODUCT.md`:118-121 already concedes
  that a third party *"must still trust our verifier that the SMT obligation was actually
  discharged."* Nothing measured here touches that, and a green result must not be read as reaching it.
- **Not that the vectors are the specification.** They are the strongest available proxy and they are
  incomplete by construction: `data_identity` has zero vectors, so no arm can be scored on it, and §9's
  "A wrong-key signature REJECTS" has no vector either. An arm passing 26 of 26 would have been tested
  on 11 of 12 implemented checks.
- **Not a measure of implementer skill.** A subagent is not a domain expert reading carefully over
  days. It is a fixed-effort faithful reader, which makes the arms comparable to each other and makes
  a *pass* strong evidence — but makes a single failure weaker evidence than an expert's failure would
  be. Where an arm's failure looks like inattention rather than ambiguity, that must be said.
- **Nothing about the capability envelope.** No detector, repairer, premise or corpus figure is touched
  by this work. `docs/trust/premise-acquisition-result.md` stands unchanged.
- **Not that agreement between our two existing implementations was worthless.** It excludes a large
  class of transcription and arithmetic error. It just cannot exclude a shared misreading of the
  specification, which is the only thing under test here.

## Expected outcome, stated in advance

I expect **H1 to be confirmed** and **P1, P6, P7 and P9 to hold**. I am genuinely unsure about three:

**P5** is the prediction I would most like to be wrong about, and the one I have thought hardest
about. It rests on my having correctly traced five witness vectors against a single sentence of schema
prose by hand. If Arm B fails the witness set anyway, the likely reason is that "the written value's
count equals its support" is ambiguous about *which* count when a digest appears more than once, and
my hand trace silently assumed the charitable reading.

**P8** could fail in either direction and I cannot predict which. §6.2 says the field is required and
non-nullable; the committed vector says a null there is a vocabulary failure and not a schema failure.
Both readings are defensible from the document, which is itself the finding whichever way the arms
land.

**P11 is the one most easily satisfied on paper and not in fact** — the same warning
`entailment_witness.md`:89-90 attached to its own F4. It is scored by a fresh agent that has seen
neither arm, or it is not scored at all.

If P1 fails and Arm A passes every vector, H1 is refuted, and under K3 that is the result that gets
published: it would be the strongest evidence for the word *without* this project has ever produced,
and considerably more valuable than the finding I expect.

---

## Amendment 1 — Arm A and Arm B results, 2026-09-15

Appended, not edited. Both arms were built and run before any character of
`specs/SPEC_repair_attestation.md` was changed, satisfying K7. Raw per-vector outcomes are in
`eval/results/specification_sufficiency.json`; the runner is
`scripts/bench/measure_specification_sufficiency.py`.

### Headline

| Arm | Inputs | Agrees | Rate | Checks emitted |
| --- | --- | --- | --- | --- |
| **A** | `SPEC_repair_attestation.md` only | 17 of 26 | 0.6538 | 11 |
| **B** | that plus `repair_attestation.schema.json` | 3 of 26 | 0.1154 | 12 |

The two arms disagree **with each other on 20 of 26** vectors.

**H1 is confirmed.** But the result that matters is not the rate, it is this: **the arm that followed
the specification more faithfully agreed with our implementation less.** §7 mandates that a verifier
*"MUST fail closed on anything unrecognised."* Arm B obeyed that instruction on `Provenance` — a
vocabulary §6.2 promises is *"published as enums in [the JSON Schema]"* and which the schema declares
as `{"minLength": 1, "type": "string"}` — and therefore rejected `valid-deterministic-applied`,
`valid-signed`, and eighteen more. Arm A disobeyed it, reporting `skip` for values it could not
adjudicate, and scored five times better. Faithfulness to the document is **anti-correlated** with
conformance to the reference implementation. No amount of additional prose fixes that; only publishing
the vocabulary does.

### Direction of error, which matters more than the count

| Arm | accepts we reject | rejects we accept | same verdict, wrong checks |
| --- | --- | --- | --- |
| **A** | **5** | 1 | 3 |
| **B** | 0 | 5 | 18 |

Arm A's five unsafe accepts are `reject-unknown-review-reason` and all four witness-rejection vectors.
Four of the five are attestations whose **own witness arithmetic contradicts the write it
accompanies** — precisely the case the witness was added to catch. So a third party holding a faithful
independent implementation built from this document would report `verified` for a repair whose
embedded evidence is self-contradictory. That is the measured failure of the word *without*, and it is
the finding this pre-registration exists to record.

Arm B's errors run the other way: it never accepts anything we reject. An over-strict verifier is a
false-alarm problem; an over-permissive one is a trust problem.

### Scorecard: every prediction, including the two that were wrong

| # | Prediction | Verdict | Evidence |
| --- | --- | --- | --- |
| **H1** | insufficient; ≥1 vector fails | **CONFIRMED** | Arm A fails 9 |
| **P1** | ≥4 vectors fail, the witness set | **CONFIRMED, exactly** | Arm A accepts all 4 witness-rejection vectors |
| **P2** | 11 checks, not 12 | **CONFIRMED** | Arm A emits exactly §7's 11 names |
| **P3** | cannot implement `vocabulary_closed` without `vocabulary.py` | **CONFIRMED, and it is the dominant cause of disagreement in both arms** | Arm A enforced 2 of 7 closed sets and named **zero** `ReviewReason` members, so it accepted `review_reason: "because_i_said_so"`. Arm B failed closed and rejected 20 vectors |
| **P4** | `data_identity` passes vacuously | **CONFIRMED** | both arms emit it, both skip it on all 26; it appears in no failure list |
| **P5** | Arm A fails ≥4 of the witness set, Arm B ≤1 | **REFUTED as stated; substance vindicated** | see below |
| **P6** | both arms fail `reject-unknown-provenance` | **CONFIRMED as stated; mechanism half wrong** | see below |
| **P7** | both arms fail `valid-dry-run` on `verdicts_accepting` | **CONFIRMED, exact mechanism, both arms** | §7.8 states no dry-run branch; our `_check_verdicts` has two |
| **P8** | ≥1 arm adds `schema_complete` on `reject-missing-verification-strength` | **CONFIRMED** | both arms did, and both also added `strength_is_earned`, which I did not predict |
| **P9** | arms disagree with each other on ≥2 | **CONFIRMED, by an order of magnitude** | 20 of 26 |
| **P10** | neither arm reports `constraints_present` on `reject-entity-consensus-claimed-proven` | **REFUTED, both arms, opposite direction** | see below |
| **P11** | Arm C passes all vectors | pending | Arm C not yet run |

Nine confirmed, two refuted, one pending. The refutations:

**P5 was wrong in its letter and right in its substance, and the reason is a defect I did not
anticipate.** Arm B derived the witness coherence rule correctly from the schema's `description`
prose — it fires on exactly the four incoherent witnesses and not on the coherent one, which is
perfect behaviour. It fails the comparison because it named the check **`witness_coherent`** while
ours is **`witness_is_coherent`**, and because the `Provenance` cascade adds unrelated failures. Its
own notes record the cause: *"Name is MINE — spec defines the obligation but not the check name."* So
the schema does carry enough to derive the witness rule, and the specification still cannot yield a
conforming implementation, because **the conformance suite compares check names and the names are not
published anywhere.** An unnamed check is conformance-blocking even when its logic is exactly right.
I predicted a content gap and the binding constraint was a naming gap.

**P6 is confirmed as stated but my mechanism was half wrong.** Arm A *did* reject the unknown
provenance — Appendix A row 6 names `some_future_corrector` as a non-member, which is the one negative
example the document supplies — and then failed to also fire `strength_is_earned`. So Arm A's
disagreement on that vector is a missing second check, not an inability to reject. Arm B's is exactly
the mechanism I predicted. I was right about the vector and wrong about half the reason.

**P10 is refuted in the opposite direction, and the refutation is stronger evidence than a
confirmation would have been.** I predicted neither arm would report `constraints_present` on an
`entity_consensus` fix recorded `proven` with `constraints: null`. **Both** arms reported it, having
independently reached the same literal reading of §7.10 — *"a `proven` untrusted fix requires embedded
constraints"* — against a committed vector that expects `strength_is_earned` alone. Two isolated
faithful readers converging against our implementation means the defect is in the sentence, not in the
readers. Our verifier is the outlier here, and §7.10's scope needs stating rather than the arms needing
correcting.

### K1 audit: method and result

Isolation was audited objectively rather than taken on report, by grepping each arm's committed source
for tokens that exist only behind the prohibition.

**Arm A passes.** `witness`, `witness_is_coherent`, `group_size`, `strict majority`, `llm_live`,
`escalate`, `ambiguous_fd`, `not_inferable`, `verification_strength_for` — **all zero**. The decisive
marker is `witness` = 0: the word appears in the JSON Schema and in both existing implementations and
nowhere in the spec markdown, so zero occurrences is positive evidence Arm A read none of them. The
four vocabulary tokens it does use (`deterministic`, `external`, `entity_consensus`,
`some_future_corrector`) all appear in the spec's own §7 and Appendix A.

**Arm B passes.** `witness_is_coherent`, `llm_live`, `verification_strength_for`, `AttestationCheck`,
`verify_attestation` and the distinctive clause *"not entailed by the rule"* — all zero. Two markers
were non-zero and were resolved by reading them in context rather than by assumption:
`Verify.java:1074` emits `"support " + support + " exceeds group_size " + group`, which is
near-identical to the Python's message, and `:1077` emits a differently-phrased strict-majority
message. Both are convergent phrasings over two field names the schema publishes; Arm B reproduced
neither the Python's distinctive 16-word tail nor any code comment.

**That convergence is worth keeping, because it calibrates a separate finding.** The evidence that
`playground/web/src/attestation/verify.ts` was ported rather than independently written is three
character-identical message strings plus an identical code comment
(`__init__.py:656/658/664/697` against `verify.ts:464/467/470/510`). Arm B is an accidental control
group for that inference: genuine independent convergence produced **one** short phrase over shared
field names and **no** comment. The port produced long distinctive clauses and a comment. The
inference survives and is now empirically calibrated rather than merely plausible.

### Deviations, disclosed

- **The harness auto-injected `CLAUDE.md` into Arm A's context**, which Arm A volunteered rather than
  concealed. It is not one of the two prohibited implementations, so K1 is not triggered, and the
  grep audit above shows no check name and no vocabulary member reached either arm. But the honest
  statement is that **structural isolation was incomplete by construction**: a subagent cannot be
  fully sandboxed from repository-level instruction files under this harness. The contamination
  channel existed and was empty in this instance; it is not guaranteed empty for a future arm, and
  Arm C inherits the same exposure.
- **Arm B's narrative report was lost.** The agent was cut off after its 33 self-tests passed, while
  validating its PAE against the DSSE protocol's published example. Its instrument, sources and
  pre-coding check enumeration (`eval/cleanroom/armB/NOTES.md`) all survived and the vector run is
  unaffected, but the exhaustive markdown-versus-schema divergence list I asked it for does not
  exist. That list was reconstructed independently by direct reading and is published in
  `docs/trust/`, so the finding is not lost — but it rests on my reading rather than on two
  independent readings, and it is weaker for that.
- **No repair was made to either arm under K6.** Both produced well-formed verdicts on all 26
  vectors, so the instrument carve-out was never invoked. Every disagreement above is scored as a
  specification defect.

---

## Amendment 2 — Arm C's inputs, a disclosed deviation from P11, 2026-09-15

Written **before Arm C was launched and before any Arm C result existed**, because the deviation
would otherwise be indistinguishable from choosing the inputs that flatter the amendment.

**P11 says "given the amended prose alone".** That is no longer the right test. The amendment adds
§3.1, which for the first time *declares* the normative surface to be three artifacts — the
markdown, the generated JSON Schema, and the vectors — and deletes the false claim that the
markdown alone suffices. Testing "prose alone" would now be testing a claim the specification
deliberately no longer makes, which is a strawman and would produce a failure that means nothing.

**Arm C therefore receives the amended markdown plus the amended JSON Schema: Arm B's inputs,
after the fix.** That makes Arm C a direct before-and-after on the same input class — Arm B scored
3 of 26 — and it tests the sufficiency claim the specification actually asserts.

**Arm C does not receive the vectors**, even though §3.1 names them normative, because they are the
answer key and an arm that reads them measures nothing. This is fair rather than convenient: the
vectors are normative only for the *check names*, and §7 now publishes every name, which is exactly
the gap that cost Arm B four vectors on witness logic it had implemented correctly.

**Two consequences for scoring, fixed here rather than after the fact.** The suite has grown from
26 vectors to 30 — four were added, none weakened, so K4 holds — which means Arm C's raw rate is
not directly comparable to Arm A's or Arm B's. The write-up must report Arm C **both** over all 30
and restricted to the original 26. And P11's bar stands unchanged: **all** vectors, not most. A
partial pass is a failure of P11 and gets published as one.

---

## Amendment 3 — Arm C result, P11 refuted, and one instrument defect, 2026-09-15

### Result

| Arm | Given | Over the original 26 | Over all 30 | Checks |
| --- | --- | --- | --- | --- |
| **A** | markdown only | 17 of 26 — 0.6538 | 21 of 30 — 0.7000 | 11 |
| **B** | markdown + schema, before | 3 of 26 — 0.1154 | 3 of 30 — 0.1000 | 12, one misnamed |
| **C** | markdown + schema, after | 25 of 26 — **0.9615** | 29 of 30 — **0.9667** | 12, all correctly named |

Arm C is Arm B's input class after the amendments, so **0.1154 → 0.9615 over the identical 26
vectors** is the measured effect of the fix. Arm C emitted every check name correctly, including
`witness_is_coherent`, which is the name that cost Arm B four vectors on logic it had implemented
perfectly.

### P11 is REFUTED

P11 predicted Arm C would pass **all** vectors. It passed 29 of 30. Under the terms fixed in
amendment 2 — *"a partial pass is a failure of P11 and gets published as one"* — this is a
refutation, and it is recorded as one rather than as a near-miss.

The single residual disagreement is a specification gap nobody had named across three arms and two
sessions: **the specification does not say whether a failing `signature` stops the remaining
checks.** The reference verifier short-circuits and reports `signature` alone; Arm C ran all twelve
checks on the tampered payload and additionally reported `subject_matches_post_state`, because the
tampering sets `applied` to false and the subject digest then no longer matches `source.digest`. Arm
C is correct on the letter of §7's *"Every check is reported individually"*.

§7 now states the short-circuit rule explicitly. **That amendment is untested by any arm.** It closes
the gap for a future one; claiming it closes the gap now would be exactly the inference this
pre-registration was written to prevent.

### One instrument defect, repaired under K6

Arm C's first run reported **28 of 30**, with `reject-data-identity-mismatched-bytes` scored as an
unsafe accept. That was false. The runner
(`scripts/bench/measure_specification_sufficiency.py`) never passed `--data` to the arms: the
`data_b64` field had been added to the vector format and the runner was never wired to consume it,
so Arm C had never been handed the bytes whose digest it was accused of not checking.

This falls inside K6 category (d) — output that does not reflect a verdict the arm was in a position
to reach — and it is a defect in the **runner**, not the arm, which is a clearer case than K6
anticipated. Repaired, re-run, result above. The diff is a three-line addition writing the decoded
bytes to a scratch file and appending `--data`.

Recorded because the shape of the mistake is the one the handoff warned about: a single, oddly
specific failure on exactly the vector that exercises a newly added field is a bug in the instrument
before it is a finding.

### Deviations, disclosed

- **Arm C's narrative report was lost**, as Arm B's was — the agent's result was unavailable when
  collected, though its sources, compiled classes and verdicts all survived. So for two of the three
  arms I have the instrument and the measurement but not the reasoning. The ambiguity inventory in
  `docs/trust/specification-sufficiency.md` therefore rests on Arm A's report plus my own reading,
  not on three independent readings, and it is weaker for that.
- **Arm C inherits Arm A's `CLAUDE.md` exposure.** The audit found zero occurrences of
  `verification_strength_for`, `AttestationCheck`, `verify_attestation`, `NORMATIVE_CHECKS`,
  `_check_strength`, `_check_witness`, or the Python's distinctive error clause in Arm C's source.
  Note that `witness_is_coherent` and the five `Provenance` members are **legitimate** for Arm C:
  the amendments publish both, which is the entire point of the amendments.

### Final scorecard

| # | Verdict |
| --- | --- |
| H1 | **CONFIRMED** |
| P1, P2, P3, P4, P6, P7, P8, P9 | **CONFIRMED** (P6's mechanism half wrong for Arm A) |
| P5 | **REFUTED as stated**, substance vindicated — the binding constraint was an unpublished check *name*, not missing content |
| P10 | **REFUTED**, both arms, opposite direction — two isolated readers agreed against our implementation |
| P11 | **REFUTED** — 29 of 30, one residual named defect |

Nine confirmed, three refuted, none unscored. The three refutations are the most useful results in
the document: P5 identified a defect class nobody had named, P10 established that the reference
implementation was the outlier, and P11 stopped the amendments being declared sufficient on the
strength of having been made.
