# Engineering Reliable Agentic Systems

Analyze
Interestingly, the most common error in agentic systems is the OOM error :)

When you build an agent, almost everything you query and everything it needs is held in memory. Things usually work fine locally, but when you put it into production, or just add a little more load - longer conversations, more tool results, bigger documents - the process dies from running out of memory.

To be honest, these systems work perfectly during development, only to fail once conversations get longer or traffic starts increasing. Of course, the issue is not the model here, but the amount of context and state we keep around it. Here are some common culprits:

- tool results held in context
- search results, API responses, and outputs pile up
- no context truncation in place
- external call results accumulate in memory
- entire doc loaded when only a small portion is needed

Also, the fixes are not exotic in any way: truncate aggressively, summarize, intermediate steps, remove what's not needed from context and mem, retrieve only what is needed, stream instead of buffering, and persist state externally instead of keeping everything in memory.

The key is identifying what truly needs to stay in memory and what can be moved elsewhere. Also, it is equally important to understand how memory usage grows as conversations get longer or agent loops run far beyond what was originally expected.

Given how long-running AI systems are, it is important to design them to handle errors, rate limits, and failure scenarios gracefully, with a well-defined degradation policy.

We have all solved these kinds of problems before. Agentic systems are no different - the constraints are familiar, but the surface area is new.

Hope this helps.

---

We do not think about token budgets until something breaks - the app stops working, a sentence gets cut off midway, etc. Fun fact: token budgets are more of a system design problem :)

Token budgets matter because they are the edge condition for everything an LLM does. A model is capped by its context window. Go beyond it, and you get failures. Stay too far under it, and you are making your system less intelligent.

Token budgets are a system design problem.

What fills a context window is not random, and hence it does not need to be treated as random. It is system prompts, conversation history, retrieved documents, tool call results, and reasoning chains. Every one of these is an architectural decision.

If your RAG pipeline dumps 10 unranked chunks into the context, that is a retrieval design problem. If your conversation history grows unbounded across turns, that is a state management problem. A prompt instruction does not fix either.

System design gives you levers - chunking strategy, context window allocation, history summarization, tiered retrieval, parallelization, etc. These decisions compound, and you need a rock-solid design and data flow to build a robust AI system.

By the way, a well-designed system does more with a 32k context window than a poorly designed one with 200k - and at a fraction of the cost.

Models also behave differently near their context limit. Attention degrades, key details get dropped, and output quality falls non-linearly. You cannot prompt your way around that. You design around it.

The prompt is the last 5% - the system is the other 95%.

---

Yesterday, I was building a small Agentic PR reviewer for myself, and I realised how critical topological sort was in its entire application.

Essentially, every AI workflow is fundamentally a dependency problem. We do not just chain the prompts together, but also have situations where we may need to do things in an order that respects the dependencies.

This is where the classic DAG and topological sort come in handy.

I just wrote an essay on why DAGs and topological sorting are the core primitives required to design, debug, and scale AI workflows.

In this article, I break down how the dependency problem breaks linear pipelines, how to unlock "free" parallelism and cycle detection at definition time, and how this mental model scales seamlessly to multi-agent orchestration.

If you are building AI workflows (which I am sure you are), RAG pipelines, or multi-agent systems, this essay will give you a solid first-principles framework.

Give it a read.

https://arpitbhayani.me/blogs/ai-topological-sort

---

Everyone talks about agent intelligence. Then agents reach production - or face even the slightest bit of load - and suddenly the hard problems are:

- memory management
- concurrency
- backpressure
- retries
- timeouts
- failure handling
- observability

Agentic loops are long-running, non-deterministic, and inherently error-prone, which makes reliability difficult. The more complex the agents, the more interesting the failure modes.

Turns out, agents are often more of a classic software engineering problem than an AI problem. Good engineering practices are not going anywhere.

To make production ready software
- Agents needs context not just about the task but the entire system
- Agents need to coordinate amongst themselves and humans and 
- Agent needs to verify and publish evidences so that their work can be trusted. 

This is what software factory will solve for.

---

The future of knowledge work is not dark software factories, it's software factories that give you the right balance of autonomy, control, security, auditability, governance, and cost controls --- that self improve, both autonomously and with human in the loop

Humans are meant to do Untrivial things, and we are here to enable them

---

One of the best mental models around for building reliable systems is to be a pessimist. Not in the "nothing will ever work" sense, but in the structured sense of asking hard questions before something goes wrong.

What could break here? What could break without us ever realizing it? What happens to the system if this dependency goes down? What is error-prone in this flow, and are we just getting lucky right now?

