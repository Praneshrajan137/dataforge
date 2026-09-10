# Research brief for the automation cycle

Compiled **2026-09-10** on a machine with internet access, because **a fire has none**. This is the
only external evidence a session may cite.

## How to use this file

- **Read the parts your assignment needs, not the whole thing.** It is a reference, not a document to
  ingest wholesale. Measured performance degrades with input length even at constant task difficulty
  (Chroma, *Context Rot*, 2025).
- **Cite it or mark it unknown.** If you want to assert something about the outside world and it is
  not here, record it as an UNKNOWN in `STATE.md` for a human to research. Your training data is not
  a citation.
- **Authority is stated for every claim.** Treat "arXiv, unrefereed, self-reported" differently from
  "SIGMOD 2005" or "read from the reference implementation's source". Where two sources conflict, say
  so rather than picking one.
- **The comparability caveats are the most important content here.** Several widely quoted numbers
  are not measured under comparable protocols, and in this area the differences are large enough to
  invert rankings.

---

# Part A — The headline warning

**Cross-paper correction F1 numbers on `hospital` are not comparable.** Four things vary silently
between papers:

1. whether the corrector is handed **ground-truth error locations** (an oracle arm),
2. whether `hospital` is even the **same artifact** (row and column counts and error rates differ),
3. whether scoring is **cell-level or tuple-level**,
4. whether the paper **redefined which cells count as errors**.

Any claim of the form "F1 X on hospital, competitive with Baran's Y" is meaningful only if the arm is
named. `CLAUDE.md` already imposes that discipline internally. **The published literature does not.**

---

# Part B — The canonical protocol, read from the reference implementation

Authority: **highest**. This is `raha/dataset.py::get_data_cleaning_evaluation` in
`github.com/BigDaMa/raha` (Apache-2.0) — the code every paper claiming a Raha/Baran comparison
actually runs. Not the papers' prose.

## B1. The scoring function, and what it cannot express

```python
actual_errors = {cell: clean_value for cells where dirty != clean}   # cell-level
for cell in correction_dictionary:
    output_size += 1
    if cell in actual_errors:
        ed_tp += 1
        if correction_dictionary[cell] == actual_errors[cell]: ec_tp += 1
ec_p = ec_tp / output_size            # denominator = EVERY cell written
ec_r = ec_tp / len(actual_errors)     # denominator = ALL errors, not detected ones
```

Consequences that matter more than the formula:

- **Corrupting a clean cell is penalised only in precision, and is arithmetically indistinguishable
  from mis-fixing a real error.** A system that writes 100 cells, fixes 50 and corrupts 50 clean
  cells scores *identically* to one that writes 100 cells, fixes 50 and mis-fixes 50 real errors.
  There is no corruption counter. **Therefore RAHA F1 structurally cannot represent this project's
  safety invariant.** The per-detector unconditional-write measurement in
  `docs/trust/bypass-allowlist-evidence.md` — including how many already-correct cells a detector
  would overwrite — is strictly more informative and has no F1 equivalent.
- **Detection recall caps correction recall.** Baran states it: *"the error detection recall is the
  upper bound of the error correction recall."*
- **Abstention is free in precision and invisible otherwise.** Declining to write never hurts
  precision, and there is no protocol slot for "refused, and was right to refuse."
- `sampled_rows_dictionary` allows evaluation restricted to sampled rows. **A sampled `tax` number is
  not comparable to a full-corpus one.**

## B2. Baran's headline numbers are measured with perfect error detection handed in

Mahdavi & Abedjan, *Baran*, PVLDB 13(11):1948-1961, 2020, section 6.2, verbatim: *"All the error
correction systems in this section take as the input the same correct and complete set of data
errors."* Confirmed in code: `correction.py` does
`data.detected_cells = dict(data.get_actual_errors_dictionary())`.

This is an **oracle arm** in exactly the sense this repository uses the term. It is a ceiling, not a
user-reachable configuration. **This is the most commonly mis-cited fact in the area** — downstream
papers quote Baran's 0.87/0.91 alongside their own end-to-end numbers.

## B3. Twenty tuples of ground truth enter the scored output

`correction.py::label_with_ground_truth` reads `d.clean_dataframe` for a sampled tuple, and the
labelled true values then enter the correction dictionary and are scored as correct outputs.
`LABELING_BUDGET = 20`. The paper is explicit that 20 tuples are labelled, so this is not
misconduct — but **the number is not achievable with zero ground truth**, and the size of that
contribution is unreported.

