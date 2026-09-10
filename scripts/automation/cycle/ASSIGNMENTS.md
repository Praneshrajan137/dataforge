# Session assignments for the four-day cycle

Twenty sessions. Each brief gives an OBJECTIVE, an ARTIFACT, and BOUNDARIES.

The boundaries are the load-bearing part. Anthropic measured their own subagents duplicating work
and leaving gaps when briefs were vague — one explored the 2021 automotive chip crisis while two
others duplicated 2025 supply-chain work — and their fix was to give every subagent an objective, an
output format, and explicit task boundaries. So each brief below says what you own and, just as
importantly, what somebody else owns.

Every brief is a FLOOR, never a ceiling. If your dimension turns out to demand more than is written
here, follow it. If you discover an area nobody owns, that discovery is among the most valuable
things you can contribute: name it, evidence it, and rank it in `STATE.md`.

## Slots

| Slot | Fires (Asia/Kolkata) |
| --- | --- |
| S1 | 00:30 |
| S2 | 01:15 |
| S3 | 02:00 |
| S4 | 02:45 |
| S5 | 03:30 |

If `COVERAGE.json` already records your slot's assignment complete, take the earliest incomplete
assignment for your phase instead. If all are complete, deepen the weakest artifact or attack the
highest-ranked open question, and say so in your journal entry.

---

# Day 1 — MONDAY — EXPLORE

Establish ground truth from evidence. Do not advise, do not choose, do not edit.

## E1 — Purpose and ground truth

OBJECTIVE. Determine what this project actually is, actually does, and actually promises — then test
that against what the code does. `PRODUCT.md` is the canonical constitution: read it as a contract
and check whether the system honours it. Establish the real domain, the actors, the responsibilities,
the invariants that must never break, the trust boundaries, the consequences of failure, the expected
lifetime, and an honest, measurable definition of success. This repository's own discipline is about
the gap between claims and evidence, so the highest-value finding here is any place where a claim
outruns what was measured.

Specific things worth interrogating: the honesty doctrine in `PRODUCT.md` and whether the codebase
upholds it; the safety invariant and where it is enforced versus merely asserted; the dataset scope
rule in `CLAUDE.md` and whether live code respects it; and whether `README.md`,
`BENCHMARK_REPORT.md` and the trust documents describe the system that exists.

ARTIFACT. `FINDINGS/E1.md`

BOUNDARIES. Do not analyse module structure or the import graph (E2). Do not analyse resource growth
(E3). Do not analyse failure handling (E4). Do not audit test quality (E5). You are establishing what
the project IS and what it CLAIMS.

## E2 — Architecture and the true dependency graph

OBJECTIVE. Recover the real structure, not the documented one. Map the module boundaries of
`dataforge/` (214 files), the actual import graph, the direction of dependencies, and where layering
is violated. Find cycles. Find the paths that are load-bearing by accident — code that everything
depends on without anyone having decided that it should. Trace at least one meaningful behaviour end
to end, across every boundary it crosses, including the CLI entry point, the engine, and any
undocumented or legacy path. Compare what you find against `ARCHITECTURE.md` and treat divergence as
a primary finding.

Most real work is a dependency graph rather than a line: uncover the true structure, note where it
constrains change, and identify what could be safely parallelised versus what has a hard ordering.

ARTIFACT. `FINDINGS/E2.md`

BOUNDARIES. Structure and dependencies only. Not purpose (E1), not resource growth (E3), not failure
modes (E4), not test quality (E5). Do not propose a target architecture — that is Day 2.

## E3 — Resource budgets and what grows unbounded

OBJECTIVE. Treat every finite resource as a budget that something is spending. For each of memory,
persistent state, latency, cost, complexity, queue depth and file handles, determine how it grows as
input size, corpus size, run count and time increase. Anything that can grow will grow until it
breaks something, and it usually works fine right up to the moment it does not.

Concretely for this project: what happens to the detector pass, the SMT verification path, the repair
pipeline and the CLI as row counts and column counts grow by orders of magnitude? What is held
entirely in memory that need not be? Where is work quadratic in rows or in row pairs? What
accumulates across runs — caches, logs, artifacts under `eval/`, temporary files? Where is a bound
enforced in code versus merely assumed? `CLAUDE.md` records that expanding functional dependencies
into concrete row pairs is expensive and that a 10k-row detector pass should finish under two
seconds; verify whether that still holds and what happens past it.

