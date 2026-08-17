# Live Key Regression and Model Revert

## 2026-08-17 — Fresh-key acceptance run

After configuring a fresh Tavily key, the exact acceptance command reached both providers:

```bash
uv run ai_tutor.py "Does temperature zero make an LLM fully deterministic?"
```

LangSmith trace `01a0116a-529b-70c1-941f-7878a7b01a88` showed one successful basic Tavily request, five returned sources, and one consumed credit. The shared run, trace, and thread ID was present throughout. The CLI still failed because Kimi's post-tool turn reported completion tokens and `finish_reason: stop` but returned empty visible content.

## Root cause and KISS correction

The retrieval change was working as designed. The regression came from two model settings added in the same change: low reasoning effort and a 2,048-token output budget. Raw Nebius diagnostics showed that Kimi can return provider-specific reasoning text while leaving visible `content` empty, and the explicit settings did not make that behavior reliable.

A no-Tavily regression check reused the successful trace evidence and restored the starter's original model construction: `ChatNebius(model=model_name, streaming=False)`. That produced a 1,581-character visible answer from the same post-tool context.

The implementation therefore removes only the two model overrides. It keeps the actual KISS retrieval fix: one basic Tavily request, one-credit normal cost, deterministic domain enforcement for current questions, and no retry or fallback generation path.

## Final acceptance

The exact CLI command passed after the revert. LangSmith trace `01a0116e-5873-7760-814b-12d0603540ba` produced a non-empty lesson with all required headings and validated citations. The CLI reported one search, five sources, and one Tavily credit, and the UUID matched the run ID, LangSmith trace ID, and thread ID.

The full deterministic suite also remained green: 22 tests passed with Ruff formatting and lint checks and Git whitespace validation.
