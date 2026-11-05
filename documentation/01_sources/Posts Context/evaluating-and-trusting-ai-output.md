# Evaluating and Trusting AI Output

My team is probably going to kill me for posting this.

Even with state-of-the-art LLMs, speech-to-text can produce outputs that make absolutely no sense. In this case, it somehow decided that an English response should be transliterated into Hindi...for absolutely no reason.
This is exactly why building AI products feels fundamentally different from building traditional software.

In traditional systems, we worry about latency, CPU utilization, memory, and 2XX, 4XX, and 5XX response codes. Those are objective metrics. They tell you whether the system is behaving correctly.

LLMs don't have that luxury.

An answer can return HTTP 200, execute perfectly, and still be completely wrong.

Now you're dealing with subjective quality, relevance, grounding, hallucinations, language consistency, safety, and finally, user intent. The number of possible failure modes isn't just large, it's practically infinite.

That's why observability and evaluation become first-class citizens of the product. You need automated evaluation pipelines, semantic similarity metrics, LLM judges, and increasingly, humans in the loop to determine whether your AI is actually doing the right thing.

The hardest part of building AI isn't getting the model to answer.

It's knowing whether the answer can be trusted.

---

If you're an engineer visiting the Wispr office, odds are that within an hour you'll hear our Chief Science Officer, Ariya Rastrow, say:

“Evaluate, evaluate, evaluate.”

But what does this mean in practice?

Without evaluations, everyone relies on individual opinions to make decisions. There's no way to systematically improve something that's opinion-based. Unless you set up clear evaluations that capture the real-world cases you want to improve, you're never going to consistently get better.

Vibes can get you from zero to one. Even the first version of Claude Code was built without evals. But to scale, everyone needs to know what they're working toward.

Evals should measure different things:

- Challenging scenarios: These represent your biggest opportunities for improvement. Once an eval reaches a 5% error rate, your model starts to saturate on it. Find the domains where the error rate is 30%, and things will start improving rapidly.

- Regression testing: Your evals should also include slices where the model already works well. These function similarly to unit tests or integration tests, ensuring that new changes don't break existing capabilities.

- Slices and subpopulations of your data: Measure performance across different cohorts. One example for Wispr is accents: your model might improve overall but get far worse for Indian-accented English. If your evals measure those categories, you can verify that your changes are improving the model as expected without harming performance elsewhere.

That's how you can have a team of 10 people working on improving the same model. One person might work on RL, another on SFT, and another on balancing data for new languages. Every time someone ships an improvement, they know it hasn't created side effects elsewhere—and everyone can confidently merge their changes.

Evals are key both to building better products for customers and to enabling teams to work together.

---

A few months ago, I started going deeper into LLM evaluation.

And I realized something uncomfortable: Building an LLM application is only half the job.
The harder part is knowing whether it’s actually getting better.

For deterministic software, we can write tests.

But with LLMs, the same question can have many valid answers. So how do you evaluate them?

I’ve been learning DeepEval, an open-source framework that uses LLM-as-a-judge alongside other evaluation approaches.

A few things to know:
→ Correctness: Is the answer actually right?
→ Answer relevance: Did the model answer the question, or add unnecessary noise?
→ Faithfulness: Does the response stick to the retrieved context?
→ Conversation quality: Is the interaction professional and appropriate?

What I found especially interesting is that you can build custom metrics and evaluation datasets, then automatically compare different models on your specific task.

That changes the question from:

"Which model is better?"

to:

"Which model performs better for MY application?"

I’m still learning this space and sharing what I learn along the way

---

LLMs are probabilistic. Credit decisions shouldn’t be.

We dug into the research on making LLM-based systems and foundation models reliable enough for financial decisioning.

Don’t try to make the model deterministic. Instead shrink the surface area where probabilistic judgment is allowed:
- Use LLMs to interpret messy information. 
- Make the facts explicit and validate them. 
- Let deterministic code execute the credit policy.
https://www.kita.ai/blog/deterministic-decisioning-llm-research
