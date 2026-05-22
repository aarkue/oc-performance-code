"""W2 via Neo4j (strong): mirror of the Kuzu strong query."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry

_CYPHER = """
MATCH (o)<-[:E2O]-(e)
WITH o, e ORDER BY e.time, e.id
WITH o, COLLECT({eid: e.id, t: e.time, type: labels(e)[0]}) AS evs
UNWIND range(1, size(evs) - 1) AS i
WITH evs[i].eid AS eid,
     evs[i - 1].t AS pred_t,
     evs[i - 1].type AS pred_activity,
     o.id AS o_id,
     labels(o)[0] AS o_type
ORDER BY pred_t DESC, o_id ASC
WITH eid,
     COLLECT(pred_activity)[0] AS best_act,
     COLLECT(o_type)[0] AS best_type
RETURN best_act AS pred_activity, best_type AS o_type, COUNT(*) AS cnt
"""


def run(model, _inputs) -> list[tuple[str, str, int]]:
    rows = model.execute_cypher(_CYPHER)
    return [(str(a), str(t), int(c)) for a, t, c in rows]


registry.register_impl("oc_perf_delaying", "neo4j_strong", sys.modules[__name__])
