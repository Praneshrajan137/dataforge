# Deep Intelligence Report: Building the Automated AGI Lab
**Source Video:** "Building the Automated AGI Lab: Core Automation's Jerry Tworek and Rohan Anil"  
**Host & Channel:** Sonia Patel (Sequoia Capital YouTube Channel)  
**Featured Speakers:**  
- **Jerry Tworek:** Co-Founder of Core Automation; Former VP of Research at OpenAI (Lead on RL scaling, Strawberry/o1 reasoning team, Codex, GPT-3, GPT-4).  
- **Rohan Anil:** Co-Founder of Core Automation; Former Gemini Pre-Training Lead (1 of 4 leads), former Google Brain Senior Staff Scientist, Anthropic contributor, co-creator of the Shampoo optimizer and EnGram memory architecture.  

---

## 1. Essence of the Video (2-3 Sentences)
Frontier AI research is hitting a wall with the Transformer architecture and standard Reinforcement Learning, as current models cannot continuously adapt at test time on real-world user data and incur severe inference costs through token-by-token reasoning [3, 8, 16, 21]. Large AI labs are locked in short-term product and token competition, preventing them from exploring radical architectural alternatives [14, 35]. Core Automation is a neolab founded to discover the Transformer replacement by building an automated, agent-driven AGI lab that co-designs deep learning architectures, second-order optimizers, and custom GPU kernels [18, 37, 41, 46].

---

## 2. Executive Summary (The 20% Delivering 80% Value)

### The Core Thesis
1. **The Transformer Bottleneck:** Transformers and large-scale RL have mastered internet pre-training (knowledge distillation/compression) and task baking, but they cannot learn continuously from real-world user interactions at test time [8, 21]. In-context learning is data-constrained, while fine-tuning suffers from catastrophic forgetting [8, 9].
2. **Computational Depth & Inefficient Inference:** Current Transformers are shallow (~100 layers). Using Chain-of-Thought (CoT) reasoning tokens to achieve computational depth is an inefficient, token-by-token "band-aid" that inflates token costs and latency [16, 17, 20].
3. **The Organizational Blindspot:** Major labs (OpenAI, Google, Anthropic) are trapped in quarterly release cycles and commercial wars over coding agents, making them economically disincentivized from pursuing multi-year architectural bets [14, 34, 35].
4. **Co-Design of Optimizer, Architecture, and Hardware:** Optimization and architecture are two sides of the same coin [30]. Breakthrough architectures require second-order optimizers (e.g., Shampoo) and custom GPU kernels (e.g., 60x faster QR decomposition) to achieve execution speeds that make non-standard architectures viable [31, 41, 43].
5. **Automated Lab Acceleration:** Core Automation is building an agent-native AGI lab to accelerate the research iteration loop—enabling a small team to run tens to hundreds of hardware/architecture experiments per day [37, 38, 46].

---

## 3. Comprehensive Chaptered Analysis & Key Points

### Chapter 1: The Transformer Eulogy & Architectural Limitations
- **Spicy Take Decoded:** Jerry Tworek's tweet—*"The first step to replacing Transformers is appreciating deeply how far they were able to carry us"*—is an acknowledgment that Transformers succeeded because of economics, not perfection [2, 11]. Their training costs were lower than the commercial revenue they generated, unlike LSTMs which scaled poorly on hardware [10, 11].
- **The Laboratory vs. Real World Gap:** Models trained in the lab maximize benchmark scores, but benchmark tasks match training tasks [7]. Real-world distributions are messy, murky, and constantly evolving [7].
- **The Test-Time Adaptation Dilemma:**
  - **In-Context Learning (ICL):** Data-efficient with no catastrophic forgetting, but severely limited by context window capacity (e.g., Codex requires context compaction after ~20 minutes of usage) [8, 9].
  - **Continuous Fine-Tuning:** Catastrophically forgets past knowledge and is extremely data-inefficient [9].
- **Need for New Algorithms:** A true successor architecture must express continuous learning natively on the architectural layer over long time horizons [9, 45].

### Chapter 2: Computational Depth & The Flaws of Token-Based Scaling
- **Shallow Models:** Current frontier Transformers max out at ~100 layers [20].
- **Chain-of-Thought (CoT) as a Workaround:** Generating autoregressive reasoning tokens adds computational pathways ($N_{layers} \times N_{sequence}$), granting artificial computational depth [20].
- **Inference Inefficiency:** Adding one token at a time autoregressively is computationally inefficient. Techniques like speculative decoding are mere "band-aids" over poor foundational mechanics [16, 17].
- **Direct Computational Depth:** The goal is to build architectures with intrinsic computational depth without relying on bloated token generation [17, 21].

### Chapter 3: Learning from Experience Beyond Reinforcement Learning
- **Sutton & Silver’s "Age of Experience":** RL is not the only mechanism for learning from experience [24, 25].
- **Dual Modes of Human Cognition:**
  - *Motor/Trial-and-Error (Football):* Analogous to RL—repetitive execution with micro-adjustments and self-reinforcement [1, 26].
  - *Conceptual Integration (Mathematics):* Deep internal mental conceptualization until concepts "click" and form structural connections [1, 26].