## B4. Normalisation erases a class of errors before scoring

`Dataset.value_normalizer` applies `html.unescape`, collapses `[\t\n ]+`, and strips — to **both**
frames at read. Pure whitespace and HTML-entity differences therefore never appear in `actual_errors`
and cannot be scored. **Directly relevant to `rayyan`:** some format-canonicalisation work is
invisible to this metric in *both* directions — it can neither earn recall nor cost precision.

Two further code-level hazards:

- `get_dataframes_difference` on a shape mismatch writes to `stderr` and **does not raise**, then
  produces garbage. A mis-shaped frame yields a plausible-looking F1.
- The **write path normalises, the scoring path does not.** An unnormalised proposal can be scored
  wrong while the written cell is right.

## B5. Published numbers are means of ten stochastic runs

Baran section 6.1: *"For each metric, we report the mean of 10 independent runs."* Tuple sampling
uses `numpy.random.choice` over argmax ties. **A single-run number is not comparable to a published
mean**, and the variance is unreported.

## B6. The shipped code no longer matches the published paper

`BigDaMa/raha` master carries a merged patch *"Fix correction selection to use highest confidence
instead of last prediction"* (PR 26, approx. 2024), and master has a live typo
(`return d.corrected_cell`) in `Correction.run`. **Reproducing "Baran" today does not reproduce
Baran-2020.** Any re-measurement must pin a commit and say which.

---

# Part C — Reported correction F1 on `hospital`, arms made explicit

| System | P / R / F1 | Arm | Source |
| --- | --- | --- | --- |
| Baran | 0.88 / 0.86 / **0.87** | **oracle detection**, 20 GT tuples | Baran PVLDB'20 T3 |
| Baran + transfer | 0.94 / 0.88 / **0.91** | oracle detection + 300k Wikipedia revisions | Baran T3 |
| HoloClean | 1.00 / 0.71 / **0.83** | oracle detection + supplied DCs/MDs | Baran T3 (re-run) |
| **Raha + Baran, end to end** | 0.89 / 0.52 / **0.66** | mined detection, 2x20 GT tuples | Baran T7 |
| Raha + Baran, integrated | 0.95 / 0.52 / **0.67** | mined detection, 1x20 GT tuples | Baran T7 |
| Raha + perfect correction | 0.98 / 0.58 / **0.73** | **ceiling given mined detection** | Baran T7 |
| Raha + HoloClean | 0.19 / 0.41 / **0.26** | mined detection | Baran T7 |
| Raha+Baran, BClean's re-run | 0.971 / 0.585 / **0.730** | self-configured labels | BClean T4 — **different `hospital`** |
| BClean, best variant | 1.000 / 0.960 / **0.980** | 12 regexes + expert constraints | BClean T4 — **different `hospital`** |
| PClean | 1.000 / 0.927 / **0.962** | expert-authored PPL program | BClean T4 — **different `hospital`** |
| Garf | 1.000 / 0.556 / **0.715** | self-supervised | BClean T4 — **different `hospital`** |
| Garf, own paper | 0.99 / 0.69 / **0.81** | self-supervised | Garf PVLDB'22 T3 — **tuple-level, 100K rows** |
| Raha+Baran, Cocoon's re-run | 0.91 / 0.60 / **0.72** | GT for 20 cells | Cocoon T1 — **rescored** |
| Cocoon (LLM) | 0.87 / 0.93 / **0.90** | Claude 3.5, human step replaced by GT | Cocoon T1 — **rescored** |
| Cocoon, error set redefined | 0.99 / 0.99 / **0.99** | + column-type and DMV counted as errors | Cocoon T3 — **not comparable to anything** |
| CleanAgent (LLM) | 0.00 / 0.00 / **0.00** | — | Cocoon T1 |
| RetClean (LLM) | 0.00 / 0.00 / **0.00** | no external clean tables supplied | Cocoon T1 |

## C1. `hospital` is not one dataset

- **Raha/Baran:** 1000 x 20, **3%** errors, typos plus violated attribute dependencies, *randomly
  imposed*. Constraints: `city->zip, city->county, zip->city, zip->state, zip->county, county->state`
  plus column patterns.
