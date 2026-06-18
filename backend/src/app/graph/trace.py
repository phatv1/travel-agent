"""Build the agent step trace shown in the thinking panel (non-streaming path).

The streaming endpoint (graph/stream.py) emits the live trace. This rebuilds an
equivalent trace from the final OutputState for the non-streaming POST /chat
path and for reload, so both paths render an accurate, consistent trace.
"""

from app.graph.stream import NODE_META
from app.schemas.session import ToolCallData


def build_trace(message: str, result: dict) -> list[ToolCallData]:
    """Reconstruct the node trace from the final result.

    Only nodes that produced output appear (matches what streaming would have
    shown): supervisor always, each domain agent whose state is populated,
    synthesize always.
    """
    answer = result.get("final_answer") or ""
    errors = result.get("errors") or []
    plan = result.get("plan") or []

    steps: list[ToolCallData] = [
        ToolCallData(
            name="supervisor",
            label=NODE_META["supervisor"]["label"],
            icon=NODE_META["supervisor"]["icon"],
            status="done",
            input={"message": message},
            output={"trip_request": result.get("trip_request"), "plan": plan},
        )
    ]

    for key, node in (
        ("itinerary", "itinerary"),
        ("recommendations", "recommendation"),
        ("cost_report", "cost"),
    ):
        if result.get(key):
            steps.append(
                ToolCallData(
                    name=node,
                    label=NODE_META[node]["label"],
                    icon=NODE_META[node]["icon"],
                    status="done",
                    input={},
                    output=result.get(key),
                )
            )

    steps.append(
        ToolCallData(
            name="synthesize",
            label=NODE_META["synthesize"]["label"],
            icon=NODE_META["synthesize"]["icon"],
            status="error" if errors else "done",
            input={},
            output=answer[:300] if answer else (errors[0] if errors else None),
        )
    )

    return steps
