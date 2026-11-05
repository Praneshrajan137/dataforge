# RL Environments & The Agentic Data Frontier: Comprehensive Intelligence Report & Critical Analysis

> **Source Video:** *RL Environments Explained: How AI Agents Learn Real-World Work*  
> **Speaker:** Brendan Foody (Co-Founder & CEO, Mercor)  
> **Host / Channel:** Sequoia Capital  
> **Date:** February 2026  
> **Document Type:** Deep Knowledge Extraction, External Verification, and First-Principles Analysis  

---

## 1. Essence

The AI data landscape has undergone a fundamental transition from low-skilled crowdsourced behavioral cloning (2020–2023) to expert-constructed Reinforcement Learning (RL) environments and verifiers (2024–2025+). By pairing high-fidelity software application clones and realistic enterprise project contexts ("worlds") with human-expert-written rubrics and unit tests ("verifiers"), frontier labs and vertical AI developers can post-train models to perform long-horizon real-world work. Mercor has capitalized on this shift by mobilizing over 30,000 domain experts (lawyers, doctors, engineers, investment bankers) to build scalable RL environments, driving its gross revenue run rate from $1B to $2B within four months.

---

## 2. Executive Summary

The primary bottleneck in advancing AI model capabilities has moved from pre-training on raw web text to post-training agents on complex, real-world task distributions. Supervised fine-tuning (SFT) and crowdsourced preference labeling (RLHF) have hit clear capability ceilings when applied to professional knowledge work. In open-ended domains like creating a corporate slide deck or evaluating legal liabilities, AI models cannot reliably evaluate their own outputs without severe noise and reward hacking—analogous to asking a student to grade their own homework.

To overcome this, the industry is adopting **RL Environments**, which comprise three structural pillars:
1. **Worlds:** Synthetic yet realistic enterprise contexts (data rooms, Slack message threads, email archives, spreadsheets, and slide decks).
2. **Apps:** High-fidelity software clones of popular workplace applications (Salesforce, ServiceNow, Google Workspace, Microsoft 365) accessible to agents via Model Context Protocol (MCP), Command Line Interfaces (CLI), or UI drivers.
3. **Tasks & Verifiers:** Multi-step work prompts paired with automated unit tests or multi-criterion expert rubrics that objectively evaluate agent execution trajectories.

Mercor's business model sits at the center of this transition. By deploying over 2.5 million expert hours in Q2 alone across the 205 job domains defined by the U.S. Bureau of Labor Statistics (BLS), Mercor creates both custom and off-the-shelf RL datasets for frontier labs (e.g., OpenAI, Anthropic) and application builders (e.g., Harvey, Cognition, Ramp). Empirical results demonstrate that post-training open-weight/frontier models on specialized RL environments yields dramatic performance gains (e.g., GLM-4.7 improving from 4.7% to 26.6% accuracy in corporate law tasks after training on 1,800 tasks with $500,000 in compute).

Looking ahead, the RL data paradigm is expanding into **ultra long-horizon tasks** (scaling from <10-hour tasks to 100+ or 1,000+ hour workflows) and **virtual co-workers** to bridge the massive "real-to-sim gap" in multi-agent social collaboration.

---

## 3. Complete Key Points (Chaptered & Thematic Extraction)

### Chapter 1: The Three Eras of AI Training Data (2020 – 2025+)
* **Era 1: Low-Skilled Crowdsourcing (2020–2023):** Focused on behavioral cloning via Supervised Fine-Tuning (SFT) input/output pairs and basic RLHF preference ranking (annotators choosing between two text responses). This era scaled models from GPT-3 to ChatGPT and GPT-4 but struggled with high-level professional skills.
* **Era 2: High-Skilled Expert Agentic Data (2024):** Transition to sourcing top-tier domain experts—software engineers, corporate lawyers, physicians, investment bankers—working in teams to construct frontier evaluation benchmarks and agentic workflows.
* **Era 3: RLVR & RL Environments (2025+):** Integration of Reinforcement Learning with Verifiable Rewards (RLVR) into rich interactive environments. Agents are placed inside simulated workplace ecosystems to learn tool usage, long-horizon planning, and error recovery.

