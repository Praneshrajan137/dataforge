# Charter, Epistemic Standards & Two-Epoch Methodology (`DataForge` Frontier Intelligence Corpus)

## 1. Mission & Quality Standard

This `documentation/` tree is the verified strategic, scientific, and architectural intelligence foundation for **DataForge** (`c:/dev/dataforge`) — a local-first, formally verified tabular and agent-state mutation protocol (`SafetyFilter` -> N-version `SMTVerifier` [Z3] + `DirectVerifier` [Python] -> cohort/conformal calibration -> hash-chained byte-reversible `PatchPlan` transaction journals -> `in-toto` DSSE cryptographic attestations).

Every artifact in this directory is governed by a single acceptance bar:

> **"Would this be accepted as the definitive standard by the world's top 0.1% of experts in AI systems, formal methods, database internals, and product engineering? Exceed that standard."**

At the same time, every architectural and go-to-market conclusion is grounded in our concrete operational reality:
- **Founder & Compute Constraint:** Solo builder (`pranesh`) operating with **`$50` in remaining Claude Pro credit** and a strict **`$0.00` marginal cloud/inference burn mandate** for DataForge's runtime engine.
- **Scale Ambition:** A category-defining protocol and developer experience capable of protecting millions of developers, data pipelines, and autonomous agent workflows worldwide without burning founder or server tokens.
- **Single Current Product Bottleneck ([PRODUCT.md](file:///c:/dev/dataforge/PRODUCT.md)):** DataForge's verification and attestation kernel is built and regression-tested; the primary existential milestone to unlock next is **`design_partner_evidence: NOT MET -> MET`**.

---

## 2. Corpus Provenance & Population Scope (`66` Files, `13,476` Lines)

- **Origin:** `c:\IS DATA` (`66` Markdown intelligence reports across `14` channel directories + `_manifest.csv` organized into `Batch 1` through `Batch 6`).
- **Exact Verified Telemetry:**
  - **Files:** `66` (`DOC-001` through `DOC-066`), archived verbatim (UTF-8 LF-normalized) under [01_sources/](./01_sources/) with `100%` SHA-256 parity recorded in [00_corpus_manifest.json](./00_corpus_manifest.json).
  - **Volume:** `13,476` lines (mean `204.2`, median `190.0`, range `87–492` lines) and `198,762` whitespace-delimited words (~`194,700` prose words).
  - **Secret Scan:** `0` credential or secret matches across all `66` files against DataForge's CI `SECRET_PATTERNS`.

---

## 3. Strict Two-Epoch Sequencing & Cryptographic Unlock Gate

To prevent premature code churn before full-population understanding, work is partitioned into two strictly ordered epochs enforced by [verify_corpus_integrity.py](./_tools/verify_corpus_integrity.py):

1. **Epoch I — Forensic Verification, Organization & Complete `66/66` Synthesis (Current Epoch):**
   - Archive all `66` source files verbatim under [01_sources/](./01_sources/).
   - Produce `14` exhaustive, line-by-line channel dossiers under [02_dossiers/](./02_dossiers/) covering every single document (`DOC-001`..`DOC-066`) with zero lossy compression.
   - Produce `5` cross-corpus synthesis ledgers under [03_synthesis/](./03_synthesis/) reconciling all upstream hallucinations/ASR errors, mapping concrete codebase transformations across six explicit buckets, codifying the 12 Laws of Unasked Wisdom, detailing the `$50` solo-founder survival & growth playbook, and pre-registering falsifiable hypotheses.
   - Run `verify_corpus_integrity.py --unlock` to verify `66/66` coverage, `0` SHA mismatches, `0` broken links, and `0` secrets before setting `"epoch_2_unlocked": true` in [00_corpus_manifest.json](./00_corpus_manifest.json).
2. **Epoch II — Recursive Deep Web Research, Specification, Pre-Registered Evals, Code & Distribution:**
   - Unlocked **only** after `epoch_2_unlocked == true`.
   - Iterates through 5 disciplined passes ("plan and redo again and again"): **(A)** Primary-source web research & hypothesis falsification -> **(B)** Crisp `SPEC_*.md` authoring -> **(C)** Pre-registered `dataforge-evals` / Stanford Harbor / RLVR red-team benchmarks (`hospital`, `flights`, `rayyan`, `tax`; **never `beers`**) -> **(D)** Surgical code execution on a `$50` token budget -> **(E)** Zero-CAC GEO/PLG distribution & 48-hour PR-rescue design-partner conversion.

---

## 4. The Epistemic Verification Gate (Why Upstream `[Verified]` Tags Are Untrusted)

All `66` files in `01_sources/` are secondary LLM extractions generated from YouTube/Whisper transcripts and scraped operator posts. Line-by-line forensic auditing uncovered five systemic upstream failure classes documented in [03_synthesis/ERRATA_AND_VERIFICATION_LEDGER.md](./03_synthesis/ERRATA_AND_VERIFICATION_LEDGER.md):

| Epistemic Tag | Definition & Handling Rule in `02_dossiers/` and `03_synthesis/` |
| :--- | :--- |
| `[VERIFIED-PRIMARY]` | Confirmed directly against primary papers (`arXiv`, *Nature*, *ISCA*), official engineering blogs/repositories, SEC filings, or verified `c:/dev/dataforge` source lines (`L#`). Safe for architectural and strategic decisions. |
| `[WEB-SECONDARY]` | Corroborated via reputable secondary tech/financial reporting or conference summaries where primary filings are private (e.g., private round valuations such as Databricks `$134B` -> `$190B` or Ricursive `$4B`). Cited with secondary attribution. |
| `[STALE-CUTOFF-FALSE-ALARM-FIXED]` | Upstream summarizer/verifier LLM with a 2024/early-2025 knowledge cutoff hedged or backdated a real 2025–2026 release or event (e.g., `DOC-002` hedging Claude Opus 4.7 & Mythos Preview as *"Scenario-Verified / Partially Speculative"*, Jarred Sumner's `535,496`-LOC Bun Zig-to-Rust port across `1,448` files, OpenAI's Feb–Mar 2026 graviton/gluon amplitude preprints, DeepSeek's Jan 12, 2026 **Engram** paper `arXiv:2601.07372`). Reconciled against primary/secondary evidence. |
| `[ASR-CORRUPTION-FIXED]` | Whisper speech-to-text phonetic error (often compounded by upstream LLM confabulation stamped `[Verified]`, such as `"Gabe Rastgoufard"` for Gabe Pereyra, `"Neuripedia"` for Neuronpedia, `"RKGI V3"` for ARC-AGI-3, `"After, Corey"` for AfterQuery, `"Solo"` for Sola, `"ReRAM"` for RePlAce, `"Recursive"` for Ricursive Intelligence, `"Zeekr (Ohoi)"` for Waymo Ojai). Corrected to canonical entity. |
| `[PROVENANCE-CONFLATION-FIXED]` | Misattributed speaker, company, or folder (e.g., `Rainmatter/` containing an a16z Kimberly Tan / EO interview; `DOC-064` conflating Alex LeBrun & Yann LeCun's March 2026 `$1.03B` **AMI Labs** with May 2024's `$220M` **H Company**; `DOC-045` conflating `conductor.build` with `ConductorOne`). |
| `[VENDOR-SELF-REPORTED]` | Plausible internal customer, ARR, latency, or benchmark figure reported by a founder/vendor with commercial incentives; cited with explicit attribution and never treated as an audited physical constant. |
| `UNVERIFIED` | Claim in an upstream report that could not be independently corroborated from primary or reputable secondary records within Epoch I; quarantined from all architectural assumptions. |

---

## 5. The Six-Bucket Strategic Classification Schema

Every dossier in [02_dossiers/](./02_dossiers/) and the master matrix in [03_synthesis/ADAPT_CHANGE_REBUILD_MATRIX.md](./03_synthesis/ADAPT_CHANGE_REBUILD_MATRIX.md) classifies findings into six mutually exclusive action buckets for DataForge:

1. **`[ADAPT]`** — Existing DataForge architecture (`SafetyFilter`, [`differential_verify`](file:///c:/dev/dataforge/dataforge/verifier/differential.py#L62) [`SMTVerifier` + `DirectVerifier`], `dataforge.premise/v1`, `PatchPlan`, conformal calibration, `in-toto` DSSE with `35/35` cross-runtime Java `Arm D` conformance across `13` normative checks, `DuckDB`/`sqlglot`, `dataforge-dbt`) that is structurally validated by frontier practice and should be sharpened in place (e.g., closing the `journal.head_sha256` vector gap and `"disagreed"` vocabulary edge in [`specification-sufficiency.md`](file:///c:/dev/dataforge/docs/trust/specification-sufficiency.md#L181-L215)).
2. **`[CHANGE]`** — Existing DataForge implementation details containing verified code-level defects or asymmetries (`del retry_context` and JSON field ordering in [`llm_corrector.py`](file:///c:/dev/dataforge/dataforge/repairers/llm_corrector.py#L217-L328), unreachable `"confirm_escalations"` check in [`disposition.py:326`](file:///c:/dev/dataforge/dataforge/safety/disposition.py#L326), missing Anthropic pricing in [`spend.py:82-108`](file:///c:/dev/dataforge/dataforge/spend.py#L82-L108), and `p > 28.6%` blind-guessing step reward in [`reward.py:37-45`](file:///c:/dev/dataforge/dataforge/env/reward.py#L37-L45)).
3. **`[BUILD-NEW]`** — High-leverage net-new capabilities missing from DataForge today (governed external reference gazetteer lookup [`STRATEGY.md` Lever 1], Julio Pereyra's Rubric-First Backward Corruption Generator + Stanford Harbor/RLVR task exports replacing `environment.py:209, 217`'s circular detector ground truth, `dataforge.premise/v2` bi-temporal `as_of` bounds, Agent Memory Write-Gate, and `60`-second zero-key disaster onboarding).
4. **`[REBUILD-0-TO-1]`** — Surfaces whose current abstraction should be cleanly re-architected from first principles (specifically [`dataforge-mcp/dataforge_mcp/tools.py`](file:///c:/dev/dataforge/dataforge-mcp/dataforge_mcp/tools.py) to eliminate full-table JSON dumps, MECE tool overlaps, omitted `verification_schema` / `differential_verify` in `dataforge_verify_fix`, and missing `AgentRepairReceipt` attestations, paired with an ultra-thin `SKILL.md` + `llms.txt` GEO surface).
5. **`[REJECT / TRAP]`** — Capital-destroying or architecture-corrupting sirens explicitly rejected (custom GPU SFT/RL model training in excised `archive/training/`, `$200–$500/day` tokenmaxxing, runtime `LLM-as-a-Judge` over deterministic checks, unstructured PDF/DOM scraping, bespoke consulting traps, and pre-PMF package sprawl).
6. **`[UNASKED-WISDOM]`** — Second-order structural laws, hidden failure modes, and non-obvious asymmetries discovered across the 66 reports that were not explicitly asked for in chat.

---

## 6. Constitutional Invariants for Documentation & Future Epoch II Work

1. **Permanent Retirement of `beers`:** Per [CLAUDE.md](file:///c:/dev/dataforge/CLAUDE.md) and [PRODUCT.md](file:///c:/dev/dataforge/PRODUCT.md), the `beers` dataset is permanently excluded from all active evaluation, benchmarking, and roadmap proposals (`hospital`, `flights`, `rayyan`, and `tax` are the canonical real-error benchmarks, always cited with exact evaluation arm/flag qualifications).
2. **Governance & CI Ratchet Isolation:** Root governance files (`CLAUDE.md`, `PRODUCT.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `README.md`) are never bloated with raw research notes; helper scripts live strictly under `documentation/_tools/` (never in the repository root, preserving `tests/regression/test_env.py`), and `documentation/` is pruned from wheel (`MANIFEST.in`) and container (`.dockerignore`) builds.
