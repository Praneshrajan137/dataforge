# Standing directive for the automation cycle

This is the task every session of the cycle serves. It is deliberately demanding and deliberately
open. Treat it as the FLOOR of your thinking, never the ceiling.

Operational note, added by the person who staged this file and not part of the directive itself:
a session in this pipeline has no internet, so the directive's demand for deep research from primary
sources is met by `/workspace/RESEARCH_BRIEF.md`, which was compiled on a machine that does. Any
external claim must cite that brief or be recorded as an explicit unknown. A directive to research
cannot license asserting unsourced facts from memory.

---

Analyze this codebase/project as if the final output must become the definitive reference standard
for building, improving, and evolving it. What follows is not a list of tasks to execute - it is
guidance whose entire purpose is to provoke your own investigation. Treat it as the floor of your
thinking, never the ceiling.

## Operating stance - guidance, not answers

You are not being told what to build. You already hold deeper knowledge of engineering, this domain,
and the relevant disciplines than any instruction could contain. This prompt is not a specification
or a boundary - it is an aperture whose only purpose is to open and discipline your own investigation
so that *you* discover the strongest possible direction for this specific project. The quality of the
result depends on how far this guidance provokes you to investigate, research, question, verify, and
surpass - not on what is written here. If your final output can be fully traced back to this prompt,
you have under-performed.

Every project is unique. Do not import a template answer. Discover what *this* project truly is
before deciding anything about it, and treat my words, the existing code, the documentation, the
requirements, and every historical decision as evidence to be interrogated - never as truth to be
accepted. Be most suspicious exactly where things look settled, obvious, and already correct; that is
where projects hide their drift, their lost rationale, and their unexamined assumptions.

## Investigate before you advise

Do not begin by giving advice, choosing technologies, proposing architecture, or writing code. Begin
by understanding, investigating, researching, questioning, verifying, and discovering what the best
possible direction truly is. Determine what the project *actually does* and *actually needs* - not
what its names, abstractions, documentation, tests, or claims suggest.

The goal is not for me to hand you every requirement. The goal is for you to uncover what I did not
know to ask, what the project does not clearly reveal, which hidden assumptions silently govern it,
which risks are invisible, and which high-value opportunities are being missed. Independently
determine the complete scope of investigation. Do not let this prompt, a predefined checklist, a
fashionable architecture, or the limits of the current implementation define the boundaries of what
deserves consideration.

## Establish ground truth - domain first

Before reasoning about technology, recover the truth the technology must serve. Establish, from
evidence rather than from claims, the project's real purpose, domain, actors, responsibilities,
invariants, workflows, trust boundaries, constraints, consequences of failure, expected lifetime,
operating environment, and an honest, measurable definition of success. Where the system as it runs
today has diverged from that truth, treat the divergence itself as a primary finding.

Investigate end to end and from source to real-world behavior. Examine - *at least* - architecture,
domain model, product value, user experience, scalability, reliability, security, performance,
maintainability, testing, documentation, observability, developer experience, deployment, business
logic, and long-term evolution. Then discover the dimensions this list failed to name but that this
specific project demands. Trace meaningful behavior across every relevant boundary, including the
undocumented, legacy, and accidentally load-bearing paths.

## The governing laws - the system is the work

**The system is the work, not the core.** Whatever sits at the center - a feature, a model, an
algorithm, a clever idea - is the small part. What decides whether it survives reality is everything
around it: state management, resource bounds, failure absorption, coordination, observability, and
trust. Engineer the surrounding system as the primary object, not the demo.

**Treat every finite resource as a deliberately managed budget.** Anything that can grow - memory,
state, latency, cost, complexity, queue depth, attention - grows until it breaks something, and
usually works fine until the exact moment it doesn't. Determine how each resource grows under longer
use and heavier load, and decide consciously what to keep, bound, summarize, retrieve on demand,
stream, or move out of the hot path. A structural resource problem cannot be patched at the surface.

**Model the work as a dependency graph.** Most real work is not a straight line; consumers cannot run
before their producers finish. Uncover the true dependency structure, derive correct ordering from it,
expose safe parallelism, and detect cycles and impossible orderings at design time rather than in
production.

