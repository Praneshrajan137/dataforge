# Pre-registration: how much of the published prose is actually bound to evidence

Written 2026-09-14, **before** the instrument exists and before any coverage figure is known.
Nothing below is edited afterwards; results and deviations are appended as amendments, including
amendments recording my own predictions being refuted.

## The finding this responds to

`scripts/ci/docs_truth.py --check` verifies 149 numeric claims registered in
`docs/quantitative_claims.yaml` against JSON artifacts, in both directions per claim: the artifact
must render the expected value, and the value must appear in the named document.

It is an **allowlist**. `_load_claims()` reads the ledger; the only document ever opened is the one
a claim names. **Nothing anywhere scans a document for numbers that are not registered.** The
repository states this about itself in two places:

- `tests/unit/test_release_gate.py`: *"`docs_truth` is an allowlist … by construction cannot see a
  number nobody registered … A planted **unregistered** bolded numeral passes, which is a coverage
  direction this gate does not have."*
- `tests/unit/test_docs_truth_discloses_coverage.py` records a 2026-09-13 sweep estimating
  "roughly 55-70%" coverage of quantitative and behavioural claims.

That estimate is hand-made and, measured against numeric literals rather than claims, looks
optimistic: a survey found ~1,113 decimal-bearing prose lines across `docs/trust/`, `PRODUCT.md`
and `DECISIONS.md` against 149 registered claims, only **60** of which are decimal-valued.
**30 of 49 `docs/trust/*.md` carry zero claims. `README.md` is not a registered document at all**,
and it restates `0.1918`, `1.0000` and `0.4599`, which are bound in *other* files — so README's
copies can drift alone with every gate green.

This matters more here than it would elsewhere. The project's thesis is that its numbers are true.
An unbound number is exactly how the hospital anchor was stale for 54 days.

## Prior art, and what it changes about the design

Named because `PRODUCT.md` 9 requires citing prior art rather than assuming a gap.

- **The completeness pattern is settled in safety-critical engineering.** DO-178C, ISO 26262 and
  IEC 62304 require bidirectional traceability, and they achieve completeness by **enumerating the
  artifact, not the links**. An unlinked requirement is a named category — a *derived requirement*
  — with an obligation attached; untraceable code is *dead* or *deactivated code* with an explicit
  objective (DO-178C Table A-7 Objective 9). Terminology: *traceability matrix*, *coverage
  analysis*. This instrument copies that shape, and so the design is not novel.
- **`statcheck`** extracts statistics from prose and recomputes them. It reports recognising
  **~60%** of statistical tests, cannot read numbers that appear only in tables, and requires exact
  APA formatting — in the most format-standardised reporting domain that exists. So **automated
  extraction has a ceiling well below 100%**, and any instrument claiming total coverage of prose
  numbers is lying. This is the single most useful constraint on the design.
- **Literate programming (Quarto, knitr, Org-babel) *injects* computed values into prose** via
  inline code, eliminating drift structurally rather than checking for it. That is the *first-best*
  mechanism, and this repository already uses it: `BENCHMARK_REPORT.md` is generated, and the
  README benchmark block is generated from `eval/results/agent_comparison.json`. A ledger is the
  second-best mechanism, appropriate only where prose must be hand-written.
- **`doctest` is check-based, like this gate — but it enumerates every `>>>` example.** No
  allowlist. That is the shape to copy.
- **Ratchets fail by Goodhart.** Fowler on coverage targets: *"If you make a certain level of
  coverage a target, people will try to attain it … high coverage numbers are too easy to reach
  with low quality testing."* A ratchet on *registered claim count* is satisfiable by registering
  the easiest numbers, so the ratchet must not be on that quantity.

**The distinction from each, stated rather than assumed:** statcheck recomputes a statistic from
the prose's own reported components and needs no external artifact; this binds a number to an
artifact produced by a separate measurement run. Quarto removes the number from the source; this
leaves it reviewable in the diff and checks it. No established name exists for the reverse
direction — scanning prose and demanding each number be sourced — which is why it is being built
rather than adopted.

## The design, fixed now

Every extracted number is placed in exactly one **named** category. The categories are the point:
the DO-178C answer is that the unlinked remainder gets a name and an obligation, not silence.

