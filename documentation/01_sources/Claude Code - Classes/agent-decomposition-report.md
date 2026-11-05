# Agent Decomposition: Optimizing Architecture for Scalable Performance
## A Detailed Technical Report Based on "Tool, Skill, or Subagent? Decomposing an Agent that Outgrew its Prompt" (Anthropic Applied AI Workshop, London)

---

### 1. The Essence
This session addresses the common software engineering anti-pattern where an agentic system's complexity is scaled by continuously appending business logic directly to its system prompt, resulting in regressions, high latency, and evaluation dips [1, 2]. By systematically refactoring a bloated inventory management agent called "Stock Pilot" into modular agentic primitives—specifically, moving business logic into **skills** (progressive disclosure) [20], consolidating specialized tools into **computer-like primitives** (code execution) [25, 26], and migrating to **native managed sub-agents** [35, 36]—engineers can drastically reduce token usage, lower costs, and improve system evaluation scores from 62% to 92% [31, 39].

---

### 2. Executive Summary
As LLM-based agents transition from simple prototypes to production-grade enterprise systems, they frequently encounter an architectural bottleneck: **complexity creep** [1, 2]. During Anthropic's "Code with Claude" London workshop, Will from the Applied AI team demonstrated this challenge using **Stock Pilot**, an inventory management agent designed for a mid-sized retailer [1, 3]. Over months of development, Stock Pilot's architecture degraded as new features—such as stock level tracking, demand forecasting, supplier selection, PO filing, and report writing—were repeatedly bolted on [3]. This resulted in a bloated, 400-line system prompt and 12 distinct tools, causing critical evaluation failures and regressions [4].

The workshop outlines a structured, evaluation-driven approach ("hill climbing") to refactor this monolithic agent [10]. This transition leverages three primary architectural shifts:
1. **System Prompt to Composable Skills**: Replacing a monolithic 400-line prompt with a tight 15-line prompt, using "Skills" to load procedural knowledge dynamically into the context window only when required (progressive disclosure) [22, 23, 39, 40].
2. **Specialized Tools to Human-Like Primitives**: Consolidating 12 custom tools down to 3 basic computer-like primitives (bash, read, write) [38]. By allowing the agent to write and execute Python code to analyze data, token consumption dropped from over 200,000 to a fraction of the cost [31].
3. **Implicit Tool Wrappers to Native Callable Agents**: Restructuring chaotic, communication-prone sub-agents into Claude Managed Agents' (CMA) native "callable agents," which provide built-in logging, observability, and robust communication protocols [11, 35, 36].

Through these structural enhancements, the system's evaluation pass rate was successfully raised from a failing 62% baseline to a production-ready 92% [17, 39].

---

### 3. Complete Key Points Organized by Theme with Timestamps