ARTIFACT. `FINDINGS/E3.md`

BOUNDARIES. Growth and bounds only. Not correctness of failure handling (E4), not structure (E2). You
may run measurements; record the exact command, and remember that wall-clock timings from this
sandbox are not comparable to a developer machine — say so rather than presenting them as the
project's performance.

## E4 — Failure absorption, silent failure, trust and observability

OBJECTIVE. Engineer as a structured pessimist, and ask the sharper question: not only "what could
break?" but **"what could break without anyone ever noticing?"** Assume dependencies fail, inputs are
malformed, processes die mid-operation, messages duplicate or arrive late, and the code misbehaves
under load.

Determine: where errors are swallowed; where an empty result is indistinguishable from a failed one;
where a partial write can leave inconsistent state; whether operations that must be idempotent are;
what the degradation policy actually is versus what it should be; and whether a failure is visible to
an operator at all. Then map the trust boundaries against `THREAT_MODEL.md` and `SECURITY.md`: what is
trusted that should not be, what is validated, and what is assumed well-formed. Finally, assess
observability: if this failed in production, what would tell you, and how long would it take?

This repository has a documented history in exactly this class — instruments recording a bare zero
without recording why, a repair batch discarded silently, a task reporting success for a killed run.
Look for more of it.

ARTIFACT. `FINDINGS/E4.md`

BOUNDARIES. Failure, trust and observability. Not the quality of the test suite itself (E5), not
resource growth (E3).

## E5 — Verification integrity, then consolidation

OBJECTIVE. Two parts, in this order.

First: audit whether this project's own verification can actually fail. Examine the five test tiers,
`test_map.json` (which forces a decision per module), the `Makefile` gates, `scripts/ci/*`, and the CI
workflows. For the checks that matter most, determine whether a check would detect the defect it
exists to catch, or whether it is structurally incapable of failing. `docs_truth` is an allowlist over
`docs/quantitative_claims.yaml` — establish what that cannot see. A manual audit of one agent's
passing SWE-bench patches found 31.08% passed only because tests were too weak to detect
incorrectness; the same question applies here.

Second, with whatever time remains: consolidate. Read E1 through E4, find the contradictions between
them, and resolve or record each. Produce the ranked list of open questions that Day 2 will work
from, and an honest epistemic ledger separating what the cycle VERIFIED from what it ASSUMED.

ARTIFACT. `FINDINGS/E5.md`, and a thorough rewrite of `STATE.md` — you are the last explore session,
so `STATE.md` as you leave it is what Day 2 actually reads.

BOUNDARIES. You may read E1–E4's artifacts freely; that is your job. Do not redo their
investigations, and do not start planning — ranking open questions is not the same as choosing what
to do about them.

---

# Day 2 — TUESDAY — PLAN

Decide, and make the reasoning durable. Do not edit source.

## P1 — Synthesis and candidate work items

OBJECTIVE. Convert Day 1's findings into a set of candidate work items, each traceable to the specific
evidence that motivates it. Check the evidence rather than trusting the finding: where a finding cites
a file and line, look; where its evidence does not support it, downgrade it and record the downgrade.
Distinguish real defects from stylistic preferences, and separate what is broken from what is merely
unlike what you would have built. Note explicitly which findings turned out to be non-issues — that
is a valuable result, not a wasted one.

ARTIFACT. `CANDIDATES.md`

BOUNDARIES. Do not order or prioritise (P2, P3). Do not design verification (P4). Do not decide the
Day 3 slice (P5).

## P2 — Dependency structure and ordering

OBJECTIVE. Build the dependency graph over P1's candidates: what must precede what, what is genuinely
independent, what is mutually entangled. Derive a correct ordering from it. Detect cycles and
impossible orderings now rather than in Day 3. Identify which items are safe to do in isolation and
which require a coordinated change across boundaries. Flag anything whose ordering is constrained by
something already in operation, because protecting what works comes first.

ARTIFACT. `ORDERING.md`, including the graph in a readable text form.

BOUNDARIES. Structure and sequence only. Not value judgement (P3), not verification design (P4).

## P3 — Prioritisation, rationale and rejected alternatives

