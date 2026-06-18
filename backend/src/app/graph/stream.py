"""Stream travel graph execution as structured events for live UI.

Yields ``(event_type, payload)`` tuples as the graph runs, so the caller (the
SSE endpoint) can both serialize them to the client and capture state for
persistence without re-parsing its own output.

Event types:
  - session:    {session_id}                  (emitted by the endpoint, not here)
  - plan:       {route: [{name,label,icon}]}  (supervisor's plan, for the pipeline)
  - node_start: {name, label, icon}
  - node_end:   {name, output}                (state delta the node produced)
  - llm_start:  {node}                        (an LLM call began inside a node)
  - llm_end:    {node}                        (an LLM call finished)
  - reasoning:  {node, text}                  (raw LLM tokens for non-answer nodes;
                                              fills the silent phase-2 gaps live)
  - tool_start: {node, name, input}
  - tool_end:   {node, name, output}
  - token:      {text}                        (final-answer tokens, synthesize only)
  - final:      {final_answer}                (authoritative answer from synthesize)
  - error:      {message}

Design notes:
  - Tools fire on_tool_* because gather_via_tools calls ``tool.invoke()`` inside
    the node; LangChain's callback context propagates those as child events.
  - final_answer is captured from synthesize's node_end output (the source of
    truth), NOT from accumulated tokens — the clarify / supervisor-failed paths
    return a static string without an LLM call, so no tokens ever stream there.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

# Node display metadata — single source of truth for labels/icons, shared with
# the non-streaming trace fallback (graph/trace.py).
NODE_META: dict[str, dict[str, str]] = {
    "supervisor": {"label": "Phân tích & lên kế hoạch", "icon": "🧭"},
    "itinerary": {"label": "Lập lịch trình", "icon": "🗺️"},
    "recommendation": {"label": "Gợi ý lưu trú & ăn uống", "icon": "🏨"},
    "cost": {"label": "Ước lượng chi phí", "icon": "💰"},
    "synthesize": {"label": "Tổng hợp câu trả lời", "icon": "✨"},
}

# Node whose chat_model tokens ARE the final answer (streamed live). Other nodes
# use structured output, so their tokens are JSON noise we must not show.
_ANSWER_NODES = {"synthesize"}

# Framework wrapper names to ignore when filtering node chain events.
_FRAMEWORK_WRAPPERS = {"LangGraph", "RunnableSequence", "RunnableParallel"}


def _safe_jsonable(value: Any) -> Any:
    """Return a JSON-serializable copy, falling back to str() for exotic types."""
    if value is None:
        return None
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError, OverflowError):
        return str(value)


def _build_route(plan: list[str] | None) -> list[dict[str, str]]:
    """Turn the supervisor's ordered plan into a display pipeline.

    Always starts with supervisor and ends with synthesize (both always run),
    with the planned domain agents in between, in the LLM-chosen order.
    """
    route = [{"name": "supervisor", **NODE_META["supervisor"]}]
    for step in plan or []:
        if step in NODE_META and step not in {"supervisor", "synthesize"}:
            route.append({"name": step, **NODE_META[step]})
    route.append({"name": "synthesize", **NODE_META["synthesize"]})
    return route


def _extract_plan(node_output: Any) -> list[str] | None:
    if not isinstance(node_output, dict):
        return None
    plan = node_output.get("plan")
    return plan if isinstance(plan, list) else None


def _extract_final_answer(node_output: Any) -> str | None:
    if not isinstance(node_output, dict):
        return None
    answer = node_output.get("final_answer")
    return answer if isinstance(answer, str) and answer else None


async def stream_travel(
    graph: CompiledStateGraph,
    message: str,
    thread_id: str,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Run the graph and yield ``(event_type, payload)`` tuples as events arrive.

    Only nodes/tools that actually run are yielded, in execution order, with
    their real inputs and the state delta they produce — so the UI shows the
    genuine reasoning trace rather than a mocked timeline.

    ``thread_id`` (= session_id) keys the checkpointer so the full TravelState —
    including message history — persists across turns, giving the supervisor the
    prior conversation when resolving follow-ups.
    """
    inputs = {"messages": [HumanMessage(content=message)]}
    started_nodes: set[str] = set()
    ended_nodes: set[str] = set()
    # run_id -> {node, name}: tool_end needs the caller node captured at start.
    tool_context: dict[str, dict[str, Any]] = {}
    final_answer: str | None = None

    try:
        async for ev in graph.astream_events(
            inputs,
            version="v2",
            config={"configurable": {"thread_id": thread_id}},
        ):
            kind = ev["event"]
            name = ev.get("name", "")
            node = ev.get("metadata", {}).get("langgraph_node")
            data = ev.get("data", {})

            # --- Node lifecycle (keep named nodes, drop framework wrappers) ---
            if (
                kind == "on_chain_start"
                and name in NODE_META
                and name not in started_nodes
            ):
                started_nodes.add(name)
                yield "node_start", {"name": name, **NODE_META[name]}

            elif (
                kind == "on_chain_end"
                and name in NODE_META
                and name not in ended_nodes
                and name not in _FRAMEWORK_WRAPPERS
            ):
                ended_nodes.add(name)
                output = _safe_jsonable(data.get("output"))
                yield "node_end", {"name": name, "output": output}

                if name == "supervisor":
                    yield "plan", {"route": _build_route(_extract_plan(output))}

                if name == "synthesize":
                    final_answer = _extract_final_answer(output)

            # --- Tool lifecycle (tools invoked via .invoke() inside agent nodes) ---
            elif kind == "on_tool_start":
                tool_context[ev["run_id"]] = {"node": node, "name": name}
                yield "tool_start", {
                    "node": node,
                    "name": name,
                    "input": _safe_jsonable(data.get("input")),
                }
            elif kind == "on_tool_end":
                ctx = tool_context.pop(ev["run_id"], {"node": node, "name": name})
                yield "tool_end", {
                    "node": ctx.get("node") or node,
                    "name": ctx.get("name") or name,
                    "output": _safe_jsonable(data.get("output")),
                }

            # --- Chat-model activity: thinking indicator + token streaming ---
            # Every LLM call fires start/end so the UI shows a live "thinking"
            # state during the long phase-2 structured-output gaps (each agent's
            # with_structured_output call is otherwise silent for 30-60s).
            # Token content routes to the final answer for synthesize, and to a
            # raw "reasoning" preview for all other nodes — so the user watches
            # the agent plan and emit JSON in real time. (Tool-deciding gather
            # calls usually emit empty content — their tool_calls go via the
            # tool_* events — so reasoning lights up mainly during phase 2.)
            elif kind == "on_chat_model_start":
                yield "llm_start", {"node": node}
            elif kind == "on_chat_model_end":
                yield "llm_end", {"node": node}
            elif kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                text = getattr(chunk, "content", "") if chunk else ""
                if isinstance(text, list):  # some providers emit content blocks
                    text = "".join(
                        b.get("text", "") for b in text if isinstance(b, dict)
                    )
                if isinstance(text, str) and text:
                    if node in _ANSWER_NODES:
                        yield "token", {"text": text}
                    else:
                        yield "reasoning", {"node": node, "text": text}

    except Exception as exc:  # noqa: BLE001 — surface to client, keep stream alive
        yield "error", {"message": str(exc)}

    # Authoritative answer for persistence (handles clarify/no-LLM paths where
    # no tokens streamed).
    yield "final", {"final_answer": final_answer or ""}