- **BClean:** 1000 x **15**, **5%**, errors **re-injected by the authors**, sourced from HoloClean.
  Different shape, therefore definitively a different artifact.
- **Garf:** **100K x 10**, errors injected at **10%**.
- **Cocoon:** cites `hospital` to HoloClean with error-type counts that do not match Baran's ~600.

**No cross-paper `hospital` comparison above is valid except within a single row-source.**

## C2. Garf scores tuples, not cells

Garf, PVLDB 16(3):433, section 5.1, verbatim: *"Precision (P): The number of correctly repaired
**tuples** over the total number of repaired **tuples**."* Tuple-level scoring on a 100K-row
synthetically corrupted table is a different quantity from cell-level F1 on 1000 rows. **Garf's 0.81
and Baran's 0.87 are not the same units.**

## C3. Garf has been independently reproduced twice, far below its own claims

- **BClean** (T4): Garf F1 **0.715** hospital, **0.024** flights, **0.021** beers, **0.166**
  inpatient; recall collapses to 0.011-0.09 on three of six datasets.
- **Conformal Data Cleaning** (AISTATS 2024): *"Garf is in all cases worse than CDC and ML"* on TPR;
  and on **5 of 16 datasets Garf failed to produce a valid cleaned dataset at all.*

Two independent groups, different protocols, same direction. **Treat Garf's self-reported numbers as
unreproduced.**

## C4. Documented reproduction failures, and unreleased configurations

- **Cocoon** could not reproduce HoloClean: *"Despite experimenting with various threshold values, we
  were unable to replicate their results."*
- **BClean:** *"Because DCs and labels used in HoloClean and Raha+Baran papers have not been
  released, we configure them by ourselves."*

**So the baseline numbers in the two strongest recent comparison papers are re-implementations under
self-chosen supervision. There is no protocol-stable published baseline to beat.**

## C5. Cocoon changes the scoring rules mid-paper, and says so

Cocoon (arXiv:2410.15547, Columbia, **arXiv-only, no venue**) grants baselines case-insensitivity,
then in an appendix **adds column-type and disguised-missing-value errors to the error set** and
re-reports itself at 0.99. Also: *"we skip these and use the LLM provided ground truth."* Authority:
**low to moderate** — honest about its changes, but self-serving. The 0.99 is a different benchmark,
not a SOTA claim on the canonical one.

---

# Part D — Conformal / statistically guaranteed cleaning

## D1. What the guarantee actually is, and is not

