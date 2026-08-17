"""Grounded, observable AI tutor CLI."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any, Protocol
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import langsmith as ls
import typer
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import BaseTool, tool
from langchain_core.tracers.langchain import wait_for_all_tracers
from langchain_nebius import ChatNebius
from langchain_tavily import TavilySearch
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

DEFAULT_MODEL = "moonshotai/Kimi-K2.6"
MAX_SEARCHES = 2
MAX_RESULTS = 5
SNIPPET_LIMIT = 700
PRIMARY_AI_DOMAINS = (
    "acm.org",
    "ai.google",
    "anthropic.com",
    "arxiv.org",
    "deepmind.google",
    "github.com",
    "huggingface.co",
    "ieee.org",
    "langchain.com",
    "meta.com",
    "metr.org",
    "microsoft.com",
    "openai.com",
    "scale.com",
    "tavily.com",
)
REQUIRED_HEADINGS = ("Answer", "Explanation", "What to remember")
CITATION_PATTERN = re.compile(r"\[(S\d+)\]")
CITATION_LIKE_PATTERN = re.compile(r"\[[^\]\n]*\bS\d+\b[^\]\n]*\]")
URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
CURRENT_QUESTION_PATTERN = re.compile(
    r"\b(current|currently|latest|recent|recently|today|this year)\b",
    re.IGNORECASE,
)
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"", "0", "false", "no", "off"}

app = typer.Typer(add_completion=False)
console = Console()


class ConfigurationError(ValueError):
    """Raised when required runtime configuration is missing or invalid."""


class RetrievalError(RuntimeError):
    """Raised when Tavily cannot provide usable evidence."""


class GroundingError(ValueError):
    """Raised when the generated answer violates the grounding contract."""


class SearchBackend(Protocol):
    """Small seam used by the live Tavily client and deterministic tests."""

    def invoke(self, input: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class RuntimeConfig:
    tracing_enabled: bool
    langsmith_project: str | None


@dataclass(frozen=True)
class Source:
    source_id: str
    title: str
    url: str
    snippet: str

    def as_tool_payload(self) -> dict[str, str]:
        return {
            "id": self.source_id,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
        }


@dataclass(frozen=True)
class SearchRecord:
    query: str
    include_domains: tuple[str, ...]
    request_id: str | None
    response_time: float | None
    credits: float | None


class SourceRegistry:
    """Assign stable IDs to unique URLs for one tutor invocation."""

    def __init__(self) -> None:
        self._sources_by_url: dict[str, Source] = {}
        self._sources_by_id: dict[str, Source] = {}

    @property
    def sources(self) -> tuple[Source, ...]:
        return tuple(self._sources_by_id.values())

    def __len__(self) -> int:
        return len(self._sources_by_id)

    def get(self, source_id: str) -> Source | None:
        return self._sources_by_id.get(source_id)

    def add_results(self, results: Sequence[Mapping[str, Any]]) -> list[Source]:
        sources: list[Source] = []
        seen_ids: set[str] = set()

        for result in results:
            url = _valid_url(result.get("url"))
            if not url:
                continue

            key = _canonical_url(url)
            source = self._sources_by_url.get(key)
            if source is None:
                source_id = f"S{len(self._sources_by_id) + 1}"
                source = Source(
                    source_id=source_id,
                    title=_clean_text(result.get("title")) or "Untitled source",
                    url=url,
                    snippet=_truncate(
                        _clean_text(result.get("content")), SNIPPET_LIMIT
                    ),
                )
                self._sources_by_url[key] = source
                self._sources_by_id[source_id] = source

            if source.source_id not in seen_ids:
                sources.append(source)
                seen_ids.add(source.source_id)

        return sources


class SearchSession:
    """Bound Tavily use and retain evidence plus request metadata for one run."""

    def __init__(
        self,
        backend: SearchBackend,
        registry: SourceRegistry,
        max_searches: int = MAX_SEARCHES,
        default_domains: Sequence[str] = (),
    ) -> None:
        self.backend = backend
        self.registry = registry
        self.max_searches = max_searches
        self.default_domains = tuple(default_domains)
        self.records: list[SearchRecord] = []

    @property
    def search_count(self) -> int:
        return len(self.records)

    @property
    def total_credits(self) -> float | None:
        credits = [
            record.credits for record in self.records if record.credits is not None
        ]
        return sum(credits) if credits else None

    @property
    def has_domain_restricted_search(self) -> bool:
        return any(record.include_domains for record in self.records)

    def search(self, query: str, include_domains: Sequence[str] | None = None) -> str:
        query = _clean_text(query)
        if not query:
            raise RetrievalError("Search query cannot be empty.")
        if self.search_count >= self.max_searches:
            raise RetrievalError(f"Search limit reached ({self.max_searches} per run).")

        domains = list(
            dict.fromkeys(
                domain
                for value in include_domains or self.default_domains
                if (domain := _clean_text(value))
            )
        )
        search_input: dict[str, Any] = {"query": query}
        if domains:
            search_input["include_domains"] = domains

        raw_payload = self.backend.invoke(search_input)
        payload = _as_mapping(raw_payload)
        results = payload.get("results")
        result_list = results if isinstance(results, list) else []
        sources = self.registry.add_results(
            [result for result in result_list if isinstance(result, Mapping)]
        )

        record = SearchRecord(
            query=query,
            include_domains=tuple(domains),
            request_id=_optional_text(payload.get("request_id")),
            response_time=_optional_float(payload.get("response_time")),
            credits=_usage_credits(payload.get("usage")),
        )
        self.records.append(record)

        if not sources:
            raise RetrievalError("Tavily returned no usable sources for this search.")

        tool_payload = {
            "query": query,
            "sources": [source.as_tool_payload() for source in sources],
            "request_id": record.request_id,
            "response_time": record.response_time,
            "usage": payload.get("usage"),
        }
        return json.dumps(tool_payload, ensure_ascii=False)


def validate_environment(environ: Mapping[str, str] | None = None) -> RuntimeConfig:
    env = os.environ if environ is None else environ
    missing = [
        name
        for name in ("TAVILY_API_KEY", "NEBIUS_API_KEY")
        if not str(env.get(name, "")).strip()
    ]
    if missing:
        raise ConfigurationError(
            f"Missing required environment variable(s): {', '.join(missing)}"
        )

    raw_tracing = env.get("LANGSMITH_TRACING", "").strip().lower()
    if raw_tracing not in TRUE_VALUES | FALSE_VALUES:
        raise ConfigurationError("LANGSMITH_TRACING must be true or false.")

    tracing_enabled = raw_tracing in TRUE_VALUES
    project = str(env.get("LANGSMITH_PROJECT", "")).strip() or None
    if tracing_enabled:
        missing_langsmith = [
            name
            for name in ("LANGSMITH_API_KEY", "LANGSMITH_PROJECT")
            if not str(env.get(name, "")).strip()
        ]
        if missing_langsmith:
            raise ConfigurationError(
                "Tracing is enabled but environment variable(s) are missing: "
                + ", ".join(missing_langsmith)
            )

    return RuntimeConfig(
        tracing_enabled=tracing_enabled,
        langsmith_project=project,
    )


def build_system_prompt(today: date | None = None) -> str:
    current_date = today or date.today()
    return f"""You are AI Tutor, a concise and trustworthy tutor for artificial
