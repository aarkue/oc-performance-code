"""DFG via Kuzu."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import PerTypeInputs

# Kuzu requires LIMIT after ORDER BY in WITH; i64::MAX = no real cap
_DFG_STRONG_CYPHER = """
MATCH (o:`{object_type}`)<-[:E2O]-(e)
WITH o, LABEL(e) AS activity, e.time AS t, e.id AS eid
ORDER BY t, eid
LIMIT 9223372036854775807
WITH o, COLLECT(activity) AS trace
UNWIND range(1, size(trace) - 1) AS i
RETURN trace[i] AS src, trace[i+1] AS tgt, COUNT(*) AS cnt
"""

# Kuzu requires LIMIT after ORDER BY in WITH; i64::MAX = no real cap
_DFG_WEAK_CYPHER = """
MATCH (o:Object)<-[:E2O]-(e:Event)
WHERE o.type = $object_type
WITH o, e.type AS activity, e.time AS t, e.id AS eid
ORDER BY t, eid
LIMIT 9223372036854775807
WITH o, COLLECT(activity) AS trace
UNWIND range(1, size(trace) - 1) AS i
RETURN trace[i] AS src, trace[i+1] AS tgt, COUNT(*) AS cnt
"""


def run(model, inputs: PerTypeInputs) -> list[tuple]:
    if model.name == "kuzu_weak":
        rows = model.execute_cypher(_DFG_WEAK_CYPHER, {"object_type": inputs.object_type})
    else:
        cypher = _DFG_STRONG_CYPHER.format(object_type=inputs.object_type)
        rows = model.execute_cypher(cypher)
    return [(src, tgt, int(cnt)) for src, tgt, cnt in rows]


registry.register_impl("dfg", "kuzu", sys.modules[__name__])
registry.register_impl("dfg", "kuzu_weak", sys.modules[__name__])