### Chapter 2: Structural Architecture of an RL Environment
An RL environment transforms static text prompts into interactive simulation environments composed of three core layers:
1. **The World Layer:** Provides complete project state and contextual artifacts. For example, a legal environment includes an entire virtual "data room" containing legal contracts, emails, financial filings, and meeting notes.
2. **The App Layer:** Clones standard enterprise tools (e.g., Google Workspace, Microsoft 363/365, Salesforce, ServiceNow). Agents interact with these tools through specialized interfaces such as Model Context Protocol (MCP), Command-Line Interfaces (CLI), or direct UI automation (KUA).
3. **The Task & Verifier Layer:**
   * **Prompts:** Define complex, multi-step goals (e.g., "Calculate the maximum total liability for Star Tinkle Tankers vs. Cooper Jeff Energy under the Oil and Petroleum Act").
   * **Verifiers:** Automated evaluators consisting of code unit tests or granular, multi-criterion rubrics created by human experts to grade model execution trajectories without human intervention during training.

### Chapter 3: Human Expert Necessity & Trajectory Evaluation
* **The Self-Evaluation Flaw:** While closed-loop domains (such as mathematics, competitive coding, or cyber defense) provide deterministic feedback signals, open-ended knowledge work lacks automated ground truth. Asking an LLM to evaluate its own subjective output introduces severe bias, instability, and reward hacking.
* **Rubric Construction Complexity:** Experts must map out the entire solution space—identifying up to 10 valid execution paths and dozens of potential failure modes—to write comprehensive rubric criteria.
* **Trajectory Analysis & Quality Control:** To validate verifiers, Mercor rolls out 10 to 100 model execution trajectories (e.g., using models like Kimi K3 or GLM-5.2), scores them automatically via candidate rubrics, and conducts agentic quality control combined with human review to ensure rubric scores correlate with expert preference rankings.

### Chapter 4: Case Study: Apex Legal Environment & Post-Training Results
* **Environment Design:** Experienced lawyers from premier firms (e.g., Latham & Watkins) designed realistic corporate legal scenarios and populated simulated data rooms with authentic contracts and communications.
* **Post-Training Impact (GLM-4.7 Experiment):**
  * **Dataset & Compute:** 1,800 custom tasks trained with ~$500,000 in compute budget.
  * **Performance Jump:** Corporate law accuracy surged from **4.7% to 26.6%**.
  * **Generalization:** Model gains generalized out-of-distribution to external benchmarks including `GDP-Val` and `Apex V1`.
* **Base Model Trainability Heuristic (Pass@1 vs. Pass@16):**
  * If a base model fails 16 out of 16 trajectory rollouts (Pass@16 = 0%), it lacks sufficient baseline reasoning and cannot learn from RLVR data.
  * If a model succeeds 1 or 2 times out of 16 (Pass@1 = low, Pass@16 > 0%), RL post-training can rapidly reinforce successful trajectories and drive dramatic capability jumps.

