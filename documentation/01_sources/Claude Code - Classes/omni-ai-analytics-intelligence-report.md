# Building Omni: Powering AI Analytics with Claude and Blobby
## Complete Intelligence & Knowledge Report
*Based on the presentation by Chris Merrick (Co-founder & CTO of Omni) at Code with Claude London (February 2026)*

---

### 1. Essence
This presentation details how Omni, an AI analytics startup, integrated Anthropic’s Claude models to accelerate internal software development and power "Blobby," their production-grade agentic data analyst [1, 12, 40]. By pairing an agentic architecture with a robust, pre-existing database semantic layer, Omni overcomes standard LLM limitations in data precision, enabling business users to safely generate complex SQL and interactive dashboards through natural language [5, 6, 8, 30]. The talk serves as an architectural blueprint for transitioning LLMs from conversational novelty to predictable, enterprise-ready agentic tools [18, 22, 29].

---

### 2. Executive Summary (The 20% that delivers 80% of value)
*   **The Velocity Unlock (Internal Development)**: By implementing Anthropic's CLI-based developer tool *Claude Code*, Omni's 25-person engineering team dramatically increased their git commit slope [1, 3]. CTO Chris Merrick noted that the tool allowed him to remain hands-on with coding despite executive duties, while senior engineers declared the tool "real" once the Opus model integration matured [2, 3].
*   **The Core Analytics Problem**: LLMs possess deep general knowledge but lack specific business context [7]. General phrasing like "last quarter" has distinct meanings across departments (calendar vs. fiscal) [8]. Real-world databases contain chaotic, duplicative schemas rather than sanitized schemas [9]. 
*   **The Semantic Layer Solution**: Rather than connecting Claude directly to raw SQL databases, Omni routes queries through a "semantic layer" (a translation map) [6]. This layer curates tables, encodes localized business logic next to field definitions, handles permissions, and feeds user questions back into a learning loop [8, 9, 10, 11].
*   **Blobby's Evolution**: 
    1. *V1 (Single-Shot Q&A)*: Foundational single-question, single-answer model that was heavily dependent on AI context fields, sample queries, and sample data values to steer results [15, 16, 17].
    2. *V2 (Agentic Loop & Error Recovery)*: Introduced an agentic task harness with a dedicated "error recovery budget." Giving the agent descriptive system errors to self-correct was the single largest unlock for eval performance [18, 19].
    3. *Haiku to Sonnet Transition*: Shifting from Claude Haiku to Claude Sonnet exploded user engagement, enabling multi-turn, complex data reasoning in under two minutes [19, 20].
*   **Critical Architectural Pivot ("The Blobotomies")**: In analyzing "bad sessions," Omni discovered that a split-brain design (an outer orchestrator agent and a query-generation sub-agent) caused failures because the outer agent did not understand what could actually be solved in a single query [21, 22, 23, 24]. They resolved this by "consolidating the brain" into a single, unified agent [24, 25].
*   **The SQL Shift**: Initially, Omni forced Claude to generate queries in a highly structured, proprietary JSON format [27]. Discovering Claude’s remarkable native SQL and CTE (Common Table Expression) generation capabilities, they revived a discarded SQL parsing engine [25, 26, 28]. Switching to raw SQL generation bypassed the need to train Claude on a custom schema, dramatically improving one-shot query accuracy and execution efficiency [27, 28, 29].
*   **Philosophy**: "AI to build, UI to validate, troubleshoot, and refine" [36]. The AI handles rapid generation (dashboards, models, SQL), but the user is provided with direct, visual workbooks and UI controls to audit, adjust, and trust the output [36, 37].

---

### 3. Complete Key Points (Chaptered Analysis)

