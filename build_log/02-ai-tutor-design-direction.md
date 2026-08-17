# AI Tutor Design Direction

## 2026-08-17 — Follow-up instructions

The customer-support workflow proposed during discovery was challenged and replaced with an on-demand **AI Tutor**. The agent should answer AI-related questions as a trusted tutor while retaining the previously approved improvements around LangSmith tracing, grounded evidence, clear uncertainty, and evaluation.

The user explicitly set two constraints:

1. Follow KISS principles. This is a small take-home assignment and must not be made clever or over-engineered.
2. Replace the single root build log with a `build_log/` directory containing a separate numbered Markdown file for each meaningful step in the engineering session. The first entry must preserve the existing build log; this file must record the new instructions and decisions.

## Decisions made

### Product promise

The product will be a single-turn CLI tutor for AI and machine-learning questions. It will give a direct explanation, teach the underlying idea, provide an example when useful, identify material uncertainty, and cite current evidence.

“Trusted” will not be implemented as an unsupported claim that the model knows everything. It will mean:

- every substantive answer performs Tavily retrieval;
- the tutor prefers primary sources such as official documentation and research papers;
- cited source identifiers must come from the current run's Tavily results;
- deterministic code renders the corresponding source titles and URLs;
- missing evidence, invalid citations, and provider failures remain visible rather than being replaced with an ungrounded answer.

### Simplest useful architecture

Retain the starter's basic shape: one Python CLI, one LangChain agent, one Nebius chat model, and one Tavily-backed search tool. Add only a small search-session wrapper, citation validation, LangSmith run configuration, and tests.

There will be no UI, database, vector store, conversation persistence, multi-agent workflow, subagents, or Deep Agents skills in the initial implementation.

### Tutoring response contract

The tutor will produce:

1. A direct answer.
2. A concise explanation with inline source IDs such as `[S1]`.
3. A practical example when it improves understanding.
4. A short “What to remember” takeaway.
5. Material uncertainty or disagreement, only when relevant.
6. One optional check-your-understanding question.

The model will not author final source URLs. The CLI will append a Sources section from the validated source registry.

### Retrieval and grounding

- Every substantive AI answer must use Tavily at least once.
- Each Tavily result receives a stable source ID within the run.
- The model sees compact source records containing ID, title, URL, and snippet.
- A response with no citations, an unknown citation ID, or no usable retrieved sources fails validation.
- Validation proves citation provenance, not semantic truth. Semantic support will be checked in a small reviewed live evaluation rather than hidden behind another model call.

### Observability

- LangSmith tracing is enabled through its standard environment variables.
- Each invocation receives one run ID, a stable run name, tags for `ai-tutor` and `cli`, and small metadata fields such as the selected model.
- The CLI visibly reports whether tracing is enabled and prints the run ID for correlation.
- If tracing is explicitly enabled but misconfigured, startup fails clearly. If tracing is not enabled, the tutor may run with an explicit warning.

### Evaluation

Keep evaluation local and legible:

- fixture-backed tests for source normalization and citation validation;
- failure-path tests for missing credentials, empty search results, and invalid citations;
- a few fixed live questions covering a foundational concept, a current topic, and a nuanced misconception;
- manual review that each live answer is clear and that its cited snippets actually support its claims;
- record the exact live results and LangSmith trace evidence in a later build-log entry.

No LLM-as-judge or hosted evaluation pipeline is planned for the first version.

## Next engineering step

Implement the smallest vertical slice: configuration, one normalized Tavily tool, one agent run, deterministic citation validation, and one fixture-backed happy-path test. Stop and verify that slice before adding the remaining documentation and evaluation cases.
