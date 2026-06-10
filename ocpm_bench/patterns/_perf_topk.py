"""Top-K cap for the per-event perf patterns (sync, sojourn).

These patterns emit one row per event (~1.2M for BPIC17). Returning all of them lets the
engine->Python transfer dominate the timing instead of the compute, so each engine truncates
in-engine to the top-K rows by value. Set PERF_TOP_K to 0 (or None) to return all rows.
"""

from __future__ import annotations

PERF_TOP_K: int | None = 100


def perf_top_k() -> int | None:
    return PERF_TOP_K if PERF_TOP_K and PERF_TOP_K > 0 else None