intelligence and machine learning.
Today's date is {current_date.isoformat()}.

For every answer:
- Call search_ai_sources before answering. Use one focused search first.
  Use a second only when the first evidence is insufficient, current evidence
  needs primary-source verification, or the question has two distinct parts.
- Prefer official documentation, standards, and original research.
- For a current or recent question, include {current_date.year} in the first
  query and check publication dates. Current-question searches are restricted
  to primary AI and research domains. Use a second focused search only if needed.
- Do not present an older benchmark result as current when newer evidence exists.
- Do not cite social media, community forums, or unsourced aggregations when an
  official source or original research is available.
- Teach directly and define necessary jargon. Use an example only when it helps.
- Distinguish established facts from judgment, uncertainty, or active debate.
- Cite factual teaching points with source IDs exactly as [S1], [S2], and so on.
- Write multiple citations as [S1][S2], never as [S1, S2].
- Use only source IDs returned by search_ai_sources during this run.
- Never write source URLs and never add a Sources section; the CLI adds
  validated sources.

Use these required Markdown headings:
## Answer
## Explanation
## What to remember

You may also add these headings only when useful:
## Example
## Uncertainty
## Check yourself
"""


def create_search_tool(session: SearchSession) -> BaseTool:
    @tool
    def search_ai_sources(query: str, include_domains: list[str]) -> str:
        """Search AI sources; pass [] broadly or primary domains for evidence."""

        return session.search(query, include_domains)

    return search_ai_sources


def validate_answer(answer: str, registry: SourceRegistry) -> list[str]:
    answer = answer.strip()
    if not answer:
        raise GroundingError("The model returned an empty answer.")
    if not registry.sources:
        raise GroundingError("The answer has no retrieved sources.")

    missing_headings = [
        heading
        for heading in REQUIRED_HEADINGS
        if not re.search(rf"(?m)^## {re.escape(heading)}\s*$", answer)
    ]
    if missing_headings:
        raise GroundingError(
            "The answer is missing required heading(s): " + ", ".join(missing_headings)
        )
    if re.search(r"(?m)^## Sources\s*$", answer):
        raise GroundingError("The model must not author the Sources section.")
    if URL_PATTERN.search(answer):
        raise GroundingError("The model must cite source IDs instead of writing URLs.")

    malformed_citations = list(
        dict.fromkeys(
            token
            for token in CITATION_LIKE_PATTERN.findall(answer)
            if CITATION_PATTERN.fullmatch(token) is None
        )
    )
    if malformed_citations:
        raise GroundingError(
            "The answer contains malformed source citation(s): "
            + ", ".join(malformed_citations)
            + ". Cite each source separately, for example [S1][S2]."
        )

    citations = list(dict.fromkeys(CITATION_PATTERN.findall(answer)))
    if not citations:
        raise GroundingError("The answer contains no source citations.")

    unknown = [source_id for source_id in citations if registry.get(source_id) is None]
    if unknown:
        raise GroundingError(
            "The answer cites unknown source ID(s): " + ", ".join(unknown)
        )
    return citations


def render_answer(
    answer: str, citation_ids: Sequence[str], registry: SourceRegistry
) -> str:
    source_lines = []
    for source_id in citation_ids:
        source = registry.get(source_id)
        if source is None:
            raise GroundingError(f"Cannot render unknown source ID: {source_id}")
        source_lines.append(f"- [{source.source_id}] {source.title} — {source.url}")
    return answer.strip() + "\n\n## Sources\n\n" + "\n".join(source_lines)


def extract_final_answer(result: Mapping[str, Any]) -> str:
    messages = result.get("messages")
    if not isinstance(messages, list):
        raise GroundingError("The agent returned no messages.")

    for message in reversed(messages):
        if getattr(message, "type", None) != "ai":
            continue
        if getattr(message, "tool_calls", None):
            continue
        text = _message_text(message).strip()
        if text:
            return text
    raise GroundingError("The agent returned no final answer.")


def new_correlation_id() -> UUID:
    """Create the shared UUIDv7 used for run, trace, and thread correlation."""

    return ls.uuid7()


def build_run_config(run_id: UUID, model_name: str) -> dict[str, Any]:
    """Use one correlation ID for the LangSmith root run, trace, and thread."""

    return {
        "run_id": run_id,
        "run_name": "ai-tutor-answer",
        "tags": ["ai-tutor", "cli"],
        "metadata": {
            "model": model_name,
            "cli_run_id": str(run_id),
            "thread_id": str(run_id),
        },
        "recursion_limit": 8,
    }


def run_tutor(
    question: str, model_name: str, run_id: UUID
) -> tuple[str, SearchSession]:
    registry = SourceRegistry()
    tavily = TavilySearch(
        max_results=MAX_RESULTS,
        search_depth="advanced",
        include_raw_content=False,
        include_answer=False,
        include_usage=True,
    )
    current_evidence_required = requires_current_evidence(question)
    session = SearchSession(
        tavily,
        registry,
        default_domains=PRIMARY_AI_DOMAINS if current_evidence_required else (),
    )
    chat_model = ChatNebius(model=model_name, streaming=False)
    agent = create_agent(
        model=chat_model,
        tools=[create_search_tool(session)],
        system_prompt=build_system_prompt(),
    )

    thread_metadata = {"thread_id": str(run_id)}
    with ls.tracing_context(metadata=thread_metadata):
        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config=build_run_config(run_id, model_name),
        )
    answer = extract_final_answer(result)
    if current_evidence_required and not session.has_domain_restricted_search:
        raise GroundingError(
            "A current or recent question requires a domain-restricted search."
        )
    citations = validate_answer(answer, registry)
    return render_answer(answer, citations, registry), session


@app.command()
def main(
    question: Annotated[list[str], typer.Argument(help="AI question")],
    model: Annotated[str, typer.Option(help="Nebius model name")] = DEFAULT_MODEL,
) -> None:
    """Ask one AI question and receive a grounded, cited lesson."""

    load_dotenv()
    question_text = " ".join(question).strip()
    if not question_text:
        console.print("[bold red]Question cannot be empty.[/bold red]")
        raise typer.Exit(code=2)

    try:
        runtime = validate_environment()
    except ConfigurationError as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        console.print("Copy .env.example to .env and fill in the required values.")
        raise typer.Exit(code=1) from None

    run_id = new_correlation_id()
    tracing_status = (
        f"enabled → {runtime.langsmith_project}"
        if runtime.tracing_enabled
        else "disabled"
    )
    console.print(Panel.fit(question_text, title="AI Tutor", border_style="cyan"))
    console.print(
        f"[dim]Run ID / LangSmith Trace ID / Thread ID: {run_id} · "
        f"LangSmith tracing: {tracing_status}[/dim]"
    )

    try:
        with console.status("Researching and preparing a grounded lesson..."):
            answer, session = run_tutor(question_text, model, run_id)
        console.print()
        console.print(Markdown(answer))
        console.print()
        metrics = (
            f"{session.search_count} search(es) · {len(session.registry)} source(s)"
        )
        if session.total_credits is not None:
            metrics += f" · {session.total_credits:g} Tavily credit(s)"
        console.print(
            f"[dim]{metrics} · Run ID / LangSmith Trace ID / Thread ID: {run_id}[/dim]"
        )
    except KeyboardInterrupt:
        console.print("\n[red]Interrupted.[/red]")
        raise typer.Exit(code=130) from None
    except Exception as exc:
        console.print(f"\n[bold red]Tutor run failed:[/bold red] {exc}")
        console.print(f"[dim]Run ID / LangSmith Trace ID / Thread ID: {run_id}[/dim]")
        raise typer.Exit(code=1) from None
    finally:
        if runtime.tracing_enabled:
            wait_for_all_tracers()


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return ""


def requires_current_evidence(question: str) -> bool:
    return CURRENT_QUESTION_PATTERN.search(question) is not None


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _valid_url(value: Any) -> str | None:
    url = _clean_text(value)
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return url


def _canonical_url(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, "")
    )


def _as_mapping(payload: Any) -> Mapping[str, Any]:
    if isinstance(payload, Mapping):
        return payload
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise RetrievalError("Tavily returned an unreadable response.") from exc
        if isinstance(parsed, Mapping):
            return parsed
    raise RetrievalError("Tavily returned an unexpected response shape.")


def _optional_text(value: Any) -> str | None:
    text = _clean_text(value)
    return text or None


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _usage_credits(value: Any) -> float | None:
    if isinstance(value, Mapping):
        return _optional_float(value.get("credits"))
    return None


if __name__ == "__main__":
    app()