#### Chapter 1: Claude's Impact on Engineering Velocity & Team Culture
*   **CTO Hands-On Retention**: Chris Merrick (CTO) assumed growing executive demands would force him to stop writing code [1, 2]. Using Claude Code allowed him to remain active in software engineering [2].
*   **The Claude Code Turning Point**: Early experimentation in 2025 was inconsistent [2, 3]. The launch of Claude Code with the Opus model convinced senior engineers of its viability, leading to a team-wide upskilling over the winter holidays and a surge in commit velocity starting in January [3, 4].
*   **Culture of Transparency**: Omni champions the core values of "ship it" and absolute transparency [4]. Every Friday, the team holds an all-hands meeting featuring 10 minutes of announcements and 50+ minutes of live engineering demos [4]. The CEO, Colin Zima, personally edits these recordings every Saturday morning and posts them to YouTube (`omni.co/demos`) [4, 5].

#### Chapter 2: The Omni Architecture and the Crucial Semantic Layer
*   **Bridging General LLM Intelligence and Business Specifics**: Claude excels at general reasoning but lacks context about individual businesses [6, 7]. The semantic layer acts as an intermediary map sitting on top of the data warehouse [6, 8].
*   **The Ambiguity Challenge**: A query like "last quarter" can mean a calendar quarter to engineering or a fiscal quarter to sales [8].
*   **The Data Chaos Problem**: Real databases feature tens of thousands of tables with highly redundant names (e.g., dozens of "revenue" or "opportunity" tables) [9]. The semantic layer curates these, telling Claude which tables are authoritative and which to ignore [8, 9].
*   **Localizing Context**: Similar to how developers place `claude.md` files near specific code in Claude Code, Omni's semantic layer embeds context strings and business metadata directly next to the relevant database field definitions [10, 11].
*   **Permissions and Safety**: The semantic layer enforces system permissions, ensuring users only retrieve data they are authorized to see [11]. It also maintains an active feedback loop where new user queries continually inform and update semantic definitions [11].

#### Chapter 3: The Evolution of Blobby: From Simple Q&A to Agentic Loop
*   **Phase 1 (Basic Q&A)**: Blobby started 18 months prior as a single-turn pipeline [12, 15]. To guide it, engineers created three specific metadata constructs:
    *   *AI Context*: Steering hints indicating when and how to reference specific fields [15, 16].
    *   *Sample Queries*: Archetypes showing Blobby how to answer typical questions [16].
    *   *Sample Values*: Visual previews of field data (e.g., regions like AMEA, NAM, APAC) to facilitate fuzzy matching and abbreviation mappings (e.g., mapping "United States" to "US") [17, 18].
*   **Phase 2 (The Agentic Loop)**: Omni built a proprietary agentic harness with a task-based model [18]. 
*   **The Error Recovery Budget**: Omni’s most significant leap in eval performance came from providing Blobby with a specific "token/execution budget" to recover from runtime failures combined with verbose, highly descriptive database error messages [18, 19].
*   **The Model Transition (Haiku to Sonnet)**: While Claude Haiku was sufficient for fast, basic Q&A, it struggled under complex agentic loops [19]. Upgrading to Claude 3.5 Sonnet increased token consumption but unlocked advanced reasoning [20]. This shift caused in-app usage to skyrocket, with users getting answers to highly complex queries in two minutes rather than hours [20].

#### Chapter 4: The Blo-botomies: Tracing, Observability, and Consolidating the Brain
*   **CEO Backlash**: CEO Colin Zima acted as a demanding user, refusing to accept that LLM unpredictability was an excuse for failed queries ("Not good enough. Go fix it.") [21].
*   **The Value of Session Traces**: Omni invested heavily in trace observability, allowing engineers to watch the agent "talk to itself" in execution loops [21, 22].
*   **The Split-Brain Bug**: Traces revealed that a multi-agent setup was causing silent failures [22, 23]. An "outer" orchestrator agent managed the task list but had no understanding of SQL query generation [23]. An "inner" query agent was tasked with creating a single query to fulfill requests [23]. When asked a complex question requiring multiple separate queries, the inner agent would fail or freeze because it was hardcoded to produce only one query, while the outer agent was blind to this restriction [23, 24].
*   **Consolidating the Brain**: Lead engineer Joel spearheaded "the blobotomies," a series of major structural refactors that consolidated the split-brain system [22, 24]. They pulled the query generation tools directly into the outer orchestrator, eliminating unpredictable loop behaviors [24, 25].

