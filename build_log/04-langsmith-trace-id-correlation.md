# LangSmith Trace ID Correlation

## 2026-08-17 — Incomplete observability correction

The user identified that the LangSmith correlation setup was likely incomplete and directed the implementation back to the official LangChain/LangSmith documentation. The first correction verified the relationship between the CLI UUID, the root LangChain run, and the LangSmith trace. It did not yet address LangSmith thread configuration; that gap was subsequently corrected in the implementation.

## Verified behavior

The implementation already passed its generated UUID as `run_id` in the `RunnableConfig` supplied to the top-level `agent.invoke` call. LangSmith's documented data model defines a trace ID as the ID of the trace's root run, and the LangChain tracing documentation explicitly states that a custom `run_id` supplied at the root becomes the `trace_id`.

The installed LangSmith 0.11.0 source agrees: when a run has no parent and no explicit trace ID, `RunTree` assigns `trace_id = id`.

Therefore the existing relationship was:

```text
CLI UUID = top-level LangChain run_id = LangSmith root run id = LangSmith trace_id
```

This relationship was correct but incomplete. A root `run_id` becoming the `trace_id` does not configure a LangSmith thread. At this stage, the application had no `thread_id` metadata, still generated UUIDv4 identifiers, and had not verified thread metadata propagation to child runs.

## Explicit implementation changes

- Extracted `build_run_config` so the ID mapping has one named, testable boundary.
- Kept the UUID object as the top-level `run_id`.
- Added its string value as `cli_run_id` metadata for an additional searchable field.
- Changed success, failure, and startup output to label it `Run ID / LangSmith Trace ID`.
- Updated the README, design, and technical statement with the exact relationship and UI lookup instruction.
- Added a deterministic test that asserts the CLI UUID is used as `config["run_id"]` and duplicated exactly as `metadata["cli_run_id"]`.

## Lookup workflow

Open the `tavily-ai-tutor` project in LangSmith, filter by Trace ID, and paste the UUID printed by the CLI. The same value is also present in root-run metadata under `cli_run_id`.

## Verification

Ruff formatting and lint checks passed, `git diff --check` passed, and the expanded deterministic suite passed 13 tests.

## Completed thread correction

The user then supplied the authoritative Configure Threads documentation because the missing thread setup had not been resolved by this trace-ID-only change. The complete fix introduced UUIDv7 generation, shared run/trace/thread correlation, `thread_id` metadata, tracing-context propagation, and a deterministic test proving that the same thread ID reaches the root and child runs.
