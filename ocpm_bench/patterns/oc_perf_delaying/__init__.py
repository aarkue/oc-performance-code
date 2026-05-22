"""P3 / W2: counts of (predecessor activity, correlating object type) pairs
that appear as the latest predecessor of an event.

For each event ``e``, enumerate all df-edges ``(p, o)`` where ``o`` is an
object related to both ``p`` and ``e`` via E2O and ``p.time < e.time``.
Pick the df-edge with the latest ``p.time``; break ties on ``o.ocel_id``
ascending (handles the case where multiple objects of ``e`` share the
same predecessor event). Emit one ``(p.activity, o.type)`` tuple per
event, then count occurrences.

Output is the unordered set of ``(predecessor_activity, object_type, count)``
triples. Events without predecessors are skipped.
"""

from __future__ import annotations

from typing import Any

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OutputSchema, PatternContract

_OUTPUT = OutputSchema(
    kind="tuple_set",
    columns=["predecessor_activity", "object_type", "count"],
)


def _instances(_dataset) -> list[tuple[str, Any]]:
    return [("W2", None)]


CONTRACT = PatternContract(
    name="oc_perf_delaying",
    output=_OUTPUT,
    instances=_instances,
    oracle_model="duckdb",
)

registry.register_pattern(CONTRACT)
