# Pre-registration: can a third party check the premise?

Written 2026-09-16, **before** writing the wire format, the check, or any vector. Nothing below is
edited afterwards; results, deviations and refutations are appended as amendments at the bottom.

## The finding this responds to

Three authority axes have now been closed or measured:

| axis | question | status |
| --- | --- | --- |
| 1. kind enforceability | can *any* verifier reject on this kind? | closed 2026-09-14 |
| 2. type checkability | can the verifiers *encode* this declared type? | closed 2026-09-16 |
| 3. per-kind power | *how much* can each kind reject? | measured 2026-09-16, published, unfixed |

All three made the **engine** internally honest about authority it grants itself. This document is
about a gap none of them touched, one layer up.

> **The certificate's load-bearing claim is unbound to the premise it cites.**

Read directly, not from a report. `_check_strength` (`dataforge/attestation/__init__.py`:1024-1090)
emits two checks. The one that mentions constraints is this, in full:

```python
    if needs_constraints:
        has_constraints = isinstance(constraints, Mapping) and bool(constraints)
        checks.append(
            AttestationCheck(
                "constraints_present",
                has_constraints,
                "embedded constraints support the schema-proven writes"
                if has_constraints
                else "a write is proven only by schema authority, but no constraints are embedded",
            )
        )
```

The assertion is `bool(constraints)`. The detail string says the constraints *support the
schema-proven writes*. The check does not test that, has never tested that, and cannot test that —
nothing in the function compares `constraints` to anything.

Three supporting facts, each verified by reading the code:

1. **`authority.authoritative_columns` is trusted input.** `_check_strength` reads it at `:1031` and
   re-derives per-fix strength from it. A reader running the check learns nothing about the premise,
   because the check's input *is* the claim.
2. **`authority.constraints` is not derived from the schema the engine used.** `cli/emit.py`:97
   re-reads the operator's `--schema` file from disk; `cli/attest.py`:254-259 accepts an arbitrary
   JSON file. Neither is a projection of the parsed `Schema` that `authoritative_columns` was computed
   from.
3. **`authority.constraints_digest` is verified by nobody.** It occurs at `__init__.py`:258 (a
   comment), :405 (computed) and :429 (embedded) — all three inside `build_attestation`. It occurs
   zero times in `playground/web/src/attestation/verify.ts`. The three clean-room Java verifiers
   assert only that it is 64 hex characters.

Therefore: **a producer can emit any `authoritative_columns` beside any `constraints` payload and pass
all twelve normative checks.** The thesis says a third party can verify *without trusting DataForge*.
At the premise layer they cannot; they can only re-read our own claim back to themselves.

There is also no `Schema` → dict projection anywhere in the package. `cli/common.py`:262-264 records
the reason and calls an unreviewed wire format "not a trade worth making". That is a requirement to
*specify* one before putting it on a normative path, which is what step 2 below does.

## H1

**A recomputation check is addable without weakening any existing vector, and it rejects a forged
authority claim that passes today.**

Concretely: the authoritative column set is a pure function of the premise
(`authoritative_columns`, `engine/repair.py`:1400-1444, whose two inputs are fixed allowlists), so it
can be recomputed by any implementation from a published premise and a published rule. If that is
true, `proven` stops being a claim a reader must accept and becomes arithmetic a reader can check.

## Predictions

Each is scored in an amendment. I expect P2 and P6 to be the ones that bite.

**P1.** All eleven `Schema` fields round-trip losslessly through the canonical form:
`premise_from_canonical(premise_to_canonical(s)) == s` for hypothesis-generated schemas. The four
`frozenset[str]` fields and the six `tuple[...]` rule collections are the risk; `DomainBound`'s
`min_value`/`max_value` floats and the `Literal["sum","avg"]` on `AggregateDependency` are the fiddly
ones.

**P2.** Exactly **one** of the thirty existing vectors changes verdict: `dangling`
(`generate_attestation_vectors.py`:207), which claims `authoritative_columns: ["amount"]` with
`constraints=None`. It gains `authority_is_entailed` alongside the `constraints_present` it already
fails. No vector loses a failure.

