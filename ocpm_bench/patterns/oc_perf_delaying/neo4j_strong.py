"""W2 via Neo4j (strong): latest directly-preceding event's (activity, object
type) over ``:DF`` edges, counted per pair. ``df.id`` is the object ocel_id,
``df.EntityType`` the object type. Tie-break: object ocel_id ascending.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry

_CYPHER = """
MATCH (e2)-[df:DF]->(e)
WITH e, e2, df ORDER BY e2.time DESC, df.id ASC
WITH e, COLLECT({act: labels(e2)[0], otype: df.EntityType})[0] AS best
RETURN best.act AS pred_activity, best.otype AS o_type, COUNT(*) AS cnt
"""


def run(model, _inputs) -> list[tuple[str, str, int]]:
    rows = model.execute_cypher(_CYPHER)
    return [(str(a), str(t), int(c)) for a, t, c in rows]


registry.register_impl("oc_perf_delaying", "neo4j_strong", sys.modules[__name__])
