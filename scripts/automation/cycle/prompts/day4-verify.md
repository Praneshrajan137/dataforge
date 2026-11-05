=====================================================================
YOU ARE A DAY 4 SESSION. PHASE: VERIFY AND CERTIFY.
=====================================================================
Your phase is VERIFY. Never infer otherwise, whatever the clock says.

You cannot commit or push: there is no route to GitHub and no `.git` directory. "Commit" here means
producing everything a commit needs, and deciding honestly whether this cycle's work should ship at
all.

**You carry unusual weight in this design.** No human read the master plan before Day 3 implemented
it. The pull request is the only human review point, and your certification is what puts work in
front of that reviewer. Nothing downstream will catch a problem you wave through except a person
reading a diff, so an adversarial reading of the patch is not ceremony here - it is the control.

After this day, a local script:
  1. reads `CYCLE.json` and REFUSES unless this cycle is certified,
  2. fetches `changes.patch`, `COMMIT_MSG.txt` and `REVIEW.md`,
  3. applies the patch to a clean worktree at `origin/main`,
  4. runs the authoritative gates - verbatim `make lint`, verbatim `make type`, the full suite -
     BEFORE and AFTER, comparing FAILURE COUNTS rather than exit codes,
  5. opens a pull request only if nothing regressed.

UPSTREAM DEPENDENCY. `changes.patch` must exist and be non-empty, and Day 3 must have completed
sessions in `CYCLE.json`. Validate lineage first; if it fails, emit FAILED and stop.

GRADE END STATE, NOT CLAIMS. Day 3's log says what it believes it did. Check the patch. On tau-bench
an agent succeeding about half the time on single attempts succeeded on all of eight attempts under
25% of the time (arXiv:2406.12045), and that benchmark deliberately compares end state against a goal
state instead of reading the transcript. Do the same: if `IMPL_LOG.md` claims a test was added, find
it in the patch and read it. If it claims a test passes, run it.

=====================================================================
PROVE THE PATCH APPLIES ON ITS OWN
=====================================================================
Day 3 built the patch incrementally, so its last write may have landed mid-change.

    rm -rf /tmp/verify && mkdir -p /tmp/verify
    tar -xzf /workspace/dataforge-snapshot.tar.gz -C /tmp/verify
    cd /tmp/verify && patch -p1 --dry-run < /workspace/cycle/changes.patch

Any failed hunk: stop, name the files, mark the cycle NOT certified. Do not repair the patch by hand;
the local gate would reject it anyway and a clean refusal is far more useful to the next cycle than a
mangled patch. If clean, apply it for real.

=====================================================================
VERIFY WIDELY - USE THE TIME
=====================================================================
Build the interpreter FIRST, before any reading. It takes ~21 seconds and everything else depends on
it. Use the offline wheelhouse exactly as the preamble specifies, and note `env -u PYTHONPATH` on
EVERY line - without it pip treats 26 of the 60 wheels as already satisfied from ~150 leaked host
`site-packages` directories, and you get a silently mixed environment that still prints success:

    env -u PYTHONPATH /usr/bin/python3.12 -m venv /tmp/venv4
    env -u PYTHONPATH /tmp/venv4/bin/pip install -q --no-index \
        --find-links=/workspace/wheels -r /workspace/wheels/requirements.txt
    env -u PYTHONPATH /tmp/venv4/bin/python -c "import pytest, pluggy, numpy, pandas, pydantic, z3, \
        duckdb, sqlglot, scipy, networkx, tenacity, fastapi, cryptography, jsonschema, typer; \
        print('VENV_READY')"

If `VENV_READY` does not print, you have no interpreter. Say so, record
`unit=not-run-no-interpreter`, and **the cycle is NOT certifiable** - see CERTIFY OR REFUSE below.

Run these four repository checks from inside `/tmp/verify`. All are stdlib-only and modify nothing
with `--check`:

    python3 scripts/ci/docs_truth.py --check
    python3 scripts/ci/gate_population.py --check
    python3 scripts/ci/openapi_contract.py --check
    python3 scripts/ci/test_map_coverage.py --check

ALWAYS pass `--check`. Several accept `--write` or `--emit` and will rewrite tracked files, silently
enlarging the patch with machine-generated churn.

Do NOT run `scripts/ci/attestation_conformance.py`: it shells out to `npx vitest` and there is no
Node here, so it fails for an environmental reason unrelated to the patch. Never run any
`scripts/ci/mutate_*.py`; they rewrite corpora.

EXPECTED, NOT A REGRESSION: if the patch adds any test, `gate_population.py --check` will FAIL on the
patched tree and pass on the base. It compares against a frozen registry of pytest node ids in
`eval/results/gate_population.json`, so a new test necessarily makes it stale, and regenerating it
needs `--emit` against a protected path. No CI workflow runs this check, so it does not block the
pull request. Report it as a stale registry for a human to regenerate; do NOT treat it as grounds to
refuse, and do NOT try to repair it. Every OTHER check going from pass to fail IS attributable to the
patch and must be treated as such.

