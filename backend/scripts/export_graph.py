"""Export the compiled travel graph to PNG for docs/architecture.md.

Regenerate after changing graph wiring:

    cd backend && uv run python scripts/export_graph.py

Writes ``docs/graph.png`` (embedded in architecture.md). Requires pygraphviz
or network access for LangGraph's PNG renderer; if unavailable the script
prints the error and exits non-zero.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The script lives in backend/scripts/; add backend/src to sys.path so it can
# import the app package without an editable install.
_backend = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_backend / "src"))

from app.graph.builder import build_travel_graph  # noqa: E402

_docs = _backend.parent / "docs"  # repo-root/docs


def main() -> None:
    # No checkpointer needed — we only draw the topology, never run the graph.
    drawable = build_travel_graph().get_graph()

    try:
        png = drawable.draw_mermaid_png()
    except Exception as exc:  # noqa: BLE001 — surface the renderer requirement
        sys.exit(f"could not render graph.png ({exc})")
    png_path = _docs / "graph.png"
    png_path.write_bytes(png)
    print(f"wrote {png_path}")


if __name__ == "__main__":
    main()
