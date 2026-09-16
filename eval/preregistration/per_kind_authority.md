# Pre-registration: what is one declaration worth?

Written 2026-09-16, **before** adding any premise arm and before running the harness. Nothing below
is edited afterwards; results, deviations and refutations are appended as amendments at the bottom.

## The finding this responds to

`docs/trust/authority-enforcement-correspondence.md` closed a correspondence defect on 2026-09-14:
`authoritative_columns` conferred write authority for ten `Schema` constraint kinds while the two
verifiers enforced six. The fix partitioned the kinds into `ENFORCEABLE_CONSTRAINT_KINDS` and
`UNENFORCEABLE_CONSTRAINT_KINDS` and asserted the partition total against `Schema`'s own fields.

That closed the question *"can any verifier look at this kind?"* It left a different question
entirely untouched, and this document is about the second one:

> **How much can each kind actually reject?**

Eight kinds now confer write authority, and they confer **identical** authority.
`strength_for_fix` (`dataforge/engine/repair.py`:1472-1477) keys on nothing but column-name
membership:

```python
def strength_for_fix(fix: ProposedFix, covered_columns: frozenset[str]) -> VerificationStrength:
    """Column-scoped strength: authority only extends to columns the schema constrains."""
    return verification_strength_for(
        fix.provenance,
        authoritative_schema_present=fix.fix.column in covered_columns,
    )
```

So a column named by `not_null_columns` and a column named by `accepted_values` are equally
authoritative, and a fix on either is equally eligible to be labelled `proven` — including a fix
whose provenance is an LLM. But the two declarations are not remotely equally strong. For a string
column, `not_null` is checked as one comparison (`dataforge/verifier/direct.py`:160-162):

```python
        if (column in schema.not_null_columns or column in schema.primary_key_columns) and (
            ctype in _STR_TYPES and new_value == ""
        ):
```

It can reject the empty string. That is the whole of its power. An `accepted_values` enumeration, by
contrast, rejects everything outside a named set.

**The existing bar for conferring authority is "can this reject a value at all?"** That is the bar
`type_discriminates` applies, and it is why `str` was demoted on 2026-08-25 after the permissive
premise was measured admitting 10 of 14 attacks. `not_null` clears that bar — it rejects `""` — so it
confers. The question this document asks is whether clearing that bar is *sufficient*, and it is
answerable with an instrument that already exists.

## Why this is urgent rather than academic

The only path to write authority in this repository today is a **hand-authored YAML file**. Every
other premise source either confers nothing by construction (`schema init`, mined constraints
without `--trust-mined-constraints`) or is unreachable (`dataforge/integrations/dbt.py` is on the
public API, is tested, and no CLI flag accepts a manifest).

The two external sources worth wiring up — a dbt manifest and a database's DDL — supply a
characteristic *subset* of the eight authority-conferring kinds:

| Kind | dbt generic tests | Database DDL | In `TIGHT_SCHEMA`? |
| --- | --- | --- | --- |
| `not_null_columns` | **yes** (`not_null`) | **yes** (~56% of columns, SchemaPile SIGMOD 2024) | no |
| `primary_key_columns` | no | **yes** | no |
| `unique_columns` | **yes** (`unique`) | **yes** | no |
| `accepted_values` | **yes** (`accepted_values`) | only via `CHECK ... IN` (~0.2-1% of columns) | **yes** |
| `regex_constraints` | no | rare | **yes** |
| `domain_bounds` | no | only via `CHECK` range | **yes** |
| `columns` (types) | only when `data_type` present | yes, but 48.8% of real values are Text (DBTest'18) | **yes** |
| `functional_dependencies` | no | no | no |

The three kinds an external source reliably supplies are exactly the three **absent from
`TIGHT_SCHEMA`**. And `TIGHT_SCHEMA`'s celebrated 0-of-14 result is a **bundle** measurement — types,
`accepted_values`, `regex_constraints` and `domain_bounds` together — so it attributes strength to
none of its members. A realistic externally-derived premise is *`TIGHT` minus everything that might
be doing the work*, and its behaviour has never been measured.

If the weak kinds confer real proof, wiring up dbt and DDL is a large capability unlock. If they do
not, wiring them up as authority sources would mass-produce the exact defect that was removed on
2026-08-25. That is a decision worth an experiment rather than an argument.

## Method

The instrument exists and is the one that produced the published 10-of-14 figure:
`scripts/measure_trust_ledger.py` over `tests/adversarial/corpus.py`. Each new arm is
**`PERMISSIVE_SCHEMA` plus exactly one added field**, following the discipline the file already
states, so any difference in outcome is attributable to that field and to nothing else. The 14
discriminable attacks and the ground-truth table are untouched: `build_corpus()` is not extended,
because its 14 attacks are the denominator of a published number and moving a denominator to
accommodate a new finding would restate history rather than add to it.

One arm breaks the one-field rule deliberately and is labelled as doing so: `ddl_typical` models
what a real DDL importer would emit (`not_null` + `primary_key` + all-string types), and exists to
answer a product question rather than to attribute a delta.

Reported per arm, for the `discriminable` subset (n=14): `cells_applied`, `corruptions`, and
`wrongly_blocked`. The third is not optional. Zero writes is not a safety result — `permissive`,
`unenforceable_relationship` and `unenforceable_aggregate` all write zero today and are inert rather
than safe — and the corpus's single legitimate proposal (`correct-score-repair`) is what separates
the two. An arm that writes nothing *and* blocks the legitimate repair has bought safety by
refusing to work.

## Pre-committed hypothesis and predictions

**H1.** The eight authority-conferring kinds are not equally discriminating, and the kinds an
external premise source reliably supplies are the weak ones. Specifically: at least one
authority-conferring kind, declared alone, admits materially more of the 14 discriminable attacks
than `TIGHT_SCHEMA`'s zero.

Predictions are traced through `direct.py` and `smt.py` by hand before running anything, so a wrong
one is informative about my model of the code rather than merely unlucky.

| # | Prediction |
| --- | --- |
| **P1** | `not_null_only` corrupts **at least 7** of 14. Its only rejection is `new_value == ""`, so of the thirteen attacks that should be blocked it can catch exactly one — `empty-string-into-score`. |
| **P2** | `primary_key_only` is **identical to `not_null_only`** on every reported field, because `direct.py`:160 tests membership of either set with the same predicate. |
| **P3** | `unique_only` corrupts **at least as many as `not_null_only`**, and misses `empty-string-into-score`, because `""` is distinct from every existing score and therefore satisfies a uniqueness check. |
| **P4** | `accepted_values_only` corrupts **0** of 14 and keeps the 1 legitimate repair — i.e. it alone reproduces the entire `TIGHT` bundle's result. |
| **P5** | `ddl_typical` is **indistinguishable from `not_null_only`**, because a DDL importer that maps unconstrained `VARCHAR`/`TEXT` to a non-discriminating type contributes no authority beyond the two key kinds. |
| **P6** | At least one arm reproduces the retired `str` premise's **10 of 14** exactly, which would make this the third independent route to the same number after `str` types and unenforceable kinds. |
| **P7** | `not_null_only` applies the `newline-injection-into-city` attack, taking the committed table from **6 rows to 7** — the structural damage `authority-enforcement-correspondence.md` recorded for the unenforceable premise. |
| **P8** | No arm's addition moves `tight` or `permissive` on any field. This is K1 below, stated as a prediction so that a violation is scored rather than explained. |

## Pre-committed kill criteria

- **K1 — instrument falsification, and it outranks every finding.** `_PRE_EXISTING_ARMS` is
  `("tight", "permissive")` and the harness already binds them to `eval/results/trust_ledger_adversarial.json`
  field-for-field. If extending the harness moves either arm, **the harness is what changed**, no new
  number may be reported, and the discrepancy is investigated before anything else. A missing
  artifact is not a pass.
- **K2 — the denominator is frozen.** `build_corpus()` is not extended. Vectors and attacks may not
  be added, removed, reworded or reordered. The 14 discriminable attacks are a published
  denominator.
- **K3 — no arm may be tuned to a result.** Each arm is `PERMISSIVE_SCHEMA` plus one field, chosen
  before running, named after the kind it isolates. An arm may not be adjusted after seeing its
  number. `ddl_typical` is the single declared exception to the one-field rule and its composition is
  fixed here: `not_null_columns` and `primary_key_columns` over every column, types all `str`.
- **K4 — zero writes is not a safety result.** Every arm reports `wrongly_blocked`. An arm with 0
  corruptions is scored as **inert** rather than safe if it also blocks `correct-score-repair`, and
  the write-up must say which.
- **K5 — anti-motivated-stopping, in the direction that costs me work.** If P1 and P4 both hold, the
  consequence is that dbt and DDL importers **must not confer authority from the weak kinds**, which
  makes the dependent work smaller and less impressive than planned. That result gets published and
  acted on. If instead the weak kinds turn out to be adequate, that gets published too, and it is the
  better outcome for the product.
- **K6 — the fix must not be a corrected literal.** Any change to which kinds confer authority is
  made as a derived population with a totality assertion, in the shape `PRODUCT.md` section 1.3
  prescribes — enumerate the artifact, name the remainder, refuse on the unnameable — not by editing
  a set in place.

## What this does not claim

- **Not that the corpus generalises.** Five rows, five columns, one hand-built table with committed
  ground truth. It measures whether a *class* of declaration can reject a *class* of attack. It says
  nothing about yield on a real corpus, which is a separate measurement on `hospital` and is not
  attempted here.
- **Not that `accepted_values` is safe.** If P4 holds it shows that kind rejects these 14 attacks. It
  does not show it rejects a value that satisfies the enumeration and is nonetheless false — the
  corpus marks three such attacks `discriminable=False` precisely because no verifier can reject them,
  and `PRODUCT.md` section 1.2 already concedes the limit.
- **Not a claim about detection.** Every arm here concerns *write authority*. A weak declaration may
  be perfectly good for finding candidates and for gating them; the question is only whether it
  should license a write.
- **Not that DDL constraints are a bad premise source.** If the weak kinds fail, the conclusion is
  that they must not confer authority — not that they are worthless. A constraint that drives
  detection and verification while conferring no right to write is exactly what C4 already does for
  mined constraints, and it is a shipped, coherent position rather than a fallback.
- **Nothing about in-table premise inference.** `docs/trust/premise-acquisition-result.md` stands
  unchanged and untouched. This is about premises a human already authored elsewhere.

## Expected outcome, stated in advance

I expect **H1 confirmed** and **P1-P5, P7, P8 to hold**. I am least confident about two.

**P3** requires that a uniqueness check passes a value distinct from all others even when the
declaration is *false* of the existing data — `unique` on `city` is false, since `chicago` appears
twice. If the verifier evaluates the declaration against the current table before using it, an arm
declaring a false uniqueness constraint could reject everything and look deceptively strong. Either
outcome is interesting; I do not know which the code does.

**P6** is the one I would most like to be wrong about, because a third independent route to 10 of 14
would suggest the number is a property of the corpus rather than of the premises — in which case the
figure is less informative than three sessions have treated it as, and that would be worth knowing.

---

## Amendment 1 — results, two refutations, and a correction to a published claim, 2026-09-16

Appended, not edited. `build_corpus()` was not touched; the 14 discriminable attacks and the
ground-truth table are as committed. Raw artifact:
`eval/results/trust_ledger_adversarial.json`.

### Result, `discriminable` subset (n=14)

| arm | corrupted | corrected | held | verdict |
| --- | --- | --- | --- | --- |
| `tight` (bundle of 4 kinds) | 0 | 1 | 13 | strong |
| `permissive` (all `str`) | 0 | 0 | 14 | **inert** — blocks the legitimate repair |
| `unenforceable_relationship` | 0 | 0 | 14 | **inert** |
| `unenforceable_aggregate` | 0 | 0 | 14 | **inert** |
| **`not_null_only`** | **9** | 1 | 4 | **dangerous** |
| **`primary_key_only`** | **0** | 0 | 14 | **inert**, and not for the reason predicted |
| **`unique_only`** | **10** | 1 | 3 | **dangerous — the worst arm measured** |
| **`accepted_values_only`** | **0** | 1 | 13 | **strong — matches the whole bundle alone** |
| **`ddl_typical`** | **9** | 1 | 4 | **dangerous** |

**H1 is confirmed decisively.** The eight authority-conferring kinds are not equally discriminating:
declared alone, one admits 0 of 14 and another admits 10 of 14, and the gate is identical in every
run. `accepted_values` alone reproduces the entire `TIGHT` bundle's result — 0 corruptions with the
legitimate repair intact — while `unique` alone reproduces the retired `str` premise's **10 of 14**
exactly. The existing bar for conferring authority, *"can this reject a value at all?"*, is therefore
satisfied by declarations whose measured discriminating power differs by a factor of ten.

**The product consequence is direct.** `ddl_typical` — what a DDL importer would emit for a typical
production table — corrupts **9 of 14**. `not_null` is the most abundant real-world constraint
(~56% of columns, SchemaPile SIGMOD 2024) and `unique` is among the four dbt generic tests. So an
importer that treated these as authority sources would mass-produce the defect removed on 2026-08-25.
**K5 fires: the dependent work is smaller than planned, and this is the reason.**

### Scorecard

| # | Verdict | Evidence |
| --- | --- | --- |
| **H1** | **CONFIRMED** | 0 to 10 of 14 across single kinds |
| **P1** | **CONFIRMED, mechanism exact** | `not_null_only` corrupts 9 (≥7 predicted) and its 4 held are precisely `empty-string-into-score` plus the three it cannot reach structurally |
| **P2** | **REFUTED** | `primary_key_only` corrupts 0, not 9 — see below |
| **P3** | **CONFIRMED, mechanism exact** | `unique_only` corrupts 10 ≥ 9, and `empty-string-into-score` is in its corrupting list: `""` is distinct from every existing score, so uniqueness passes it |
| **P4** | **CONFIRMED exactly** | 0 corrupted, 1 corrected |
| **P5** | **CONFIRMED exactly** | `ddl_typical` identical to `not_null_only` on all three fields |
| **P6** | **CONFIRMED** | `unique_only` = 10 of 14, a third independent route to that number |
| **P7** | **REFUTED in substance** | see below — and it produced the most valuable finding here |
| **P8** | **CONFIRMED** | no `INSTRUMENT FALSIFIED`; `tight` and `permissive` reproduce the committed artifact field-for-field, so K1 holds |

Seven confirmed, two refuted. Both refutations were worth more than the confirmations.

### P2 refuted: the safety constitution, not the premise

`primary_key_only` confers authority on all five columns — verified directly,
`authoritative_columns(PRIMARY_KEY_ONLY_SCHEMA)` returns every column, identical to
`not_null_only`. So the zero is not an authority difference. Probing one fix at a time showed
`verifier='not_run'` with `safety='allow'` and an empty review queue on **every** case, including a
fix on `id` that both other arms applied: the proposal never reached the verifier at all.

The cause is `dataforge/safety/constitution.py`'s `_primary_key_edit`, which refuses any fix editing
a declared primary-key column. Declaring a primary key over every column therefore makes every write
target off-limits. That is a real and good safety property, it is *stronger* than anything either
verifier does, and I did not know it existed — I predicted from `direct.py`:160, which tests
`not_null_columns` and `primary_key_columns` with one predicate, and reasoned no further.

It is also the clearest illustration of **K4** in the run. `primary_key_only` scores 0 corruptions
and is **inert, not safe**: it blocks the legitimate repair too, because `score` is a declared key in
that arm. Without `wrongly_blocked` it would have been indistinguishable from `accepted_values_only`
on the headline number, and the two are opposites.

### P7 refuted, and a published claim corrected

P7 predicted `not_null_only` would apply `newline-injection-into-city` and take the table from 6 rows
to 7. It **does** apply it, so the value corruption is real and is counted among the nine. The
structural half is false, and checking it rather than reporting it is what mattered.

Measured directly with a CSV reader, the file after the write is:

```
1,"springfield\n9,x,y,z,0",il,62701,10.0
```

Valid CSV. **Parsed rows 6 before and 6 after, five fields in every row.** Only the *physical line*
count rises, because a quoted field may legally contain a newline. `test_the_table_shape_is_never_changed`
was counting `splitlines()`, so it reported a shape change where the shape was intact — a false alarm
on valid output, which is exactly the kind of assertion that hides a real one.

**Consequence for an existing published claim.** `docs/trust/authority-enforcement-correspondence.md`
and the generated `correspondence` string in `scripts/measure_trust_ledger.py` both state that *"one
applied injection took the table from 6 rows to 7"*. That sentence reports a physical-line count from
this same assertion and does **not** establish that a row was created. It is corrected at both sites.

What I cannot settle: whether the original measurement was ever a structural corruption. Reproducing
it would require an arm where an unenforceable kind confers authority, and those arms now write zero.
The CSV writer uses minimal quoting, which has always quoted embedded newlines, so a real unquoted
row split is implausible — but that is an inference, not a measurement, and it is recorded as
unresolved rather than resolved in my favour.

The invariant now asserts parsed row count and per-row field count. Correctly measured, **the shape
invariant holds under all nine premises**, including the two that corrupt 9 and 10 cells. That is a
stronger statement than the test previously made, and it separates value corruption from structural
corruption instead of conflating them.

### Deviation, disclosed

`primary_key_only` and `ddl_typical` were diagnosed with two throwaway probe scripts written outside
the repository (`%TEMP%\dfprobe\`), because the harness reports aggregates and the question was about
one fix at a time. They are not committed and are not part of the instrument; every number above
comes from `scripts/measure_trust_ledger.py`.

---

## Amendment 2 — a new prediction, registered before it is measured, 2026-09-16

Nothing below has been run. This is written first precisely because the change it licenses looks
obviously safe, and "obviously safe" is the condition under which this repository has previously
shipped three instances of one defect class.

### The third authority axis

Two axes have been closed. **Axis 1**, constraint-kind enforceability: `authoritative_columns`
conferred authority for ten `Schema` kinds while the verifiers enforced six (closed 2026-09-14).
**Axis 3**, per-kind discriminating power: measured for the first time in amendment 1 above.

**Axis 2 — declared-type checkability — is open, and it is the same defect a third time.**

`type_discriminates` is a **denylist**: authority is conferred by any type spelling *not* in
`NON_DISCRIMINATING_COLUMN_TYPES` = {`""`, `str`, `string`, `text`, `object`, `any`}. The verifiers
can encode a **closed** set: `direct.py`:37-39 defines `_INT_TYPES` ∪ `_FLOAT_TYPES` ∪ `_STR_TYPES` =
{`int`, `integer`, `float`, `decimal`, `real`, `str`, `string`}, and `direct.py`:148 returns UNKNOWN
for anything else. `_normalize_type` only strips and lowercases, so no unrecognised spelling is
mapped into the encodable set.

Intersecting: types that both confer authority and can be checked are exactly {`int`, `integer`,
`float`, `decimal`, `real`}. Every other discriminating spelling — `date`, `datetime`, `timestamp`,
`bool`, `uuid`, `varchar`, `bigint`, `numeric`, and any spelling nobody has thought of, because a
denylist is unbounded — **confers authority that no verifier can act on**.
`tests/unit/test_column_scoped_authority.py`:77-79 asserts this as intended behaviour for `date`,
`datetime` and `bool`.

### P9 — revoking authority from non-encodable types is write-neutral

**Prediction.** A premise arm `non_encodable_type_only` — `PERMISSIVE_SCHEMA` with every column
declared `date`, one field changed — writes **0 cells and corrupts 0 of 14 both before and after**
the rule is changed from a denylist to the derived encodable set. Authority is granted today, but
every proposal on such a column returns UNKNOWN, and UNKNOWN does not license a write. So removing
the authority should change no write outcome and only make `authoritative_columns` truthful in the
attestation.

**P10.** The arm's `wrongly_blocked` contains `correct-score-repair` both before and after, because
the arm is inert in both conditions. If it were empty before and populated after, the change would be
a regression and not write-neutral.

**Kill criteria.**

- **K8.** If the arm writes anything **before** the fix, P9 is refuted and the finding is far more
  serious than a truthfulness defect: it would mean UNKNOWN permits writes, which is a **fourth**
  instance of the defect class and outranks the rule change. In that case the rule change is
  suspended and the write path is investigated first.
- **K9.** If the arm's numbers differ before versus after in any field, the change is not
  write-neutral. The claim is then withdrawn, not reworded, and the measured difference is published.
- **K10.** `tight` and `permissive` must continue to reproduce the committed artifact (K1 still
  binds). The type rule touches `columns`, which `TIGHT_SCHEMA` populates, so this is the arm most
  likely to move something it should not — `tight` declares `int`/`float`, both of which stay
  authoritative, so the prediction is that it does not move.

**What would make me abandon the change.** If `tight` loses its one legitimate repair, the derived
set is too narrow and the denylist was load-bearing. That is a real possibility and it is why this is
measured on both sides rather than tested after the fact.

---

## Amendment 3 — Axis 2 results, 2026-09-16

Measured on both sides of the change, in that order, with the arm added before the rule was touched.

| condition | authority conferred | cells written | corrupted | held | `wrongly_blocked` |
| --- | --- | --- | --- | --- | --- |
| **before** (denylist) | all 5 columns | 0 | 0 / 14 | 14 | `correct-score-repair` |
| **after** (derived allowlist) | none | 0 | 0 / 14 | 14 | `correct-score-repair` |

**P9 confirmed. P10 confirmed. K8, K9 and K10 all silent.**

- **K8 does not fire**, and this was the outcome worth checking for: before the change the arm held
  authority over every column and still wrote nothing, so UNKNOWN does not license a write. Had it
  written anything, the write path would have outranked the rule change entirely.
- **K9 does not fire**: every reported field is identical before and after. The change is
  write-neutral, as predicted, and its whole effect is that `authoritative_columns` now reports what
  it can actually support.
- **K10 does not fire**: no `INSTRUMENT FALSIFIED`, so `tight` and `permissive` still reproduce the
  committed artifact. `TIGHT_SCHEMA` declares `int` and `float`, both of which remain authoritative,
  and it keeps its one legitimate repair.

### What was actually changed

`type_discriminates` went from a **denylist** (`not in NON_DISCRIMINATING_COLUMN_TYPES`, unbounded
and failing open) to an **allowlist derived** from the verifiers' encodable set:

```
DISCRIMINATING_COLUMN_TYPES = ENCODABLE_COLUMN_TYPES - NON_DISCRIMINATING_COLUMN_TYPES
                            = {int, integer, float, decimal, real}
```

The set is a *consequence*, not a list, and
`test_the_authoritative_set_is_derived_not_enumerated` asserts the derivation rather than the
membership — so a spelling added to the encodable set becomes authoritative automatically and one
removed loses authority automatically. That is the same correspondence the Axis-1 fix established for
constraint kinds.

### An unplanned finding: the same table existed three times

`ENCODABLE_INT_TYPES` and `ENCODABLE_FLOAT_TYPES` were hardcoded as inline literals in
`verifier/direct.py`, `verifier/smt.py` **and** `verifier/inferred.py` — three hand-maintained copies
of one specification, the exact defect shape recorded four times in this repository. They now derive
from one constant in `domain/vocabulary.py`.

This does **not** weaken N-version diversity, and the reasoning matters enough to state: the
diversity that earns anything is in *how* each verifier decides — a z3 encoding versus direct
evaluation — not in how each spells `"int"`. The Axis-1 lesson was that N-version diversity cannot
catch what is absent from the specification both implementations share, so making that shared
specification explicit is the fix, not the risk. `require_independent_agreement` needs both to
accept, so the operative set is their intersection; all three modules listed identical tokens, so
intersection and union coincided, and a test now asserts they still do.

### A gate hole found by walking into it

The five new constants initially escaped `generate_domain_vocabulary.py`'s projection-coverage check
entirely, because that gate's population is `vocabulary.__all__` — and `__all__` is hand-maintained.
A constant imported by three other modules but absent from `__all__` is public in practice and
invisible to the gate. Adding them made the gate demand a project-or-withhold decision for each, as
designed; all five are withheld with reasons, and `DISCRIMINATING_COLUMN_TYPES` records the specific
condition that would reverse that.

The hole itself is **not fixed here** — it is a population-derivation defect in a gate, one axis away
from the three this pre-registration covers, and folding it in would make this change unattributable.
It is surfaced separately.

### Planted failure, per `PRODUCT.md`:280-283

Reverting `type_discriminates` to the denylist form fails exactly
`test_narrowing_but_unencodable_types_do_not_confer_authority` and
`test_an_unrecognised_spelling_confers_nothing` — 2 failed, 17 passed — and restoring gives 19
passed. The gate has been seen to fail on the case it newly covers.