Jäger & Bießmann, AISTATS 2024, PMLR v238 (*"Conformal Data Cleaning: Statistical Guarantees for Data
Quality"*). Code at `github.com/se-jaeger/conformal-data-cleaning`. Authority: **high**, refereed.

Mechanism: one per-column model predicting column *c* from the others, conformalised on 1000 held-out
points; a cell is flagged erroneous iff its value falls outside the conformal prediction set; then
overwritten with the point prediction.

The guarantee is **marginal coverage**, which in cleaning terms means: **for a cell that is actually
correct, the probability of wrongly flagging and overwriting it is at most alpha.** That is a bound on
the **false-positive rate — a bound on corrupting clean cells.** It is **not** a bound on whether the
replacement value is right.

**This is the closest thing in the literature to a formal version of this project's safety invariant,
and worth reading closely for that reason.** It guarantees only *not touching* clean cells, never
*repairing correctly*.

## D2. The precondition is violated by the task it is applied to

Coverage requires exchangeability between calibration and test data, but the whole premise is that
test data is **corrupted**, i.e. distribution-shifted. The authors are candid: *"In such a scenario,
the conformal framework is no longer valid and loses its guarantees"* — and patch it with a
**heuristic** (apply the rule only when the prediction set is non-empty). Empirically: at confidence
0.999 it improves downstream performance in ~71% of experiments; at 0.8, **~18%**; at 0.5, **~15%**;
and the 20% of experiments with the largest confidence sets *"mostly degrade the downstream
performance, often by several tens of percent."*

**So "statistically guaranteed data cleaning" is rigorous but conditional, one-sided, and
demonstrably loses its guarantee under the shift it exists for.** Do not cite it as solved.

## D3. The cost, and the total absence of comparability

Requires a **clean training corpus** (an 80% clean split, which the RAHA setting does not give), 1000
held-out calibration rows, and one AutoGluon model **per column** with hyperparameter search. It is
**not evaluated on RAHA datasets at all** — 16 OpenML tables, synthetic corruptions, scored by
TPR/FPR and downstream utility, never cell-level correction F1. **Zero comparability with Part C.**

## D4. Nearest successor

Bashari, Sesia, Romano, *Robust Conformal Outlier Detection under Contaminated Reference Data*
(arXiv:2502.04807, 2025): calibrating on a **contaminated** reference set yields **conservative**
type-I error control — the guarantee survives, power is lost — recovered via active labelling.
Relevant if calibration data cannot be assumed clean. Authority: moderate to high.

---

# Part E — LLM-based cleaning: established versus hyped

## E1. Most published LLM cleaners score approximately zero on the canonical benchmarks

Cocoon's own measurements: **CleanAgent 0.00 F1 on all five benchmarks; RetClean 0.00 on four of
five**. Cocoon's framing: *"existing data cleaning tools utilizing LLMs achieve close to zero accuracy
and recall for the majority of standard data cleaning benchmarks."* A **pro-LLM paper reporting it**,
which raises its credibility. Caveat: RetClean needs external clean reference tables that were not
supplied.

## E2. The most rigorous LLM-adjacent result is negative, and it endorses abstention

Liu, He, Dong, Xing, Han, Zhang, Chaudhuri, *Auto-Fill*, VLDB 2026 (arXiv:2607.19847), Microsoft
Research. Authority: **high**.

Frontier reasoning models are *"costly to deploy at scale and tend to be **overconfident, often
generating hallucinated or false-positive predictions**."* Their answer: three post-trained specialist
small models plus *"a **calibrated ensemble mechanism that either dynamically selects the most
confident specialist or abstains**."* Eleven benchmarks, 2200 real tables, beating o3-pro and Gemini 3
Pro at **under 1% of frontier cost**. Scope caveat: **missing-value imputation only**, not general
repair, and not RAHA cell-level F1.

## E3. Weaker authority, still relevant

- **LasRepair** (arXiv:2606.17582, 2026): LLM-as-instructor plus small-model corrector, with
  **column-calibrated confidence to down-weight unreliable repairs**. Claims *"average F1-score
  improvement of 18.1% over the strongest baseline"* — relative, baseline unstated, **unverified**.
  Motivated by the same two failure modes this project cares about: repairing *inside* a dirty
  context, and using uncertain outputs directly as repairs.
- **LLMClean** (arXiv:2404.18681, 2024): LLM-generated ontology functional dependencies, claiming
  parity with expert-crafted context models on three datasets. Authority low to moderate. Interesting
  as an alternative to the declared-premise path: an LLM authors the premise, ground truth grades it.
- **Survey:** *A Survey of LLM x DATA* (arXiv:2505.18458). Orientation only, not for numbers.

**Net: one genuinely rigorous entrant whose finding is that LLMs are overconfident and abstention is
necessary; one honest but unrefereed system; a cluster of unreproduced arXiv claims. Nothing here
displaces Baran as the reference point on RAHA.**

---

# Part F — Abstention and selective prediction for repair

## F1. There is no formal treatment of abstention for data repair specifically

The pieces exist, unassembled: Auto-Fill has calibrated abstention but only for imputation; conformal
cleaning is a *de facto* abstention rule with an alpha-level guarantee on clean cells but never frames
it that way and offers no guarantee on the repair; LasRepair down-weights rather than abstains.

**Not found:** any paper that defines a risk-coverage curve for cell-level repair, proves a bound on
corruption rate under an abstention policy for FD repair, or reports "cells declined" as a
first-class metric alongside P/R/F1.

**The RAHA protocol actively obscures this** (see B1): abstention is invisible except as lost recall.
**If principled refusal is this project's differentiator, that is a genuine white space — and the
corollary is that it cannot be demonstrated on the standard metric and needs its own instrument.**
That is a defensible position, not a gap to paper over.

---

# Part G — FD repair theory: minimality, hardness, order dependence

## G1. The cost model and the original hardness result

Bohannon, Flaster, Fan, Rastogi, *A Cost-Based Model and Effective Heuristic for Repairing Constraints
by Value Modification*, **SIGMOD 2005**, pp. 143-154. Introduces the weighted value-modification cost
framework and proves *"finding minimal-cost repairs in this model is **NP-complete in the size of the
database**."* Authority: **highest**. This is the correct citation for "minimal-cost FD repair is
NP-complete."

## G2. The modern complexity landscape is a set of sharp dichotomies

- Livshits & Kimelfeld (arXiv:1708.09140): cardinality repair — PTIME for certain fixed schemas,
  **NP-hard for every schema not covered**, with an efficient test for which side a schema falls on.
- Livshits, Kimelfeld, Roy (arXiv:1712.07705, ICDT/TODS): optimal subset-repair is **APX-complete**
  outside the tractable class, so no better-than-constant approximation; extended to cell-update
  repairs.
- Miao, Cai, Li et al. (arXiv:2001.00315): NP-hard to approximate better than **17/16** in most
  cases; gives a `(2 - 0.5^(sigma-1))`-approximation for sigma FDs.
- **Kimelfeld & Livshits (arXiv:2608.15328, August 2026)** — *newest result in this thread*:
  completely resolves **unary** FDs for update repairs; every unary FD set is either in a known
  tractable class or **NP-hard**. **Cite this as the state of the art on update-repair hardness.**

## G3. Order-dependence of FD repair is a named, published phenomenon with a named remedy

Boeckling & Bronselaer, *Cleaning data with Swipe* (arXiv:2403.19378, 2024): *"A well-known approach
builds a **Chase tree** in which each internal node resolves violations of one functional dependency
and leaf nodes represent repairs"* — different orders of resolving FDs yield different repairs, and
the branching factor trades quality against cost. Swipe collapses this to a single path via attribute
partitioning and a fixed FD ordering ("priority repairing"), reporting **one to three orders of
magnitude** speedup at comparable or better quality.

**This is the citation to use for "FD repair is order-dependent."** It is not folklore; it is the
explicit structure of the standard algorithm. **Corollary: any FD repair engine that does not fix an
order is non-deterministic across runs, and any F1 measured from it inherits that variance.** This
repository fixed an order-dependence defect in `dataforge/repairers/fd_violation.py` on 2026-08-29;
that fix has a literature home.

Supporting:

- Beskales, Ilyas, Golab, *Sampling the Repairs of Functional Dependency Violations under Hard
  Constraints*, PVLDB 3(1):197-207, 2010 — treats the repair *space* as something to sample from
  rather than a single point to pick. The right formalisation of "there is no single answer."
- Zheng et al. (arXiv:2105.08105) on ontology FDs: *"FDs define attribute relationships based on
  **syntactic equality**, and, when used in data cleaning, they **erroneously label syntactically
  different but semantically equivalent values as errors**."* **Directly relevant: a large fraction of
  an FD detector's false positives on `rayyan`-style data are this, not a bug.**

---

# Part H — Reversibility and lineage of repairs

## H1. Snapshot reversibility is a commodity; per-cell reasoned provenance is not

**Commodity, verified against Apache Iceberg 1.10.1 docs:** `TIMESTAMP AS OF`, `VERSION AS OF`,
branch and tag refs, schema-aware time travel. Delta Lake ships the equivalent. So "you can undo a
cleaning run" is **table-format table stakes and must not be marketed as a differentiator.**

**Not commodity, and this is the real gap:** Iceberg's incremental read is explicitly limited —
*"Currently gets only the data from **append** operation. **Cannot support `replace`, `overwrite`,
`delete` operations.**"* A repair run is precisely an overwrite. So the table format gives you
whole-table rollback and gives you **nothing** for: which cells changed, what the prior value was,
**which rule or detector authorised each write**, what the verifier verdict was, and why a candidate
was refused.

**Recommended framing: drop "reversible cleaning" as a claim; keep "per-cell repair provenance with a
recorded authorising premise, verifier verdict, and refusal reason."** Pointed internal precedent: the
2026-09-08 lesson was that five instruments reported a bare zero and none reported why. That is
exactly the capability no table format supplies.

---

# Part I — On running a pipeline of short unattended sessions

Relevant to E5 and to Day 4, because it is about whether verification can fail.

- **METR** (arXiv:2503.14499): agent success is predicted by task **length** more than difficulty —
  near-100% under 4 human-minutes, under 10% beyond ~4 human-hours. Authority: high. **Implication:
  size an assignment to about fifteen minutes of human work.**
- **tau-bench** (arXiv:2406.12045): `pass^8 < 25%` where single-pass is under 50%, and it grades by
  comparing **end state** to a goal state, not by reading the transcript. **Implication: a prior
  session's claim is one sample from a poor distribution. Grade artifacts.**
- **SWE-bench+** (arXiv:2410.06992): manual audit of one agent's passing patches found **32.67%**
  involved solution leakage and **31.08%** passed only because tests were too weak; filtering both
  dropped resolution from **12.47% to 3.97%**. This is about **benchmark validity, not agents
  lying** — be precise, it is routinely miscited. **Implication: a passing check is evidence only if
  it could have failed.**
- **Lost in the Middle** (TACL 2023, arXiv:2307.03172): accuracy highest at the beginning and end of
  an input, degraded in the middle. Peer-reviewed, heavily replicated. **Implication: `STATE.md`
  layout is not cosmetic.**
- **Chroma, Context Rot** (2025): 18 models degrade with input length at constant task difficulty,
  including on a task that only asks for a word list to be repeated. Vendor technical report, strong
  methodology, not peer-reviewed. **Implication: prefer a small structured artifact to a large
  faithful one.**
- **Anthropic multi-agent system** (2025): vague subtask briefs measurably caused duplication and
  gaps; the fix was an objective, an output format and **explicit boundaries**. Vendor blog, no
  released data.
- **Cognition, "Don't Build Multi-Agents"** (2025): *"actions carry implicit decisions, and
  conflicting decisions carry bad results."* Reasoned argument, **zero quantitative evidence**.
  **Implication: record decisions and rejected alternatives, not only findings.**

---

# Part J — What could NOT be established

Do not treat any of these as verified. Each is a candidate UNKNOWN for `STATE.md`.

1. **`movies` appears not to be a RAHA dataset.** Baran's Table 2 lists Hospital, Flights, Address,
   Beers, Rayyan, IT, Tax — no `movies`. `movies` appears in **Cocoon**, cited to the Magellan
   repository. The Raha SIGMOD 2019 paper could not be read directly (ACM blocked), so this cannot be
   fully excluded there.
2. **Raha's own published detection F1 on `hospital`.** P 0.98 / R 0.58 / F1 0.73 was **derived** from
   Baran Table 7's perfect-correction row, not quoted. Label it as a derivation.
3. **HoloClean's primary numbers.** Only available as re-run by others. Corroborated from two
   secondary sources, **not primary-verified**.
4. **Fan et al., "certain fixes" with editing rules and master data** — repairs that are *provably*
   correct given master data, i.e. the likely theoretical ancestor of a verified-repair posture. **Not
   on arXiv; could not be retrieved.** This is the single highest-value unresolved lookup for this
   project.
5. **Whether Garf actually benchmarks against Baran.** Listed as a baseline in its section 5.1 but not
   found in the experiment tables read.
6. **BClean's venue.** arXiv:2311.06517, widely treated as VLDB-track; **not confirmed.** Cite as
   arXiv.
7. **Any competitor number for `tax` or `rayyan` end to end.** Baran gives oracle-arm `tax` 0.81/0.83
   and `rayyan` 0.52/0.57, and end-to-end `tax` 0.74-0.80, `rayyan` 0.28-0.35. **No other paper here
   measures `rayyan` or `tax` at all.** So Baran's own table is the only comparison point in
   existence, and end-to-end `rayyan` at 0.28-0.35 is far weaker than commonly assumed.
8. **PClean** not primary-verified; its 0.962 is BClean's re-run with expert-authored probabilistic
   programs, an unquantified advantage.

---

# Part K — Three consequences worth carrying into every session

1. **The RAHA F1 metric structurally cannot represent this project's central safety claim** (B1).
   Corruption of clean cells folds indistinguishably into precision; abstention earns nothing. The
   per-detector unconditional-write measurement already in `docs/trust/` is the stronger instrument.
2. **The right comparison target for an end-to-end `hospital` number is 0.66-0.67** (Raha+Baran end to
   end), **not 0.87/0.91** (Baran oracle-fed), with 0.73 the ceiling imposed by mined detection. The
   0.4599 figure in `docs/trust/fd-repair-yield-mechanism.md` sits *below* end-to-end Raha+Baran on
   F1 but at materially higher precision with zero corruptions — **which is the trade the standard
   metric cannot show.**
3. **Retire "reversible cleaning" as a differentiator; keep per-cell authorising premise, verifier
   verdict, and refusal reason** (H1).
