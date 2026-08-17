# Final Acceptance and Release Audit

## 2026-08-17 — Pre-submission request

The user requested a complete repository audit before commit, publication, and submission. The audit re-read the assignment, reconciled each deliverable, ran the deterministic checks, exercised all three documented live questions, inspected their exact Tavily snippets, and queried LangSmith directly for trace and thread evidence.

## Defects found and repaired

### Exact citation enforcement

The initial validator recognized exact tokens such as `[S1]` but did not reject grouped syntax such as `[S1, S2]`. A live answer could therefore retain an unresolved grouped citation while rendering only source IDs that appeared elsewhere in exact form.

The implementation now detects any citation-like bracket containing a source ID and rejects it unless the entire token is exactly `[S<number>]`. The prompt explicitly requires adjacent tokens such as `[S1][S2]`, and a regression test reproduces the previously accepted mixed-format answer.

### Current primary-source retrieval

Prompt instructions alone did not reliably stop the model from using stale secondary sources for the freshness-sensitive question. The retrieval boundary now exposes Tavily's `include_domains` parameter, requires the model to supply that argument, and provides a compact default list of first-party AI and research domains whenever the question contains current-time wording such as “recent” or “latest.” A deterministic postcondition prevents a current answer from being shown unless a domain-restricted search occurred.

This remains one agent and one search tool. The change adds a narrow evidence-quality policy rather than another model, evaluator, or retrieval service.

## Accepted live evidence

| Scenario | Shared run / trace / thread ID | Review result |
| --- | --- | --- |
| Foundational: “What is retrieval-augmented generation?” | `01a01151-d01a-7cb2-9cb6-880e9e8782f7` | Passed. One Tavily search returned five sources including two research reviews plus NVIDIA and Microsoft documentation. The cited snippets support the definition, retrieval/generation stages, freshness benefit, and stated use cases. |
| Freshness: “What changed recently in how AI agents are evaluated?” | `01a0114f-e984-7480-ac20-d10319e03adc` | Passed. One domain-restricted search returned two original papers plus official Anthropic, NeurIPS, and OpenAI sources. Publication dates and snippets support the benchmark-suite, dynamic-environment, human-evaluation, and OpenAI Evals-platform claims. |
| Misconception: “Does temperature zero make an LLM fully deterministic?” | `01a01150-6051-7a41-a267-e0857ba8c54f` | Passed. One search returned five sources from arXiv and the vLLM project. The answer used only exact citation tokens, every cited ID rendered, and the evidence supports the distinction between greedy-decoding intent and practical inference nondeterminism. |

Direct LangSmith inspection found each UUID as the successful `ai-tutor-answer` root run and trace ID in project `tavily-ai-tutor`. Each trace contained eight root/child runs, and all eight runs carried the same UUID as `thread_id` metadata.

## Honest iteration record

The first freshness runs were operationally successful but rejected during human review because they used social or secondary sources and included stale benchmark figures. A later run was rejected automatically because it had not performed the required domain-restricted search. The first final-code RAG sample was also rejected during human review for an unsupported absolute statement about training data. None of those runs is presented as acceptance evidence.

## Final local verification

The final release checks cover the locked dependency graph, formatting, lint, byte-compilation, deterministic tests, CLI help, ignored inputs/secrets, and staged Git whitespace. Provider secrets remain only in the ignored `.env`; the supplied assignment folder and `starter_agent.py` remain ignored and outside the deliverable set.
