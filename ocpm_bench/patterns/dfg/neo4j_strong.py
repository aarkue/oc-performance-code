"""DFG via Neo4j (strongly-typed schema)."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models.primitives import clean_type_name
from ocpm_bench.patterns.base import PerTypeInputs

_DFG_CYPHER = """
MATCH (o:`{object_type}`)<-[:E2O]-(e)
WITH o, labels(e)[0] AS activity, e.time AS t, e.id AS eid
ORDER BY t, eid
WITH o, COLLECT(activity) AS trace
UNWIND range(0, size(trace) - 2) AS i
RETURN trace[i] AS src, trace[i+1] AS tgt, COUNT(*) AS cnt
"""


def run(model, inputs: PerTypeInputs) -> list[tuple]:
    cypher = _DFG_CYPHER.format(object_type=clean_type_name(inputs.object_type))
    rows = model.execute_cypher(cypher)
    return [(src, tgt, int(cnt)) for src, tgt, cnt in rows]


registry.register_impl("dfg", "neo4j_strong", sys.modules[__name__])
