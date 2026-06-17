"""Agent tools: deterministic computation + real-time external lookup.

Cost tools are deterministic (no LLM in the loop) so correctness contracts like
budget status and totals are guaranteed. The flight tool wraps a live scraper with
a curated fallback. Agents drive these via bind_tools; see loop.py for the runner.
"""
