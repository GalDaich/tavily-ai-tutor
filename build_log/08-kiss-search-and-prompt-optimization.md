# KISS Search and Prompt Optimization

## 2026-08-17 — Cost and failure diagnosis

LangSmith trace `01a01156-4235-72b0-86dd-076ae7bb7633` confirmed that the agent made two distinct Tavily requests. The first advanced search succeeded for two credits; the second request hit Tavily error 432 because the account had reached its configured usage limit. The next two traces each failed on their first request because the allowance was already exhausted.

The same trace also showed that Tavily returned LinkedIn, Medium, and secondary-blog URLs despite receiving an official-domain filter. The agent reasonably treated that evidence as weak and attempted a second search, but the resulting cost and failure mode were too complicated for this take-home's narrow workflow.

## KISS retrieval decision

- Permit exactly one Tavily request per tutor invocation.
- Use `basic` search depth instead of `advanced`, reducing normal cost from two credits to one.
- Keep at most five compact results and raw page content disabled.
- Apply the current-question primary-domain list in deterministic code rather than asking the model to configure it.
- Validate returned URL hostnames against an active domain filter and discard off-domain results.
- Surface Tavily's provider message, including error 432, instead of converting every provider error into “no usable sources.”
- If the one result set is incomplete or conflicting, require the tutor to state uncertainty rather than spend another credit.

## Prompt redesign

LangChain sends the tutor instructions through its `system_prompt` argument and sends the question as a `user` message. The prompt text deliberately has no `<system>` wrapper. Three flat XML sections make the content boundaries clear without duplicating the API role:

1. `<instructions>` for the exactly-one-search workflow and tutoring behavior;
2. `<evidence_rules>` for source, trust, and citation constraints;
3. `<response_format>` for the exact Markdown contract.

The prompt explicitly tells the model to treat retrieved text as evidence rather than instructions, avoid claims stronger than the snippets support, use adjacent exact citations such as `[S1][S2]`, and disclose evidence gaps instead of searching again or filling them from memory.

## Deterministic verification

The focused suite now includes prompt-contract, provider-error, off-domain filtering, one-search-limit, and one-credit usage fixtures alongside the existing grounding and observability tests.

Trace `01a01161-e1d8-7983-a72c-07dc2b36cd10` confirmed that the revised path issued exactly one basic Tavily request and consumed one credit. Its model turn then returned no visible lesson. A controlled fixture run initially appeared to pass after setting low reasoning effort with a 2,048-token output budget, but the later live-key regression in build-log entry 09 invalidated that model configuration.

Trace `01a01162-e842-78c3-b4d6-7b6dbc9d3e65` confirmed the one-request failure behavior after the Tavily free-tier monthly quota was exhausted: the first provider request returned error 432, the exact provider message reached the CLI, and the shared run/trace/thread ID remained intact. Combined acceptance was unavailable at this stage; build-log entry 09 records the later fresh-key regression, model-setting revert, and successful end-to-end run.

## Final local verification

The final implementation passed all 22 deterministic tests, Ruff formatting and lint checks, locked dependency resolution and synchronization, Python bytecode compilation, the CLI help smoke test, and Git whitespace validation. The role boundary is visible in the production call path: `build_system_prompt()` is passed through LangChain's `system_prompt` parameter, while the question is passed as a message with `role: "user"`.