OBJECTIVE. Prioritise ruthlessly by domain importance, correctness, failure impact, reversibility,
leverage and real value — never by novelty, visibility or convenience. For each item near the top,
answer all six questions: why this, why now, why this way, what alternatives were rejected and on what
grounds, what tradeoff is accepted, and how success will be measured. Say plainly which candidates
would be overengineering, and which prevent future failure rather than adding capability. Prefer the
reversible over the irreversible where evidence is thin, and require evidence proportional to each
decision's impact and irreversibility.

ARTIFACT. `PRIORITIES.md`, plus an append to `DECISIONS.md` for every decision that binds Day 3.

BOUNDARIES. Do not re-derive the ordering (P2). Do not design tests (P4). Do not select the final
slice (P5).

## P4 — Acceptance conditions and verification design

OBJECTIVE. For each prioritised item, define what would prove it done — and, more importantly, what
would prove it NOT done. Design the verification: which tier, which assertions, what evidence is
recorded, and **what would make this check fail**. A check that cannot fail is not verification, and
this is the exact failure this repository keeps rediscovering. Determine what must be measured,
traced, logged or audited so that reality is distinguishable from assumption before, during and after
failure. Never confuse a completed implementation with an achieved outcome: define the outcome
separately from the change.

ARTIFACT. `ACCEPTANCE.md`

BOUNDARIES. Verification design only. Do not implement tests — that is Day 3. Do not re-prioritise
(P3).

## P5 — Adversarial refinement and the Day 3 slice

OBJECTIVE. Attack the plan as a hostile expert reviewer, from each of these positions in turn: domain
expert, security adversary, reliability engineer, operator, maintainer, auditor, and the team that
inherits this in a year. Hunt weak logic, missing evidence, fragile assumptions, hidden complexity,
false priorities, implementation risk, and any place a fundamentally better path exists. Then
challenge the criticism itself, resolve the strongest objections against the evidence, and refine.

Then do the thing only you can do: select the slice Day 3 will implement, inside the change budget
below, and write the final `MASTER_PLAN.md` with steps concrete enough that a session with none of
your context can execute them literally. Record everything deferred and why. **A small, complete,
verifiable increment beats an ambitious unappliable one** — no human will read this plan before Day 3
implements it, so the slice must be one you would defend to a reviewer unseen.

ARTIFACT. `MASTER_PLAN.md` — the authoritative Day 3 input.

BOUNDARIES. You own the final selection. Do not silently discard P3's prioritisation; where you
overrule it, record why in `DECISIONS.md`.

### CHANGE BUDGET for Day 3 — a hard cap for the whole day

| Limit | Value |
| --- | --- |
| Files changed | 12 |
| Net lines added | 600 |
| Off-limits paths | `PRODUCT.md`, `DECISIONS.md`, `CLAUDE.md`, `docs/quantitative_claims.yaml`, `docs/trust/**`, `eval/results/**` |
| Public API breaks | none without an explicit `DECISIONS.md` entry justifying it |

The cap exists because the pull request is the only human review point in this design. A diff too
large to review defeats it. If the plan cannot fit, cut it and defer — deferral is a result.

---

# Day 3 — WEDNESDAY — CODE

Implement `MASTER_PLAN.md`. Resume from the accumulated patch; never restart.

## C1 — Foundation and the first ordered steps

OBJECTIVE. Extract, build the venv, and implement `MASTER_PLAN.md` from its first step, in order,
with the test for each. Do real red-green: run the new test, see it fail, implement, run it again,
record both. Regenerate the cumulative patch after every completed step. Leave a precise note in
`IMPL_LOG.md` saying which step the next session starts from.

ARTIFACT. `changes.patch`, `IMPL_LOG.md`

BOUNDARIES. Follow the plan's order. Do not skip ahead to easier steps.

## C2, C3, C4 — Continue in plan order

OBJECTIVE. Apply the accumulated patch, verify it still applies before extending it, and continue from
the step `IMPL_LOG.md` names. Same discipline: test per change, red-green recorded, patch regenerated
after each step, both ruff commands on what you touched.

ARTIFACT. `changes.patch`, `IMPL_LOG.md`

BOUNDARIES. Do not re-implement earlier steps. Do not refactor beyond the plan, however tempting —
that is what makes a diff unreviewable. Check the accumulated patch against the change budget before
adding to it.