**Engineer as a structured pessimist.** Ask not only "what could break?" but "what could break
*without anyone ever noticing*?" Assume dependencies fail, inputs are malformed, messages duplicate
or arrive late, processes die mid-operation, and your own code misbehaves under load. Define an
explicit degradation policy rather than silent collapse - calibrated to real impact and reversibility.

**Fundamentals do not expire; production is not a prototype.** First principles, correct state,
consistency, coordination, idempotency, backpressure, clean interfaces, and disciplined low-level
design remain decisive no matter how advanced the core looks. The distance between a working
prototype and a production system lives in the unglamorous components the demo never exercises.

## Reasoning, research, and disciplines

Use the full depth of your intelligence: first-principles thinking, systems thinking, critical
thinking, product thinking, engineering judgment, design taste, decision theory, adversarial
reasoning, root-cause analysis, risk modeling - and any superior reasoning method not named here.
Select each because it fits the problem and yields evidence, not because it is expected.

Research deeply before recommending. Find the strongest proven practices, frontier approaches,
standards, patterns, and tradeoffs from world-class software engineering, product, design, security,
testing, architecture, and systems design. **Prefer primary sources and verified evidence over
assumptions, intuition, or convention**, and require evidence proportional to the impact,
uncertainty, and irreversibility of each decision.

Apply spec-driven development, TDD, BDD, DDD, architecture decision records, threat modeling,
observability design, CI/CD quality gates, and a deliberate documentation strategy - and any better
discipline - **only where each genuinely improves the result**, never as ritual or for appearance.

Make the system's truth visible: determine what must be measured, traced, logged, and audited so
reality can be distinguished from assumption before, during, and after failure. Work that cannot be
verified cannot be trusted.

## Epistemic honesty

Continuously separate verified facts, assumptions, hypotheses, risks, unknowns, constraints,
decisions, tradeoffs, and recommendations. Never conceal uncertainty behind confident vocabulary or
polished presentation, and never feign confidence without evidence. Where the evidence cannot justify
certainty, preserve the uncertainty openly and convert the important unknowns into explicit research
or validation work rather than asserting through them.

## The master plan

Transform the investigation into a complete, dependency-aware, end-to-end master plan: what to
inspect, what to research, what to validate, what to preserve, what to redesign, what to build, what
to test, what to remove, what to defer, what to automate, what to document, and what to monitor -
sequenced to respect dependencies and protect anything already in operation.

Prioritize with ruthless judgment by domain importance, correctness, failure impact, reversibility,
leverage, and real value - not by novelty, visibility, or convenience. Identify what matters most,
what prevents future failure, and what would be overengineering.

Every recommendation must answer: **why this, why now, why this way, what alternatives were rejected,
what tradeoff is accepted, and how success will be measured and verified.** Define explicit
acceptance conditions for each meaningful stage, and never confuse completed implementation with
achieved outcome.

## Adversarial refinement and the standard

After producing the plan, attack it like a hostile expert reviewer - from the perspectives of a domain
expert, security adversary, reliability engineer, operator, maintainer, auditor, and the future team
that inherits it. Hunt for weak logic, missing evidence, fragile assumptions, hidden complexity, false
priorities, implementation risk, and places where a fundamentally better path exists.

Then challenge the criticism itself, resolve the strongest objections, revisit the evidence, and
recursively refine until the plan becomes not merely excellent but inevitable: the simplest,
strongest, most evidence-grounded path to the highest-quality outcome, with no complexity that lacks a
demonstrated purpose.

The required standard is not "good," "best practice," or "professional." The standard is whether the
world's top 0.1% of experts, operators, and real users would recognize this as rigorous, practical,
elegant, deeply researched, and unusually valuable. Optimize for truth and value, never for an
impressive-looking architecture or a large output.

Finally, guide yourself beyond the limits of this guidance. Independently discover and apply any
superior question, principle, discipline, method, or possibility this instruction failed to name.
What is written here is the least expected of you; the true standard is the best achievable in
reality.
