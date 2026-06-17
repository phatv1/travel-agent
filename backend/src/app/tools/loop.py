"""Tool-calling loop helper: run an LLM with tools until it stops calling them.

Two-phase agent pattern:
  Phase 1 (this helper): LLM bind_tools → calls tools → ToolMessage feedback →
    repeat until the LLM emits no more tool calls (it has gathered what it needs).
  Phase 2 (caller): LLM produces the structured domain result from the gathered
    context via with_structured_output.

The agent never trusts LLM arithmetic for correctness-critical values: the caller
recomputes those deterministically afterward. The tool calls here showcase the
agentic loop (model autonomously deciding what to look up / compute).
"""

from collections.abc import Sequence

from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.tools import BaseTool


def gather_via_tools(
    llm: object,
    tools: Sequence[BaseTool],
    messages: list[BaseMessage],
    *,
    max_iters: int = 4,
) -> list[BaseMessage]:
    """Run the LLM with tools, executing each tool call, until none remain.

    Returns the full message history including ToolMessage results, so the caller
    can feed it into a structured-output invocation. Bounded by max_iters as a
    safety net against tool-calling loops.
    """
    bound = llm.bind_tools(list(tools))  # type: ignore[attr-defined]
    tool_map = {t.name: t for t in tools}
    for _ in range(max_iters):
        resp = bound.invoke(messages)
        messages.append(resp)
        calls = getattr(resp, "tool_calls", None) or []
        if not calls:
            break
        for tc in calls:
            fn = tool_map[tc["name"]]
            result = fn.invoke(tc["args"])
            messages.append(
                ToolMessage(content=str(result), tool_call_id=tc["id"], name=tc["name"])
            )
    return messages