#### Chapter 5: Unlocking Raw SQL: The Shift from JSON to CTEs
*   **The Failed Parser Backstory**: When Omni launched, they built a SQL parsing engine that was eventually abandoned because it couldn't reliably compile the chaotic, arbitrary SQL queries written by human users [25, 26].
*   **The API Interface Pivot**: Initially, Blobby was restricted to outputting database queries in a highly rigid, proprietary, structured JSON format so Omni could guarantee safety [27]. This proved inefficient, forcing engineers to continuously "teach" the model their custom JSON format [28].
*   **Dusting Off the Parser**: Recognizing that Anthropic was heavily optimizing Claude's SQL generation, engineer Stephen revived and updated the abandoned SQL parser [26, 27].
*   **The CTE Marriage**: Claude naturally favors writing SQL using Common Table Expressions (CTEs) [28]. Omni’s parser proved highly effective at processing CTE structures [28]. By allowing Claude to output raw SQL instead of JSON, Omni bypassed custom training, enabled "one-shot" query generation for tasks that previously required 3-4 steps, and increased database efficiency [27, 28, 29].

#### Chapter 6: Current State, Evals, and Live Demonstration
*   **System Architecture (Dual Loops)**:
    *   *Outer Loop*: Manages state checkpointing to allow complete recovery from runtime exceptions [29].
    *   *Inner Loop*: Accesses a rapidly expanding toolset, including tools for dashboard building, automatic visualization, semantic model adjustments, and validation [29, 30].
*   **Eval Philosophy**: Chris Merrick emphasized his passion for evals, specifically the "observability" aspect [30, 31]. While automatic AI judges provide efficiency, reviewing raw session trace data directly exposes root causes of bad agent behavior [31].
*   **Empathy in Engineering**: Merrick argues that because Omni's engineers use Claude Code daily, they intimately understand what makes a high-quality agentic harness [32, 33]. Since a database semantic model is functionally similar to a code base, engineers could directly translate their Claude Code developer experiences into Blobby's user experience [32, 33].
*   **The Live Demo Execution**:
    *   *Action*: Merrick prompted Blobby to "create a dashboard of engineering activity in the Omni repository" [34].
    *   *Process*: Blobby analyzed "Omni topics" (wide, combined datasets mapping multiple sources), formulated a plan, generated multiple queries, and successfully assembled a split-pane dashboard with PR volumes, top authors, and trend charts [35, 38].
    *   *The Hybrid UI Pivot*: To illustrate their "AI to build, UI to validate" philosophy, Merrick seamlessly moved the AI-generated chart into a standard Omni "Workbook" [36]. This allowed him to visually inspect, audit, and adjust the filters (e.g., switching the target repository from the core code to the docs repository) without writing code [36, 37].
    *   *An Honest Failure*: One of the workflow charts in the live dashboard generated a blank tile [39]. Merrick openly admitted he didn't know why it was blank on the spot, suspecting a backend data-population gap—a moment of transparent, unpolished engineering reality [39, 40].

---

### 4. Notable Quotes
*   > "I think, as CTO of a growing company with hundreds of customers, I sort of assumed that at some point I'd have to stop writing code. And I thank Claude very much for making me still able to do some software engineering from time to time." — **Chris Merrick** [2]
*   > "Earlier in 2025 we said to the team, 'I don't know when, and I don't know how, but I know our jobs are changing... so let's just start experimenting...'" — **Chris Merrick** [2]
*   > "Claude is incredible at answering questions, but you need to tell it more about your business if you want it to answer questions about your business." — **Chris Merrick** [6, 7]
*   > "We have to be really careful about how we separate the information and the knowledge of the outer agent and inner agent... consolidating the brain." — **Chris Merrick / Joel (Engineer)** [24]
*   > "AI to build, UI to sort of validate and troubleshoot and refine." — **Chris Merrick (Omni Philosophy)** [36]

---

### 5. Facts, Data, and Resources

