"""Sojourn via Neo4j (strong): per-event time since the latest predecessor."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.patterns._perf_topk import perf_top_k

_CYPHER = """
MATCH (e2)-[:DF]->(e)
WITH e, MAX(e2.time.epochSeconds * 1000000 + e2.time.nanosecond / 1000) AS latest
RETURN e.id AS eid,
       (e.time.epochSeconds * 1000000 + e.time.nanosecond / 1000) - latest AS sojourn_us
"""


def run(model, _inputs) -> list[tuple[str, int]]:
    cypher = _CYPHER
    k = perf_top_k()
    if k is not None:
        cypher += f"\nORDER BY sojourn_us DESC, eid ASC\nLIMIT {k}"
    rows = model.execute_cypher(cypher)
    return [(str(eid), int(s)) for eid, s in rows]


registry.register_impl("oc_perf_sojourn", "neo4j_strong", sys.modules[__name__])
