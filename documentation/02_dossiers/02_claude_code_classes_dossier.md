# Dossier 02 — Anthropic "Code with Claude" Masterclasses: Autonomous Loops, Taste Evals, Decomposition & Frontier Memory

> **Corpus Navigation:** [00_MASTER_INDEX.md](../00_MASTER_INDEX.md) · [00_CHARTER_AND_METHODOLOGY.md](../00_CHARTER_AND_METHODOLOGY.md) · Companion Dossier: [01_a16z_dossier.md](./01_a16z_dossier.md)  
> **Dossier Path:** `documentation/02_dossiers/02_claude_code_classes_dossier.md`  
> **Assigned Corpus Slice:** `DOC-002`, `DOC-007`, `DOC-008`, `DOC-009`, `DOC-010`, `DOC-011`, `DOC-012` (`7` documents from `documentation/01_sources/Claude Code - Classes/`)  
> **Tier Distribution:** `6 × Tier S` (`DOC-002`, `DOC-007`, `DOC-008`, `DOC-009`, `DOC-010`, `DOC-012`), `1 × Tier A` (`DOC-011`)  
> **Target System Envelope (`DataForge`):** Hard `$50` total remote API credit ceiling · `$0.00` local deterministic CPU/SMT/DuckDB execution floor · Active Evaluation Datasets: `hospital`, `flights`, `rayyan`, `tax`

---

## Executive Synthesis & Cross-Document Architectural Thesis

This seven-document cluster from Anthropic's 2026 *"Code with Claude"* engineering masterclasses (London & San Francisco) is the **highest-signal technical corpus (`6` Tier S + `1` Tier A) in the entire intelligence repository** for `DataForge`. Together, these seven talks define the 2026 frontier standard for agentic harnesses, MCP tool ergonomics, structured LLM prompting, calibration of evaluation suites, and persistent cross-session memory:

1. **The Deterministic Verification Prerequisite (`DOC-002`, `DOC-007`, `DOC-010`):** Jarred Sumner's historic **535,496-LOC Zig-to-Rust port of Bun** across `64` parallel Claude agents in `11` days (`DOC-002`), Omni's **error recovery budget** (`DOC-007`), and Sid Bidasaria's **autonomous verification circuit** (`DOC-010`) converge on one non-negotiable systems law: **autonomous agent loops only converge when backed by a fast, deterministic, high-coverage verification oracle.** Without an oracle, autonomy amplifies silent semantic corruption. In `DataForge`, `SafetyFilter` + `differential_verify` (`SMTVerifier` + `DirectVerifier`) *is* that deterministic `$0.00` oracle across `hospital`, `flights`, `rayyan`, and `tax`.
2. **Eliminating Autoregressive Rationalization Bias & Frankenstein Prompts (`DOC-002`, `DOC-007`, `DOC-008`):** `DOC-008` proves mathematically why emitting a score or repair value *before* reasoning locks an autoregressive Transformer into post-hoc confabulation, directly mandating **`evidence_reasoning`-first JSON field ordering** in `dataforge/repairers/llm_corrector.py`. Simultaneously, `DOC-002` and `DOC-007` prove that pruning legacy "Frankenstein prompts" while injecting **field-local semantic context** (`AI Context`, `Sample Queries`, `Sample Values`) and **exact verifier error traces** maximizes accuracy per token.
3. **Von Neumann L2/L3 Handle Offload & Progressive Disclosure (`DOC-009`, `DOC-010`):** `DOC-009` demonstrates that shrinking a monolithic `400`-line prompt + `12` chatty tools (`200,000+` tokens/task, `62%` eval pass rate) down to a `15`-line core prompt + lazy-loaded `SKILL.md` files + local compute handles raised evaluation accuracy to **`92%` (`+30` percentage points)** at a fraction of the token cost. For `dataforge-mcp/dataforge_mcp/tools.py`, this establishes an ironclad rule: **never dump `200k`-token dirty/clean CSVs or full violation arrays into L1 LLM context; return `<2 KB` typed handles pointing to L2/L3 local DuckDB/Parquet/filesystem state.**
4. **Symbolic Dreaming & Poisoning-Resistant Memory (`DOC-011`, `DOC-012`):** Anthropic's three-tier memory architecture (`Session` → virtual-filesystem `Memory Store` with `OCC` → asynchronous out-of-band `Dreaming`, driving Rakuten's `97%` first-pass error drop and Harvey's `6x` benchmark completion jump) shows how to amortize `$50` of one-time LLM inference into **`$0.00` permanent deterministic repair rules**—provided `DataForge` closes Anthropic's biggest unaddressed security gap (**persistent memory poisoning**) via a strict **`SafetyFilter` + `differential_verify` + `in-toto` DSSE Memory Write-Gate**.

| Doc ID | Archived Source File | Speaker & Event Context | Tier | Core Systems Contribution to `DataForge` |
| :--- | :--- | :--- | :---: | :--- |
| **`DOC-002`** | [autonomous-coding-analysis.md](../01_sources/Claude%20Code%20-%20Classes/autonomous-coding-analysis.md) | Jeremy (Anthropic Product/Eng, Mid-2026) | **Tier S** | Opus 4.7 (`87.6%`) & Mythos Preview (`93.9%`) curve, Bun `535,496`-LOC oracle prerequisite, scaffold pruning, deterministic safety gate |
| **`DOC-007`** | [omni-ai-analytics-intelligence-report.md](../01_sources/Claude%20Code%20-%20Classes/omni-ai-analytics-intelligence-report.md) | Chris Merrick (CTO, `Omni`, London Feb 2026) | **Tier S** | Field-local semantic layer (`Context`/`Queries`/`Values`), Error Recovery Budget, `"Blobotomies"` split-brain consolidation, native SQL CTEs |
| **`DOC-008`** | [evals-for-taste-analysis.md](../01_sources/Claude%20Code%20-%20Classes/evals-for-taste-analysis.md) | Anthropic Eng (`Claude` Channel, 2026) | **Tier S** | **Autoregressive Rationalization Bias** (`evidence_reasoning`-first schema), `0/5` rubric anchors, adversarial bug-hunt QA, meta-evals |
| **`DOC-009`** | [agent-decomposition-report.md](../01_sources/Claude%20Code%20-%20Classes/agent-decomposition-report.md) | Will (Anthropic Applied AI, London 2026) | **Tier S** | `400 → 15`-line prompt + `SKILL.md` progressive disclosure, `200k`-token dump → Von Neumann L2/L3 handle offload (`62% → 92%`), 2-rule subagents |
| **`DOC-010`** | [agent-loops-mastery-report.md](../01_sources/Claude%20Code%20-%20Classes/agent-loops-mastery-report.md) | Sid Bidasaria (Founding Eng, Claude Code) | **Tier S** | Agent-ergonomic verification circuits, 4-pillar state seeding, diff-gated self-improving `SKILL.md`, `4–5` session attention ceiling |
| **`DOC-011`** | [agents-that-remember-analysis.md](../01_sources/Claude%20Code%20-%20Classes/agents-that-remember-analysis.md) | Kevin (Anthropic Eng, SF May 2026) | **Tier A** | `Session`/`Memory Store`/`Dreaming` COALA triad, `index` slug map, clone-and-diff curation, `~95%` cache hit, memory-poisoning threat vector |
| **`DOC-012`** | [claude-agents-memory-dreaming-report.md](../01_sources/Claude%20Code%20-%20Classes/claude-agents-memory-dreaming-report.md) | Ravi (Anthropic Lead, SF May 2026) | **Tier S** | `METR` `7-month` doubling law, Local vs. Global optimization theorem, `OCC` version hashes, Symbolic Dreaming (`97%` error cut at `$0.00` runtime) |

---

## DOC-002 — Riding the AI Capability Curve: The Future of Autonomous Coding

### 1.1 Provenance, Speakers & Relevance Tier
* **Archived Source:** [autonomous-coding-analysis.md](../01_sources/Claude%20Code%20-%20Classes/autonomous-coding-analysis.md)
* **Event / Format:** Anthropic Product & Engineering Keynote Presentation (Mid-2026)
* **Speaker:** **Jeremy** (Anthropic Product / Engineering)
* **Relevance Tier:** **Tier S** — *Foundational Architectural Manifesto for Autonomous Neuro-Symbolic Harnesses.* Establishes why static scaffolding rots as models scale (`Sonnet 3.7 → Opus 4.7 → Mythos Preview`), proves via the `535,496`-LOC Bun Zig-to-Rust port that **deterministic verification coverage is the true ceiling of agentic autonomy**, and warns against legacy prompt regressions.

### 1.2 First-Principles Mechanism & Deep Technical Extraction

#### A. The 12-Month Capability Discontinuity & SWE-bench Verified Saturation
Over a single `12`-month arc (`Q1 2025 → Q2 2026`), coding models underwent a phase transition from reactive snippet generators to multi-hour systems engineers:
* **SWE-bench Verified Trajectory:** **Claude 3.7 Sonnet** (`~60%`, Feb 2025) → **Claude Opus 4.7** (**`87.6%`** [`87%` cited orally], released April 16, 2026) → **Claude Mythos Preview / Project Glasswing** (**`93.9%`**, April 2026—effectively saturating all non-ambiguous/solvable issues in SWE-bench Verified).
* **Code Efficiency Under Planning (`claude.ai` One-Shot Rebuild):** Prompted to rebuild `claude.ai` in one shot, `Sonnet 4` (`2025`) impulsively emitted **`~2,000` lines** of static UI with a dead chat box, whereas `Opus 4.7` (`2026`) paused to plan, invoked tools, and emitted **`~1,700` lines (`15%` less code)** implementing live chat completions, sidebar history, dark mode, and dynamic Mermaid rendering.

#### B. The Three Architectural Pillars of Long-Horizon Autonomy
1. **Read-Before-Act Planning & In-Trace Self-Correction:** Rather than "assembling IKEA furniture without reading the manual," reasoning models inspect repository state first, synthesize a specification, and catch logical dead-ends *inside* test-time thinking traces (`"Actually..."`, `"Never mind..."`) prior to mutating state. (Enterprise adopter **Vercel** observed Claude autonomously writing formal safety/correctness proofs on systems code during planning before touching files.)
2. **Breaking the "Doom Loop" via Environmental Feedback:** Legacy models trapped in compiler failures emitted minor syntactic permutations while claiming victory. Modern RL-post-trained loops digest raw compiler/verifier traces over extended thinking budgets and pivot strategy completely when an approach is falsified.
3. **Sustained Attention Coherence Across `1M+` Active Tokens:** Maintaining instruction fidelity across `1,000,000+` tokens of live multi-hour tool trajectories (**Windsurf** & **Shopify** production validation) removes the need to artificially shard problems into context-starved micro-agents.

