# Tavily AI Tutor

Ask one question about artificial intelligence or machine learning and receive a concise lesson backed by current Tavily sources.

## Setup

Requirements: Python 3.11–3.14 and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env
uv sync --locked
```

Fill in `.env`:

| Variable | Required | Value |
| --- | --- | --- |
| `TAVILY_API_KEY` | Yes | Tavily API key from <https://app.tavily.com> |
| `NEBIUS_API_KEY` | Yes | Nebius Token Factory key from <https://tokenfactory.nebius.com> |
| `LANGSMITH_TRACING` | For traced demo | `true` |
| `LANGSMITH_API_KEY` | When tracing | LangSmith API key |
| `LANGSMITH_PROJECT` | When tracing | `tavily-ai-tutor` |
| `LANGSMITH_WORKSPACE_ID` | Multi-workspace keys only | LangSmith workspace ID |
| `LANGSMITH_ENDPOINT` | Regional accounts only | Your LangSmith regional API endpoint |

Do not commit `.env`; it is ignored by Git.

## Run

```bash
uv run ai_tutor.py "Why does retrieval-augmented generation reduce hallucinations?"
```

The verified default is `Qwen/Qwen3-30B-A3B-Instruct-2507`, a current Nebius model with tool support and no reasoning-only response mode. The CLI retains `--model` for deliberate experiments, but the submission exercises only this default path.

The CLI prints whether LangSmith tracing is enabled and assigns one UUIDv7 as `Run ID / LangSmith Trace ID / Thread ID`. That UUID is passed as the top-level LangChain `run_id`, so it becomes both the root run ID and the LangSmith `trace_id`. It is also propagated to root and child runs as `thread_id` metadata and stored as `cli_run_id` metadata for convenient filtering.

To find a run in LangSmith, open project `tavily-ai-tutor`, filter by Trace ID, and paste the UUID printed by the CLI. The same one-turn interaction also appears in the project's Threads tab under that ID.

The tutor remains deliberately single-turn: LangSmith thread metadata groups and measures the interaction, but the application does not persist or replay chat history.

## Verify

```bash
uv run ruff check .
uv run pytest
```

Recommended live checks:

```bash
uv run ai_tutor.py "What is retrieval-augmented generation?"
uv run ai_tutor.py "What changed recently in how AI agents are evaluated?"
uv run ai_tutor.py "Does temperature zero make an LLM fully deterministic?"
```

For each live answer, confirm that its cited snippets support its claims and that the matching run appears in the configured LangSmith project.

## Trust boundary

Every substantive answer must retrieve Tavily sources. Retrieved URLs receive stable IDs such as `[S1]`; the model cites those IDs, deterministic code rejects missing or invented IDs, and the CLI renders the final URLs. This proves citation provenance, not semantic truth, so the recorded sample runs also require human review.

Each run permits exactly one basic-depth Tavily search with at most five results. Basic search normally costs one Tavily API credit; see [Tavily Credits & Pricing](https://docs.tavily.com/documentation/api-credits).

For questions containing current-time language such as “recent” or “latest,” the run supplies a compact first-party AI and research-domain filter. Returned URLs are checked against that filter before the model can cite them.

Provider failures—including Tavily plan-limit messages—empty retrieval, off-domain retrieval, and invalid citations are reported directly. The tutor does not substitute an ungrounded fallback answer.

See [DESIGN.md](DESIGN.md) for the architecture and [build_log/](build_log/) for the engineering record.
