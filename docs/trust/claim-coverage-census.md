# Claim coverage: 8.41% of published decimal figures are bound to evidence

**Date:** 2026-09-14
**Pre-registration:** [eval/preregistration/claim_coverage_census.md](../../eval/preregistration/claim_coverage_census.md)
**Instrument:** `scripts/ci/claim_coverage.py`
**Baseline:** `eval/results/claim_coverage_baseline.json`
**Gate:** `make claim-coverage`, `tests/unit/test_claim_coverage_census.py`

## What was not being checked

`docs_truth.py` verifies 149 registered claims against JSON artifacts, in both directions per
claim. It opens no document except the ones its claims name, so it is an **allowlist**: a number
nobody registered is invisible to it. That is the direction the hospital anchor drifted through for
54 days with every gate green, and the repository already said so about itself —
`tests/unit/test_release_gate.py`: *"a planted unregistered bolded numeral passes, which is a
coverage direction this gate does not have."*

## The measurement

Decimal figures with two or more fractional digits, across 53 live documents
(`docs/trust/*.md` globbed, plus `README.md`, `PRODUCT.md`, `ARCHITECTURE.md`):

| category | count | meaning |
| --- | --- | --- |
| **BOUND** | **89** | a ledger entry binds it to an artifact for that document |
| **GENERATED** | **12** | inside a `<!-- BENCH:START -->` block, so it cannot drift |
| **RESTATED** | **185** | the same value is bound in a *different* document |
| **UNSOURCED** | **772** | nothing binds it |
| total extracted | **1,058** | |

**Bound share: 0.0841.** 38 of 53 documents contain no bound figure at all.

### The three categories that are not `BOUND` are not equal

`GENERATED` is the **first-best** mechanism and is not a gap. A number written into prose by a
generator cannot disagree with its artifact, which is what Quarto and knitr achieve with inline
code and what `BENCHMARK_REPORT.md` and the README benchmark block already do here. A ledger entry
is the second-best mechanism: appropriate where prose is hand-written, and strictly worse where it
is not, because it creates a second place for the same fact to live.

`RESTATED` — 185 figures — is the sharpest finding. These are values bound *somewhere*, restated in
a document that binds nothing. `README.md` repeats `0.1918`, `1.0000` and `0.4599`, all bound in
other files, and `README.md` is not a registered document at all. **A copy can therefore drift
alone with every gate green.** The category is reported separately rather than folded into
`UNSOURCED` because the remedy differs: a restatement needs a pointer to what it copies, not a new
artifact binding.

## What this figure is not

`extracted_figures` is a **lower bound** on the published claim population, and `bound_share` is
coverage over that lower bound — never coverage of all published claims. Only decimals with two or
more fractional digits are counted. Integers (`451` repairs, `116` corruptions), percentages and
one-place decimals (`0.73`) are outside the extractor entirely. Fenced code is skipped.

The ceiling is real and was established before building this. `statcheck`, doing the same job on
statistics in academic prose — the most format-standardised reporting domain that exists — reports
recognising **~60%** of statistical tests and cannot read numbers that appear only in tables. An
instrument claiming total recall over free prose would be lying, so this one reports its blindness
in its own payload's `limitations` field rather than only here.

**False positives are declared, not silently filtered.** 8 arXiv identifiers were excluded as
`arxiv_id`; semantic versions and ISO dates are excluded as named classes. The pre-registration's
K2 required publishing the confusion rather than a ratio over a junk denominator.

## The design is borrowed, and from where

DO-178C, ISO 26262 and IEC 62304 require bidirectional traceability, and they achieve completeness
by **enumerating the artifact rather than the links**. An unlinked requirement is not invisible and
not an error — it is a *derived requirement*, a named category carrying an obligation. Code that
cannot be traced is *dead* or *deactivated code*, with an explicit verification objective
(DO-178C Table A-7 Objective 9). The artifact is a **traceability matrix**; auditing its
completeness is **coverage analysis**.

`UNSOURCED` is the derived-requirement analogue: named, counted and ratcheted rather than silent.
`doctest` supplies the other half of the shape — it is check-based like this gate, but it enumerates
every `>>>` example and has no allowlist.