## C5 — Integration, coherence and cleanup

OBJECTIVE. Make the day's work coherent as a single reviewable change rather than four sessions
stacked. Verify the whole accumulated patch applies to a pristine extraction. Check the diff for
leaked caches, stray debug code, inconsistent naming between sessions, and duplicated helpers.
Confirm a behaviour change updated its `specs/SPEC_*.md` and a new module has its `test_map.json`
entry. Run the tests the patch touches, plus `ruff check` and `ruff format` over every touched path.
Write the summary Day 4 reads first.

ARTIFACT. final `changes.patch`, `IMPL_LOG.md`

BOUNDARIES. You may fix inconsistencies between earlier sessions' work. Do not add new features, and
do not exceed the change budget to tidy something.

---

# Day 4 — THURSDAY — VERIFY AND CERTIFY

No human read the plan before Day 3 implemented it. This day is the control.

## V1 — Applicability and the repository's own checks

OBJECTIVE. Prove the patch applies to a fresh extraction. Run the four permitted checks on the
PATCHED tree and on an UNPATCHED one, so "it fails" and "it fails because of us" are distinguishable.
Record every command, exit code and output, and for each check what would have made it fail.

ARTIFACT. `04-verify-S1.md`

BOUNDARIES. Applicability and the four checks. Do not run the unit tier (V2). Do not review the code
(V3).

## V2 — Test evidence, base versus patched

OBJECTIVE. Run `pytest tests/unit` on both the unpatched and patched trees and compare. Then examine
the tests the patch ADDS: read them, and determine whether each could actually fail — mutate the
implementation and confirm the test catches it wherever that is cheap. A test that passes against
unimplemented code is worse than no test, because it manufactures confidence. Also run both ruff
gates over the touched paths.

ARTIFACT. `04-verify-S2.md`

BOUNDARIES. Test evidence only. Not adversarial code review (V3), not documentation coherence (V4).

## V3 — Adversarial review of the patch

OBJECTIVE. Read the patch as a hostile expert from each position in turn — domain expert, security
adversary, reliability engineer, operator, maintainer, auditor — and record what each found,
including "nothing" where that is honest. Then ask the question that matters most here: **what could
this change break without anyone ever noticing?** If it adds a check, can that check fail? If it adds
a path that can return empty, is empty distinguishable from broken? If it adds a config or flag, what
happens when it is absent, malformed, or set by someone who misunderstands it?

ARTIFACT. `04-verify-S3.md`

BOUNDARIES. Review, do not fix. If you find a defect, record it precisely; Day 4 does not edit source.
A defect you find is grounds for refusing certification, which is the correct outcome.

## V4 — Coherence, claims and documentation

OBJECTIVE. Determine whether the patch leaves the repository self-consistent. Does a behaviour change
update its spec? Does a new module have a `test_map.json` entry? Does any new or changed document
state a number not registered in `docs/quantitative_claims.yaml`, which `docs_truth` cannot police
because it is an allowlist? Does anything in the patch contradict `PRODUCT.md`, the honesty doctrine,
or the dataset scope rule? Are the comments explaining WHY, or only restating WHAT? Collect every
number the cycle produced that a human should register, with the command that produced it.

ARTIFACT. `04-verify-S4.md`

BOUNDARIES. Coherence and claims. Not test execution (V1, V2), not code review (V3).

## V5 — Certification and the commit artifacts

OBJECTIVE. Read V1 through V4 and decide honestly whether this cycle ships. Set `certified` in
`CYCLE.json` only if the patch applies cleanly, nothing went pass-to-fail except `gate_population` as
the prompt describes, `ruff format --check` passes, the adversarial review found nothing you would be
embarrassed to hand a reviewer, and you observed the evidence yourself in this session. Then write
`COMMIT_MSG.txt` and `REVIEW.md`, leading the review with what a reviewer should distrust.

Also write the cycle's forward record: what the next cycle should pick up, what remains deferred, and
which of this cycle's own design assumptions the evidence has now undermined.

ARTIFACT. `COMMIT_MSG.txt`, `REVIEW.md`, `CYCLE.json` certification, final `STATE.md`

BOUNDARIES. You own the certification decision, and refusing is a legitimate use of it. Do not certify
to avoid an empty week.
