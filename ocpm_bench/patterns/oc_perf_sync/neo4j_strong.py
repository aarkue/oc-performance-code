"""Sync via Neo4j (strong): per-event span + delaying object over ``:DF`` edges.

Span = ``MAX - MIN`` of the incoming predecessor times (integer microseconds);
the delaying object is the ``df.id`` of the latest predecessor (``ORDER BY`` time
DESC, tie-break object ocel_id, then ``COLLECT[0]``).
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.patterns._perf_topk import perf_top_k

_CYPHER = """
MATCH (e2)-[df:DF]->(e)
WITH e, df.id AS oid, (e2.time.epochSeconds * 1000000 + e2.time.nanosecond / 1000) AS pt
ORDER BY pt DESC, oid ASC
WITH e, COLLECT(oid)[0] AS delaying_object, MIN(pt) AS mn, MAX(pt) AS mx
RETURN e.id AS eid, (mx - mn) AS sync_us, delaying_object
"""


def run(model, _inputs) -> list[tuple[str, int, str]]:
    cypher = _CYPHER
    k = perf_top_k()
    if k is not None:
        cypher += f"\nORDER BY sync_us DESC, eid ASC\nLIMIT {k}"
    rows = model.execute_cypher(cypher)
    return [(str(eid), int(s), str(o)) for eid, s, o in rows]


registry.register_impl("oc_perf_sync", "neo4j_strong", sys.modules[__name__])