**P3.** The other twenty-nine verdicts are byte-identical. Twenty-six use `_base_predicate()` with
`authoritative_columns: []` and `constraints: None` — an empty claim, which any premise entails,
including none. Three use `_with_authority` with `{"columns": {"amount": "int"}}` claiming
`["amount"]`; `int` is in `DISCRIMINATING_COLUMN_TYPES`, so that premise entails exactly that column.

**P4.** A document whose `authoritative_columns` names a column the embedded premise does not entail
is REJECTED by **both** implementations, and the *same document* is ACCEPTED by the pre-change code.
Demonstrating both halves is the point; showing only the rejection would not establish that the check
changed anything.

**P5.** The per-kind breakdown in the check's detail names `columns` as the conferring kind on the
three authority-passing vectors. This is the first time a consumer of an attestation can see *which*
kind conferred authority — `witness.constraint_kind` has exactly one enum member
(`functional_dependency`), so seven of the eight authority-conferring kinds currently publish nothing.

**P6.** A premise declaring a column `str` and claiming authority over it is rejected. This is the
Axis-2 fix becoming externally checkable: `str` is encodable but non-discriminating, so it confers
nothing, and until 2026-09-16 an unrecognised spelling like `date` would have conferred authority. A
clean-room implementation reading only the old spec would over-credit here, which is why the rule must
be published verbatim rather than described.

**P7.** Verifying `constraints_digest` catches nothing that the entailment check does not already
catch. It digests the payload sitting beside it, so it is **tautological with respect to forgery** — an
attacker editing the premise recomputes it for free. I predict it detects only transcription damage
(truncation, encoding corruption), and I am recording that prediction because the honest options are
to verify it while stating that limit, or to remove it. Adding it and implying it prevents forgery
would be the same defect as the `constraints_present` detail string above.

**P8.** No existing test outside the attestation suite changes behaviour. The premise projection is
additive; `authoritative_columns` itself is untouched.

## Kill criteria

**K1.** If the existing vectors cannot satisfy the check without relaxing it, **the design is wrong
and is abandoned** — the check is not loosened to fit. A check that passes because it asks less than
it claims is the defect this whole document is about.

**K2.** No vector may have an assertion removed. `expect_failures` is an exact set on both sides, so
`dangling` gaining a name is a strengthening; any vector *losing* a name is a regression and stops the
work.

**K3.** If the round-trip is lossy for any `Schema` field, that field is **named in the spec as
unrepresentable and the check refuses on a premise containing it**. Silently ignoring an
unrepresentable field would let a premise confer authority through a channel the published format
cannot express — the same shape as Axis 1.

**K4.** If the TypeScript half cannot reach parity, **the entire change is reverted** rather than
shipped as a Python-only check. This session already measured what a single-implementation format is
worth: the "independent" TS verifier turned out to have been *ported*, and a check that only one
implementation runs is an assertion, not evidence.

**K5.** An unrecognised key or shape in the embedded premise must be a **refusal**, not an ignore.
`schema_from_mapping` silently `continue`s past malformed input at seven sites
(`cli/common.py`:78, 134, 152, 165, 179, 203, 206) and accepts two different shapes for
`accepted_values` and `regex_constraints`. A third party cannot be asked to replicate silent discards,
so the canonical form is one shape per field and anything else fails closed.

**K6.** If `--trust-mined-constraints` cannot be made self-consistent — the flag computes authority
from a merged schema whose mined constraints never enter the attestation, so the document understates
its own authority basis — then attestation under that flag **refuses**. Publishing a premise that is a
strict subset of the authority basis would be a *new* instance of the defect, introduced by the fix
for it.

**K7.** The instrument binding: the twelve existing checks must keep their current verdicts on all
thirty vectors. If adding a thirteenth check perturbs an existing one, the harness is wrong and the
result is not reportable until it is understood.

## What I expect to be wrong about

