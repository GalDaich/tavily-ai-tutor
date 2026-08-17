from __future__ import annotations

import json
from datetime import date
from typing import Any
from uuid import UUID

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableLambda

from ai_tutor import (
    DEFAULT_MODEL,
    ConfigurationError,
    GroundingError,
    RetrievalError,
    SearchSession,
    SourceRegistry,
    build_run_config,
    build_system_prompt,
    new_correlation_id,
    render_answer,
    requires_current_evidence,
    validate_answer,
    validate_environment,
)


class FakeSearchBackend:
    def __init__(self, payloads: list[Any]) -> None:
        self.payloads = payloads
        self.calls: list[dict[str, Any]] = []

    def invoke(self, input: dict[str, Any]) -> Any:
        self.calls.append(input)
        return self.payloads[len(self.calls) - 1]


class MetadataRecorder(BaseCallbackHandler):
    def __init__(self) -> None:
        self.metadata: list[dict[str, Any]] = []

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: Any,
        **kwargs: Any,
    ) -> None:
        self.metadata.append(kwargs.get("metadata") or {})


def result(
    url: str, title: str = "Source", content: str = "Evidence"
) -> dict[str, str]:
    return {"url": url, "title": title, "content": content}


def grounded_answer(citations: str = "[S1]") -> str:
    return f"""## Answer

Retrieval adds external evidence {citations}.

## Explanation

The model can use retrieved context {citations}.

## What to remember

Retrieval and generation are separate steps {citations}."""


def test_run_config_uses_one_uuid7_for_run_trace_and_thread_correlation() -> None:
    run_id = new_correlation_id()

    config = build_run_config(run_id, "test-model")

    assert config["run_id"] == run_id
    assert config["metadata"]["cli_run_id"] == str(run_id)
    assert config["metadata"]["thread_id"] == str(run_id)
    assert run_id.version == 7


def test_thread_id_metadata_propagates_to_child_runs() -> None:
    run_id = UUID("01990f3e-7f97-74c5-a9b6-8d3f7e8e2f11")
    recorder = MetadataRecorder()
    chain = RunnableLambda(lambda value: value + 1) | RunnableLambda(
        lambda value: value * 2
    )
    config = {
        **build_run_config(run_id, "test-model"),
        "callbacks": [recorder],
    }

    assert chain.invoke(1, config=config) == 4
    assert len(recorder.metadata) == 3
    assert all(metadata["thread_id"] == str(run_id) for metadata in recorder.metadata)


def test_system_prompt_encodes_one_search_and_output_contract() -> None:
    prompt = build_system_prompt(date(2026, 8, 17))

    assert "<system>" not in prompt
    assert "<instructions>" in prompt
    assert "exactly once" in prompt
    assert "include 2026" in prompt
    assert "<evidence_rules>" in prompt
    assert "<response_format>" in prompt
    assert "non-empty Markdown lesson" in prompt
    assert "## Answer\n## Explanation\n## What to remember" in prompt


def test_default_model_is_the_verified_non_reasoning_instruct_model() -> None:
    assert DEFAULT_MODEL == "Qwen/Qwen3-30B-A3B-Instruct-2507"


def test_environment_requires_provider_keys() -> None:
    with pytest.raises(ConfigurationError, match="TAVILY_API_KEY, NEBIUS_API_KEY"):
        validate_environment({})


def test_environment_requires_langsmith_values_when_tracing_is_enabled() -> None:
    env = {
        "TAVILY_API_KEY": "tavily",
        "NEBIUS_API_KEY": "nebius",
        "LANGSMITH_TRACING": "true",
    }
    with pytest.raises(
        ConfigurationError, match="LANGSMITH_API_KEY, LANGSMITH_PROJECT"
    ):
        validate_environment(env)


def test_environment_allows_explicitly_disabled_tracing() -> None:
    runtime = validate_environment(
        {
            "TAVILY_API_KEY": "tavily",
            "NEBIUS_API_KEY": "nebius",
            "LANGSMITH_TRACING": "false",
        }
    )
    assert runtime.tracing_enabled is False
    assert runtime.langsmith_project is None


def test_source_registry_assigns_stable_ids_and_deduplicates_urls() -> None:
    registry = SourceRegistry()
    first = registry.add_results(
        [
            result("https://example.com/docs/", "Docs"),
            result("https://example.com/docs", "Duplicate"),
            result("not-a-url", "Invalid"),
        ]
    )
    second = registry.add_results([result("https://example.com/paper", "Paper")])

    assert [source.source_id for source in first] == ["S1"]
    assert [source.source_id for source in second] == ["S2"]
    assert len(registry) == 2
    assert registry.get("S1").title == "Docs"  # type: ignore[union-attr]


def test_search_session_normalizes_results_and_records_usage() -> None:
    backend = FakeSearchBackend(
        [
            {
                "results": [
                    result("https://example.com", "Primary", "A   useful fact")
                ],
                "request_id": "request-123",
                "response_time": 1.25,
                "usage": {"credits": 1},
            }
        ]
    )
    session = SearchSession(backend, SourceRegistry())

    payload = json.loads(session.search("  retrieval augmented generation  "))

    assert backend.calls == [{"query": "retrieval augmented generation"}]
    assert payload["sources"][0] == {
        "id": "S1",
        "title": "Primary",
        "url": "https://example.com",
        "snippet": "A useful fact",
    }
    assert session.search_count == 1
    assert session.total_credits == 1
    assert session.records[0].request_id == "request-123"
    assert session.has_domain_restricted_search is False


