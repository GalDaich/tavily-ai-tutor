# Test Suite Audit

## 2026-08-17 — Review goal

The user requested a walkthrough of every entry in `tests/test_ai_tutor.py` to ensure that redundant, irrelevant, or misleading tests did not pollute the take-home repository.

Each entry was evaluated against three criteria:

1. It protects a current product, grounding, configuration, or observability contract.
2. It would fail after a plausible regression rather than merely asserting an implementation detail.
3. It remains deterministic and makes no provider call.

## Test infrastructure

| Entry | Purpose | Decision |
| --- | --- | --- |
| `FakeSearchBackend` | Exercises the real `SearchSession` boundary with deterministic Tavily-shaped payloads and records outgoing queries. | Keep. This is the single provider seam used by all retrieval tests. |
| `MetadataRecorder` | Captures metadata from actual LangChain root and child runnable callbacks. | Keep. It verifies the documented all-runs thread requirement without LangSmith network access. |
| `result` | Builds minimal Tavily-shaped search results. | Keep. It removes repetitive fixture dictionaries. |
| `grounded_answer` | Builds one valid response-contract fixture with configurable citations. | Keep. It keeps negative grounding tests focused on one changed condition. |

## Observability tests

| Test | Contract protected | Decision |
| --- | --- | --- |
| `test_run_config_uses_one_uuid7_for_run_trace_and_thread_correlation` | Production generates UUIDv7 and uses the identical value for root `run_id`, `cli_run_id`, and `thread_id`. | Keep after repair. The previous version asserted UUIDv7 on a hard-coded fixture, which did not test production generation. `new_correlation_id` is now the production boundary under test. |
| `test_thread_id_metadata_propagates_to_child_runs` | LangChain passes the same `thread_id` to the root and child runs, as required for LangSmith thread filtering and aggregation. | Keep. This tests framework propagation behavior that the configuration-only test does not prove. |

These two tests are complementary: one validates the configuration values; the other executes a LangChain runnable tree and validates propagation.

## Configuration tests

| Test | Contract protected | Decision |
| --- | --- | --- |
| `test_environment_requires_provider_keys` | The tutor cannot start without Tavily and Nebius credentials. | Keep. Prevents a confusing late provider failure. |
| `test_environment_requires_langsmith_values_when_tracing_is_enabled` | Explicitly enabled tracing requires both API key and project. | Keep. Prevents a falsely observable run. |
| `test_environment_allows_explicitly_disabled_tracing` | Local deterministic use may disable tracing without supplying LangSmith credentials. | Keep. Covers the valid opposite branch; it is not redundant with the tracing-error case. |

## Retrieval and source-registry tests

| Test | Contract protected | Decision |
| --- | --- | --- |
| `test_source_registry_assigns_stable_ids_and_deduplicates_urls` | Valid URLs receive stable sequential IDs, trailing-slash duplicates collapse, and invalid URLs are excluded. | Keep. These behaviors form one cohesive normalization boundary. |
| `test_search_session_normalizes_results_and_records_usage` | The wrapper trims the query, normalizes the source payload, and records Tavily request ID, search count, and credits. | Keep. This is the retrieval happy path and observability-data contract. |
| `test_search_session_rejects_empty_results` | Empty retrieval cannot produce an answer from model memory. | Keep. Protects the central honest-failure rule. |
| `test_search_session_enforces_search_limit` | A run cannot exceed its configured Tavily request budget. | Keep. Protects bounded cost and agent behavior. |

## Grounding and rendering tests

| Test | Contract protected | Decision |
| --- | --- | --- |
| `test_validate_and_render_answer_uses_only_cited_sources` | Valid citations are deduplicated and only cited sources are rendered. | Keep. This is the grounding happy path. |
| `test_validate_answer_rejects_missing_citations` | A retrieved but uncited answer is not presented as grounded. | Keep. Distinct from unknown citations. |
| `test_validate_answer_rejects_unknown_citations` | The model cannot invent a source ID. | Keep. Distinct from missing citations. |
| `test_validate_answer_rejects_model_authored_urls` | The model cannot bypass deterministic source rendering with a URL. | Keep. Protects URL provenance. |
| `test_validate_answer_rejects_model_authored_sources_section` | The model cannot author a competing Sources section. | Added. This was a real untested branch of the deterministic-rendering contract. |
| `test_validate_answer_requires_response_headings` | The tutor must return the minimum Answer, Explanation, and What-to-remember structure. | Keep. Protects the approved user-facing response contract without asserting prompt wording. |

The four negative citation tests are not duplicates. They reject different invalid outputs: no attribution, invented attribution, model-authored URLs, and a model-authored Sources section.

## Deliberate non-coverage

The unit suite does not call Tavily, Nebius, or LangSmith and does not judge semantic answer quality. Those checks require credentials, cost, mutable external services, and human review of cited evidence. They belong in the three documented live acceptance runs, not in the deterministic repository suite.

The suite also avoids brittle tests of exact prompt prose, Rich formatting, or private LangChain internals.

## Audit result

- No test was redundant or irrelevant enough to remove.
- One misleading self-fulfilling UUID assertion was repaired to exercise production generation.
- One missing deterministic-source boundary test was added.
- At the end of this audit step, the suite contained 15 focused tests in one file. Later release-audit regressions are recorded in the next numbered entry.