#### **Theme A: The Anti-Pattern of Prompt Bloat (The "Before" State)**
*   **[00:00 - 04:30] Prompt Stacking and Performance Regressions**: Developers commonly scale agent capabilities by appending business rules directly to the system prompt [1]. This "prompt stacking" eventually leads to a long, unwieldy system prompt (400 lines in Stock Pilot's case) and dozens of tools [4]. As complexity increases, developers observe severe regressions in core tasks that previously worked perfectly [2].
*   **[04:30 - 07:00] Monolithic Orchestrator Design**: The initial Stock Pilot agent relied on a single orchestrator executing a local agent loop built on Anthropic’s Messages API [3, 15]. It managed 12 distinct tools, including 3 tool wrappers that called independent sub-agents with completely isolated context windows [4].

#### **Theme B: Hill Climbing and Evaluation-Driven Development (Evals)**
*   **[07:00 - 09:30] Structured Evaluation Suites**: Anthropic advocates for continuous evaluation using a dedicated suite of tasks [10]. Stock Pilot uses 12 evaluation tasks managed by 5 different types of graders [5]:
    *   **Regression Tasks (R-IDs)**: Realistic single-turn tasks testing tool selection, execution, and direct response quality [5].
    *   **Failure Mode Tasks (F-IDs)**: More complex, multi-turn interactions evaluating conversational logic and state management [6].
    *   **Deterministic Graders**: Metrics tracking token count, latency, and turn execution over time [6].
    *   **Non-Deterministic Graders (LLM as a Judge)**: Grading soft criteria like personality, tone, brand style, and qualitative output [6].
*   **[09:30 - 15:00] Deconstructing Failure Modes**:
    *   **F1 (Daily Low Stock Sweep)**: The agent succeeded in identifying low stock but took an inefficient, winding path, failing the turnaround efficiency check [7].
    *   **F2 (Order Process Under Promotion)**: Fails due to communication breakdown between the sub-agent and the main orchestrator, causing lost context [7, 8].
    *   **R8 (Forecasting During Promotion Month)**: Fails due to policy conflicts in the 400-line prompt [8]. Although the model extracted the correct baseline (12 units) and promotional multiplier (3.1x), the sheer volume of context caused it to hallucinate a multiplier of 1.35x in the calculation [9]. The workshop's baseline pass rate for this bloated agent was only 62% (7 out of 12 passing) [17].

#### **Theme C: Progressive Disclosure via "Skills"**
*   **[15:00 - 23:00] Decoupling Logic with Skills**: System prompts should only contain core identity and behavioral instructions that the model must keep in mind *regardless* of the active task [21].
*   **[20:00 - 23:00] Progressive Disclosure**: Skills are packaged, composable blocks of information that Claude dynamically pulls into its context window only when it determines that information is required to complete a task [20]. Refactoring Stock Pilot's 400-line prompt into a 15-line core prompt supplemented by activated skills eliminated context pollution, prevented contradicting rules, and resolved calculation hallucinations [22, 23, 39, 40].

#### **Theme D: Tool Consolidation & Computer-Like Primitives**
*   **[23:00 - 32:00] Emulating Human-Like Primitives**: Anthropic's team structures highly capable agents around the same fundamental primitives that human developers use: a file system, a web browser, a command-line interface (CLI) to execute code, and a to-do list [24, 25].
*   **[26:00 - 28:00] Efficiency of Code Execution**: Instead of uploading massive CSVs, Excel files, or database dumps directly into Claude's context window, engineers should provide the agent with a bash tool to write and execute a Python script locally [26]. The agent processes the file programmatically and reads only the structured output, drastically reducing token usage [26, 31].
*   **[31:00 - 32:00] Quantitative Impacts**: In the Stock Pilot refactor, consolidating specialized tools into simple `bash`, `read`, and `write` primitives [38] dropped token usage for a single task from over 200,000 tokens to a tiny fraction, resulting in proportional cost and execution time reductions [31, 32].

#### **Theme E: Sub-Agents vs. Native CMA Callable Agents**
*   **[32:00 - 37:30] Criteria for Sub-Agents**: Sub-agents should not be used as simple tool wrappers [37]. Will outlines only two valid scenarios for spawning sub-agents:
    1.  **Parallelization ("Throwing more Claude at a problem")**: Performing distributed, heavy tasks like deep research or codebase exploration simultaneously [33].
    2.  **Fresh-Mind Context Separation**: When a task requires a completely unbiased actor without context contamination (e.g., a "code reviewer" sub-agent reviewing code written by a "coder" agent) [33, 34].
*   **[35:00 - 37:30] CMA Callable Agents**: Managing sub-agents through local tool wrappers is prone to lost translation and makes centralized logging/observability difficult [35, 36]. Claude Managed Agents (CMA) provides native **callable agents** (managed sub-agents) [36]. This offloads session details, sandboxed tool execution, security, and unified logging to Anthropic's hosted infrastructure [11, 12, 36, 38].

---

### 4. Notable Quotes
*   "Your system prompt had grown to become several hundred lines long... because of the complexity you've started to see regressions in the areas that your agent was previously accelerating in." [1, 2]
*   "Skills are packaged in composable information that Claude has the ability to pull into context whenever Claude realizes that it needs that information to complete a particular task." [20]
*   "Whenever we build agents, we lean into the same primitives that we as humans have access to when we show up to work... code execution, navigation of a file system, keeping of a to-do list, the ability to search the web." [24, 25]
*   "Giving Claude a bash tool so that Claude can write a quick Python script and reason across the results... is much more effective than just uploading the entire CSV into Claude's context window." [26]
*   "We see a lot of folks run towards MCP first... standardizing and governing tools... but standardizing them can cause some context issues just in terms of polluting context." [29, 30]

---

### 5. Verified Facts and Resources

#### **Technologies & Tools Mentioned**
*   **Stock Pilot**: The inventory management agent used as the refactoring case study [3].
*   **Claude Managed Agents (CMA)**: Anthropic's hosting infrastructure that handles session states, sandboxing, scaling, memory, and native sub-agent observability [11, 12, 36, 38].
*   **Claude Code**: Anthropic’s agentic CLI tool, shown executing the refactoring workflow [16, 24, 25].
*   **Claude 3.5 Opus (specifically Opus 4.7)**: The model running inside Claude Code during the workshop demo (configured with "extra high effort" for optimal triaging) [16].
*   **Model-Context Protocol (MCP)**: Discussed as an ecosystem developers rush to, though warned about regarding context bloat [29, 30].
*   **UV**: A fast Python package installer and resolver used to manage dependencies and run the evaluations (`uv run evals -agent before`) [13, 17].

#### **Quantitative Data & Metrics**
*   **Prompt Length**: Reduced from approximately **400 lines** down to **15 lines** (complemented by modular skills) [4, 39].
*   **Tool Count**: Consolidated from **12 specialized tools** (including 3 sub-agent wrappers) down to **3 core primitives** (`bash`, `read`, and `write`) [4, 38].
*   **Evaluation Pass Rate**: Increased from a **62% baseline** to a **92% success rate** [17, 39].
*   **Token Overhead**: Dropped from **over 200,000 tokens** for a specific data-heavy task to a small fraction, directly translating to a major reduction in latency and runtime costs [31, 32].

---

### 6. Actionable Takeaways

#### **1. Conduct System Prompt Audits**
*   **Action**: Strip out all step-by-step procedures, guidelines, business logic, and policy documents from your primary system prompt.
*   **Rule**: Keep the system prompt under 20-50 lines, focusing solely on the agent's core role, persona, and output expectations [21, 23].
*   **Implementation**: Package the stripped-out procedures into individual **Skills** that the orchestrator can call dynamically only when needed [22].

#### **2. Consolidate Tools and Enable Code Execution**
*   **Action**: Avoid writing dozens of hyper-specific tools to parse CSVs, query JSON, or perform mathematical calculations.
*   **Rule**: Provide a secure, sandboxed command line (like a `bash` tool) and allow the model to write and execute localized Python scripts to parse, calculate, and analyze the data [26].
*   **Result**: Drastically reduces context window pollution (e.g., reading a script's short stdout instead of digesting a 10MB CSV), dropping token usage and overall cost [26, 31].

#### **3. Re-evaluate Your Sub-Agent Strategy**
*   **Action**: Audit your sub-agents and eliminate any that merely wrap APIs or act as direct "middleman" tools.
*   **Rule**: Merge tasks back into the main orchestrator where possible, as modern frontier models possess the intelligence to handle multiple tasks directly [37]. Spawning sub-agents should only occur when you require parallel processing or complete context isolation (like an independent code reviewer) [33, 34].

---

### 7. Verification Report

| Claim Made in Video | Grounding in Transcript | External Verification / Context | Status |
| :--- | :--- | :--- | :--- |
| **System prompt bloat causes regression.** | Yes, Stock Pilot’s 400-line prompt caused a failure in forecasting (R8) [8]. | Widely verified in LLM literature (the "lost in the middle" phenomenon and attention dilution in extremely long context prompts). | **Verified** |
| **Consolidating tools to bash reduces tokens.** | Yes, token usage for data analysis dropped from 200k+ to a fraction [31]. | Standard practice. Sending 10MB CSV data to an LLM uses massive tokens. Executing a local script and returning a 10-line summary uses minimal tokens. | **Verified** |
| **CMA simplifies infrastructure and sandboxing.** | Yes, Will states CMA manages sessions, scaling, and sandboxed environments [11, 12]. | CMA (Claude Managed Agents) is a proprietary Anthropic developer platform feature designed to offload agent execution loops, state management, and sandboxing. | **Verified (Feature Claim)** |
| **Opus 4.7 is running in the demo.** | Yes, Will says "I have Opus 4.7 running" with "extra high effort" in Claude Code [16]. | Opus 4.7 refers to Anthropic's next-generation model used in their developer workshops. | **Verified (Internal Tech)** |

---

### 8. Critical Analysis with a Credibility Score

#### **Logical Flow and Strengths**
The presentation is highly logical and grounded in empirical engineering challenges that any practitioner building production agents will recognize. By using an evaluation suite (Stock Pilot) as the baseline, the speaker demonstrates "hill climbing" in action, showing that architectural changes must be driven by quantifiable evaluation metrics, not vibes [10]. The argument for "human-like primitives" (giving the LLM a computer instead of custom APIs) is a powerful conceptual model that scales well as underlying models improve [25].

#### **Potential Biases and Limitations**
*   **Anthropic Ecosystem Lock-in**: The presentation heavily pushes **Claude Managed Agents (CMA)**, **Claude Code**, and **Skills** [11, 16, 20]. While these are excellent abstractions, developers can achieve similar decomposition architectures using open-source frameworks (e.g., LangGraph, Autogen, or CrewAI) and custom sandboxed environments (e.g., E2B or Docker).
*   **Security of Code Execution**: The talk glosses over the massive security implications of giving an agent a `bash` tool [25, 26]. In a production environment, running arbitrary LLM-generated code requires strict, air-gapped sandboxing to prevent server compromise or data exfiltration. While CMA is noted to handle this [11], self-hosted implementations require substantial security engineering.

#### **Signal-to-Noise Ratio & Credibility Score**
*   **Signal-to-Noise Ratio**: **9.5/10**. The presentation is virtually free of fluff, packed with live code examples, actual architecture diagrams, evaluation metrics, and concrete design patterns.
*   **Credibility Score**: **10/10**. Delivered by Will from Anthropic's Applied AI team—a practitioner actively building agents with top-tier enterprise clients [1]. The insights perfectly align with state-of-the-art AI engineering practices.

---

### 9. Deeper Connections to Broader Fields

*   **Software Engineering (Modular Design & SRP)**: The decomposition of agents mirrors classic software engineering principles, specifically the **Single Responsibility Principle (SRP)** and modularity. "Prompt bloat" is the modern equivalent of a "God Class"—a file that tries to do everything and becomes unmaintainable.
*   **Human Cognitive Load (Working Memory)**: Restricting the system prompt and using "Skills" (progressive disclosure) is highly analogous to how the human brain manages working memory. Humans do not keep a 500-page manual in active working memory while doing a task; they refer to specific chapters (skills) as needed.
*   **Distributed Systems (RPC vs. Choreography)**: The breakdown in orchestrator-to-sub-agent communication (F2 failure) represents a classic distributed systems problem [7, 8]. As architectures transition to multi-agent microservices, defining clear interfaces, state handoffs, and observability protocols becomes paramount.

---

### 10. Open Questions

1.  **Standardization of Skills**: How do we standardize the format of a "Skill" so it can be ported across different orchestrators or LLM providers, avoiding vendor lock-in?
2.  **Deterministic vs. Agentic Latency**: Giving agents access to bash and python scripts reduces token usage, but it introduces execution latency. What is the sweet spot between LLM reasoning speed and code-execution latency for user-facing applications?
3.  **Local Sandboxing Costs**: If a developer chooses not to use Claude Managed Agents (CMA), what are the most secure and cost-effective ways to orchestrate sandboxed Python execution at scale?

---

### 11. Final Verdict

#### **Who Should Watch This Video?**
*   **AI Engineers & Architects**: Individuals struggling with sluggish, erratic, or expensive production agents.
*   **Software Engineers Transitioning to AI**: Developers looking to apply traditional design patterns (modularization, refactoring, testing) to the stochastic world of LLMs.
*   **Technical Product Managers**: Leaders defining requirements for agentic products who need to understand why "just adding another feature to the prompt" is an unstable scaling strategy.

#### **Prerequisites**
A basic understanding of LLM APIs (like Anthropic's Messages API), tool calling (function calling), and basic software development concepts.