| category | meaning |
| --- | --- |
| `BOUND` | a `quantitative_claims.yaml` entry covers it |
| `GENERATED` | it sits inside a generated block, so it cannot drift by construction |
| `RESTATED` | it repeats a number bound in another document, and **names the claim id it copies** |
| `UNSOURCED` | declared in a baseline file, with a reason |

`DECISIONS.md` is exempt **wholesale and by principle, not convenience**: `PRODUCT.md` 5 forbids
editing it, so its numbers are historical record rather than live claims. Frozen artifacts under
`eval/results/` likewise.

The `RESTATED` category is what closes the README hole: a copy must point at what it copies, so it
cannot drift alone.

## Predictions

| # | Quantity | Prediction |
| --- | --- | --- |
| **P1** | Extractor re-finds every registered claim's value in its own document | **149 of 149.** This is also K1. |
| **P2** | `BOUND` share of extracted numbers across the live corpus | **between 5% and 20%.** Stated as a range because the denominator depends on extraction choices nobody has fixed yet, and a point prediction would be false precision. |
| **P3** | `docs/trust/*.md` files with zero `BOUND` numbers | **at least 25** of 49. |
| **P4** | `README.md` | **zero** `BOUND`, at least three `RESTATED` candidates (`0.1918`, `1.0000`, `0.4599`). |
| **P5** | Highest-`UNSOURCED` file among live docs | one of `real-error-detection-result.md`, `cell-level-detection-result.md`, `deductive-coverage-result.md`, `queue-filter-result.md` — all four carry measured precision/recall/F1 figures and zero registered claims. |
| **P6** | Extraction precision | **imperfect, and reported.** Dates, version numbers, arXiv ids, thresholds and line references will be extracted as if they were measurements. The instrument must report its own false-positive class rather than claim it has none. |

## Kill criteria, fixed now

* **K1 — instrument falsification.** If the extractor cannot locate all 149 already-registered
  claim values in the documents that register them, **report no coverage figure at all** and fix
  the extractor first. An extractor that cannot see the numbers we know about cannot be trusted
  about the ones we do not. Bound to the ledger and the documents, never to a constant in prose.
* **K2 — no fabricated denominator.** If the extracted population turns out to be dominated by
  non-measurements (dates, versions, line numbers) such that the coverage percentage is
  meaningless, publish the **counts and the confusion**, and do **not** publish a headline
  percentage. A ratio whose denominator is junk is worse than no ratio.
* **K3 — anti-Goodhart.** The ratchet must be on `UNSOURCED` **decreasing**, never on `BOUND`
  increasing. If the only way to make the gate pass is to register easy numbers, the gate is
  measuring compliance rather than coverage and must be redesigned.
* **K4 — the ratchet must fail closed on a bad merge.** The baseline carries its own total, and the
  gate refuses when the total disagrees with the sum of its parts. If that self-check cannot be
  made to work, ship the census as a **report** and not as a gate: a ratchet that silently loosens
  is worse than no ratchet, because it looks like protection.
* **K5 — no new number invented.** Every threshold in this instrument must be a count derived from
  the current state, not a target chosen because it looks good.
* **K6 — anti-motivated-stopping.** The coverage figure is published even if it is embarrassingly
  low, and especially then. A low figure is the finding.

## What is deliberately not being done

**No attempt at 100% extraction.** statcheck's ~60% ceiling in a stricter domain settles that.
Coverage is therefore reported as `BOUND / extracted`, with `extracted` stated as a lower bound on
the true population of claims and the instrument's blindness recorded as a limitation.

**No auto-registration.** The instrument will not add ledger entries. A claim needs a human to say
which artifact pointer is the right one, and a machine guess would create exactly the false
binding this whole apparatus exists to prevent.

**No conversion of hand-written prose into generated blocks.** That is the first-best fix and it is
a separate, larger piece of work with its own review burden — Quarto's own docs note inline
expressions cannot be used in YAML and should stay confined to simple values, and here every
regeneration would require re-running a measurement. Recorded as the better long-term direction,
not attempted now.

## Scope

**Does not** change `docs_truth.py`'s existing behaviour. The ledger check stays exactly as it is;
this adds the direction it structurally lacks.

**Does not** claim that a `BOUND` number is correct — only that it is bound. Whether the artifact
it points at measures what the sentence says remains a human judgement, and
`docs/trust/baseline-protocol-comparability.md` exists because that judgement has been wrong here
before.