Most engineers think about the happy path and are done with the work. But it is important to think about edges and even the edges of the edges. Yes, the depth of your edge case handling is always a function of timeline and ROI on the effort.

By the way, we are not being pessimistic for its own sake. Here, pessimism is a forcing function. When you sit down and genuinely ask, "What could go wrong?"

- you write readable code
- you handle errors better
- you add the required alerting
- you design better fallbacks
- you don't assume - DB will remain up
- you don't assume - 3P API is available
- you don't assume that your own code will always behave as expected under load

I would say: ship something reliable because, at the end of the day, you are accountable for the code you ship. If it breaks tomorrow, you will be asked questions. Plus, you should be proud of what you are shipping.

Remember, reliability is the output of asking uncomfortable questions early.

Hope this helps.

---

The AI harness matters more than the model. 

Models have gotten really good. Great reasoning, large context windows, better instruction following.

But, what makes *use* of those capabilities is actually the harness. It's what provides tools, memory, skills and context to the model.

ChatGPT is a harness. Claude Cowork is a harness. 

Without the harness, the model is just an engine with no car. You don't get anywhere.

---

The more I build agentic systems at Razorpay, the more I understand that - at its core, it is an agentic loop with tool calls, integrations, and retrieval. The hard part is...

actually making it run reliably, at scale, under real production load. And this is what makes system design even more important.

Your AI system is still expected to scale. It will still need microservices, message queues, consistency guarantees, load balancing, work distribution, state management, rate limiting, throttling, fallbacks, service-to-service communication, QoS, etc.

It is great that you are looking into AI and are interested. You should be. Everyone should be. But it is important not to skip system design and cs fundamentals. I know it seems overwhelming, but it is what it is.

First principles are not going anywhere, and that is super essential to actually build applied AI systems and run them reliably at scale. If you are a backend engineer and are kind of skipping these things, pause and reflect once.

It is always good to be great at system design, not because it will help you crack interviews (it will), but because it will make you meaningfully better at your job. Seeing it firsthand.

Remember, you will not be shipping prototypes to production. The difference between prototype and production code is 15 components and 1000 commits.

Hope this helps.

---

Now that I am working on full-fledged AI systems at Razorpay and building them from the ground up, two things are pretty clear...

1. The workflow of AI systems is genuinely different.

You have to think AI first from the start - how execution flows, how skills are composed and invoked, sub-agent orchestration, active and passive evals, etc. The only way to develop that intuition is to build a lot of prototypes and know SDKs and patterns inside out. Reading about it does not get you there.

2. System design and low-level design are more crucial than ever.

The harness around these systems demands serious system design, no exaggeration here. Features like pause and resume workflows, serving, checkpoints, pipelines, sync async invocations, observability, cost tracking, versioning, rate limiting, quota management - just to make your long-running executions work without hiccups at any scale is a super interesting challenge.

Apart from this, the importance of low-level design is very high because of extensibility, and over-abstraction - that we all joke about - is actually super critical. Think of external systems that you connect to for your workflows, downstream systems that need to interface and fall back from one system to another, etc.

To be honest, I am not as AI-pilled as some of the other folks in the org, but I am getting there :) And it has been an insane learning curve. But yes, building production AI applications is so much fun.

There is a lot to learn. That part never changes.

---

AI agents will retry. They will always retry. Given how long-running agentic loops are, network drops, timeouts, machines rotate, and rate limits kicking in are just part of the deal.

What breaks in production is not the model, but the plumbing around it. Some gaps worth noting...

First - A half-dead (slow and stalled) API can hang an entire agent chain. So, every tool call should have a hard timeout, and when it fires. This way, the agent fails loudly instead of waiting indefinitely.

Second - A retry here and there is fine (and essential). But if a downstream tool is actually down and you keep hammering it, you burn through your quota for nothing. So, have a backoff on failure, then trip the circuit after a run of n consecutive failures, then probe again later. Do not retry blindly into a dead service.

Third - If the process dies halfway through a long task, can it pick up from where it stopped, or does it start over from scratch? That only works if each step's progress is written somewhere durable, not just kept in memory.

Fourth - Tracing. Once an agent is chaining multiple steps, "something felt slow" is not debuggable. You need to see exactly which step took eight seconds instead of two.

None of these four are hard on their own. We have all done this while designing traditional systems, and those practices are not going anywhere :) We just need to pack them together in one system.

That is really the bar for production readiness. You do not need a smarter model; you need a rock-solid harness and plumbing around your agentic loop. Everyone loves a reliable system.

Hope this helps.

---