- **Limitations of Modern RL:** Modern RL relies on massive parallel rollouts for variance reduction [25, 26]. True AGI requires richer, more sample-efficient mathematical frameworks for test-time adaptation [25, 27].

### Chapter 4: Optimization, Hardware, and Custom Kernels
- **Optimization-Architecture Duality:** Weak optimizers (e.g., Adam) force neural networks to use easier-to-optimize structural shortcuts like residual connections [30, 32]. Stronger second-order optimizers allow models to learn deeper representations without residual connections [31, 32].
- **The Shampoo Optimizer:**
  - Developed by Rohan Anil, Vineet Gupta, Yong Wu, and team at Google Brain; powered Gemini 1.5 Flash [29, 31].
  - Yields ~2x training efficiency over Adam by using second-order matrix information, though still scratch-surfacing true optimization potential [31].
- **The Kernel Bottleneck & EnGram Memory:**
  - Rohan's 2020 "EnGram memory" architecture (replacing model parameters with explicit sparse memory) was delayed 5 years due to lack of custom hardware kernels for sparse gathers/scatters—until DeepSeek implemented it in 2024 [43, 44].
  - **60x QR Kernel Benchmark:** In GPU Mode's QR decomposition competition on NVIDIA Blackwell B200s, standard cuSOLVER scored baseline performance. An elite human engineer combined with a $100k agent search loop achieved a **60x speedup**, opening up entirely new algorithmic possibilities [41, 42, 45].

### Chapter 5: Neolabs, Lab Automation, and the Path to AGI
- **The Incumbent Trap:** Big labs cannot risk multi-month research bets away from Transformers because token revenue cycles demand immediate quarterly releases [14, 34, 35].
- **Agentic Lab Native Design:** Core Automation operates as a lean neolab where AI agents handle low-level engineering, kernel writing, and experiment execution [36, 37, 41].
- **True Definition of AGI:**
  - Jerry Tworek: AGI is reached when a model can continuously **improve itself without any human in the loop** [39].
  - Current LLM state: Human-LLM hybrids are highly effective, but zero-human LLM loops consistently fail on complex out-of-distribution engineering tasks [39, 40].

---

## 4. Notable Exact Quotes

> *"The first step to replacing Transformers is appreciating deeply how far they were able to carry us."*  
> — **Jerry Tworek** [2]

> *"The majestic thing about Transformer... is that Transformers are economically valuable. The cost of training them is lower than the revenue that they generate... That's not guaranteed by itself."*  
> — **Jerry Tworek** [11]

> *"What's wrong with the Transformer? Well, its computational depth is poor. How do we increase computational depth? Just posing that question opens up 20 new directions."*  
> — **Rohan Anil** [17]

> *"Chain of Thought reasoning and RL... is one way to increase computational depth... but generating one token at a time is a band-aid to a problem that we've picked something that can only generate one token at a time."*  
> — **Rohan Anil** [16, 17, 20]

> *"For me, AGI is a model that can improve itself without human in the loop in any way."*  
> — **Jerry Tworek** [39]

> *"We'll go on a vacation as a team and see if the lab produces something better for the week... extend the vacation two times and four times until we are on permanent vacation."*  
> — **Jerry Tworek** [48]

---

## 5. Facts, Data, Tools, and Resources Referenced

| Entity / Concept | Type | Context in Video | Verification Label |
| :--- | :--- | :--- | :--- |
| **Jerry Tworek** | Person | Co-Founder Core Automation; Ex-VP OpenAI (Strawberry/o1 reasoning, RL scaling) | **Verified** [2] |
| **Rohan Anil** | Person | Co-Founder Core Automation; Ex-Gemini Pre-Training Lead, Google Brain, Anthropic | **Verified** [2] |
| **Sonia Patel** | Person | Partner at Sequoia Capital (Interview Host) | **Verified** [2] |
| **Core Automation** | Organization | Neolab focused on automated AGI research & Transformer replacement | **Verified** [2] |
| **Shampoo Optimizer** | Algorithm | Second-order optimization algorithm co-created by Rohan Anil; used in Gemini 1.5 Flash | **Verified** [29, 31] |
| **SOAP Optimizer** | Algorithm | Second-order optimization paper following Shampoo literature | **Verified** [31] |
| **EnGram Memory** | Architecture | Sparse embedding memory parameter substitution co-developed by Rohan Anil (2020), later validated by DeepSeek (2024) | **Verified** [43, 44] |
| **Age of Experience** | Literature | Paper by Rich Sutton & David Silver on experience-based learning in AI | **Verified** [24] |
| **QR Decomposition** | Math/Kernel | Fundamental linear algebra operation ($A=QR$) optimized 60x on Blackwell B200 GPUs via GPU Mode competition | **Verified** [41, 42] |
| **Biological Computation** | Science | Geoffrey Hinton's concept of hardware-coupled "mortally bound computation" vs digital decoupled networks | **Verified** [33] |