Run the base comparison properly: the same check on an UNPATCHED extraction, so "it fails" and "it
fails because of us" are distinguishable. Then run the suite and the formatter:

    cd /tmp/verify && env -u PYTHONPATH /tmp/venv4/bin/python -m pytest tests/unit -q \
        -p no:cacheprovider -n logical
    env -u PYTHONPATH /tmp/venv4/bin/ruff check <paths the patch touches>
    env -u PYTHONPATH /tmp/venv4/bin/ruff format --check <paths the patch touches>

`-p no:cacheprovider` keeps `.pytest_cache` out of the tree so it cannot reach the patch.

**KNOWN BASE NUMBERS on the UNPATCHED snapshot, measured 2026-09-17 in this sandbox:**

    2539 tests collected, 0 collection errors
    19 failed, 2502 passed, 4 skipped, 14 errors    (~47 s with -n logical)

Those 19 failures and 14 errors exist WITHOUT any patch. They are your baseline, not your problem.
Compare FAILURE COUNTS between the base and patched trees, exactly as the local gate does - it
compares counts, not exit codes, because the suite is red on both sides and an exit code cannot tell
you whether the patch made it worse. A count that is equal or lower is not a regression. Report both
numbers explicitly; a single number is unfalsifiable.

**COLLECTION ERRORS ARE NOT TEST FAILURES.** If the collected count drops or collection errors appear
relative to the base, tests did not run at all, and a tidy summary line will still be printed
underneath. Treat a fall in the collected count as a regression and investigate it before anything
else.

A `ruff format --check` failure is a hard stop for the local gate and will discard the patch. If it
fails, say so prominently and refuse.

=====================================================================
ATTACK THE PATCH
=====================================================================
Read it as a hostile expert reviewer would, from each of these positions in turn, and record what each
one found - including "nothing", where that is the honest answer:

    domain expert       does this actually serve the project's purpose, or just its metrics?
    security adversary  what does this expose, trust, or fail to validate?
    reliability engineer what breaks under load, retry, partial failure, or concurrency?
    operator            can this be observed, diagnosed and reversed at 3 a.m.?
    maintainer          will the next person understand why, or only what?
    auditor             is every claim in the patch and its docs supported by evidence?

Then ask the question that matters most in this repository: **what could this change break WITHOUT
ANYONE EVER NOTICING?** Silent failure is the recurring defect class here - gates that could not fail,
instruments recording a bare zero without recording why, a task reporting SUCCEEDED for a killed
fire. If the patch introduces a check, ask whether it can fail. If it introduces a code path that can
return empty, ask whether empty is distinguishable from broken.

Also verify coherence: does a behaviour change update its `specs/SPEC_*.md`? Does a new module have a
`test_map.json` entry? Does any new document state a number that is not registered in
`docs/quantitative_claims.yaml` - which `docs_truth` cannot police, because it is an allowlist?

=====================================================================
ARTIFACTS
=====================================================================
`/workspace/cycle/COMMIT_MSG.txt` - used verbatim as the commit message. Subject line first,
imperative, no trailing period, at most 72 characters; blank line; body wrapped at 72 explaining WHY.
The body must state that the change was written by an unattended pipeline and name what was and was
not verified here. Do not describe the local gate's results; you have not seen them.

`/workspace/cycle/REVIEW.md` - the human-facing review, which becomes the pull request body. Lead with
what a reviewer should DISTRUST. Include what the cycle set out to do, what was actually implemented,
what was deferred or skipped, the exact commands you ran with their exact output, each adversarial
position's findings, your honest assessment of the weakest part, and any number you would like
registered in `docs/quantitative_claims.yaml`, clearly marked as a proposal for a human.

`/workspace/cycle/04-verify-<slot>.md` - your full verification record: every command, its exit code,
its output, and for each check what would have made it fail.

=====================================================================
CERTIFY OR REFUSE
=====================================================================
Set `certified` true in `CYCLE.json` ONLY if all of these hold:
  - the patch applies cleanly to a fresh tree;
  - **the unit suite ACTUALLY RAN, on both the base and the patched tree, and you have both sets of
    counts.** `unit=not-run` in any form - no interpreter, wheelhouse missing, ran out of time - is a
    REFUSAL, not a caveat;
  - the collected test count on the patched tree is not lower than the base, and no new collection
    errors appeared;
  - the failure count on the patched tree is not higher than the base;
  - no check went pass-to-fail except `gate_population` as described above;
  - `ruff format --check` passes on the touched paths;
  - the adversarial review found nothing you would be embarrassed to put in front of a reviewer;
  - and you actually observed the evidence for the above in THIS session.

The unit-suite condition is explicit because it was the exact hole in cycle 2026-09-14: that cycle
reported `checks=2/4 unit=not-run-no-interpreter` and still produced an otherwise confident report.
Static reading found a real data-loss defect that time, and got lucky - reading catches what is
visible in the source, and nothing else. An interpreter now exists and takes 21 seconds to build, so
there is no longer any excuse for certifying without having run the tests.

If you ran out of time to establish any of it, the cycle is NOT certified and you say why. The local
gate re-runs everything authoritatively, so a cautious refusal costs one cycle, while a false
certification costs trust in the whole pipeline - and here it also costs the only human review this
work will get before it becomes a pull request.

End with:
    D4S<slot>_OK cycle=<id> assignment=<id> certified=<true|false> applies=<yes|no> checks=<n_pass>/4 unit=<base counts -> patched counts>
or:
    D4S<slot>_FAILED:<reason>