**P7 is the one I most expect to be judged wrong in spirit rather than in fact.** The digest is
tautological, and the temptation will be to verify it anyway because it is five lines and looks like
diligence. If verifying it cannot be stated to catch something real, the honest outcome is to remove
the field or document it as decorative — and I am pre-committing to that rather than shipping a check
whose detail string overstates it, which is precisely the defect that opened this document.

**P2 is the prediction most likely to fail on a detail I have not seen.** `expect_failures` is an
exact set and cascading failures must all be listed; if `authority_is_entailed` fires on a vector I
predicted was empty-claim-trivial, the cause is a premise shape I mis-read, and that is a finding
about the vectors rather than about the check.

---

## Amendment 1 — results, 2026-09-16

Appended, not edited. All gates green: 3155 tests pass, the eight CI gates pass,
`mutate_attestation.py` reports **all 15 mutants killed covering every one of the 13 normative
checks**, and `attestation_conformance.py --check` reports both implementations agreeing on all 35
vectors.

### H1 confirmed

The check is addable without weakening any existing vector, and it rejects forgeries that passed
before. The decisive evidence is a single line of output from the forged document:

```
FORGED -- authority claimed over a column the premise never names
  ok       : False
  failures : ['authority_is_entailed']
```

**One name in the failure list.** Every other check passes on that document, so the twelve-check
verifier that existed this morning issued it a clean certificate. The honest sibling, differing only
in that its claim matches its premise, reports `ok: True` with
`conferred by {'columns': ['amount']}`.

The independent implementation gives the same evidence from the other side. Before the TypeScript
half was written, `vitest` reported `failures=[]` on all five new forgery vectors — the browser
verifier **accepted every one of them**. That is not a theoretical gap.

### Scorecard

| # | Verdict | Evidence |
| --- | --- | --- |
| **P1** | **CONFIRMED** | exact-identity round-trip over 200 generated schemas covering all 11 fields, plus 9 fail-closed refusals. Preserving rule order rather than sorting was what made identity hold |
| **P2** | **CONFIRMED, with a disclosure** | exactly one original vector changed verdict — see below |
| **P3** | **CONFIRMED** | the other 29 verdicts unchanged |
| **P4** | **CONFIRMED, both halves** | quoted above |
| **P5** | **CONFIRMED** | `conferred by {'columns': ['amount']}` in the passing detail |
| **P6** | **CONFIRMED** | `str` and `date` premises both REJECT; two committed vectors |
| **P7** | **honoured as pre-committed** | digest verification was **not** added; the limitation is published instead, in SPEC section 6.4 |
| **P8** | **REFUTED** | the change is not purely additive — see below |

### P2, and the choice I had to make

`reject-external-off-authority` overrides `authoritative_columns` to `["id"]` to test that a fix on
`amount` is unproven. Its premise was `{"columns": {"amount": "int"}}`, which entails `["amount"]` —
so leaving it alone would have made that vector fail **two** checks and stop isolating the one it
exists for. I gave it a premise declaring `id`, matching its own claim.

That is a deliberate choice and it is worth naming: the alternative was also a correct REJECT, and it
would have been a worse vector, because "one vector per distinct rejection reason" is what lets a
failure name point at a cause. Had I not looked, P2 would have been refuted by a second changed
verdict that I had caused rather than discovered.

### P8 refuted: `attest build` now needs the premise

I predicted the projection was purely additive. Six tests in
`tests/integration/test_attest_build_cli.py` failed, and the reason is a genuine behaviour change:
**a receipt claiming authority over columns can no longer be turned into a verifiable certificate
unless the premise is supplied.** `attest build` without `--constraints` now refuses.

The cause is a distinction I had not drawn. `constraints_present` fires only when a fix needs
constraints — untrusted provenance, proven by schema. Those fixtures repair with `deterministic`
provenance, so it passed trivially while `authoritative_columns` was still published as a fact. So
the pre-existing check let a document publish an authority claim that nothing needed and nobody could
check. `authority_is_entailed` is unconditional on purpose: a derived fact published without its
derivation is exactly the unfalsifiable claim this work exists to remove.

