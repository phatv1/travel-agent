"""Export the travel agent LangGraph as a PNG diagram.

Renders via the Mermaid API (mermaid.ink) — no extra packages required,
just network access.

Run from backend/:
    uv run python scripts/export_graph.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `app` importable when run as a plain script (pyproject pythonpath is [src]).
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from app.graph.builder import build_travel_graph  # noqa: E402


def main() -> None:
    out = ROOT.parent / "docs" / "travel_graph.png"
    out.parent.mkdir(parents=True, exist_ok=True)

    draw = build_travel_graph().get_graph()
    png = draw.draw_mermaid_png(output_file_path=str(out))
    print(f"wrote {out} ({len(png)} bytes)")


if __name__ == "__main__":
    main()