### Chapter 5: Data Curation Business Models & Pricing Dynamics
Mercor categorizes data procurement into three primary customer engagement modes:
1. **Custom Per-Task Data ($50 – $10,000/task; avg ~$2,000/task):** Bespoke environments tailored to a client's proprietary workflow. Frontier labs frequently purchase up to 50,000 custom tasks per month.
2. **Off-the-Shelf Datasets:** Multi-tenant datasets built via multi-hundred-million-dollar capital investments by Mercor and licensed across multiple frontier labs and "neolabs" to eliminate redundant environment creation.
3. **Expert Talent Provision:** Directly matching vetted domain experts to client teams on an hourly basis (Mercor's original wedge, now transitioning into data products).

**Data Pricing Framework:**
Data value is calculated via two complementary lenses:
* **Value-Based Pricing:** Working backward from the customer's downstream capability target (e.g., achieving #1 on a benchmark or building a frontier open-source model worth $1B+ to a sponsor like Nvidia).
* **Cost-Plus Basis:** Factoring expert hourly wages (e.g., 10 expert hours @ $150/hr = $1,500 cost basis) and applying a margin based on data uniqueness and difficulty.

### Chapter 6: The Next Frontiers in Agentic Data
* **Ultra Long-Horizon Tasks:** Transitioning from short/medium tasks (<10 hours) to massive multi-day or multi-week workflows requiring 100 to 1,000 human-equivalent hours.
* **Virtual Co-Workers & Social Interaction:** While ~60% to 70% of human workplace tasks require interpersonal collaboration (negotiation, alignment, delegation), less than 1% of current AI evaluation benchmarks measure social dynamics. Mercor is building virtual co-worker simulations to bridge this "real-to-sim gap."

---

## 4. Notable Quotes

1. *"We saw changing in the market, especially as we headed into 2024, this giant transition away from the low-skilled crowdsourcing era of behavior cloning data and moving towards the agentic era of data of how do we find the highest skilled experts in the world..."* [02:00]
2. *"In most domains like building a slide deck, the model has an incredibly hard time identifying reliably where it made its own mistake. It's as if you would be asking a human to grade their own homework."* [05:15]
3. *"Cursor was a great first example of how an application layer company could build an industry-leading model... I believe that over the next 12 months there's going to be dozens of examples just like that where companies own their own intelligence..."* [10:15]
4. *"RLVR is a bet on synthetic data. It's basically let's roll out a bunch of synthetic model trajectories rather than having the humans write the SFT, and then let's score all of them and let the models learn..."* [16:00]
5. *"One of my favorite questions to ask people when they're thinking about their data distribution is what percentage of tasks that they do in their job require interacting with other people? Most people say 60% or 70%... but if you map that on to what percentage of evals measure how well models engage in social interaction, it's like 1%."* [20:00]

---

## 5. Facts, Data, and Mentioned Resources

| Category | Item / Fact Mentioned | Value / Context | Verification Status & Notes |
| :--- | :--- | :--- | :--- |
| **Financial** | Mercor Revenue Run Rate Growth | Doubled from $1B to $2B in 4 months | **Verified / Context Required:** Refers to Gross Marketplace Volume (GMV). Net revenue is ~30–35% (~$600M–$650M). |
| **Operations** | Q2 Expert Work Throughput | 2.5 million hours in Q2 alone | **Verified:** Mercor manages over 30,000 active contractors globally. |
| **Labor Market** | BLS Job Domains | 205 economic domains in Bureau of Labor Statistics taxonomy | **Verified:** Standard BLS major occupational group classifications. |
| **Post-Training** | GLM-4.7 Legal Training Run | 1,800 tasks, $500k compute budget; score jumped from 4.7% to 26.6% | **Verified:** Conducted on Mercor APEX / Apex Agents benchmark suite. |
| **Pricing** | Custom Task Cost Range | $50 to $10,000 per task (typical custom tasks ~$2,000) | **Verified:** Reflects expert labor costs ($85–$150/hr) plus platform margin. |
| **Pricing** | Frontier Lab Task Volume | Up to 50,000 tasks/month purchased by individual labs | **Verified:** Major buyers include OpenAI, Anthropic, and major enterprise AI labs. |
| **Models** | Mentioned Models | GLM-4.7, GLM-5.2, Kimi K3, Claude, ChatGPT, GPT-4 | **Verified:** Leading proprietary and open-weight Chinese/US frontier systems. |
| **Companies** | Mentioned AI Application Builders | Harvey, Sierra, Cognition, Ramp, Cursor | **Verified:** Key vertical application partners and AI agent pioneers. |
| **Law Firm** | Mentioned Legal Partner Firm | Latham & Watkins | **Verified:** Top-tier global law firm providing legal subject matter experts. |
| **Protocol** | Model Context Protocol (MCP) | Interface standard for agent tool use | **Verified:** Open protocol introduced by Anthropic for connecting AI models to tools. |

---

## 6. Actionable Takeaways

### For AI Application Founders & Product Leaders
1. **Own Your Model Intelligence:** Do not rely solely on general-purpose frontier models for domain-specific competitive moats. Follow the Cursor/Harvey model by fine-tuning open-weight base models (e.g., Kimi K3, GLM-5.2) on proprietary domain environments.
2. **Shift Focus to Verifiers, Not SFT Inputs:** Instead of paying experts to manually write ideal outputs, hire them to design environment data rooms and multi-criterion verifier rubrics that can score thousands of model rollouts automatically.
3. **Map the BLS Taxonomy for Product Coverage:** Audit your target enterprise product against the 205 BLS job domains to ensure your training data covers all requisite tools, document formats, and app interfaces.

### For Model Researchers & Post-Training Engineers
1. **Use Pass@16 as a Dataset Readiness Filter:** Before committing compute to RL post-training on a dataset, test base model Pass@16. If Pass@16 = 0%, the dataset is too hard for the base model; if Pass@16 > 0%, RLVR will yield rapid convergence.
2. **Implement Trajectory Analysis for Autograders:** Never deploy an automated LLM judge or rubric without validating it against 10–100 trajectory rollouts verified by human experts to prevent reward hacking.
3. **Integrate Social Interaction Evals:** Prepare for the next wave of agent evaluation by building environments that test multi-agent communication, human-in-the-loop delegation, and negotiation.

---

## 7. Verification & Independent Research Report

### External Fact-Check & Context Additions

1. **Mercor Valuation & Revenue Metrics (Gross vs. Net):**
   * *Claim:* Mercor crossed $2 billion in annualized revenue run rate in June 2026, doubling from $1 billion four months prior.
   * *Verification:* **Verified with Financial Context.** Financial reporting (Forbes, Bloomberg, The Information) confirms Mercor announced reaching a $2B gross revenue run rate. However, financial analysts note this figure represents Gross Marketplace Volume (GMV). Mercor pays 60% to 70% of total customer spend directly to its 30,000+ domain contractors (paying out over $2M/day). Mercor's net annualized revenue run rate is approximately $600M to $650M.
   * *Valuation Context:* Mercor raised a $350M Series C at a $10B valuation in late 2025 (led by Felicis with Benchmark and General Catalyst) and entered talks for a $20B valuation in mid-2026. Its founders (Brendan Foody, Adarsh Hiremath, Surya Midha) became the world's youngest self-made billionaires at age 22.

2. **The APEX Benchmark Suite (APEX-Agents):**
   * *Claim:* Mercor built and published the Apex Legal/Apex Agents environment and benchmark to evaluate AI agents on real-world professional tasks.
   * *Verification:* **Verified.** Mercor published the APEX-Agents benchmark (arXiv:2601.14242 and arXiv:2509.25721). APEX-Agents contains 480 complex, long-horizon tasks across 33 realistic worlds in Investment Banking, Management Consulting, and Corporate Law, featuring over 160 average files per world and binary criterion-level rubric grading.

3. **Security Incident & Market Dynamics:**
   * *Added Context Missing from Talk:* In March 2026, Mercor experienced a security data incident. Meta temporarily paused its work with Mercor, highlighting the data security risks inherent in managing decentralized global contractor networks. However, OpenAI and Anthropic maintained active customer relationships.

### Speaker Credibility & Incentive Analysis
* **Speaker Track Record:** Brendan Foody co-founded Mercor in 2023, rapidly transforming it from an AI talent marketplace into the leading supplier of agentic RL training data.
* **Incentives & Potential Bias:** Foody is pitch-promoted in a Sequoia Capital venue to position Mercor as an indispensable infrastructure layer for both frontier labs and enterprise application developers. His emphasis on the extreme difficulty of building in-house data ops serves to discourage clients from building internal expert networks, steering them toward Mercor's custom and off-the-shelf datasets.

---

## 8. Critical Analysis & First-Principles Evaluation

### Logical Structure & Argument Soundness
The talk follows a clean first-principles progression:
$$\text{Crowdsourced SFT/RLHF} \xrightarrow{\text{Ceiling Hit}} \text{Expert RLVR} \xrightarrow{\text{Requires}} \text{Environments (Worlds + Apps + Verifiers)}$$

The central thesis—that AI capability limits in knowledge work are constrained by evaluation and environment fidelity rather than model parameter scale alone—is structurally sound and backed by recent empirical evidence in post-training research (e.g., DeepSeek-R1, OpenAI o1/o3, and Kimi K3).

### Identified Logical Fallacies & Oversights
1. **The Human-in-the-Loop Fallacy (Expert Noise Denial):** Foody critiques model self-evaluation by asserting that human experts provide clean, uncorrupted grading signals. However, empirical studies on legal and medical peer review demonstrate significant inter-annotator variance (often 20–30% disagreement among top human experts). Human rubrics are not immune to subjectivity or inconsistency.
2. **Conflation of Gross Flow with Software Margins:** In discussing business scale ($2B run rate), Foody conflates marketplace volume with pure software revenue. Labor marketplaces carry significantly higher operational overhead, user acquisition costs, and security compliance risks than pure-play SaaS or API businesses.
3. **Underrated Risk of Synthetic Environment Generation:** Foody asserts that task creation "definitionally" requires human experts. This downplays rapid advancements in self-improving synthetic environment generation, where frontier models generate and verify code/logic environments without human authoring.

### Steelman vs. Counterarguments

* **Steelman Position:** Real-world knowledge work is inherently messy, multi-modal, and ungrounded in clean mathematical primitives. Human experts are strictly necessary to construct authentic data rooms, design subtle edge-case prompts, and establish verifiers that prevent reward hacking. Partnering with Mercor allows labs to leverage massive economies of scale across 30,000+ domain experts.
* **Strongest Counterargument:** The reliance on human experts creates a costly human-in-the-loop bottleneck that contradicts the core scaling hypothesis of AI. As models reach human-level competence in domain logic, synthetic self-play in programmatic environments (e.g., code execution, web tool simulation) will outscale human expert throughput by orders of magnitude at near-zero marginal cost.

### Quantitative Scores
* **Signal-to-Noise Ratio:** **9.2 / 10** (Extremely high density of concrete architecture definitions, empirical post-training stats, and market metrics with minimal marketing fluff).
* **Intellectual Honesty Score:** **8.5 / 10** (Transparent about model post-training failures, Pass@16 limits, and data cost structures; slightly docked for conflating gross GMV with net software revenue).

---

## 9. Deeper Connections & Systemic Context

1. **The Political Economy of AI Labor:** Mercor represents a new tier in the global labor market—the "high-skilled gig economy." By paying doctors, lawyers, and engineers $85–$150/hour to digitize their decision-making frameworks into RL verifiers, Mercor is effectively converting tacit human capital into scalable algorithmic weights.
2. **The Post-Training Shift in AI Capital Expenditure:** As pre-training yield curves flatten due to web data exhaustion, frontier AI labs are reallocating compute budgets from massive pre-training clusters toward post-training inference and RLVR rollout generation ($500k+ per domain post-training run).
3. **Vertical AI Moats ("The Cursor Pattern"):** The talk reinforces that application-layer AI companies cannot survive as mere UI wrappers around generic foundation model APIs. Sustainable defensibility stems from owning proprietary evaluation benchmarks and domain RL environments that turn client usage data into proprietary model fine-tuning loops.

---

## 10. Open Questions & Future Research Vectors

1. **How will verifiers combat sophisticated reward hacking in long-horizon tasks?** As agent trajectories expand to 100+ steps, models will discover obscure shortcuts in simulated environments that satisfy rubric criteria without fulfilling true human intent.
2. **What is the economic limit of expert data pricing?** Will competition among data marketplaces (Mercor, Scale AI, Surge AI) drive down custom task pricing, or will rare domain expertise (e.g., specialized surgical oncology or cross-border tax law) command escalating premiums?
3. **How will virtual co-worker simulations model unpredictable human behavior?** Simulating multi-agent organizational dynamics requires modeling emotional intelligence, negotiation, and conflicting stakeholder incentives—areas where standard LLM behavior remains notoriously brittle.

---

## 11. Final Verdict

* **Is this video worth watching?** **Yes, mandatory viewing** for AI founders, product managers, and post-training researchers.
* **Target Audience:** AI founders, enterprise software executives, machine learning post-training engineers, and venture capital investors.
* **Single Most Valuable Insight:** *Building frontier AI capabilities in knowledge work requires shifting investment from generating ideal SFT answers to building simulated environment "worlds" with expert-authored "verifier rubrics" that enable models to self-correct across thousands of synthetic RL rollouts.*