Agents are not just writting code but they are writing tons of testcases as well, and we will have order of magnitude large number of testcases going forward as verification layers will be the key to ship code autonomously to production.

Having a faster CI layer will be key - we will want testcases to run faster we don't want agents/human to be waiting for hours just to finish running testcases.

---

End-to-end tests do not work at scale, nor does staging infrastructure. Past a certain number of services, both turn into a liability, and a big one at that. It is nearly impossible to run a "company-in-a-box" environment at scale.

Staging is meant to be a smaller, calmer copy of production. In practice, it becomes its own fragile system. A shared database, shared services, and everything around them all need to be up, on the right version, and in the right state at the same time.

Running tests across services on top of that staging infrastructure is even more fragile. Test for service A now depends on service B being deployed, service C having the right data, and the staging database not being mid-migration because of someone else's change.

One flaky service and the whole suite goes red, for a reason that has nothing to do with the code being tested.

When that happens, nobody owns the failure, and it somehow becomes the responsibility of a central team (most likely DevOps, SRE, or Platform. Yesss... been in the same situation a decade ago).

What works instead is each service owning its own tests and mocking the responses of the services it depends on. No shared staging database. No waiting on five other teams to deploy before you can run a single test suite.

This gives you a clear separation of concerns. A service is responsible for its own contract and its own correctness, nothing more. Cross-service behavior gets verified through contract tests between two teams, not through a shared environment that everyone touches and no one owns.

It also shifts accountability to the left because there is no one to blame. If a mock does not match reality, that is a contract problem between two teams, caught early by the team that owns the code.

Fewer moving parts, less shared infrastructure to babysit.

I now believe this is a problem every single company struggles with, and there is probably a billion-dollar business to be built solving it :)

Hope this helps.

---

I was skimming through Microsoft's SUTRADHARA paper, and here are two best practices for agent latency that you might find helpful...

One of the underrated latency improvements during a tool call is to dispatch the tool call before the provider stream ends.

A model can emit a complete tool call while it is still streaming later calls or text, so waiting for the whole message turns two independent clocks into one serial clock.

SUTRADHARA, a paper from Microsoft, does exactly this, dispatching tool calls incrementally during decoding, and it cuts end-to-end latency by 10%.

The second is treating tool schemas and results the way you would treat any oversized dataset: do not load it all up front.

Represent deferred tools with compact searchable metadata and hydrate the real schema only when selected. Cursor reported a 46.9% reduction in total agent tokens after moving to this kind of dynamic context discovery.

Hope this helps.

---

If you are building self-improving agents that rewrite their own skill files or prompts, then you are prone to the classic Ship of Theseus problem.

Every self-edit replaces one more "plank" of the original spec, and after enough edits, you cannot tell if the agent is still doing the job it was built for.

The failure mode is drift.

The agent does not crash or throw errors. It also keeps updating checks along the way. Each patch looks fine in isolation, but when you look at it after `n` iterations, you see it might have just drifted from the original task.

Here are a few guardrails that would help:

1. Keep an immutable core spec separate from the mutable parts. Let the agent edit examples and phrasing, never the goal or constraints.

2. Diff every edit against the original spec, not just the previous version. Comparing to the last state only hides compounding drift.

3. Version every edit like a commit, with a rollback path to any earlier version.

We should not stop agents from improving, but do make sure the task's identity is retained; the same reason that Ship of Theseus is only interesting because we care whether it is still the same ship.

Hope this helps.

---

do smart things

One does nothing but ask how to make everything ten times better. Another just watches the other agents work and flags where they get stuck.

---

One pattern I observed while building self-improving multi-agent systems is that "self-reflecting" agents are not enough. You need an observer agent.

Worker agents focus on the particular task at hand.
- Product agent wants to shape the product.
- Architect wants to finish the architecture.
- Implementation agent wants to make the code work.

But in multi-agent systems, important failures happen between stages and during agent handoffs. These self-reflecting agents will not be able to capture that because they are focused on their local task. They will not think from the perspective of optimizing the entire workflow.

Examples:
Why did options collapse into a generic approval?
Why did implementation start before the workflow was complete?
Why did the same validation issue show up again?

The agent doing the task is biased toward task completion. We need a separate observer agent that monitors the entire workflow.

A separate learning agent can then extract learnings and classify them -
Update memory?
Process learning?
Missing skill?
Eval gap?

And then an evolution agent, after approval, can go and modify the workflow based on the feedback.

What I found is that the learnings/issues identified in a run using this flow are 5 times more than what the earlier setup without an observer agent was identifying.

The most important failures in multi-agent systems are often not inside an individual agent. They happen in the coordination between agents.