| Mentioned Entity | Details / Context | Verification Status |
| :--- | :--- | :--- |
| **Omni** | AI analytics and BI SaaS platform. Co-founded by Colin Zima and Chris Merrick. | **Verified** |
| **Chris Merrick** | CTO and Co-founder of Omni. Speaker of this presentation. | **Verified** |
| **Colin Zima** | CEO and Co-founder of Omni. Highlighted as the "loudest and most critical user." | **Verified** |
| **Joel** | Omni software engineer credited with the "consolidating the brain" refactor. | **Unverifiable** (Internal employee, highly plausible) |
| **Stephen** | Omni software engineer credited with reviving and optimizing the SQL parser. | **Unverifiable** (Internal employee, highly plausible) |
| **Blobby** | Omni's AI agent mascot and in-app analytics assistant. Developed over 18 months. | **Verified** |
| **25 Engineers** | The size of the Omni engineering team as of early 2026. | **Unverifiable** but highly plausible for a Series A/B startup |
| **Claude Code** | Anthropic's developer CLI tool that drove Omni's commit velocity surge. | **Verified** |
| **Claude 3.5 Sonnet / Opus / Haiku** | Anthropic model families utilized in Blobby's development phases. | **Verified** |
| **CTEs** | Common Table Expressions. The SQL structure favored by Claude. | **Verified** |
| **`omni.co`** | The company's official domain where weekly demos are posted. | **Verified** |

---

### 6. Actionable Takeaways
1.  **Stop Designing Split-Brain Agents**: If you utilize a multi-agent system where an outer orchestrator assigns work to an inner specialized agent, ensure the outer agent understands the physical capabilities/constraints of the tools assigned to the sub-agent. If there is a mismatch, collapse the hierarchy and pull the specialized tools directly into the outer harness ("consolidating the brain") [23, 24].
2.  **Expose Great Error Messages to LLMs**: Do not sanitize or hide runtime errors from your agent. Give the agent a specific "error recovery budget" (additional turns) and provide verbose, structured, highly descriptive system error logs. It is often cheaper and more effective to let the model self-correct than to write flawless code upfront [18, 19].
3.  **Build a Localized Semantic Layer for Context**: When feeding enterprise context to LLMs, avoid dumping a massive global markdown file. Instead, attach small, localized context strings, typical query examples, and categorical value lists directly to individual data fields [10, 11, 15, 16].
4.  **Embrace Native Strengths (SQL over Custom JSON)**: Instead of spending engineering cycles trying to force an LLM to output a complex, proprietary JSON schema to enforce structure, let the LLM output the standard programming language it was trained on (like raw SQL). Build a custom parser or compiler on your backend to handle and secure the execution of that native code [25, 27, 28].
5.  **Adopt a "Hybrid" UI Philosophy**: When building AI tools, do not force users into a pure chat interface. Use AI for the heavy lifting of zero-to-one creation (generating charts, code, dashboards), but immediately present the output in a rich visual UI (like workbooks or canvas editors) so human experts can easily validate and refine it [36].

---

### 7. Verification and Research Report (External Context)
*   **Contextual Event**: This talk was delivered at the "Code with Claude" community event in London, hosted in early 2026. This is part of Anthropic's developer-focused outreach highlighting native integrations of Claude Code and the Model Context Protocol (MCP).
*   **Model Context Protocol (MCP) Alignments**: Research indicates Omni has heavily committed to the MCP ecosystem, allowing Claude to interface directly with database schemas securely. The talk references using Claude Code and MCP connections, proving that the Omni engineering team is not only building an AI platform but is deeply integrated into the modern AI developer stack.
*   **The Claude Code Timeline**: Chris Merrick's timeline matches Anthropic's public releases. In late 2025/early 2026, the developer ecosystem saw rapid adoption of CLI-based autonomous agents (like Claude Code), which explains the steep incline in Omni's commit history shown in Chapter 1 [1, 3].
*   **Sponsorship & Bias Detection**: The presentation was given at an Anthropic-centric event. While the CTO’s praise of Claude's SQL performance is grounded in industry benchmarks (where Claude consistently leads in text-to-SQL tasks), there is a structural incentive to minimize alternative models (such as GPT-4o or Gemini 1.5 Pro) and downplay the financial costs of Sonnet token consumption. However, the speaker’s high intellectual honesty in showing a broken live demo and detailing past structural errors balances this bias.

