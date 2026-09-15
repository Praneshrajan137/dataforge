# Inferred-Guard Gap Registry

The advisory inferred guard (`dataforge/verifier/inferred.py`) is the value-check
used **only** when there is no authoritative schema and a fix is not deterministic
-- i.e. for a `plausibility_only` correction (typically an LLM value). It is
deliberately conservative: it rejects values it can prove violate an inferred
constraint and lets everything else pass. This file is the honest, enumerated
registry of what it does **not** catch, and why that is safe.

## Why these gaps are safe (the latency guarantee)

A gap here can only matter for a `plausibility_only` fix, and such a fix is
**never auto-applied** under any policy unless the operator sets the explicit
`allow_unproven_autoapply` opt-in (and even then the receipt records it truthfully
as `plausibility_only`). This is not a convention -- it is an enforced, tested
invariant:

- `dataforge/engine/repair.py` classifies every accepted fix as `proven`
  (deterministic OR authoritative-schema-verified) or `plausibility_only`, and
  only `proven` fixes reach the auto-apply path by default.
- `tests/property/test_no_corruption_invariant.py::test_permissive_policy_never_auto_applies_plausibility_only`
  proves that even a fully permissive policy with confirmed escalations cannot
  auto-apply a plausibility-only value without the opt-in.
- Under an **authoritative schema**, this advisory guard is not the gate at all:
  the full N-version differential verifier (`SMTVerifier` + `DirectVerifier`,
  fail-closed) enforces the real specification, and `reverify_certificate` re-runs
  that differential pair per applied cell.

So every gap below is *latent by construction*: it lives on a path that does not
write to disk by default.

## Enumerated gaps

| # | Gap | Where | Why conservative (safe direction) |
| --- | --- | --- | --- |
| 1 | Non-numeric values skip the domain check | `domain_violation` returns `None` when `parse_numeric` fails | A categorical/string domain is not expressed as numeric bounds; rejecting on numeric range would be wrong for text. Passing is the safe (non-corrupting) direction on a propose-only path. |
| 2 | Only `int`/`float` types are enforced | `type_violation` | `str`, `date`, `bool`, and other inferred types are not value-validated (e.g. a malformed date string passes). Type inference on dirty data is itself uncertain; over-rejecting would block legitimate canonicalizations. |
| 3 | A fully-absent numeric domain passes | `domain_violation` (`low is None and high is None`) | With no observed range there is nothing to bound against. (The one-sided case -- only min or only max known -- **is** now enforced; see the Round-2 hardening.) |
| 4 | An un-compilable inferred regex passes | `regex_violation` on `re.error` | An inferred pattern that does not compile is treated as no-constraint rather than rejecting every value; the pattern was itself a heuristic guess. |
| 5 | FD check fires only on a **unanimous** peer group | `fd_consensus_violation` | It rejects only when every other row sharing the determinant agrees on one dependent value. Mixed groups, empty determinant keys, or absent determinant columns pass. Firing on non-unanimous groups would guess. |
| 6 | No uniqueness / primary-key enforcement | (not implemented) | Uniqueness is a table-global constraint; enforcing it on a single proposed value cannot distinguish the correct owner of a key. Left to authoritative-schema verification, **and that mitigation is real**: both `SMTVerifier` (`smt.py:342,356`) and `DirectVerifier` (`direct.py:160,169`) enforce `unique_columns` and `primary_key_columns`. |
| 7 | No cross-column arithmetic, referential, or cross-row aggregate constraints | (not implemented) | These require a declared specification. The inferred guard is value-local plus a single safe FD-consensus signal by design. **The mitigation named for gap 6 does NOT extend here -- see the correction below.** |
| 8 | Single-pattern regex only | `value_local_violation` iterates inferred patterns individually | Columns with a disjunction of legitimate formats are not modeled as an OR; each inferred pattern is checked independently. |

## What closes a gap

A gap is closed for a given repair the moment an **authoritative schema** is
supplied: the differential SMT/Direct verifier then enforces the real constraint
and the fix becomes `proven` (or is rejected). The inferred guard is not meant to
be a complete verifier -- it is a safe advisory floor for the propose-only path.
Tightening any gap above (making it reject more) is sound and cannot regress the
deterministic or authoritative path; loosening it is not permitted.

### Correction, 2026-09-14: that paragraph was false for gap 7, in the dangerous direction

The sentence above says an authoritative schema closes a gap because "the differential
SMT/Direct verifier then enforces the real constraint". For **referential** and **cross-row
aggregate** constraints it does not. `Schema` accepts `relationships` and
`aggregate_dependencies`, `dataforge/verifier/constraint_ir.py:125-136` compiles a relationship
into a SQL proof query, and **neither verifier contains any branch that reads either field**.
`DirectVerifier` checks exactly six kinds and its accept string says so -- "satisfied all
*tracked* verifier constraints" (`direct.py:262`).

So for gap 7 the declared specification was accepted, granted write authority over the columns
it named, and then never checked. That was worse than not accepting it, because the operator
had reason to believe the column was constrained. Measured: adding a relationship on every
column to the adversarial corpus's permissive premise -- one field, nothing else changed -- took
it from 0 writes to **11**, corrupting **10 of 14** discriminable attacks, and one applied
injection took the table from 6 rows to 7
([authority-enforcement-correspondence.md](authority-enforcement-correspondence.md)).

**What actually closes gap 7 today: nothing, and it no longer pretends otherwise.** Declaring a
relationship or an aggregate dependency now confers **no write authority**
(`dataforge.domain.vocabulary.UNENFORCEABLE_CONSTRAINT_KINDS`), so the gap is honest rather
than closed. Implementing referential verification requires loading the referenced relation,
which no verifier does; it is a capability with its own design question, not a doc fix.

The distinction matters for reading the rest of this file: gap 6's mitigation is real and
measurable, gap 7's was aspirational. They sat in the same table, in the same words, for months.

## Change rule

If you add a check to `inferred.py`, update this registry and confirm the
corruption oracle still passes. If you make a plausibility-only fix auto-applyable
by any path other than the `allow_unproven_autoapply` opt-in, you have broken the
latency guarantee -- do not ship it.