---

An AI coworker has to understand, investigate, act, verify, and close the loop — across multiple systems, policies, and tools.

the future of enterprise AI isn’t just about the smartest model. It’s about the system around the model.
Orchestration. Context. Policies. Tool use. Verification. Memory. Human oversight.

---

Most teams building AI agents are solving the wrong problem.

Harness, Loop, or Graph?

They sound similar, but each solves a completely different layer of agent reliability.

→ Harness: what the agent can do
→ Loop: how it learns from feedback
→ Graph: what happens next

I broke down when you actually need each one and why adding more orchestration often doesn’t fix the real problem.

If you’re building agents, this framework will save you a lot of unnecessary complexity.

---

The people who understand this shift early will build software very differently over the next few years.

This piece explains why the conversation is shifting from prompts → loops → graphs, and why the biggest bottleneck is no longer the models it's how they coordinate.

---

The problem is not prompt quality alone.
The hard part is building the system around the model:
High-quality context pipelines
Retrieval and ranking over large codebases
Eval harnesses for accuracy and regressions
Tool orchestration and agent runtime reliability
Observability, latency, and cost controls
Codebase knowledge graphs that capture real architectural context

A big part of this work is building Swiggy’s codebase knowledge graph so agents can reason better about services, APIs, data flows, dependencies, and implementation patterns.

---

LLMs have learned from millions of software projects. That gives them an incredible ability to recognize common engineering patterns.

But architecture isn't just about common patterns. It's about making trade-offs for a specific company, team, product, and set of constraints.

Those trade-offs rarely exist in the training data.

That's why I think experienced engineering judgment still matters most when designing a system's core architecture.

---

𝗠𝗼𝘀𝘁 𝗮𝗿𝗰𝗵𝗶𝘁𝗲𝗰𝘁𝘂𝗿𝗲 𝗱𝗶𝘀𝗰𝘂𝘀𝘀𝗶𝗼𝗻𝘀 𝗮𝗿𝗲 𝗺𝗶𝘀𝘀𝗶𝗻𝗴 𝘁𝗵𝗲 𝗺𝗼𝘀𝘁 𝗶𝗺𝗽𝗼𝗿𝘁𝗮𝗻𝘁 𝗶𝗻𝗴𝗿𝗲𝗱𝗶𝗲𝗻𝘁: 𝗰𝗼𝗻𝘁𝗲𝘅𝘁.

It's easy to look at a system diagram or codebase and declare:

 • "This is bad architecture."
 • "Why didn't they use microservices?"
 • "This should have been event-driven."

Before judging a system, ask:

 • What stage was the company in?
 • What was the time-to-market pressure?
 • How many engineers were available?
 • How long was the software expected to live?
 • What business problem needed to be solved?

A startup fighting for survival and a mature platform serving millions of users should not make the same architectural decisions.

Not all software is built for the same lifespan either.

𝗦𝘆𝘀𝘁𝗲𝗺 𝘀𝗼𝗳𝘁𝘄𝗮𝗿𝗲 - databases, operating systems, foundational libraries- has a high cost of change and needs careful long-term design.

𝗕𝘂𝘀𝗶𝗻𝗲𝘀𝘀 𝘀𝗼𝗳𝘁𝘄𝗮𝗿𝗲 lives under different constraints: shipping fast, validating ideas, serving customers, and adapting as the business evolves.

Great architects understand this distinction.

Architecture is not about applying design patterns everywhere. It's about making the right trade-offs given the reality on the ground.

𝗧𝗵𝗲 𝗯𝗲𝘀𝘁 𝗮𝗿𝗰𝗵𝗶𝘁𝗲𝗰𝘁𝘂𝗿𝗲 𝗶𝘀𝗻'𝘁 𝘁𝗵𝗲 𝗺𝗼𝘀𝘁 𝗲𝗹𝗲𝗴𝗮𝗻𝘁 𝗼𝗻𝗲. It's the one that was right for the business, the team, and the moment in time.

---

Google DeepMind researchers introduced a technique called 'Recirculation' that improves LLM architecture at inference time without retraining them.

Recirculation introduces a specific form of recurrence that feeds information from deeper transformer layers back into shallower layers, helping the LLM dynamically maintain and update an internal belief state.

On Gemma 3, the method reduces perplexity by 23%, achieves 21% higher accuracy on GSM8K, and improves performance across multiple downstream tasks.

This is all done while keeping the original model weights frozen and adding essentially no additional latency during generation (though it requires serial processing during the prefill phase).

---

Today I built something I’ve been wanting to understand properly for a while:

The complete lifecycle of a fine-tuned LLM — from fine-tuning → serving → benchmarking.

I didn’t want to fine-tune a model and stop at “training completed.”

I wanted to understand what happens after the model is trained.

Here’s what I put together:
 1. Fine-tuning - Unsloth AI
Fine-tuned the model and generated quantised artefacts, including GGUF weights, tokeniser configurations, and chat templates.
 2. Serving - vLLM
Served the model locally through an OpenAI-compatible API, with API-key protection and GPU memory configuration.
 3. Benchmarking - multiple layers
→ lm-evaluation-harness for standard capabilities
→ EvalPlus for coding correctness
→ Custom Python evaluation scripts against my local vLLM endpoint

What I’m realizing while learning this:
Training the model is only one piece of the engineering problem.

A model isn't really useful until you can train it, package it, serve it, measure it, and iterate on it.

Next: digging deeper into inference performance, quantization, and evaluation.

---

i have been thinking about this for years.... and finally have a good direction.

What does a "turing complete" context system for agents look like?

I truly believe our architecture at supermemory is the right abstraction for context. Supermemory supports:
- Handling ingestion queues and parsing etc.
- Contextual Retrieval
- Dreaming & learning (customizable)
- Profiles & Custom 'buckets'
- SQL-like filtering for multi-agent and permissioning
- Filesystems (for coding, research agents etc)
- use it via API, MCP, CLI, Plugins, however you want.

---

Anthropic engineer nailed it:

“You’re not supposed to prompt Claude. You’re supposed to build a system that prompts itself.”

One of the clearest breakdowns of real agent systems I’ve seen.

In just 30 minutes, Anthropic’s Member of Technical Staff breaks down how to build agents that actually improve:

→ The evolution from basic CLAUDE .md files to agents writing their own memory
→ Why in-band memory hits hard limits, and splits focus at scale
→ How “dreaming” lets agents review sessions, learn from mistakes, and get smarter between runs
→ The production guardrails (versioning, concurrency) that make self-improving systems work

Coupled with this Loop Engineering Guide, you will never prompt Claude the same again: https://lnkd.in/dVW6TGiB

---

AI coding agents made writing code cheap. Producing correct code at scale is still unsolved: you either pore over every change and go slow, or vibe-code and ship slop.

Amika gives each agent its own cloud computer and lets users build automated or human-in-the-loop workflows for agents to write code and prove it's correct. A few things it can automate:

- Monitor production and auto-fix errors, with a test proving the fix against your real app
- Ship customer feature requests straight from a shared Slack channel, and hand back a live preview

Every change runs against deterministic guardrails, so you can guarantee the behavior of your agents and their code.

---

Over the last few months, while using coding assistants more heavily, I noticed myself repeatedly correcting the same kinds of mistakes. Not necessarily because the models were bad, but because some engineering habits are difficult to infer from a prompt.

Things like:
- Making assumptions when requirements are ambiguous
- Refactoring code outside the requested scope
- Optimizing before establishing a bottleneck
- Missing failure paths and edge cases
- Claiming something works without actually verifying it

I started collecting these observations as a set of rules and checks.

The result is , an Agent Skill for Claude Code.

A few things it tries to do:
- Adapt its behavior based on whether it's writing new code, refactoring existing code, or reviewing code
- Evaluate changes through lenses such as performance, scalability, modularity, concurrency, and memory usage
- Consider reliability and security during design rather than as a final review step
- Avoid declaring success without running the command that validates it
- Structure reviews around WHAT, WHY, and FIX

There is nothing particularly novel here.

A lot of the ideas are adapted from public discussions around LLM-assisted coding, including observations from people like Andrej Karpathy, combined with lessons learned from years of building and operating systems in production.
I've simply tried to capture them in a form that a coding assistant can consistently apply.

The project is not relatively big (~30K tokens), and easy to load into everyday workflows.

---

I don't know why. but everyone thinks of the word "Memory" as just retrieval. They are NOT the same thing!

"Retrieval" is finding something relevant from a store of documents or chunks or knowledge. It's usually a natural search. You have a query, you have a corpus, you return the most relevant results. Vector search, BM25, whatever approaches - these are retrieval.

Memory is something else. Memory is the process by which an agent builds and maintains a durable understanding of the world it operates in -the user it serves, the tasks it has completed, the facts that have changed. 

Memory involves writing, not just reading. It involves knowing what to forget, not just what to store. It involves updating beliefs when new information contradicts old ones - and inferring from what we already know. Retrieval is a component of memory, but it is not the whole thing.

most of the things about "AI Memory" are really about retrieval. 
