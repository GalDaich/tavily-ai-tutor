# Core Implementation and Verification

## 2026-08-17 — Implementation request

The AI Tutor design was approved for implementation. The user reiterated that the final handoff must state precisely which provider and LangSmith environment variables belong where.

## Implemented scope

The repository now contains one complete local application path:

- `ai_tutor.py`: Typer CLI, LangChain agent, Nebius model, bounded Tavily retrieval, per-run source registry, citation validation, deterministic source rendering, visible failures, and LangSmith run configuration.
- `tests/test_ai_tutor.py`: deterministic tests using an injected fake search backend; no provider calls are made by the suite.
- `pyproject.toml` and `uv.lock`: declared and locked Python dependencies.
- `.env.example`: required provider variables plus the standard LangSmith tracing configuration.
- `README.md`: clean-clone setup, run, verification, and trust-boundary instructions.
- `TECHNICAL_STATEMENT.md`: the brief approach and value statement required by the assignment.
- `DESIGN.md`: the approved product and architecture contract.

## Grounding implementation

The agent must call a single custom `search_ai_sources` tool before answering. The tool wraps `TavilySearch` with these fixed bounds:

- advanced search;
- at most five results per search;
- at most two searches per tutor run;
- no raw page content;
- usage metadata enabled.

Each valid result URL receives a stable ID such as `S1`. Duplicate URLs reuse their existing ID. The model sees compact ID/title/URL/snippet records and cites only IDs. After the agent returns, deterministic code requires the `Answer`, `Explanation`, and `What to remember` headings, at least one known source ID, no model-authored URLs, and no model-authored Sources section. Only then does code append titles and URLs for the cited IDs.

This validates citation provenance and presentation structure. It deliberately does not claim to prove that a cited passage semantically entails every generated sentence; that remains a documented human-review step for the live samples.

## Observability implementation

Each invocation creates one UUID and passes it to the LangChain run as `run_id`, with:

- run name `ai-tutor-answer`;
- tags `ai-tutor` and `cli`;
- selected-model metadata;
- the run ID printed on both success and failure paths.

LangSmith tracing uses its standard environment variables. When tracing is explicitly enabled, missing API-key or project configuration fails at startup. The CLI waits for pending LangChain tracers before exit so the short-lived process does not intentionally abandon trace delivery.

## Iteration evidence

- The first sandboxed `uv lock` attempt could not resolve PyPI DNS. Repeating the authorized dependency operation with external network access succeeded; 70 packages resolved and 67 installed into `.venv` using Python 3.12.13.
- The first sync warned that an unused console entry point would require packaging configuration. The entry point was removed because the documented interface is `uv run ai_tutor.py`; no build backend was added.
- The first lint pass found line-length issues. Ruff formatting plus a small prompt-wrap edit resolved them.
- The first test collection could not import the root module under the installed pytest behavior. Adding the repository root to pytest's configured `pythonpath` made the intended single-file module explicit.
- A CLI verification command initially used zsh's reserved `status` variable in its shell harness. The harness was corrected to `task_exit`; application code was unaffected.

## Verification evidence

The final local checks completed successfully:

```text
uv lock --check
Resolved 70 packages

uv sync --locked
Checked 67 packages

uv run ruff format --check .
7 files already formatted

uv run ruff check .
All checks passed!

uv run pytest
12 passed

uv run python -m py_compile ai_tutor.py tests/test_ai_tutor.py
passed

git diff --check
passed
```

The real CLI help screen rendered with its required AI question and optional Nebius model. Running without provider variables exited with status 1 and named both missing variables. Running with placeholder provider variables and tracing enabled exited with status 1 before any provider call and named the missing LangSmith API key and project.

## Requirement-to-evidence check

| Assignment expectation | Current evidence |
| --- | --- |
| Meaningfully improve the starter | AI Tutor workflow, bounded retrieval, deterministic citation provenance, explicit failure behavior |
| Create technical or business value | Current, cited explanations for developers and technical learners |
| Use or align with tracing standards | LangSmith-native run ID, project, tags, metadata, and tracer flush |
| Prefer simplicity and quality | One CLI, one model, one tool, no persistence or extra services |
| Provide a technical statement | `TECHNICAL_STATEMENT.md` |
| Provide the build record | Numbered Markdown entries in `build_log/` |
| Exclude the supplied starter | The entire supplied assignment directory remains Git-ignored |

## Honest remaining live evidence

No local `.env` or provider credentials were available during implementation, so no Tavily search, Nebius answer, or LangSmith trace has yet been claimed. The deterministic implementation and failure boundaries are verified; the three documented live questions and their trace review remain pending until the user adds credentials locally.