Two consequences, both kept:

- `--constraints` now accepts YAML as well as JSON, via the same loaders `--schema` uses. The premise
  that must be published is the one the repair ran against, and on every documented path that file is
  YAML — the flag could not previously read it.
- The operator-supplied file is now parsed into a real `Schema` rather than passed through opaquely,
  so a premise that is not a valid schema is refused at the boundary.

### K6 fired, as written

`--trust-mined-constraints` computes authority from the declared schema merged with accepted mined
candidates, and the mined half is in no schema file. Publishing the declared premise under that flag
would produce a document whose premise understates its own authority basis — a new instance of the
defect, introduced by the fix for it. So `attest_result` **withholds the attestation** under that
flag, with the reason named in the payload.

That is the conservative branch K6 pre-registered. The capability is recoverable by threading the
effective schema through the receipt; that is a change to a frozen public contract
(`RepairPipelineResult` is `extra="forbid"`, `frozen=True`) and is deliberately not bundled here,
because bundling it would make neither change attributable.

### K1, K2, K3, K4, K5, K7 all silent

- **K1** did not fire: the committed vectors satisfy the check as designed, so it was never a question
  of relaxing it.
- **K2** did not fire: `dangling` **gained** `authority_is_entailed` and lost nothing.
- **K3** did not fire: the round-trip is lossless. One case cannot be published at all — a non-finite
  `DomainBound`, which JSON has no representation for — and it **raises** rather than being dropped,
  which is the behaviour K3 required.
- **K4** did not fire: 40 of 40 TypeScript tests pass and `tsc --noEmit` is clean.
- **K5** is satisfied structurally: nine refusal tests cover a missing format, an unrecognised format,
  an unknown top-level key, an unknown rule attribute, a wrong container shape, a bare string where an
  array belongs, a rule violating its own constraint, a non-finite bound, and a non-object premise.
- **K7** did not fire: all twelve pre-existing checks keep their verdicts on every original vector.

### An unplanned consequence, and it is the one I would defend hardest

The authority rule had to move. `dataforge/attestation/__init__.py` imports nothing from the package
except `dataforge.domain.vocabulary` — the verifier is deliberately decoupled from the repair engine,
so a third party running the normative tier does not drag in the repairer. The rule lived in
`dataforge/engine/repair.py`. Restating it beside the verifier would have been a fifth instance of
the hand-maintained-duplicate defect, so `columns_named_by_constraint_kind` and
`authoritative_columns` moved to `dataforge/domain/premise.py` and the engine imports them.

**The authority rule is protocol, not engine behaviour.** That is what publishing it in the
specification asserts, and the module boundary now says the same thing.

### A reversal whose condition was written down first

Projecting `DISCRIMINATING_COLUMN_TYPES` and `ENFORCEABLE_CONSTRAINT_KINDS` to the browser reverses a
withhold made earlier the same day. The withheld entry named its own reversal condition — *"if a
browser consumer ever needs to warn that an attestation claims authority over a column whose declared
type cannot support it, this must be projected in the same change as that consumer, never before it"*
— and check 13 in `verify.ts` is that consumer. The original text is retained in
`scripts/ci/generate_domain_vocabulary.py` rather than deleted, because a reversal whose stated
condition cannot be re-read is indistinguishable from a convenient one.

The old reasoning was half right, and the half that was right is worth keeping: a second
implementation of the rule *is* a risk. The answer is that the rule is published in the specification
and projected from one source — not that the browser is denied it, which is what left
`authoritative_columns` uncheckable in the first place.

### A gate hole closed in passing

`ENFORCEABLE_CONSTRAINT_KINDS` was absent from `vocabulary.__all__`, and
`generate_domain_vocabulary.py` derives its projection-coverage population from `__all__`. So a
constant imported by another module, asserted by two tests, and now published in the specification was
invisible to the gate that exists to stop exactly that. It is in `__all__` now, with the reason
recorded at the line. This is the same population-derivation hole surfaced in
`per_kind_authority.md` amendment 3, closed for one more constant rather than in general.

