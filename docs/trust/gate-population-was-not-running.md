# The gate that freezes every other gate was not running

**Date:** 2026-09-14
**Code:** `scripts/ci/gate_population.py`, `scripts/ci/backend_gate.py`, `.github/workflows/ci.yml`
**Gate:** `tests/unit/test_gate_invocation_integrity.py`
**Manifest:** `eval/results/gate_population.json`

## The defect

`scripts/ci/backend_gate.py` declared its anti-erosion step as:

```python
GateCommand(
    "gate population",
    [PYTHON, "scripts/ci/hf_space_frontmatter.py", "scripts/ci/gate_population.py", "--check"],
)
```

That is **one** interpreter invocation. `hf_space_frontmatter.py` is the script;
`scripts/ci/gate_population.py` and `--check` are argv entries it never reads — its `main()` takes
no parameters and the module contains no `argparse` and no `sys.argv` access.

Run directly, it prints `HF Space YAML front-matter valid.` and exits **0**.

So the step reported **PASS** under the name "gate population" while a different check ran. Two
checks were collapsed into one named slot, so one of them was also being credited to the other's
name in the manifest.

**And it had no other path to execution.** Searching `.github/workflows/*.yml` for
`gate_population` returns one *comment* and zero run steps. `Makefile:100` defines a
`gate-population` target that no workflow invokes. This malformed command was the only place it
could have run, and it did not.

## Why this is worse than one dead gate

`gate_population.py` is the **meta-gate**. It is what makes a deleted test, a vanished claim, a
removed mutant, a dropped gate step or a shrunk scanned-document set detectable at all. Its
absence did not hide an instance of a defect; it hid a *class*.

The blast radius is visible in the repository's own reasoning. Both of these appear in comments
that justify a **different** decision:

- `.github/workflows/ci.yml`: *"The harness this runs already existed, was type-checked, and was
  frozen against removal by `scripts/ci/gate_population.py` — and no workflow ever executed it."*
- `Makefile`: *"the harness existed, was type-checked, was frozen against removal by
  `scripts/ci/gate_population.py` — and was never executed by CI."*

Both cite `gate_population.py` as the trustworthy freezing mechanism **in the same sentence that
explains why unexecuted protection is worthless**. The 2026-09-01 work correctly identified that a
harness nothing runs is decorative, added a `mutation-gate` job to fix it, and never asked whether
the gate it was leaning on was itself running. Every "frozen against removal by gate_population"
claim in this repository was false.

**The symptom was present and unread.** Run by hand on 2026-09-14, `gate_population.py --check`
reported **136 un-emitted pytest node additions**. Nothing was wrong with those additions; the
point is that a manifest 136 entries stale is a manifest nobody had consulted.

## The second hole in the same gate

`_step_names` derived the gate's step population by AST-scanning `backend_gate.py` for calls whose
callee was in `STEP_CALLEES = ("_run", "GateCommand")`. Seven result-contributing checks are
appended to `checks` as bare function calls and matched neither:

`_coverage_policy_check`, `_pip_audit_exception_check`, `_corrector_promotion_gate`,
`_secret_scan`, `_pip_audit_scope_check`, `_pip_audit_liveness_check`, `_npm_audit_check`.

The manifest recorded **40** steps while the gate ran **47**. Any of those seven could have been
deleted with the manifest reporting no change — including the npm audit and the entire pip-audit
exception family, which is the machinery `dependency-advisory-triage.md` was written about.

`checks` is a `list[bool]`. The booleans carry no names, so the population cannot be recovered
from the runtime values either.

## What was measured, and what the numbers are

| quantity | before | after |
| --- | --- | --- |
| workflows running `gate_population.py` | **0** | 1 (`gate-population` job) |
| backend gate steps in the manifest | 40 | **48** |
| result-contributing steps the gate runs | 47 | 48 |
| steps invisible to the population check | **7** | 0 |
| checks collapsed under another step's name | 1 | 0 |

48 rather than 47 because the malformed command was split into two correctly-named steps.

## The fix

- The command is split. `gate population` runs `gate_population.py`; `HF Space front-matter` runs
  `hf_space_frontmatter.py`.
- A `gate-population` **CI job** exists, with no `needs:`, mirroring how `mutation-gate` was added
  on 2026-09-01 for the identical reason. A gate reachable from exactly one place is one edit from
  being unreachable.
- `_step_names` no longer scans for two callee names. It enumerates **`checks` itself** — the
  initialising list, every `.append` and every `.extend` inside `main()` — and resolves each
  contributor via `_run`/`GateCommand` literals, via nested `GateCommand`s inside `_run_group`, or
  via a new `@gate_step("<name>")` decorator on the seven print-style functions.
