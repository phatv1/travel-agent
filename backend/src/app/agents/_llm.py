"""Shared LLM helpers for agent nodes."""

from collections.abc import Sequence
from typing import Any, Protocol

from langchain_core.messages import BaseMessage
from pydantic import BaseModel


class _StructuredOutputModel(Protocol):
    """Minimal LLM surface this helper depends on.

    Narrowed from BaseChatModel so unit tests can pass a fake, and the contract
    is honest — only with_structured_output() is ever called.
    """

    def with_structured_output(self, schema: type[BaseModel]) -> Any: ...


def invoke_structured[T: BaseModel](
    llm: _StructuredOutputModel,
    schema: type[T],
    messages: Sequence[BaseMessage],
    *,
    retries: int = 1,
) -> T:
    """Call the model with structured output, retrying once on failure.

    Local Ollama occasionally emits malformed or schema-mismatched JSON; one
    retry absorbs most transient hiccups. Raises after the final attempt so the
    caller records a node-level error instead of crashing the whole graph.
    """
    extractor = llm.with_structured_output(schema)
    last_exc: Exception | None = None
    for _ in range(retries + 1):
        try:
            return schema.model_validate(extractor.invoke(messages))
        except Exception as exc:  # noqa: BLE001 — LLM output failures are unpredictable
            last_exc = exc
    assert last_exc is not None
    raise last_exc


def error_label(node: str, exc: Exception) -> str:
    """One-line error string for the accumulating `errors` list."""
    msg = " ".join(str(exc).split())[:140]
    return f"{node}: {type(exc).__name__}: {msg}"
