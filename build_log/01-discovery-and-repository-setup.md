# Build Log

This is the ongoing record of how the Tavily FDE take-home submission was built. It records prompts, decisions, implementation changes, and verification evidence. It is intentionally updated throughout the project rather than reconstructed at the end.

## 2026-08-17 — Discovery and repository setup

### Starting request

Build the leanest high-quality response to Option 1 of the supplied Tavily FDE take-home assignment. The submission should meaningfully improve the starter agent, explicitly add LangSmith observability, consider a customer-specific workflow and context engineering, preserve the supplied assignment folder only as local reference material, and maintain this Markdown build record as deliverable 3.

### Assignment constraints extracted

- Improve the existing Tavily + LangChain CLI in a way that creates clear technical or business value for a real user.
- Deliver a GitHub repository without the supplied `starter_agent.py`.
- Include a brief technical statement and a shareable build record.
- Optimize for a focused, verified result that fits an estimated 4–6 hour scope.
- Demonstrate sound AI engineering; unverified model output is explicitly penalized.
- Tracing and observability are bonus criteria.

### Starter-agent inspection

The supplied program is a Python 3.11+ single-file CLI using:

- LangChain `create_agent`
- Nebius `ChatNebius` with the default `moonshotai/Kimi-K2.6` model
- the official `langchain-tavily` `TavilySearch` tool
- Typer and Rich for a streaming console interface
- `.env` loading and explicit checks for Tavily and Nebius credentials

It already streams model text, tool-call arguments, and formatted Tavily results. Its main limitations are product-level rather than presentation-level: it is a generic research assistant, has only prompt-level citation instructions, does not verify answer citations against retrieved sources, does not expose a stable quality contract, and has no trace metadata or repeatable evaluation.

### Runtime evidence

- `uv 0.12.5` is available.
- The script's declared dependencies resolved and 63 packages installed successfully using a temporary uv cache.
- The Typer help command rendered successfully and exposed the required question plus optional model.
- Python byte-compilation succeeded.
- A real invocation reached the application's credential gate and exited with the documented `Missing TAVILY_API_KEY` message.
- No Tavily, Nebius, or LangSmith credentials were present in the process environment, and no local `.env` file was found. Therefore, no live search/model answer or LangSmith trace has yet been claimed.
- The resolved inspection versions were LangChain 1.3.15, `langchain-nebius` 0.1.3, and `langchain-tavily` 0.2.18.

### Repository setup

- Initialized an empty Git repository on branch `main`.
- Added a root `.gitignore` that excludes the entire supplied `2606_Tavily_FDE_TakeHomeAssignment_v2/` directory, local secrets, Python caches, coverage output, and common editor/OS artifacts.
- Verified with `git check-ignore` that both supplied files are excluded.

### Initial architectural recommendation

The recommended submission is a **customer support research brief** for technical support engineers or FDEs handling a time-sensitive integration question. It should retain one agent and one Tavily search tool, then add three narrow improvements:

1. A workflow-specific response contract: answer, evidence, uncertainty, and next diagnostic steps.
2. Deterministic citation validation against URLs returned by Tavily, with an honest failure if the model cites an unobserved source.
3. LangSmith tracing with a named project plus per-run metadata, accompanied by a small fixture-based evaluation suite.

Deep Agents skills are not included in the recommended first slice. A single-purpose CLI does not yet have enough optional procedural context for progressive disclosure to offset the additional framework, filesystem, and testing surface. That decision can be revisited only if a second genuinely distinct customer workflow is approved.

### Pending decisions and verification

- Confirm the recommended support/FDE workflow or select an alternative workflow before implementation.
- Obtain or configure Tavily, Nebius, and LangSmith credentials for live end-to-end verification.
- Define the exact response schema and minimal evaluation cases before writing production code.
