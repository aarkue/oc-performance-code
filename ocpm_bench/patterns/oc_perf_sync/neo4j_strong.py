"""W1 via Neo4j (strong): per-event sync time over materialized DF edges.

Span = ``MAX(pred.time) - MIN(pred.time)`` over an event's incoming ``:DF`` edges,
floored to whole seconds, summed per activity. Computed in integer microseconds
to match the ``linked_ocel`` oracle's floor.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry

_CYPHER = """
MATCH (e2)-[:DF]->(e)
WITH e, labels(e)[0] AS activity,
     MIN(e2.time.epochSeconds * 1000000 + e2.time.nanosecond / 1000) AS us_min,
     MAX(e2.time.epochSeconds * 1000000 + e2.time.nanosecond / 1000) AS us_max
WITH activity, (us_max - us_min) / 1000000 AS span_s
RETURN activity, toInteger(SUM(span_s)) AS total_sync_seconds, COUNT(*) AS cnt
"""


def run(model, _inputs) -> list[tuple[str, int, int]]:
    rows = model.execute_cypher(_CYPHER)
    return [(str(a), int(t), int(c)) for a, t, c in rows]


registry.register_impl("oc_perf_sync", "neo4j_strong", sys.modules[__name__])