**The distinction from the closest prior art, stated rather than assumed.** `statcheck` recomputes
a statistic from components the prose itself reports and needs no external artifact; this binds a
number to an artifact produced by a separate measurement run. Quarto removes the number from the
source entirely; this leaves it reviewable in the diff and checks it. No established name exists for
the reverse direction — scanning prose and demanding each number be sourced — which is why it was
built rather than adopted.

## The ratchet, and the two ways it is designed to fail

772 unsourced figures cannot be triaged in one sitting, so the current state is a committed
baseline and the gate refuses any **increase** per document. New numbers are gated immediately; the
backlog is visible and shrinkable.

- **It ratchets on `UNSOURCED` decreasing, never on `BOUND` increasing.** Fowler on coverage
  targets: *"If you make a certain level of coverage a target, people will try to attain it … high
  coverage numbers are too easy to reach with low quality testing."* A ratchet on registered-claim
  count is satisfiable by registering the easiest numbers, which measures compliance instead of
  coverage.
- **The baseline self-checks its own total.** Committed baseline files conflict on nearly every
  merge, and a bad resolution is the documented way ratchets stop ratcheting. If `unsourced_total`
  disagrees with the sum of its per-document parts, the gate **fails**. A ratchet that silently
  loosens is worse than no ratchet, because it looks like protection.
- **An absent baseline is an error, not a pass.** "Nothing to compare against" and "it checked out"
  must not read the same.

## K1 fired on the first run, and caught a real instrument bug

The pre-registration required that the extractor find every already-registered claim value in the
document that registers it, and that a failure **suppress the coverage figure entirely** rather
than lower it. It fired:

```
INSTRUMENT FALSIFIED (K1). Reporting no coverage figure; fix the extractor first:
  - docs/trust/wide-table-review-burden.md: registered value '25.42' not found by the extractor
```

The document prints it as `**25.42x**`. The extractor's trailing `(?![\w.])` lookahead could not
see a figure with an `x` suffix, while `docs_truth.py` allows exactly that suffix when matching
prose. An extractor stricter than the gate it complements would have under-reported coverage while
looking precise. Fixed, and pinned by a test.

A second instrument bug was caught the same way, by disbelieving a suspiciously round result:
the first draft looked for `BEGIN GENERATED` markers and reported **zero** generated blocks. The
markers this repository actually uses are `<!-- BENCH:START -->` / `<!-- BENCH:END -->`. Reporting
zero would have described the repository's only drift-proof mechanism as absent. The marker pattern
is now derived from a grep of the corpus rather than guessed.

## Predictions, resolved

| # | Prediction | Outcome |
| --- | --- | --- |
| P1 | extractor re-finds all registered values | **CONFIRMED after the K1 fix** — failed on first run, which is the criterion working |
| P2 | bound share between 5% and 20% | **CONFIRMED — 8.41%** |
| P3 | at least 25 documents with zero bound figures | **CONFIRMED — 38 of 53** |
| P4 | README zero bound, at least 3 restated | **CONFIRMED** |
| P6 | extraction precision imperfect and reported | **CONFIRMED** — `arxiv_id: 8`, plus two more declared classes |

## Honest status

- Gate: live in `make claim-coverage`, the backend gate, and the `gate-population` CI job.
- Falsified before being trusted: a planted unregistered decimal fails the gate naming the file and
  counts; a corrupted baseline total fails rather than loosens; an absent baseline fails; a
  generated block is not penalised; fenced code is skipped.
- **Not** claimed: that a `BOUND` number is *correct*. Only that it is bound. Whether the artifact
  it points at measures what the sentence says remains a human judgement, and
  [baseline-protocol-comparability.md](baseline-protocol-comparability.md) exists because that
  judgement has been wrong here before.
- **Not** done: the 772 are grandfathered, not triaged. The highest-risk group is the measured
  precision/recall/F1 figures in `real-error-detection-result.md`,
  `cell-level-detection-result.md`, `deductive-coverage-result.md` and `queue-filter-result.md`,
  which carry measured results and zero registered claims. `RESTATED` figures do not yet name the
  claim id they copy; requiring that is the next increment.