- **An element it cannot name raises.** That refusal is the substance of the change. The previous
  implementation collected the shapes it recognised and ignored the rest, which is an allowlist
  wearing the costume of an enumeration.

## Why this keeps happening, stated generally

This is the sixth gate found unable to fail, and the third time in three weeks that a
hand-maintained population turned out to be narrower than the population it appeared to police —
after `readme_truth.py`'s eight-name literal against an eleven-member vocabulary, and
`authoritative_columns`' ten authority kinds against six enforced ones
([authority-enforcement-correspondence.md](authority-enforcement-correspondence.md)).

`PRODUCT.md` 1.3 states the rule: *"Derive the population a gate polices; never restate it."* It
states it as a **maxim**. In a repository that distrusts every unenforced claim, it was the one
doctrine rule with no mechanical enforcement — and the gate that would have made its violations
visible was the one not running.

The pattern that fixes it is not novel and is worth naming, because the safety-critical
disciplines settled it decades ago. DO-178C, ISO 26262 and IEC 62304 require **bidirectional
traceability**, and they solve completeness by **enumerating the artifact rather than the links**:
a requirement with no parent is not invisible and not an error, it is a *derived requirement*, a
named category carrying an obligation, and code that cannot be traced to a requirement is *dead*
or *deactivated code* with an explicit verification objective (DO-178C Table A-7 Objective 9). The
mechanism is a **traceability matrix**, and auditing its completeness is **coverage analysis**.

Three changes in this repository now have that shape: `ENFORCEABLE_CONSTRAINT_KINDS` paired with
`UNENFORCEABLE_CONSTRAINT_KINDS` over `Schema`'s fields, `MEASURABLE_DETECTORS` paired with
`UNMEASURED_DETECTORS` over the registrable repairers, and `checks` resolved totally with a
refusal on the unnameable. Enumerate the artifact; give the remainder a name and a reason.

## Two divergences the meta-gate should have surfaced, closed with it

- **`_DEFAULT_THRESHOLDS` covered 8 of 12 issue types.** `date_transposition`,
  `entity_consensus`, `semantic_domain_violation` and `time_format_cruft` fell through to
  `default_threshold=0.90` instead of the `1.01` never-auto-apply sentinel their siblings carry.
  Each is refused today by a *different* mechanism — two by the engine's detection-only set, one
  by having no repairer at all, one by untrusted provenance — so nothing was written that should
  not have been. Which is the problem: `PRODUCT.md` calls that *"a guarantee holding by
  accident"*, and the entire argument for C4 was that an incidental refusal must be made
  principled and named. Now asserted total against `ALL_ISSUE_TYPES` **at import**, in the shape
  `detectors/base.py:137` already used. Adding the four sentinels changed no test outcome, which
  is the evidence that the refusals were real and merely unnamed.
- **`MEASURABLE_DETECTORS` covered 5 of 8 registrable repairers**, and its guard asserted only a
  *lower* bound, so a missing member was structurally invisible. `CLAUDE.md` names that harness as
  what replaces the retired 0.7926 headline, so an unseen hole in its population is a hole in the
  evidence that replaced a headline. Two absences are genuine scope decisions and are now recorded
  as such. The third is not: **`decimal_shift` has never been measured here**, and it is the
  detector removed after 263,428 false rewrites — the motivating case for the very document this
  harness feeds. It is recorded as an open gap rather than dressed as a decision.

## Falsification, before any of it was trusted

A gate nobody has seen fail on a case it newly covers has not been shown to cover it. Each was
planted and observed to fail:

- Re-planting the two-script command fails `test_a_direct_script_invocation_passes_no_second_script`
  and `test_gate_population_is_invoked_as_a_script` — the general rule and the specific regression,
  independently.
- Commenting out `checks.append(_secret_scan())` removes `secret scan` from the derived population.
  Under the old AST scan that step was never in the population, so its deletion produced **zero**
  change.
- Appending an undecorated check raises with the message naming `@gate_step`.
- Emptying `UNMEASURED_DETECTORS` reports the unaccounted repairer by name.

## Honest status

- Fixed, falsified, and running in CI as its own job.
- **Not** claimed: that the population is now complete in every dimension. It covers pytest node
  ids, gate step names, mutants and their test paths, and claim ids. The claim *ledger* it counts
  remains an allowlist, so the number of claims is pinned while the share of published numbers
  those claims cover is not — see the claim-coverage work.
- One consequence worth stating plainly: because the manifest was 136 entries stale, the first
  `--emit` after this fix absorbs additions made by earlier work that never emitted. That is
  recorded rather than silently folded in.