---

### 8. Critical Analysis

#### Strengths of the Presentation
*   **Extreme Transparency**: Unlike typical polished marketing pitches, Merrick details actual architectural failures (the "split brain" architecture), discarded engineering attempts (abandoning their first parser), and maintains absolute honesty when a chart fails to populate in a live demo [23, 25, 39].
*   **First-Principles Engineering**: The decision to shift from proprietary JSON schemas to parsing raw SQL generated by Claude shows brilliant pragmatism [27]. They identified that Anthropic was spending millions optimizing Claude's SQL capabilities, so they chose to ride that wave rather than fight it [26].
*   **Solving the Accuracy Problem**: Data analytics has zero tolerance for hallucination. Routing LLM queries through a strict semantic layer is a highly robust solution that enforces absolute data governance and permissions while allowing natural language query flexibility [6, 8, 11].

#### Weaknesses & Unaddressed Challenges
*   **The Cost Bottleneck**: Upgrading from Haiku to Sonnet and giving Blobby an "error recovery budget" dramatically improves query accuracy but introduces a major token cost footprint [19, 20]. The presentation shows a steep token consumption graph but fails to address the unit economics of this architecture for high-volume enterprise clients.
*   **Live-Demo Fragility**: The empty tile in the engineering dashboard demonstrates that despite extensive evals and an error recovery budget, agentic BI systems remain highly sensitive to upstream data pipeline health and schema changes [39, 40].

#### First-Principles Steelmanning vs. Weak Evidence
*   *The Split-Brain Critique (Steelman)*: A split-brain setup is theoretically cleaner for microservice isolation and reduces prompt size for individual LLM calls. However, in practice, if the orchestrator does not know the schema constraints of the tool execution agent, it will continually feed it unresolvable multi-step tasks. Consolidating the brain, while increasing prompt payload size, ensures the orchestrator makes structurally sound execution plans [23, 24].
*   *Credibility & Honesty Score*: **9/10**. The speaker's background as CTO/Co-founder of a highly regarded AI startup, coupled with his willingness to dissect real failures and present an unpolished live demo, establishes exceptional credibility.

---

### 9. Deeper Connections
*   **Compiler Theory in BI**: The shift from structured JSON to raw SQL parsing mimics compiler design. Omni essentially treats Claude as a high-level natural language code generator, translating user intent into SQL, which is then parsed, optimized, and compiled against the database by Omni's backend engine [6, 27].
*   **"Eat Your Own Dog Food" (Dogfooding)**: The presentation highlights a critical sociological trend in engineering: developer velocity and product velocity are linked. Because Omni's engineers used Claude Code as developers, they developed deep empathy for what makes a great agentic harness, directly improving the design of Blobby for end-users [32, 33].

---

### 10. Open Questions
1.  How does Omni handle cost controls and token usage optimizations for enterprise customers who execute thousands of queries a day using the expensive Claude Sonnet model?
2.  What specific guardrails are in place to prevent "SQL injection" or malicious prompt engineering when Blobby transitions from structured JSON to executing raw, parsed SQL?
3.  How does the semantic layer adapt programmatically when underlying warehouse schemas undergo major, breaking migrations?

---

### 11. Final Verdict
*   **Is it worth the time?** Yes, absolutely. It is a masterclass in pragmatic AI engineering.
*   **Who should watch?** Analytics engineers, AI product managers, CTOs, and software developers building agentic systems.
*   **Single Most Valuable Insight**: *Do not fight the native strengths of state-of-the-art LLMs. Instead of building complex proprietary schemas to constrain them, let them output native code (like SQL) and build robust, traditional parsing and validation layers on your backend to secure and execute it.* [27, 28]