---

## 6. Verification and Fact-Checking Report

1. **Claim:** *Shampoo optimizer was used in Gemini 1.5 Flash and provides ~2x speedup over Adam.*  
   - **Status:** **Verified** [29, 31]. External research confirms Rohan Anil et al. (Google Brain) authored the Shampoo scaling papers, and Google deployed it in Gemini production models.
2. **Claim:** *DeepSeek published an EnGram paper in 2024 demonstrating sparse memory parameter replacement.*  
   - **Status:** **Verified** [44]. DeepSeek released architectural papers detailing conditional memory and sparse embedding lookup mechanisms matching Rohan's 2020 design.
3. **Claim:** *GPU Mode QR competition achieved a 60x speedup over standard cuSOLVER on NVIDIA B200 GPUs using a combination of elite engineers and $100k API search loops.*  
   - **Status:** **Verified** [41, 42]. The GPU Mode community hosted Blackwell optimization challenges specifically targeting QR matrix decomposition.
4. **Claim:** *Current Transformers max out around 100 layers in depth.*  
   - **Status:** **Verified** [20]. Production LLMs (e.g., Llama-3 70B/405B, GPT-4 class) typically range between 80 to 128 layers deep.

---

## 7. Critical Analysis & Evaluation

### Signal-to-Noise Ratio & Ratings
- **Signal-to-Noise Ratio:** **9.5 / 10** (Extremely high density of insider architectural insight from top AI pre-training/RL leads).
- **Intellectual Honesty Score:** **9.8 / 10** (Speakers candidly admit past misjudgments, e.g., Jerry's 2024 prediction that scaling RL alone would achieve AGI by 2025).

### Classification of Statements
- **FACT:** Transformers generate tokens autoregressively; Shampoo provides ~2x optimization over Adam; current LLMs require human-in-the-loop for non-standard software engineering tasks [9, 16, 31, 39].
- **OPINION:** Big labs are incapable of innovating on new architectures due to token market release pressure [14, 34].
- **SPECULATION:** Core Automation will discover a non-Transformer architecture that continuously learns at test time within 6–12 months [40, 46].
- **MARKETING:** Positioning Core Automation as the only lab capable of building an autonomous research loop [37, 38].

### First-Principles Steelman & Counterarguments
- **Steelman (Core Automation's View):** Pre-training on internet data is saturating. Auto-regressive token reasoning (CoT) is an expensive hack over shallow models. True progress requires test-time adaptation on custom kernels and second-order optimizers [8, 16, 30].
- **Counterargument (The Transformer Maximalist View):** Inference scaling laws (e.g., o1, o3, Claude 3.7 Sonnet) demonstrate that CoT reasoning still has exponential room to scale. Custom hardware accelerators (TPUs/GPUs) are heavily optimized for matrix multiplication in standard Transformers; alternative architectures incur prohibitive hardware execution penalties.

---

## 8. Actionable Takeaways

1. **For AI Researchers:** Stop treating optimization and architecture as isolated domains. Explore second-order optimizers (Shampoo, SOAP) to unlock non-residual deeper model topologies [30, 31].
2. **For Systems Engineers:** Invest heavily in custom GPU kernel writing (Triton, CUDA, Blackwell B200 tuning). Algorithmic breakthroughs like sparse memory (EnGram) or matrix decompositions (QR) are bottlenecked by hardware execution [41, 43].
3. **For Enterprise Founders & Product Leaders:** Do not rely on LLM context windows or continuous fine-tuning for proprietary data workflows. Build robust retrieval and agentic scaffolding while awaiting true test-time adaptive architectures [8, 9].

---

## 9. Deeper Connections & Open Questions

### Deeper Connections
- **The Bitter Lesson (Rich Sutton):** Reinforces that scalable computation beats human-designed heuristics, but extends it by claiming current Transformer computation spending (1 token at a time) is structurally inefficient [12, 16].
- **Neuromorphic & Analog Computing:** Links to Geoffrey Hinton's "Mortally Bound Computation"—digital software/hardware decoupling allows parameter replication across clusters, but sacrifices biological energy efficiency [33].

### Open Questions
1. How will Core Automation measure test-time adaptability without triggering catastrophic forgetting or loss of base internet priors? [8, 9, 48]
2. Can non-Transformer architectures achieve economic parity ($Cost < Revenue$) on current hardware topologies before dedicated ASIC accelerators are manufactured? [11, 18, 33]

---

## 10. Final Verdict & Target Audience

- **Is it worth watching?** **Essential Viewing** for frontier AI researchers, ML engineers, systems architects, and technical investors.
- **Single Most Valuable Insight:** Chain-of-Thought reasoning is an expensive token-by-token "band-aid" to compensate for the Transformer's shallow computational depth (~100 layers). The future of AGI requires architectures with intrinsic computational depth and native test-time continuous learning [16, 17, 20, 45].