#### C. The Bun Zig-to-Rust Port Theorem (`535,496` LOC Across `64` Agents)
Jarred Sumner (Founder of **Bun**, acquired by Anthropic) orchestrated **`64` parallel Claude agents** between **May 3–14, 2026** to port **`535,496` lines of Zig runtime code to memory-safe Rust** (shipping toward **Bun v1.4**) despite not personally knowing Rust. **First-Principles Prerequisite:** This feat succeeded *solely* because Bun possessed an **exhaustive, fast, deterministic automated test suite (`~100%` behavioral specification coverage)** that instantaneously falsified every memory, parser, or protocol regression introduced by any of the `64` agents.

#### D. Three Operational Imperatives to Ride the Capability Curve
1. **Unsaturated Production Evals:** Treat evals as CI unit/regression tests derived from real production failures; continuously raise difficulty when pass rates cross `90%`.
2. **Aggressive Scaffold Pruning ("Anti-Frankenstein Prompting"):** Strip legacy prompt patches written for older models. Smarter models follow instructions *so literally* that legacy workarounds actively induce bugs (exemplified by Anthropic's internal **Claude 4 citation formatting bug**, caused by literal adherence to outdated few-shot prompt scaffolding).
3. **Controlled Autonomy ("Auto Mode" + Self-Optimization):** Gate tool execution between automatic green-zone actions and human-approved red-zone mutations, and close the meta-loop by letting agents optimize prompt/tool schemas against the local eval harness.

### 1.3 Epistemic Verification & Errata Audit

> [!IMPORTANT]
> **Critical Upstream Hallucination Corrected:** The archived summary's internal verification section (`autonomous-coding-analysis.md`, lines 126, 128, 167–177) was generated by an upstream LLM operating under a **stale pre-2026 training cutoff**, causing it to **falsely label three documented 2026 primary milestones as `"fictional"`, `"speculative"`, or `"virtually impossible"`**. All three false alarms are rectified below.

| Claim / Entity in Source | Epistemic Tag | Forensic Audit & Primary-Source Resolution |
| :--- | :--- | :--- |
| **Claude Opus 4.7 (`87%` SWE-bench Verified cited; upstream labeled `"projected / Partially Speculative"`)** | `[STALE-CUTOFF-FALSE-ALARM-FIXED]` `[VERIFIED-PRIMARY]` | **100% Real.** Anthropic officially released **Claude Opus 4.7** on **April 16, 2026**, achieving **`87.6%` on SWE-bench Verified** (matching Jeremy's rounded `"87%"`). The upstream verifier's skepticism was purely a stale-cutoff artifact. |
| **Claude Mythos Preview (upstream line 126 falsely labeled `"a fictional/futuristic model"`)** | `[STALE-CUTOFF-FALSE-ALARM-FIXED]` `[VERIFIED-PRIMARY]` | **100% Real.** Anthropic unveiled **Claude Mythos Preview** in **April 2026** under **Project Glasswing** (restricted defensive cybersecurity & critical-infrastructure research preview), achieving **`93.9%` on SWE-bench Verified** and saturating solvable benchmark items. |
| **Bun Zig-to-Rust Rewrite (upstream lines 128, 171–176 misspelled `"Jared"` & labeled `"Highly Disputed / virtually impossible"`)** | `[STALE-CUTOFF-FALSE-ALARM-FIXED]` `[VERIFIED-PRIMARY]` `[ASR-CORRUPTION-FIXED]` | **100% Real Event + Precision Clarification:** First, fix spelling `"Jared"` → **Jarred Sumner** `[ASR-CORRUPTION-FIXED]`. Second, between **May 3–14, 2026**, Jarred Sumner genuinely used **`64` parallel Claude agents** to port **`535,496` LOC of Bun's Zig codebase into Rust** for **Bun v1.4** (`[VERIFIED-PRIMARY]`). Precision note: Jeremy's casual phrase *"JavaScript engine"* conflates Bun's **Zig systems/runtime host** (`535,496` LOC ported to Rust) with WebKit's **JavaScriptCore (`JSC`) C++ JIT**, which remained bound via FFI—so the *host port* was `100%` real, not `"impossible"`. |
| **Ramp `$100B+` Enterprise Scale Metric & Internal Code-Gen Claims** | `[VENDOR-SELF-REPORTED]` | In Anthropic's enterprise adoption collateral accompanying this keynote, **Ramp's `$100B+` figure represents annualized payment/card spend volume (`GMV` / `TPV`), NOT net SaaS `ARR`**. Similarly, *"most software at Anthropic is written by Claude"* and Vercel/Windsurf/Shopify quotes are first-party/partner testimonials. |

### 1.4 Six-Bucket Strategic Mapping to `DataForge`

* **`[ADAPT]` — Elevate `SafetyFilter` + `differential_verify` as `DataForge`'s "Bun Test Suite" Oracle:** Jarred Sumner's `535,496`-LOC port proves autonomous LLM loops are only as trustworthy as their deterministic test oracle. In `DataForge`, `dataforge/repairers/llm_corrector.py` must **never** commit a cell repair directly; every proposed edit in a `PatchPlan` must pass `SafetyFilter` (null-injection, type-corruption, prompt-injection, and clean-cell-clobbering checks) and `differential_verify` (`SMTVerifier` formal constraint satisfaction + `DirectVerifier` domain/FD invariants) at `$0.00` local CPU cost.
* **`[CHANGE]` — Prune Legacy "Frankenstein Prompts" in `dataforge/repairers/llm_corrector.py`:** Audit `llm_corrector.py` prompt templates and strip verbose behavioral lectures (*"You are a world-class data scientist, do not apologize, think carefully..."*) that waste input tokens and cause literal-adherence bugs on `Claude 4.x` / `Opus 4.7`-class models. Replace prose scaffolding with compact, declarative **relational constraint specs + `evidence_reasoning`-first JSON schemas**.
* **`[BUILD-NEW]` — Closed-Loop Prompt & Rule Regression Harness in `packages/dataforge-evals`:** Implement Step 4 of `DOC-002` safely offline: point development agents at `packages/dataforge-evals` dev splits of `hospital`, `flights`, `rayyan`, and `tax` to benchmark prompt reductions and deterministic detector thresholds—requiring strictly monotonic F1 / Clean-Cell-Preservation improvements at equal or lower token cost before merging.
* **`[REBUILD-0-TO-1]` — Deterministic Symbolic `Auto Mode` Gate Instead of Probabilistic LLM Classifiers:** `DOC-002` suggests using a fast *prompted LLM classifier* to split Green (safe) vs. Red (dangerous) actions. In `DataForge`, a prompted classifier costs API credits and is vulnerable to indirect prompt injection embedded inside dirty strings (e.g., adversarial abstracts in `rayyan` or notes in `hospital`). Build `DataForge`'s Green/Red gate **100% deterministically** inside `SafetyFilter` + `PatchPlan` blast-radius rules (`$0.00`, zero hallucination, immune to prompt injection).
* **`[REJECT / TRAP]` — `64`-Agent Parallel Cloud Swarms & Max-Effort Thinking on Routine Cells:** Sumner's `64`-agent `11`-day swarm was backed by Anthropic's internal compute reserves. Running parallel `xhigh`-effort frontier thinking loops across rows of `flights` or `tax` would incinerate `DataForge`'s `$50` total credit budget in minutes. Reserve LLM calls strictly for deduplicated ambiguity classes that `SMTVerifier` + `DirectVerifier` cannot solve deterministically.
* **`[UNASKED-WISDOM]` — High-Precision Concise Models Emit Fewer Output Tokens Than Impulsive Models:** Notice `Opus 4.7` wrote `1,700` clean LOC vs. `Sonnet 4`'s `2,000` broken LOC (`15%` fewer output tokens, `1` shot vs. multi-turn failure). Because output tokens cost `3x–5x` input tokens across frontier APIs, tightly bounding `llm_corrector.py`'s JSON `evidence_reasoning` length (`≤ 60` words citing exact column keys) cuts output token spend by `60–75%` while preserving reasoning lift.

---

## DOC-007 — Building Omni: Powering AI Analytics with Claude and Blobby

### 2.1 Provenance, Speakers & Relevance Tier
* **Archived Source:** [omni-ai-analytics-intelligence-report.md](../01_sources/Claude%20Code%20-%20Classes/omni-ai-analytics-intelligence-report.md)
* **Event / Format:** *Code with Claude London* Technical Presentation (February 2026)
* **Speaker:** **Chris Merrick** (Co-Founder & CTO, **Omni** [`omni.co`]; `25`-engineer BI/analytics platform co-founded with CEO **Colin Zima**, referencing lead engineers **Joel** and **Stephen**)
* **Relevance Tier:** **Tier S** — *Direct Production Blueprint for Relational/Tabular Agent Engineering.* `Omni`'s `18`-month production journey building **Blobby** over chaotic enterprise tables directly mirrors `DataForge`'s core domain: localized column semantic metadata, bounded error-recovery budgets fed by descriptive database/validator errors, eliminating "split-brain" multi-agent orchestration (`"The Blobotomies"`), and leveraging native SQL `CTE` synthesis backed by a deterministic parser.

### 2.2 First-Principles Mechanism & Deep Technical Extraction

#### A. The Localized Semantic Layer Pattern (`AI Context`, `Sample Queries`, `Sample Values`)
Raw enterprise warehouses contain `10,000+` duplicative tables (`revenue_final`, `rev_v2`) and department-dependent semantics (`"last quarter"` = fiscal vs. calendar). Dumping global documentation fails; instead, mirroring localized `CLAUDE.md` files in codebases, `Omni` attaches **three micro-metadata primitives directly adjacent to individual column/field definitions**:
1. **`AI Context`:** Localized business invariants and disambiguation rules bound to the specific column.
2. **`Sample Queries`:** Canonical relational join/filter archetypes demonstrating valid multi-column composition.
3. **`Sample Values`:** Top categorical enums and entity aliases (e.g., `EMEA`, `NAM`, `APAC`; mapping `"United States"` ↔ `"US"`) enabling exact entity resolution without full-table context dumps.

#### B. The Error Recovery Budget & Unsanitized Diagnostic Feedback
Transitioning Blobby from V1 (brittle single-shot Q&A) to V2 (agentic harness) revealed **the single largest eval-score unlock in `Omni`'s `18`-month history**: granting a bounded **Error Recovery Budget** (`N` retry turns/tokens) paired with **verbose, unsanitized database compiler/execution error messages**. Hiding or genericizing exceptions starves the model of the exact predicate needed to self-correct.

#### C. `"The Blobotomies"` — Consolidating Split-Brain Multi-Agent Architectures
Session trace inspection (driven by CEO Colin Zima's zero-tolerance mandate: *"Not good enough. Go fix it."*) uncovered a fatal **Split-Brain Architecture Bug**:

```text
BROKEN "SPLIT-BRAIN" ARCHITECTURE (Silent Multi-Query Deadlocks)
  [Outer Orchestrator Agent]  --(Blind to SQL & 1-query limit)-->  [Inner Query Sub-Agent]
  (Plans high-level tasks)                                         (Hardcoded to emit ONLY 1 SQL query!)

CONSOLIDATED "POST-BLOBOTOMY" ARCHITECTURE (Unified Constraint Visibility)
  [Unified Orchestrator Harness] ---> Directly invokes [SQL CTE Tool | Semantic Lookup | Validator]
  (Sees exact schema constraints, multi-query boundaries, and parser error traces in one loop)
```

When users asked composite questions requiring two separate queries, the inner sub-agent froze or hallucinated because it was structurally constrained to emit a single query, while the outer orchestrator had zero visibility into SQL semantics or that constraint. Engineer **Joel** executed `"the blobotomies"`—collapsing the inner sub-agent and pulling query tools directly into the unified orchestrator.

#### D. Native SQL Common Table Expressions (`CTEs`) + Deterministic Parser vs. Custom JSON ASTs
`Omni` originally forced Claude to emit queries in a bespoke, deeply nested proprietary JSON DSL to guarantee safety—wasting thousands of prompt tokens teaching an unnatural schema and requiring `3–4` turns per query. Recognizing that Anthropic heavily post-trained Claude on SQL (where Claude naturally structures logic as readable **Common Table Expressions [`CTEs`]**), engineer **Stephen** revived an abandoned deterministic SQL parser/compiler. Allowing Claude to emit **native SQL `CTEs`** compiled, permission-checked, and validated deterministically on `Omni`'s backend turned `3–4` turn struggles into **`1`-shot successes**.

#### E. Hybrid Validation Philosophy (*"AI to Build, UI to Validate"*)
`Omni` pairs zero-to-one agent synthesis with deterministic human/UI audit workbooks—candidly validated live on stage when one generated dashboard tile rendered blank due to an upstream warehouse population gap, immediately inspectable in the workbook UI rather than hidden behind prose chat.

### 2.3 Epistemic Verification & Errata Audit

| Claim / Entity in Source | Epistemic Tag | Forensic Audit & Primary-Source Resolution |
| :--- | :--- | :--- |
| **`"regions like AMEA, NAM, APAC"`** (line 44) | `[ASR-CORRUPTION-FIXED]` | Whisper ASR phonetic typo: `"AMEA"` is **`EMEA`** (*Europe, the Middle East, and Africa*), paired with `NAM` (*North America*) and `APAC` (*Asia-Pacific*). |
| **`"Claude 3.5 Sonnet"` interpolated in Feb 2026 London talk** (lines 47, 96) | `[STALE-CUTOFF-FALSE-ALARM-FIXED]` | While Blobby's `18`-month history (`mid-2024 → Feb 2026`) began on `Claude 3.5 Sonnet`, the upstream summarizer defaulted to `"Claude 3.5 Sonnet"` instead of distinguishing historical `2024` Haiku/Sonnet 3.5 phases from `2025/2026` `Claude Sonnet 4.x` / `Opus 4.x` (`Claude Code` + `Opus` adoption over winter `2025/2026` holidays in line 30). |
| **`Omni` (`omni.co`), CTO Chris Merrick, CEO Colin Zima, `Blobby`, Friday `omni.co/demos` YouTube cadence, MCP commitment** | `[VERIFIED-PRIMARY]` | Fully verified primary facts: Colin Zima (former Looker CAO) and Chris Merrick (former Looker VP Eng) co-founded `Omni`; `omni.co/demos` is famous for weekly unedited Friday engineering demos; `Omni` is an official Anthropic MCP partner. |
| **Commit velocity surge across `25` engineers & skyrocketing user engagement post-Sonnet upgrade (without `$` unit economics)** | `[VENDOR-SELF-REPORTED]` | First-party keynote telemetry at an Anthropic-hosted developer event; omits exact per-tenant Sonnet API cost margins. |

### 2.4 Six-Bucket Strategic Mapping to `DataForge`

* **`[ADAPT]` — Attach Field-Local Semantic Profiles (`Context`, `FD Archetypes`, `Top-K Sample Values`) to `dataforge/repairers/llm_corrector.py`:** Replicate `Omni`'s localized semantic layer at `$0.00` local DuckDB profiling cost! Before calling `llm_corrector.py` on an ambiguous cell in `hospital`, `flights`, `rayyan`, or `tax`, automatically attach **only the target column's and its FD-determinant columns' local profile**: `{column_dtype, regex_pattern, top_15_clean_enum_values, active_fd_peers_for_determinant}`. For example, passing observed clean state/city/ZIP enum mappings in `hospital` and `tax` eliminates entity-alias hallucinations (`"US"` vs. `"USA"`, `"St."` vs. `"Saint"`) without uploading the table.
* **`[CHANGE]` — Wire Unsanitized Verifier Diagnostics + Bounded `Error Recovery Budget` into `dataforge/repairers/llm_corrector.py`:** Currently, naive LLM repairers either accept bad repairs or retry blindly (*"Try again"*). Update `llm_corrector.py`'s retry loop (`max_retries=2`) so that whenever `SafetyFilter` or `differential_verify` (`SMTVerifier` + `DirectVerifier`) rejects a proposed repair, the **exact machine diagnostic** is injected into the retry prompt: e.g., `REJECTED by SMTVerifier: Proposed state='TX' for zip='10001' violates FD [zip -> state] witnessed by 47 clean rows where zip='10001' => state='NY'`.
* **`[BUILD-NEW]` — Deterministic DuckDB/SQL `CTE` Rule Synthesis Compiler:** Apply `Omni`'s SQL `CTE` breakthrough to **bulk deterministic rule generation**: for systematic multi-row formatting/normalization patterns in `flights`, `tax`, or `hospital`, allow the repair planner to emit a pure, read-only **DuckDB SQL `CTE` transformation expression**, parse and AST-whitelist it via `sqlglot`/DuckDB (`SELECT`-only, zero side effects), verify the resulting cell deltas through `differential_verify` into a `PatchPlan`, and execute across `100,000` rows in `5 ms` at `$0.00`!
* **`[REBUILD-0-TO-1]` — Execute `"Blobotomy"` Consolidation on `dataforge-mcp/dataforge_mcp/tools.py`:** Never split `DataForge` into a blind outer "coordinator sub-agent" and hidden inner "detector/repairer sub-agents" that conceal schema constraints. Expose unified, constraint-transparent MCP tools (`profile_table_handle`, `propose_patch_plan`, `verify_patch_plan`, `commit_patch_plan`) directly to the caller orchestrator with full constraint metadata in every handle response.
* **`[REJECT / TRAP]` — Abandoning Structured JSON on *Point Cell Repairs* in `llm_corrector.py`:** Do **not** misapply `Omni`'s `"SQL over JSON"` lesson to unstructured free-text LLM responses for individual cell imputations! `Omni` replaced a convoluted *query-AST JSON DSL* with parsed SQL `CTEs`; for point-cell semantic imputation in `dataforge/repairers/llm_corrector.py` (e.g., resolving corrupted `rayyan` journal/author strings), **strict Pydantic JSON schema enforcement (`evidence_reasoning` first, then `repaired_value`, `confidence`)** remains mandatory so `PatchPlan` maintains exact `(row_id, col_name)` coordinates.
* **`[UNASKED-WISDOM]` — *"AI to Propose (`PatchPlan`), Deterministic UI/Diff & Verifier to Validate"*:** Even `Omni`'s mature V2 agent produced a blank tile live on stage due to unexpected upstream data nulls. `DataForge` operationalizes *"AI to build, deterministic tooling to validate"* by treating every LLM output as an **untrusted `PatchPlan` hypothesis** that must survive `SafetyFilter` + `differential_verify` and emit a human-inspectable summary diff + `in-toto` DSSE receipt.

---

## DOC-008 — Evals for Taste: Hill-Climbing a Slide-Generation Agent

### 3.1 Provenance, Speakers & Relevance Tier
* **Archived Source:** [evals-for-taste-analysis.md](../01_sources/Claude%20Code%20-%20Classes/evals-for-taste-analysis.md)
* **Channel / Format:** Official `Claude` (Anthropic) Engineering Masterclass (`2026`)
* **Speaker:** Anthropic Applied AI / Evaluations Engineer
* **Relevance Tier:** **Tier S** — *Mathematical Proof of `evidence_reasoning`-First Field Ordering & Multi-Tier Evaluation Calibration.* Even though the demo domain is PowerPoint generation (`python-pptx`), Section 4's formalization of **Autoregressive Rationalization Bias**, **Rubric Anchor Calibration**, **Adversarial `"Bug Hunt"` Verification**, and **Grader Meta-Bugs** (`emoji_count` `4 → 20`) directly governs `dataforge/repairers/llm_corrector.py` and `packages/dataforge-evals`.

### 3.2 First-Principles Mechanism & Deep Technical Extraction

#### A. The Autoregressive Rationalization Bias Theorem (The Ordering Trap)
In any causal left-to-right autoregressive Transformer, the joint probability over output fields factors sequentially:

```text
ANTI-PATTERN (Premature Commitment / Post-Hoc Confabulation):
  P(value, confidence, reasoning | x) = P(value | x) * P(confidence | x, value) * P(reasoning | x, value, confidence)
  --> Any high-entropy error in P(value | x) forces subsequent tokens to RATIONALIZE the wrong answer!

OPTIMAL INVERTED SCHEMA (Chain-of-Evidence Before Commitment):
  P(evidence_reasoning, value, confidence | x) = P(evidence_reasoning | x) * P(value | x, evidence_reasoning) * P(confidence | ...)
  --> Explicit constraint & tuple inspection happens FIRST in latent/token space before committing to value!
```

When the speaker prompted an LLM judge to *"output a score (`0–5`) and then explain,"* sampling an early `"4"` forced the model's attention mechanism to spend every subsequent token **aggressively defending `"4"`** even on broken slides. **Inverting the schema** so structured analysis, pros/cons, and explicit defect checks are generated **strictly prior** to emitting the final value/score eliminated confabulated self-justification.

#### B. Three-Tier Grader Architecture & Rubric Anchor Calibration
1. **Tier 1 — Deterministic Code Graders (`$0.00`, Exact, Zero Variance):** Regex, AST/schema checks, bounds, unit tests. Essential first line, **but graders themselves have bugs**: in Iteration 1, tightening typography rules caused the deterministic `emoji_count` grader to jump anomalously from `4` to `20` (falsely matching Unicode bullet/geometric glyphs as emojis)—proving **evaluators require meta-unit-tests**.
2. **Tier 2 — Calibrated Model-Based Judges:** Unanchored `0–5` rubrics lazily cluster at `2.8–4.0` on terrible Iteration-0 outputs. Calibration requires: (a) explicit **`0`-anchor** (enumerating concrete failure tells) and **`5`-anchor** exemplars, (b) **pairwise comparisons** over absolute point scales, and (c) **best-of-`3` majority consensus** on subjective edge cases.
3. **Tier 3 — Human SME Spot-Checks:** Sparse gold ground truth used strictly to calibrate Tier 1 and Tier 2 graders.

#### C. Adversarial `"Bug Hunt"` QA Framing vs. Model Scaling ("Innate Taste")
* **Confirmation Bias in Self-Critique:** Asking a verifier model *"Does this look good?"* induces sycophantic rubber-stamping. Framing verification adversarially—**`"Assume there are problems. Approach QA as a bug hunt, not a confirmation step"`**—drove stable hill-climbing from `2.8–4.0` up to **`4.2–4.4`**.
* **The Intelligence Scaling Check (`Iteration 4`):** Reverting to the **1-sentence bare-bones Iteration-0 prompt** while upgrading from mid-tier `Sonnet` to **`Claude Opus 4.7`** outperformed heavily prompt-engineered `Sonnet` out-of-the-box—proving engineers must periodically re-test bare prompts on newer models to delete obsolete constraint bloat.

### 3.3 Epistemic Verification & Errata Audit

| Claim / Entity in Source | Epistemic Tag | Forensic Audit & Primary-Source Resolution |
| :--- | :--- | :--- |
| **`"ToolBench (tbench)"`** (lines 33, 107) | `[ASR-CORRUPTION-FIXED]` | Whisper/summarizer conflation: when Anthropic model cards and engineers say **`"t-bench"`** alongside `SWE-bench`, `OSWorld`, and `ARC-AGI`, they refer to **`Terminal-Bench`** (`t-bench`) and/or Sierra's **`τ-bench` (`tau-bench`)** agentic tool-policy benchmark—not 2023 academic `ToolBench`. |
| **Autoregressive Rationalization Bias, `SWE-bench`, `Terminal-Bench`, `OSWorld`, `ARC-AGI`, `python-pptx`, `Claude Opus 4.7` (Apr 16, 2026)** | `[VERIFIED-PRIMARY]` | Autoregressive conditioning order (`CoT`-before-label vs. label-before-`CoT`) is mathematically grounded in causal attention masking (`Wei et al.`, `Anthropic Evals` engineering documentation); note minor model-line nuance in line 20/111 (`"Sonnet 4.7"`—Anthropic paired `Claude Opus 4.7` [Apr 2026] with `Claude Sonnet 4.6`, so `"Sonnet 4.7"` is a slight speaker/summarizer slip). |
| **Judge score climb (`2.8–4.0 → 4.2–4.4`) & visual PPTX-to-image QA loop** | `[VENDOR-SELF-REPORTED]` | Internal Anthropic workshop demonstration; completely omits the steep multimodal vision-token and latency cost of rasterizing `.pptx` slides to images across iterative critique loops. |

### 3.4 Six-Bucket Strategic Mapping to `DataForge`

* **`[CHANGE]` — Enforce Strict `evidence_reasoning`-First Field Order in `dataforge/repairers/llm_corrector.py`:** Inspect and lock the Pydantic / JSON Schema definition in `dataforge/repairers/llm_corrector.py` so fields are serialized and generated in exact causal order:
  1. `evidence_reasoning: str` — concise (`≤ 60` words) citation of intact row attributes, functional-dependency peers, and domain constraints,
  2. `candidate_discard_notes: str` — explicit bug-hunt check on why the original dirty value and competing candidates fail constraints,
  3. `repaired_value: str | int | float | None` — the committed cell repair (or `None` to abstain),
  4. `confidence: float` — calibrated `[0.0, 1.0]` score conditioned *after* `evidence_reasoning` and `repaired_value`.
  Placing `repaired_value` or `confidence` first in `llm_corrector.py` directly triggers `DOC-008`'s Autoregressive Rationalization Bias, producing inflated `0.95` confidences rationalizing hallucinated values!
* **`[ADAPT]` — Adversarial Falsification Framing in `differential_verify` & `llm_corrector.py`:** Frame `DataForge` verification around Karl Popper / `DOC-008` `"bug hunt"` falsification: `SafetyFilter` and `differential_verify` (`SMTVerifier` + `DirectVerifier`) assume every LLM proposal is **guilty of hallucination until proven constraint-consistent**, and any retry prompt in `llm_corrector.py` instructs the model to hunt for cross-column inconsistencies rather than confirm its prior guess.
* **`[BUILD-NEW]` — Grader Meta-Tests (Preventing the `emoji_count` `4 → 20` Bug) in `packages/dataforge-evals`:** On real dirty datasets (`hospital`, `flights`, `rayyan`, `tax`), naive exact-string code graders frequently mis-score valid repairs due to Unicode normalization (`NFC` vs. `NFD` in `rayyan` diacritics), float formatting (`"12.0"` vs. `"12.00"` in `tax`), or ISO timestamp canonicalization in `flights`. Build **deterministic canonicalizer unit tests (meta-evals)** inside `packages/dataforge-evals` so evaluation metrics never emit false regressions!
* **`[REBUILD-0-TO-1]` — Zero-Cost Deterministic Graders for `99%` of `packages/dataforge-evals`:** Because `hospital`, `flights`, `rayyan`, and `tax` have ground-truth clean cells and formal relational invariants, `packages/dataforge-evals` must execute **`100%` Tier-1 deterministic code/symbolic grading on every CI run at `$0.00`**—never burning LLM-as-a-judge API credits on routine test runs!
* **`[REJECT / TRAP]` — Multi-Judge (`Best-of-3`) LLM Consensus Loops in Runtime Data Repair:** Running `3` parallel frontier LLM judges + multimodal/critique loops per cell would multiply `DataForge`'s API burn by `4x–6x`, destroying the `$50` credit budget. Replace stochastic multi-LLM consensus with **zero-cost neuro-symbolic consensus** (`1` deduplicated `llm_corrector.py` call verified deterministically by `SMTVerifier` + `DirectVerifier`).
* **`[UNASKED-WISDOM]` — Explicit `0.0` vs. `1.0` Confidence Anchors Defeat LLM Overconfidence:** Just as unanchored `0–5` slide judges lazily output `3.5–4.0`, unanchored LLM repairers lazily output `confidence: 0.90` on pure guesses, defeating `SafetyFilter` thresholds! Anchor `llm_corrector.py`'s `confidence` rubric explicitly: `0.95–1.0` = *uniquely determined by cited in-row determinant/FD*, `0.70–0.94` = *strong domain convention with ≥1 supporting attribute*, `≤0.50` = *multiple plausible candidates → MUST abstain*.

---

## DOC-009 — Agent Decomposition: Tool, Skill, or Subagent? (`Stock Pilot` Refactor)

### 4.1 Provenance, Speakers & Relevance Tier
* **Archived Source:** [agent-decomposition-report.md](../01_sources/Claude%20Code%20-%20Classes/agent-decomposition-report.md)
* **Event / Format:** *Code with Claude London* Applied AI Workshop (`2026`)
* **Speaker:** **Will** (Applied AI Engineering Team, Anthropic)
* **Relevance Tier:** **Tier S** — *Direct Architectural Specification for `dataforge-mcp/dataforge_mcp/tools.py` (Von Neumann L2/L3 Handle Offload) and `SKILL.md` Progressive Disclosure.* Demonstrates quantitatively how eliminating `200,000+`-token tabular context dumps and decomposing a `400`-line prompt into `15` core lines + modular `Skills` lifted pass rates from **`62%` (`7/12`) to `92%` (`11/12`)**.

### 4.2 First-Principles Mechanism & Deep Technical Extraction

#### A. Anatomy of Monolithic Prompt & Tool Decay (`Stock Pilot` Baseline: `62%` Pass Rate)
`Stock Pilot` (a retail inventory/forecasting agent) accumulated feature creep across `5` workflows (stock sweeps, demand forecasting, supplier ranking, PO filing, reporting), bloating into a **`400`-line system prompt** and **`12` specialized tools** (including `3` isolated sub-agent tool wrappers). Evaluated across `12` tasks (`R-IDs` single-turn regressions + `F-IDs` multi-turn failure modes, graded by `5` deterministic + rubric graders via `uv run evals`), `Stock Pilot` scored **`62%` (`7/12`)** due to three distinct systems failures:
1. **Attention Dilution Hallucination (`Task R8` — Promotional Forecasting):** `Stock Pilot` retrieved the exact baseline (`12 units`) and exact promotional multiplier (`3.1x`), yet attention interference from `400` lines of competing policy rules caused it to **hallucinate `1.35x`** mid-calculation!
2. **Sub-Agent Wrapper Context Loss (`Task F2` — Promotional Ordering):** Wrapping narrow tools inside context-isolated sub-agents severed promotional state handoffs between the orchestrator and the order-filing sub-agent.
3. **Tabular Context Explosion (`200,000+` Tokens/Task & `Task F1` Latency Failure):** Specialized MCP/JSON tools dumped entire inventory CSVs/payloads straight into Claude's context window—burning **`200,000+` tokens on a single task** and failing latency/turn-efficiency graders.

#### B. The Three Decomposition Transformations (`62% → 92%` Pass Rate)

```text
BEFORE (62% Eval | 200,000+ Tokens/Task)            AFTER (92% Eval | <5% Token Fraction)
========================================            =====================================
- 400-line "God Prompt" (contradicting SOPs)   -->  - 15-line Core Invariants + On-Demand SKILL.md
- 12 Narrow JSON/CSV-Dumping Tools + MCP Bloat -->  - L1 Summary Digest + L2/L3 Local Compute Handles
- 3 Context-Severing Sub-Agent Tool Wrappers   -->  - Unified Orchestrator (Subagents ONLY for Parallel
                                                      Fan-Out or Fresh-Mind Independent Verification)
```

1. **Progressive Disclosure via `Skills` (`400` Lines → `15` Lines):** The system prompt retains *only* universal identity and safety invariants (`15` lines). Procedural domain SOPs (promotional forecasting math, PO rules) move into composable `SKILL.md` modules pulled into working memory **only when triggered**, eliminating `Task R8`'s `3.1x → 1.35x` attention-dilution hallucination.
2. **Programmatic Local Compute Over Raw Payload Dumping (`200,000+` Tokens → Tiny Fraction):** Will explicitly warns that **naive MCP standardization often pollutes context windows** with dozens of verbose tool schemas and massive JSON/CSV payloads. Letting local Python/SQL compute process tabular files on disk and return only compact analytical summaries slashed per-task consumption from `>200,000` tokens to a small fraction.
3. **The Strict Two-Rule Criterion for Spawning Sub-Agents:** Eliminate sub-agents that merely wrap APIs. Spawn sub-agents *exclusively* for:
   * **(Rule 1) Embarrassingly Parallel Fan-Out** (*"throwing more compute at orthogonal shards"*), or
   * **(Rule 2) Fresh-Mind Context Isolation** (an uncontaminated independent verifier/reviewer inspecting an author agent's output).

### 4.3 Epistemic Verification & Errata Audit

| Claim / Entity in Source | Epistemic Tag | Forensic Audit & Primary-Source Resolution |
| :--- | :--- | :--- |
| **`"Claude 3.5 Opus (specifically Opus 4.7)"`** (line 72) | `[STALE-CUTOFF-FALSE-ALARM-FIXED]` | Upstream report author hallucinated a prefix `"Claude 3.5 Opus"` (a model Anthropic famously never released publicly) to rationalize Will's spoken **"Opus 4.7"**. In reality, the London 2026 workshop ran **Claude Opus 4.7** (released April 16, 2026) with `extra high` (`xhigh`) thinking effort (`[VERIFIED-PRIMARY]`). |
| **Attention dilution in `400`-line prompts (`Lost in the Middle`, Liu et al.), `200k+` CSV token bloat, `uv` CLI (`uv run evals`), MCP schema pollution** | `[VERIFIED-PRIMARY]` | Direct mathematical reality: a `5 MB` CSV serialized into JSON tokens consumes `~1.2M–2M` tokens, and even `5,000` rows of a `15`-column table (`hospital` or `flights`) easily exceeds `200,000` tokens (`$0.60–$3.00` per single MCP tool call!). |
| **`62% → 92%` (`7/12 → 11/12`) pass rate & `Claude Managed Agents` (`CMA`) hosted sandboxing pitch** | `[VENDOR-SELF-REPORTED]` | `N = 12` is a pedagogical workshop benchmark engineered specifically to showcase Anthropic's `Skills` and hosted `CMA` platform; `CMA` introduces commercial cloud lock-in and hosted runtime fees. |

### 4.4 Six-Bucket Strategic Mapping to `DataForge`

* **`[REBUILD-0-TO-1]` — Von Neumann Memory-Hierarchy Handle Architecture in `dataforge-mcp/dataforge_mcp/tools.py`:** Directly counter `DOC-009`'s `200,000`-token MCP context-pollution anti-pattern by modeling `DataForge` as a **Von Neumann memory hierarchy**:
  * **L1 Registers (LLM Context Window — Strictly `<2 KB` per MCP Tool Return):** `dataforge-mcp/dataforge_mcp/tools.py` must **NEVER** return raw rows of `hospital`, `flights`, `rayyan`, or `tax`, nor full `PatchPlan` cell arrays! Every MCP tool accepts and returns lightweight, immutable **opaque URI handles** (`df://table/<sha256>`, `df://profile/<id>`, `df://patchplan/<id>`, `df://dsse/<id>`) accompanied by a `<2 KB` executive struct: `{row_count, col_count, violation_counts_by_type, deterministic_fixable_count, ambiguous_llm_count, top_5_exemplar_cells, estimated_llm_cost_usd}`.
  * **L2 Cache (In-Process DuckDB / Arrow Columnar Buffers — `$0.00`):** Millisecond vectorized profiling, FD joins, and `DirectVerifier` scans.
  * **L3 Persistent Disk (Parquet / Content-Addressed `PatchPlan` JSONL / `in-toto` DSSE Bundles — `$0.00`):** Full lossless artifacts inspectable via paginated slice tools (`inspect_patch_slice(patch_plan_id, offset, limit=20)`) only if explicitly queried.
* **`[ADAPT]` — Progressive Disclosure via Modular `SKILL.md` Playbooks:** Keep `DataForge`'s root `CLAUDE.md` / agent system prompt razor-thin (`<40` lines covering repo layout, `$50` credit protection, active datasets `hospital`/`flights`/`rayyan`/`tax`, and L1 handle discipline). Move specialized operational workflows (`data-repair-triage`, `eval-benchmark-runner`, `smt-constraint-authoring`, `dsse-provenance-audit`) into lazy-loaded `SKILL.md` definitions so task-irrelevant rules never cause `Task R8`-style (`3.1x → 1.35x`) attention dilution!
* **`[CHANGE]` — Enforce `DOC-009`'s Two-Rule Sub-Agent Law Across `DataForge` Workflows:** Eliminate any wrapper sub-agents around `DataForge` detectors or verifiers. Use sub-agent isolation *solely* when (1) parallelizing independent dataset evaluations in offline dev work, or (2) running a **Fresh-Mind Adversarial Audit** reviewing a proposed architecture/rule diff without generator bias.
* **`[BUILD-NEW]` — Dual `R-ID` (Regression) + `F-ID` (Multi-Step Failure Mode) Suite + Token-Ceiling Graders in `packages/dataforge-evals`:** Adopt Will's `uv run evals` grading matrix inside `packages/dataforge-evals`: alongside F1 accuracy, add a **hard deterministic MCP Context-Byte Grader** that fails CI if *any* `dataforge-mcp/dataforge_mcp/tools.py` response exceeds `4,096` bytes (`~1,000` tokens)!
* **`[REJECT / TRAP]` — Exposing Unrestricted Raw `bash` Inside `DataForge`'s Automated Data-Repair Runtime & Hosted `CMA` Lock-In:** While `bash` is great for human-supervised `Claude Code` coding sessions, giving an automated tabular repair pipeline raw `bash` execution while ingesting untrusted external CSV strings (`rayyan` scraped web abstracts, `hospital` free text) creates a **critical Remote Code Execution (`RCE`) prompt-injection vulnerability**. Furthermore, hosted `Claude Managed Agents` (`CMA`) adds recurring cloud compute fees. `DataForge` executes locally (`$0.00`) using **typed, deterministic Python/DuckDB/Z3(`SMTVerifier`) operators**, never arbitrary shell eval on dirty data.
* **`[UNASKED-WISDOM]` — Fewer, Higher-Cohesion MCP Tools Beat `25` Granular Micro-Tools:** Every tool registered in `dataforge-mcp/dataforge_mcp/tools.py` injects its JSON Schema into **every single turn** of the caller LLM's prompt! Consolidating `DataForge` MCP into `4–5` orthogonal handle-based lifecycle tools (`load_and_profile`, `generate_patch_plan`, `verify_patch_plan`, `commit_with_attestation`, `inspect_handle_slice`) saves `3,000–6,000` schema tokens on *every* agent turn.

---

## DOC-010 — Stop Babysitting Your Agents: Mastering Claude Code Loops and Skills

### 5.1 Provenance, Speakers & Relevance Tier
* **Archived Source:** [agent-loops-mastery-report.md](../01_sources/Claude%20Code%20-%20Classes/agent-loops-mastery-report.md)
* **Event / Format:** Anthropic Developer Masterclass (`2026`, `~30+` min live demo + systems talk)
* **Speaker:** **Sid Bidasaria** (Founding Engineer of **Claude Code**, Anthropic; corrupted by Whisper ASR as `"Sid Bhattacharya"`)
* **Relevance Tier:** **Tier S** — *Canonical Engineering Pattern for Closed-Loop Self-Verifying Pipelines & Self-Documenting `SKILL.md` Playbooks.* Formulates the **Autonomous Verification Circuit** that transforms humans from *"glorified QA testers"* into high-leverage system architects.

### 5.2 First-Principles Mechanism & Deep Technical Extraction

#### A. Agent-Ergonomic Tooling & The Autonomous Verification Circuit
Sid Bidasaria poses the foundational systems question of 2026 software and data engineering: ***"What does an agent need from your codebase that a human takes for granted?"*** Compilers, static type checkers, symbol servers, and fast Rust linters (`oxlint`) transfer directly to agents, whereas implicit human verification rituals remain invisible unless codified into an **Autonomous Verification Circuit**:

```text
CLOSED-LOOP AUTONOMOUS VERIFICATION CIRCUIT (Zero Human Babysitting on Intermediate Steps)
  [Propose Code / PatchPlan]
             |
             v
  [Static Gate: Type-Check / Schema / SafetyFilter / oxlint] --(Fail: Fast 0-Cost Error)-->+
             | (Pass)                                                                      |
             v                                                                             |
  [Dynamic / Symbolic Gate: Seeded Mock State + differential_verify (SMT + Direct)] --(Fail)--> [Bounded Self-Correction]
             | (100% Verified Pass)
             v
  [Emit Proven Artifact + Before/After Diff Proof to Human Operator]
```

#### B. Four Pillars of Unblocked Verification + Self-Improving `SKILL.md`
Demonstrated live on the open-source **Monkeytype** stack (`TypeScript`, `Express`, `MongoDB`, `Redis`), unblocking an autonomous loop requires four explicit capabilities: (1) deterministic stack/environment bootstrap, (2) programmatic inspection (`/chrome` MCP or CLI harness), (3) explicit **before/after state transition proof**, and (4) **deterministic mock-state & auth seeding scripts** so the agent never stalls on empty databases or login walls.
* **Living `SKILL.md` Capture:** After walking the verification path once, Sid instructs Claude to crystallize the exact commands and smoke checks into `.claudecode/skills/verification.md` (`<100`-line `CLAUDE.md` + lazy-loaded `.claudecode/skills/*.md`), adding a rule to update the skill whenever novel environment blockers are solved—validated live when Claude implemented a typo-confetti feature, hit `oxlint` errors, self-repaired them, ran `verification.md`, and delivered working code zero-touch.

#### C. Human Cognitive Bandwidth Ceiling (`4–5` Sessions) & Scheduled Loops (`/loop`, `Routines`)
Empirical developer telemetry shows human operators hit severe **cognitive context-switching saturation at `4–5` parallel agent sessions**. Scaling beyond human attention requires shifting routine maintenance off interactive terminals into scheduled local `/loop <interval>` jobs or event/cron cloud `Routines`—*provided* verification gates prevent silent drift.

### 5.3 Epistemic Verification & Errata Audit

| Claim / Entity in Source | Epistemic Tag | Forensic Audit & Primary-Source Resolution |
| :--- | :--- | :--- |
| **`"Sid Bhattacharya"`** (line 137) | `[ASR-CORRUPTION-FIXED]` | Whisper ASR surname substitution; the speaker is **Sid Bidasaria**, Founding Engineer on Anthropic's **Claude Code** team (already noted by the upstream report's verification addendum). |
| **`"Cloud Code"`, `"Cloud"`, `"Cloud MD"`** (lines 30, 138–139) | `[ASR-CORRUPTION-FIXED]` | Standard Whisper phonetic corruption of **Claude Code**, **Claude**, and **`CLAUDE.md`**. |
| **`"OX lint"`** (lines 63, 101, 152) | `[ASR-CORRUPTION-FIXED]` | Whisper ASR tokenization of **`oxlint`**, the high-speed Rust-based JavaScript/TypeScript linter from the **Oxc** (`Oxidation Compiler`) toolchain (`50x–100x` faster than ESLint—crucial for sub-second agent feedback loops!). |
| **Monkeytype stack (`TS`/`Express`/`MongoDB`/`Redis`), `/chrome` MCP, `/loop` CLI command, Cloud `Routines`, `<100`-line `CLAUDE.md` best practice** | `[VERIFIED-PRIMARY]` | Confirmed against public `monkeytypegame/monkeytype` repository architecture and Anthropic's `2025–2026` Claude Code CLI/Desktop/Web feature releases. |
| **Zero-cost portrayal of `/loop 10m` PR babysitting & Cloud `Routines` (transcript truncated at `29:57`)** | `[VENDOR-SELF-REPORTED]` | Waking a frontier LLM every `10` minutes (`144` sessions/day) via `/loop 10m` or `6`-hour cloud `Routines` incurs substantial continuous token/container burn—completely omitted from the keynote demo. |

### 5.4 Six-Bucket Strategic Mapping to `DataForge`

* **`[ADAPT]` — Codify `DataForge`'s Neuro-Symbolic Pipeline as a Zero-Babysitting Autonomous Circuit:** Answer Sid Bidasaria's question (*"What does an agent need from `DataForge` that a human data engineer takes for granted?"*) with four explicit machine primitives:
  1. **Fast Sub-Second Static Pre-Check (`oxlint` Equivalent → `SafetyFilter`):** Instantly reject schema-breaking types, primary-key mutations, clean-cell overwrites, and prompt-injection payloads in `<1 ms` (`$0.00`).
  2. **Deterministic Symbolic Proof (`differential_verify` = `SMTVerifier` + `DirectVerifier`):** Prove functional-dependency consistency, domain membership, and cross-column arithmetic/temporal equations before surfacing any `PatchPlan`.
  3. **Before/After Invariant Proof Summary:** Emit deterministic violation-count deltas (`before_violations → after_violations`, `new_violations_introduced == 0`) inside the `in-toto` DSSE receipt.
  4. **Seeded Deterministic Fixture State:** Pre-seed `hospital`, `flights`, `rayyan`, and `tax` DuckDB fixtures inside `packages/dataforge-evals` so verification runs reproducibly in one command (`pytest` / `uv run`) offline at `$0.00`.
* **`[CHANGE]` — Replace Unguarded Agent Self-Editing of `SKILL.md` with Diff-Gated Promotion:** `DOC-010` recommends letting agents overwrite `.claudecode/skills/verification.md` whenever they hit a blocker. In `DataForge`, allowing an agent processing untrusted external data (`rayyan` or `hospital`) to directly mutate `SKILL.md` is a **persistent privilege-escalation / instruction-poisoning vector**! Require any proposed `SKILL.md` update to be written to a staged `.diff` proposal and verified against `packages/dataforge-evals` + human Git review.
* **`[BUILD-NEW]` — Author Concise `<80`-Line Root `CLAUDE.md` + Task-Scoped `SKILL.md` Suite:** Ensure `DataForge`'s repository guidance strictly obeys Anthropic's `<100`-line `CLAUDE.md` budget (exact `uv`/`pytest` commands, `$50` API cap warning, active datasets `hospital`/`flights`/`rayyan`/`tax`, module map) while delegating deep runbooks (`llm_corrector.py` schema rules, `dataforge-mcp/dataforge_mcp/tools.py` handle contracts, `SMTVerifier` debugging) to modular `SKILL.md` files.
* **`[REBUILD-0-TO-1]` — Deterministic Git-Hook / Event Triggers Instead of LLM Polling Loops:** Replace `/loop 10m` LLM polling with **`$0.00` local Git hooks / CI scripts** that run `SafetyFilter`, `differential_verify` unit tests, and deterministic `packages/dataforge-evals` checks on actual file diffs—invoking an LLM `0` times when nothing is broken.
* **`[REJECT / TRAP]` — Time-Based `/loop 10m` & Cloud `Routines` on Paid API Credits:** Running `/loop 10m` (`144` runs/day × `50k` cached/uncached tokens) burns `$5–$30/day`, wiping out `DataForge`'s `$50` lifetime credit pool in `2–10` days while doing zero useful work! Strictly ban cron-scheduled LLM polling in `DataForge`.
* **`[UNASKED-WISDOM]` — Verifier Speed (`oxlint` `<50 ms` vs. Slow `30 s` Suites) Governs Agent Convergence Quality:** Sid's live demo worked seamlessly because `oxlint` returned lint errors in milliseconds. In `DataForge`, keeping `SafetyFilter` + `DirectVerifier` + incremental `SMTVerifier` checks localized to affected equivalence-class slices (`<50 ms` rather than re-solving `100,000` clean rows from scratch on every candidate patch) makes bounded `2`-turn error recovery instantaneous and cheap.

---

## DOC-011 — Agents That Remember: Building Persistent AI Memory Stores & Dreaming

### 6.1 Provenance, Speakers & Relevance Tier
* **Archived Source:** [agents-that-remember-analysis.md](../01_sources/Claude%20Code%20-%20Classes/agents-that-remember-analysis.md)
* **Event / Format:** *Code with Claude San Francisco* Technical Workshop (May `2026`, immediately following the May `6, 2026` CMA launch)
* **Speaker:** **Kevin** (Software Engineer, Anthropic `Claude Managed Agents` team)
* **Relevance Tier:** **Tier A** — *Blueprint for `DataForge`'s Persistent Cross-Session Rule/Dictionary Store, Slug-Indexed Filesystem Retrieval, Non-Destructive Clone-and-Diff Curation, and Memory-Poisoning Threat Model.*

### 6.2 First-Principles Mechanism & Deep Technical Extraction

#### A. The Composable Three-Layer Memory Triad (`COALA` Cognitive Alignment)
Stateless agent sessions discard discovered schema quirks, entity aliases, and repair heuristics upon termination (`recall test` failure). Conversely, naively appending raw logs across runs causes unbounded **memory decay** (duplication, contradictions, stale rules, high retrieval latency). Kevin resolves this tension with three composable layers aligned directly with the **COALA** (*Cognitive Architectures for Language Agents*) model:

```text
+---------------------------------------------------------------------------------------------------+
| LAYER 1: SESSION (Working Memory)                                                                 |
|   Ephemeral, isolated execution container. Fast single-run focus on active dataset/task.          |
+-------------------------------------------------+-------------------------------------------------+
                                                  | Mounts virtual FS (access: read_only | read_write)
                                                  v
+---------------------------------------------------------------------------------------------------+
| LAYER 2: MEMORY STORE (Episodic & Semantic Long-Term Memory)                                      |
|   Version-controlled virtual filesystem scoped per user/workspace/org. Queried via `grep`/read    |
|   starting from an auto-maintained `index` slug map (ZERO vector-DB opacity or embedding drift!). |
+-------------------------------------------------+-------------------------------------------------+
                                                  | Clones store out-of-band (Non-destructive!)
                                                  v
+---------------------------------------------------------------------------------------------------+
| LAYER 3: DREAMING (Asynchronous Consolidation Engine)                                             |
|   Spawns 1 sub-agent per session transcript (10-100+ runs) -> Fact-checks against raw transcripts |
|   -> Enriches metadata -> Deduplicates conflicts -> Rebuilds `index` -> Emits structural DIFF!   |
+---------------------------------------------------------------------------------------------------+
```

#### B. Why Virtual Filesystems + `index` Slugs Beat Opaque Vector Databases
1. **Inspectable Exact Retrieval Over Fuzzy Embedding Drift:** Instead of black-box vector similarity (`Pinecone`/`Milvus`)—which frequently retrieves semantically adjacent *wrong* schema versions or outdated numerical thresholds—mounting memory as a **versioned virtual filesystem** lets agents inspect `index` slugs first and jump deterministically to exact markdown/JSON artifacts via `grep` and file reads (`O(1)` lookup without broad directory scans).
2. **Access Control Primitives (`access: read_only | read_write`):** Static SOPs, compliance policies, and verified domain catalogs mount strictly as **`read_only`**, physically preventing active task sessions from overwriting guardrails.
3. **Non-Destructive Clone-and-Diff Curation:** `Dreaming` **never mutates the live production memory store in place**. It clones the input store into a staging output store, writes consolidated artifacts and `index` slugs to the clone, and surfaces a complete **structural `diff`** for human/automated approval before pointer swap.
4. **Dreaming Unit Economics (`~95%` Cache Hit Rate + `50%` Batch Discount):** Because dreaming sub-agents apply uniform system instructions and shared memory prefixes across transcript batches, Anthropic achieves an estimated **`~95%` prompt-cache hit rate**, supplemented on the roadmap by **`50%` off-peak Batch API pricing**.

#### C. The Critical Unaddressed Vulnerability: Persistent Memory Poisoning
As identified in the forensic security analysis of `DOC-011`, mounting a `read_write` filesystem that downstream sessions read or execute commands against opens a **severe cross-session Persistent Memory Poisoning surface**: if an untrusted input (e.g., an adversarial string inside a dirty CSV column) tricks Session `1` into writing a poisoned rule or shell snippet into `Memory Store`, every subsequent session—and the `Dreaming` consolidator itself—inherits the exploit!

### 6.3 Epistemic Verification & Errata Audit

| Claim / Entity in Source | Epistemic Tag | Forensic Audit & Primary-Source Resolution |
| :--- | :--- | :--- |
| **`"gp to search for keywords"`** (lines 31, 75) | `[ASR-CORRUPTION-FIXED]` | Whisper ASR consonant-cluster truncation of UNIX **`grep`**. |
| **`"cloud opus 47"` and `"sonnet 46"` vs. upstream prose `"Claude 3 Opus or Claude 3.5 Sonnet"`** (lines 25, 49, 92) | `[ASR-CORRUPTION-FIXED]` `[STALE-CUTOFF-FALSE-ALARM-FIXED]` | Dual layer error: (1) Whisper transcribed **Claude Opus 4.7** as `"cloud opus 47"` and **Claude Sonnet 4.6** as `"sonnet 46"` (`[ASR-CORRUPTION-FIXED]`); (2) the upstream report author had a stale-cutoff reflex and erroneously rewrote them in lines 25 & 49 as `"Claude 3.5 Sonnet"` / `"Claude 3 Opus"` (`[STALE-CUTOFF-FALSE-ALARM-FIXED]`). At the May 6, 2026 SF workshop, the live models were **Claude Opus 4.7** and **Claude Sonnet 4.6** (`[VERIFIED-PRIMARY]`). |
| **`CMA` Memory Stores (Public Beta, May 2026), Dreaming (Research Preview, May 2026), `~95%` prompt-cache mechanics, `50%` Batch API discount, `COALA` framework** | `[VERIFIED-PRIMARY]` | Confirmed against Anthropic's May 2026 *Code with Claude* developer platform release notes, Anthropic's `90%` cached-input pricing / `50%` Message Batches API tier, and Sumers et al. (`TMLR 2024`, *COALA*). |
| **`10–100+` parallel sub-agent dreaming transcripts without total dollar bill or conflict-resolution SLA** | `[VENDOR-SELF-REPORTED]` | Preview capability ceiling presented by Anthropic engineering; omits worst-case token spend when session transcripts contain long uncached tool outputs and leaves chronological contradiction resolution underspecified. |

### 6.4 Six-Bucket Strategic Mapping to `DataForge`

* **`[ADAPT]` — Index-First Filesystem Artifact Store (`$0.00`, Zero Vector DB) for Learned Repair Knowledge:** Reject heavy vector databases (`Chroma`, `Pinecone`, `Milvus`, embedding APIs) completely! Store `DataForge`'s persistent schema profiles, validated functional dependencies, canonical entity-alias maps (`"United States" → "US"`), and dataset runbooks as **Git-versioned, content-addressed JSON/Markdown files** governed by a compact root **`index.json` slug map** (`domain_slug → {file_path, schema_fingerprint, rule_count, dsse_sha256}`). Lookup is deterministic, `100%` inspectable, `0 ms` network latency, and `$0.00`.
* **`[CHANGE]` — Strictly Enforce `read_only` Mounts on Verified Rule Catalogs During Active Dataset Runs:** Whenever `DataForge` repairs an untrusted dataset (`hospital`, `flights`, `rayyan`, `tax`), mount `SKILL.md`, system prompts, and validated constraint catalogs strictly as **immutable `read_only` structures**. Active repair sessions may only emit candidate observations to an **isolated, non-executable ephemeral staging log**—never mutating active rules mid-run.
* **`[BUILD-NEW]` — Cryptographic & Symbolic Memory/Dreaming Poisoning Write-Gate:** Directly close `DOC-011`'s #1 security vulnerability! Before *any* candidate rule, entity alias, or learned constraint from past `PatchPlan` runs can be promoted into `DataForge`'s persistent rule store:
  1. **`SafetyFilter` Sanitization:** Strip and reject any control characters, prompt-injection directives, shell metacharacters, or executable payloads originating from dirty cell strings (critical for free-text columns like `rayyan` article titles/abstracts).
  2. **`differential_verify` (`SMTVerifier` + `DirectVerifier`) Non-Regression Proof:** Prove mathematically that the candidate rule introduces **`0` contradictions** with existing `SMTVerifier` axioms and **`0` false-positive mutations** on clean reference tuples.
  3. **Clone-and-Diff + `in-toto` DSSE Attestation:** Emit a non-destructive structural diff (`dream_rule_diff.json`) signed into the `in-toto` DSSE provenance chain before atomic promotion.
* **`[REBUILD-0-TO-1]` — Deterministic Local Consolidation Instead of `100`-Subagent Cloud LLM Dreaming:** Spawning `100` cloud LLM sub-agents over raw transcripts—even at a `95%` cache hit rate—still burns precious dollars from `DataForge`'s `$50` credit pool. Replace LLM transcript dreaming with **local statistical/symbolic consolidation (`$0.00`)** over structured `PatchPlan` JSONL histories (aggregating recurring `(determinant, dirty_val → verified_clean_val)` mappings deterministically in DuckDB!).
* **`[REJECT / TRAP]` — Mounting Writable Shell-Accessible Memory Over Untrusted Tabular Inputs:** Never let an LLM run `bash` scripts or dynamic `eval()` over files written during dirty-CSV ingestion—that turns a poisoned CSV cell in `rayyan` or `hospital` into persistent cross-session RCE.
* **`[UNASKED-WISDOM]` — Ephemeral Over-Logging + Offline Pruning Beats In-Flight Compression:** Kevin highlights a subtle systems gem (line 76): during an active repair run, `DataForge` should cheaply log rich structured provenance (`candidate_values`, `smt_unsat_core`, `confidence`, `row_signature`) to local JSONL disk (`$0.00` disk bytes, outside LLM context!), because offline consolidation can deterministically prune noise later without taxing hot-path latency or context tokens.

---

## DOC-012 — The Frontier Memory System: Claude's Active Memory & Asynchronous Dreaming

### 7.1 Provenance, Speakers & Relevance Tier
* **Archived Source:** [claude-agents-memory-dreaming-report.md](../01_sources/Claude%20Code%20-%20Classes/claude-agents-memory-dreaming-report.md)
* **Event / Format:** *Code with Claude* Frontier Architecture Keynote (May `2026`)
* **Speaker:** **Ravi** (Product / Engineering Lead, Anthropic Managed Agents & Frontier Memory)
* **Relevance Tier:** **Tier S** — *Capstone Systems Synthesis for `DataForge`.* Connects the **METR `7-month` task-horizon doubling law**, the **Local-vs.-Global Memory Optimization Theorem**, **Optimistic Concurrency Control (`OCC`)**, the **Karpathy "Agent Wiki" Architecture**, and **Out-of-Band Test-Time Compute Amortization** (`97%` first-pass error reduction) directly to `DataForge`'s `PatchPlan` concurrency, `in-toto` DSSE audit trail, and `$50 → $0.00` symbolic rule distillation engine.

### 7.2 First-Principles Mechanism & Deep Technical Extraction

#### A. The `METR` `7-Month` Horizon Doubling Law & Context Entropy
Ravi situates Frontier Memory along Anthropic's multi-year composability stack: **Nov 2024 (`MCP`)** → **2025 (`Claude Code`, `Agent SDK`, `Skills`)** → **2026 (`Claude Managed Agents`, `Claude Opus 4.7` native filesystem memory, `Dreaming`)**. Grounding the urgency is **METR**'s (*Model Evaluation & Threat Research*, March 2025) empirical scaling law: **the `50%`-reliability task duration of frontier agents doubles every `~7 months`**. As horizons stretch from minutes to multi-day campaigns, stateless agents fail via repeat first-pass blunders, while naive shared note-taking fails via structural entropy.

#### B. The Local vs. Global Memory Optimization Theorem
Ravi formulates a crisp distributed-systems theorem explaining why in-session memory (`Active Memory`) alone inevitably degrades:
* **In-Session Active Writes = Locally Optimal, Globally Suboptimal:** An agent actively solving Task `A` optimizes for immediate completion latency; its quick notes (`"workaround for column X"`) lack visibility into Sessions `B..Z`, producing duplicate files, fragmented conventions, and contradictory heuristics.
* **Out-of-Band `Dreaming` = Global Cross-Session Synthesis (`0 ms` Hot-Path Latency):** Decoupled completely from the hot execution path (triggered nightly, ad-hoc, or post-batch), `Dreaming` analyzes cross-session trajectories (`e.g., 5 SRE sessions across 7 days`), detects systemic retry loops that no isolated session could perceive, and compiles a unified, deduplicated memory diff—analogous to **Andrej Karpathy's "Agent Wiki" pattern** (curated, version-controlled Markdown/schema operating manuals rather than vector soup) and **biological REM/slow-wave sleep consolidation**.

#### C. Enterprise Distributed-State Primitives: `OCC`, Session Attribution & Redaction
To allow multi-agent swarms to share `Memory Stores` safely without data corruption, Anthropic built software-engineering concurrency and compliance controls directly into the storage layer:
1. **Optimistic Concurrency Control (`OCC`):** Every memory file carries a cryptographic version/ETag hash; concurrent agent writes execute **compare-and-swap (`CAS`)** validation so simultaneous updates never silently clobber each other (requiring explicit retry/merge on version mismatch—noting the classic distributed-systems caveat that high-contention hot files suffer elevated `OCC` abort rates unless sharded!).
2. **Full Lineage Attribution & Redaction:** Every mutation records `(session_id, timestamp, parent_version_hash, diff)` alongside enterprise PII redaction and export endpoints.

#### D. Test-Time Compute Amortization (Enterprise Benchmarks)
Ravi frames `Memory + Dreaming` as **amortized pre-task test-time compute**: spending compute *once* out-of-band to distill clean organizational rules permanently raises the zero-shot floor of every downstream run—reported by early partners as a **`97%` reduction in first-pass errors at Rakuten** (alongside `27%` lower API cost and `34%` faster execution) and a **`6x` (`600%`) completion-rate jump on Harvey's complex legal benchmark**.

### 7.3 Epistemic Verification & Errata Audit

| Claim / Entity in Source | Epistemic Tag | Forensic Audit & Primary-Source Resolution |
| :--- | :--- | :--- |
| **`"Meter"`** (lines 27, 82, 97) | `[ASR-CORRUPTION-FIXED]` `[VERIFIED-PRIMARY]` | Whisper ASR phonetic corruption of **`METR`** (*Model Evaluation & Threat Research*, formerly `ARC Evals`, led by Beth Barnes). `METR`'s March 2025 landmark paper, *"Measuring AI Ability to Complete Long Tasks"* (`Kwa et al., 2025`), rigorously established the **`~7-month` doubling time** of `50%`-success software/research task horizons (`[VERIFIED-PRIMARY]`). |
| **`"Cloud MD"` / `"claw.md"` / `"Cloud Code"` / `"Cloud Managed Agents"`** (lines 26, 30, 72) | `[ASR-CORRUPTION-FIXED]` | Whisper ASR phonetic corruptions of **`CLAUDE.md`**, **Claude Code**, and **Claude Managed Agents** (`CMA`). |
| **`"gp"`** (implicit shared transcript tooling with `DOC-011`) | `[ASR-CORRUPTION-FIXED]` | Whisper ASR corruption of UNIX **`grep`** file-search utility. |
| **MCP Open-Source Launch (Nov 25, 2024), Claude Opus 4.7 (Apr 16, 2026), Optimistic Concurrency Control (`OCC` — Kung & Robinson, 1981)** | `[VERIFIED-PRIMARY]` | Primary dates and computer-science mechanisms verified (`MCP` announced Nov 25, 2024; `Claude Opus 4.7` released Apr 16, 2026; `OCC` compare-and-swap semantics standard in transactional storage). |
| **Rakuten (`97%` first-pass error cut, `27%` cost cut, `34%` speedup), Harvey (`6x` / `600%` legal benchmark jump), Wisedocs** | `[VENDOR-SELF-REPORTED]` | Official Anthropic keynote partner case-study metrics; impressive directional signal of out-of-band rule distillation, but evaluated on proprietary internal partner suites without public replication artifacts. |

### 7.4 Six-Bucket Strategic Mapping to `DataForge`

* **`[BUILD-NEW]` — "Symbolic Dreaming": Amortize `$50` LLM Repairs into `$0.00` Deterministic Rules:** This is one of the single highest-leverage architectural syntheses in the entire `DataForge` corpus!
  * *Mechanism:* Whenever `dataforge/repairers/llm_corrector.py` spends precious cents from the `$50` credit pool to resolve novel semantic dirty patterns (e.g., normalizing messy hospital provider names/cities in `hospital`, airline/airport code aliases in `flights`, journal/ISSN abbreviations in `rayyan`, or state-exemption edge cases in `tax`) and those repairs **pass `SafetyFilter` + `differential_verify` (`SMTVerifier` + `DirectVerifier`)**, `DataForge`'s **out-of-band Symbolic Dreamer** scans historical verified `PatchPlan` logs offline, extracts high-support deterministic mappings / regexes / FD rules, re-verifies them across `packages/dataforge-evals` dev splits, and promotes them into `DataForge`'s `$0.00` `DirectVerifier` / local rule catalog!
  * *Economic Payoff:* Just like Rakuten's **`97%` drop in first-pass errors**, Session `2..N` resolve those exact error classes **locally in `<1 ms` for `$0.00`**, converting finite API credits into permanent, compounding symbolic intelligence!
* **`[ADAPT]` — Optimistic Concurrency Control (`OCC`) + Shard-by-Table/Column on `PatchPlan` & Memory Stores:** Prevent multi-agent clobbering in `dataforge-mcp/dataforge_mcp/tools.py` by embedding `base_table_sha256` and `rule_catalog_sha256` into every `PatchPlan`. When `commit_patch_plan` executes, enforce an atomic **compare-and-swap (`OCC`)** check; furthermore, to avoid `DOC-012`'s high-contention `OCC` abort bottleneck when parallel agents inspect different columns/tables, shard rule files **per dataset/schema namespace** rather than locking a single monolithic file.
* **`[CHANGE]` — Bind Session Lineage & Rule Attribution Directly into `in-toto` DSSE Provenance:** Upgrade `DataForge`'s `in-toto` DSSE attestation predicate so every repaired output table cryptographically records *not only* the input SHA-256 and `PatchPlan` SHA-256, but also the exact `rule_store_commit_hash`, `llm_corrector_model_id` (if invoked), `verifier_versions` (`SMTVerifier` + `DirectVerifier`), and `session_id`—delivering full enterprise auditability and instant rollback if a rule ever needs revocation.
* **`[REBUILD-0-TO-1]` — Strict Quarantine Between Hot-Path Execution and Out-of-Band Rule Consolidation:** Enforce `0 ms` memory-consolidation overhead on `DataForge`'s hot repair path (`DOC-012` Zero-Latency Law): active `DataForge` repair runs **read** compiled rule indexes (`read_only`) and **append** immutable `PatchPlan` audit logs; rule synthesis/deduplication ("Dreaming") executes strictly out-of-band as a separate CLI/offline command producing a reviewable Git diff + `SafetyFilter` / `differential_verify` poison-gate certificate.
* **`[REJECT / TRAP]` — `"Let Claude Cook"` Unconstrained Free-Form Agent File Mutations (`Marketing Bias`):** `DOC-012` markets `"getting out of Claude's way and letting it cook"` on arbitrary markdown memory files. On tabular data cleaning over untrusted inputs (`hospital`, `flights`, `rayyan`, `tax`), unconstrained LLM rule-writing guarantees **schema drift, conflicting heuristics, and persistent memory poisoning**! Every consolidated rule in `DataForge` must conform to a strict typed schema (`JSON Schema` / Pydantic) and pass `SafetyFilter` + `differential_verify` (`SMTVerifier` + `DirectVerifier`) before commit.
* **`[UNASKED-WISDOM]` — Out-of-Band Compute Amortization Refutes the False Choice Between `$0.00` Local Purity and Frontier Semantic Intelligence:** Teams on a `$50` budget often assume they must either (a) never use frontier LLMs (losing semantic recall on hard `rayyan` or `hospital` strings) or (b) call LLMs in production loops until credits hit `$0.00`. `DOC-012` reveals the **third path**: use `$50` of frontier test-time compute **as a rule-compiler ("Symbolic Dreamer") during offline curation**, distilling verified symbolic rules and lookup dictionaries that execute forever at **`$0.00` runtime cost**!

---

## Consolidated Six-Bucket Action Ledger for `DataForge` (Dossier 02)

| Strategic Bucket | High-Leverage Architectural Actions Extracted from `DOC-002`, `DOC-007`..`DOC-012` | Target `DataForge` Modules & Datasets | Budget & Quality Impact |
| :--- | :--- | :--- | :--- |
| **`[ADAPT]`** | **1.** Field-local semantic column profiles (`Context`, `FD peers`, `Top-K clean enums`, `DOC-007`)<br>**2.** Progressive disclosure via `<40`-line `CLAUDE.md` + modular `SKILL.md` (`DOC-009`, `DOC-010`)<br>**3.** Index-first `index.json` filesystem rule store (zero vector DB) + `OCC` compare-and-swap hashes (`DOC-011`, `DOC-012`)<br>**4.** Closed-loop autonomous verification circuit (`SafetyFilter` + `differential_verify`, `DOC-002`, `DOC-010`) | `dataforge/repairers/llm_corrector.py`, `SKILL.md`, `SafetyFilter`, `differential_verify` (`SMTVerifier` + `DirectVerifier`), `PatchPlan` | Lifts task accuracy (`62% → 92%` archetype) at `$0.00` local overhead |
| **`[CHANGE]`** | **1.** Invert `llm_corrector.py` JSON schema to **`evidence_reasoning`-first** before `repaired_value` & `confidence` (`DOC-008` Autoregressive Rationalization Bias fix)<br>**2.** Inject raw, unsanitized `SMTVerifier`/`DirectVerifier` counterexamples into bounded `max_retries=2` retry context (`DOC-007`)<br>**3.** Prune legacy "Frankenstein prompt" bloat (`DOC-002`) & diff-gate `SKILL.md` updates (`DOC-010`) | `dataforge/repairers/llm_corrector.py`, `SKILL.md`, `in-toto` DSSE predicate | Eliminates post-hoc confabulated confidences & cuts output tokens `60–75%` |
| **`[BUILD-NEW]`** | **1.** **Symbolic Dreamer** (`PatchPlan` log → verified `$0.00` deterministic rules, `DOC-012`)<br>**2.** **Memory/Dreaming Poisoning Write-Gate** (`SafetyFilter` sanitization + `differential_verify` `0`-regression proof + `in-toto` DSSE signature, `DOC-011`, `DOC-012`)<br>**3.** Deterministic DuckDB SQL `CTE` bulk rule compiler (`DOC-007`) + Grader meta-tests & `<4 KB` MCP payload grader (`DOC-008`, `DOC-009`) | `packages/dataforge-evals` (`hospital`, `flights`, `rayyan`, `tax`), `SafetyFilter`, `differential_verify`, `in-toto` DSSE | Converts `$50` credit pool into permanent `$0.00` runtime rules (`97%` error-cut archetype) |
| **`[REBUILD-0-TO-1]`** | **1.** **Von Neumann L2/L3 Handle Offload** in `dataforge-mcp/dataforge_mcp/tools.py` (`<2 KB` L1 digests + `df://` handles; zero `200k`-token CSV dumps, `DOC-009`)<br>**2.** `"Blobotomy"` split-brain consolidation into constraint-transparent MCP tools (`DOC-007`)<br>**3.** `100%` deterministic `$0.00` CI graders & Git-diff hooks (`DOC-008`, `DOC-010`, `DOC-011`) | `dataforge-mcp/dataforge_mcp/tools.py`, `packages/dataforge-evals` | Eliminates `200,000+` token MCP dumps (**`>98%` context reduction**) |
| **`[REJECT / TRAP]`** | **1.** `64`-agent parallel cloud swarms (`DOC-002`), `/loop 10m` cron polling (`DOC-010`), & `Best-of-3` LLM runtime judges (`DOC-008`)<br>**2.** Raw `bash` execution or `"Let Claude Cook"` unvalidated file writes on untrusted CSVs (`DOC-009`, `DOC-011`, `DOC-012`)<br>**3.** Dropping structured JSON for point-cell edits (`DOC-007`) or hosted `CMA` lock-in (`DOC-009`) | Entire `DataForge` runtime & `dataforge-mcp/dataforge_mcp/tools.py` | Blocks RCE/memory-poisoning & prevents `$50` API budget exhaustion |
| **`[UNASKED-WISDOM]`** | **1.** **Test-Time Compute as Offline Rule Compiler:** Spend pennies of `$50` API budget *once* offline to compile `$0.00` symbolic rules (`DOC-012`)<br>**2.** Consolidate MCP tool count (`4–5` cohesive lifecycle tools) to save `3k–6k` schema tokens/turn (`DOC-009`)<br>**3.** Sub-`50 ms` incremental `SMTVerifier` slice checks (`oxlint` speed law, `DOC-010`) + anchored `[0.0, 1.0]` confidence rubrics (`DOC-008`) | `dataforge/repairers/llm_corrector.py`, `dataforge-mcp/dataforge_mcp/tools.py`, `SMTVerifier` | Compounding accuracy gains with **zero recurring cloud API burn** |