def test_search_session_forwards_primary_source_domains() -> None:
    backend = FakeSearchBackend(
        [{"results": [result("https://openai.com/research", "OpenAI")]}]
    )
    session = SearchSession(backend, SourceRegistry())

    session.search(
        "current agent evaluation research",
        include_domains=["openai.com", " openai.com "],
    )

    assert backend.calls == [
        {
            "query": "current agent evaluation research",
            "include_domains": ["openai.com"],
        }
    ]
    assert session.has_domain_restricted_search is True


def test_search_session_applies_default_primary_domains() -> None:
    backend = FakeSearchBackend(
        [{"results": [result("https://openai.com/research", "OpenAI")]}]
    )
    session = SearchSession(
        backend,
        SourceRegistry(),
        default_domains=["openai.com", "arxiv.org"],
    )

    session.search("recent agent evaluation research", include_domains=[])

    assert backend.calls == [
        {
            "query": "recent agent evaluation research",
            "include_domains": ["openai.com", "arxiv.org"],
        }
    ]
    assert session.has_domain_restricted_search is True


def test_search_session_discards_results_outside_requested_domains() -> None:
    backend = FakeSearchBackend(
        [
            {
                "results": [
                    result("https://linkedin.com/posts/example", "Social"),
                    result("https://developers.openai.com/evals", "OpenAI"),
                ]
            }
        ]
    )
    session = SearchSession(backend, SourceRegistry())

    payload = json.loads(
        session.search("current evaluation guidance", include_domains=["openai.com"])
    )

    assert [source["url"] for source in payload["sources"]] == [
        "https://developers.openai.com/evals"
    ]


def test_current_questions_require_primary_source_search() -> None:
    assert requires_current_evidence(
        "What changed recently in how AI agents are evaluated?"
    )
    assert not requires_current_evidence("What is retrieval-augmented generation?")


def test_search_session_rejects_empty_results() -> None:
    session = SearchSession(FakeSearchBackend([{"results": []}]), SourceRegistry())
    with pytest.raises(RetrievalError, match="no usable sources"):
        session.search("empty")


def test_search_session_surfaces_tavily_provider_error() -> None:
    session = SearchSession(
        FakeSearchBackend(
            [
                {
                    "error": {
                        "error": "ValueError",
                        "message": "Error 432: plan usage limit exceeded",
                    }
                }
            ]
        ),
        SourceRegistry(),
    )

    with pytest.raises(RetrievalError, match="Error 432: plan usage limit exceeded"):
        session.search("temperature zero determinism")


def test_search_session_enforces_search_limit() -> None:
    payload = {"results": [result("https://example.com")]}
    session = SearchSession(FakeSearchBackend([payload, payload]), SourceRegistry())
    session.search("first")
    with pytest.raises(RetrievalError, match="Search limit reached"):
        session.search("second")


def test_validate_and_render_answer_uses_only_cited_sources() -> None:
    registry = SourceRegistry()
    registry.add_results(
        [
            result("https://example.com/one", "One"),
            result("https://example.com/two", "Two"),
        ]
    )
    answer = grounded_answer("[S2] [S2]")

    citations = validate_answer(answer, registry)
    rendered = render_answer(answer, citations, registry)

    assert citations == ["S2"]
    assert "- [S2] Two — https://example.com/two" in rendered
    assert "https://example.com/one" not in rendered


def test_validate_answer_rejects_missing_citations() -> None:
    registry = SourceRegistry()
    registry.add_results([result("https://example.com")])
    with pytest.raises(GroundingError, match="no source citations"):
        validate_answer(grounded_answer(""), registry)


def test_validate_answer_rejects_unknown_citations() -> None:
    registry = SourceRegistry()
    registry.add_results([result("https://example.com")])
    with pytest.raises(GroundingError, match="unknown source ID.*S9"):
        validate_answer(grounded_answer("[S9]"), registry)


def test_validate_answer_rejects_grouped_citation_syntax() -> None:
    registry = SourceRegistry()
    registry.add_results(
        [
            result("https://example.com/one"),
            result("https://example.com/two"),
        ]
    )
    answer = grounded_answer("[S1]") + "\n\nComparison [S1, S2]."

    with pytest.raises(GroundingError, match="malformed source citation"):
        validate_answer(answer, registry)


def test_validate_answer_rejects_model_authored_urls() -> None:
    registry = SourceRegistry()
    registry.add_results([result("https://example.com")])
    answer = grounded_answer() + "\n\nRead https://invented.example for more."
    with pytest.raises(GroundingError, match="instead of writing URLs"):
        validate_answer(answer, registry)


def test_validate_answer_rejects_model_authored_sources_section() -> None:
    registry = SourceRegistry()
    registry.add_results([result("https://example.com")])
    answer = grounded_answer() + "\n\n## Sources\n\n- [S1] A source"
    with pytest.raises(GroundingError, match="must not author the Sources section"):
        validate_answer(answer, registry)


def test_validate_answer_requires_response_headings() -> None:
    registry = SourceRegistry()
    registry.add_results([result("https://example.com")])
    with pytest.raises(GroundingError, match="What to remember"):
        validate_answer("## Answer\nA [S1]\n\n## Explanation\nB [S1]", registry)
