# Binding the premise: making the authority claim checkable

Until 2026-09-16, a DataForge attestation could claim write authority over any set of columns beside
any constraint payload and pass every normative check. The claim was the most load-bearing field in
the certificate and the only one no implementation ever tested against anything.

That is closed. `authority.authoritative_columns` is now recomputed from `authority.premise` by both
implementations, under a rule published in the specification, and a document whose premise does not
entail its claim is rejected.

## The evidence, in one comparison

Two attestations, differing only in the authority claim. Same premise, same fixes, same signature
path.

| document | `authoritative_columns` | premise entails | verdict | failing checks |
| --- | --- | --- | --- | --- |
| honest | `["amount"]` | `["amount"]` | **accept** | none |
| forged | `["amount", "secret"]` | `["amount"]` | **reject** | `['authority_is_entailed']` |

**One name in that list.** Every other check passes on the forged document — so the twelve-check
verifier that shipped before this change issued it a clean certificate, signature and all.

The independent implementation says the same thing from the other side. Before the TypeScript half of
check 13 was written, its test run reported `failures=[]` on all five new forgery vectors: the browser
verifier **accepted every one of them**. The gap was not theoretical.

The honest document's check reports which kind conferred the authority:

```
the published premise entails authority over exactly ['amount']; conferred by {'columns': ['amount']}
```

That is the first time a consumer of an attestation can see *which* constraint kind gave the engine
authority. It matters because the eight conferring kinds differ by a factor of ten in what they can
actually reject (`docs/trust/per-kind-authority.md`), and until now a reader saw only a flat list of
column names.

## What was actually wrong

Three facts, each read from the code rather than inferred:

1. **`constraints_present` tested non-emptiness.** The assertion was
   `isinstance(constraints, Mapping) and bool(constraints)`, while its detail string said the
   constraints *"support the schema-proven writes"* — an assertion the function never made and could
   not make, because nothing in it compared `constraints` to anything. The string is corrected.
2. **`strength_is_earned` reads the claim as trusted input.** It derives every fix's strength from
   membership in `authoritative_columns`, so running it tells a reader nothing about the premise. The
   specification already admitted this: *"it re-derives strength with the same rule the producer used
   to stamp it, so within one implementation it validates field consistency rather than the rule."*
3. **`constraints_digest` was verified by nobody.** It appeared three times in the reference
   implementation, all inside `build_attestation`, and zero times in the TypeScript verifier. The
   three clean-room Java verifiers assert only that it is 64 hexadecimal characters.

And `authority.constraints` was never derived from the schema the engine used — it was the operator's
`--schema` file re-read from disk, or, via `attest build --constraints`, any JSON object at all.

## How it is checked now

The premise is published in a canonical format (`dataforge.premise/v1`, specification section 6.4.1)
that round-trips: a property test asserts
`premise_from_canonical(premise_to_canonical(s)) == s` over generated schemas covering all eleven
`Schema` fields. The authority rule is published verbatim in section 6.4.2 — both allowlists in full,
so a reimplementation does not have to infer them — and applied by check 13 in both implementations.

Three cases, and the distinction is normative:

- an **empty** claim passes whatever the premise, because it asserts no authority;
- a **non-empty** claim with an absent or unreadable premise fails, and the parse error is reported
  rather than swallowed;
- otherwise the two sets must be **equal** — not containment, because a claim narrower than the
  premise entails means producer and reader disagree about the rule, and a conservative disagreement
  is still a disagreement.

The format fails closed on everything: an unrecognised `premise_format`, an unknown top-level key, an
unknown rule attribute, a wrong container shape, a bare string where an array belongs, a rule
violating its own constraint. DataForge's own convenience loader accepts two shapes for
`accepted_values` and silently skips malformed input at seven sites; a third party cannot be asked to
reproduce silent discards, so the wire format accepts exactly one shape per field.

The per-kind breakdown is **derived at verification time, never embedded**. Publishing it would add a
field a forger could set; deriving it adds nothing to forge.

## What this does and does not claim

**Claimed.** An attestation whose `authoritative_columns` names a column the embedded premise does not
entail is rejected by both implementations. A premise declaring a column `str` (encodable, constrains
nothing) or `date` (narrows, but no verifier can encode it) confers no authority, and claiming
otherwise is rejected. The premise format round-trips every `Schema` field. All 15 mutants are killed,
covering all 13 normative checks, including one that reverts this check to taking the claim on trust.

**Not claimed — and this is the residual gap.** The check verifies that the claim follows from the
**published** premise, not that the published premise is the one the operator repaired against. A
producer that embeds a premise it never used produces a self-consistent document. Binding the premise
to the *data* is what `data_identity` and the journal do, and neither is complete: `data_identity`
binds the bytes, and nothing binds the bytes to the premise. Closing that needs the premise digest
inside the signed subject, and it is not done here.

**Not claimed.** That `constraints_digest` prevents anything. It digests the payload beside it, so an
editor of one recomputes the other for free. It is tautological with respect to forgery, and rather
than verify it and imply otherwise, the limitation is stated in specification section 6.4. The honest
options were to verify it while naming that limit or to remove it; publishing the limit is the first.

**Not claimed.** That this improves the engine's behaviour at all. Nothing about which writes are
permitted has changed. What changed is whether a third party can check the claim afterwards — and one
capability was **withdrawn**: under `--trust-mined-constraints` the attestation is now withheld,
because authority there comes from a merged schema whose mined half is in no file, so any premise
published would understate its own authority basis. Recovering it needs the effective schema threaded
through the receipt.

**Not claimed.** That the specification is now sufficient for a clean-room implementation. The last
measurement of that put two independent verifiers at 17 of 26 and 3 of 26
(`docs/trust/specification-sufficiency.md`), and check 13 has not been through that test. The
allowlists are published verbatim precisely because a clean-room reader working from the older prose
would have over-credited `date`.

## Reproducing it

```
python -m pytest tests/property/test_premise_round_trip.py -q   # the format round-trips
python scripts/ci/spec_correspondence.py --check                # 13 specified, 13 implemented, 13 exercised
python scripts/ci/mutate_attestation.py                         # 15 killed, 13 checks covered
python scripts/ci/attestation_conformance.py --check            # both implementations, 35 vectors
```

Pre-registration, predictions and the two refutations: `eval/preregistration/premise_binding.md`.
