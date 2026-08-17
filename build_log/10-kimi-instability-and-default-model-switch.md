# Kimi Instability and Default Model Switch

## 2026-08-17 — Repeated live failure

LangSmith trace `01a01170-41ee-7fe0-9657-3d575bd57545` failed on revision `d375594`, after the explicit Kimi reasoning and token-budget settings had already been removed. The trace showed:

- exactly one successful basic Tavily request;
- five returned sources and one consumed credit;
- a successful Kimi tool-selection turn;
- a post-tool Kimi response with `finish_reason: stop` and 367 completion tokens;
- empty visible content, causing the CLI to reject the run.

This disproved the earlier conclusion that the explicit token settings were the root cause. Kimi K2.6 itself is intermittent in this post-tool path through the current Nebius and LangChain integration.

## KISS decision

The implementation does not add model retries, parse provider reasoning as a user-facing answer, or introduce fallback routing. Instead, it changes the single default to `Qwen/Qwen3-30B-A3B-Instruct-2507`.

Nebius's live model catalog identifies this model as supporting tools, JSON mode, and structured output without reasoning mode. Four consecutive full LangChain-agent fixture runs each made one tool call and returned non-empty lessons with the required headings and valid citations.

The `--model` option remains available for deliberate experiments, but the documented and tested submission path uses only the Qwen default.

## Operational acceptance

The exact CLI command passed end to end with the Qwen default. LangSmith trace `01a01173-4109-70d0-bf65-c1f25f51c99e` returned a non-empty lesson with the required headings and validated citations. The CLI exited successfully and reported one basic Tavily search, five sources, and one consumed credit. The same UUID appeared as the CLI run ID, LangSmith trace ID, and thread ID.

The final deterministic suite contains 23 passing tests, including a regression assertion that pins the exercised non-reasoning default model. Ruff formatting, lint, Python compilation, and Git whitespace validation also passed.

This checkpoint established end-to-end operability, not automatic semantic entailment. Entry 11 records the final human review of the release-model samples.
