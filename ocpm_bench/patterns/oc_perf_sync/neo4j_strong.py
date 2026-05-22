"""W1 via Neo4j (strong): mirror of the Kuzu strong query.

``labels(n)[0]`` instead of ``LABEL(n)`` (Neo4j idiom); ``epochSeconds``
property on the datetime values for whole-second diffs without
``date_diff`` / ``to_epoch_ms`` calls.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry

_CYPHER = """
MATCH (o)<-[:E2O]-(e)
WITH o, e ORDER BY e.time, e.id
WITH o, COLLECT({eid: e.id, t: e.time, type: labels(e)[0]}) AS evs
UNWIND range(1, size(evs) - 1) AS i
WITH evs[i].eid AS eid, evs[i].type AS activity, evs[i - 1].t AS pred_t
WITH eid, activity, MIN(pred_t) AS t_min, MAX(pred_t) AS t_max
WITH activity, (t_max.epochSeconds - t_min.epochSeconds) AS span_s
RETURN activity, toInteger(SUM(span_s)) AS total_sync_seconds, COUNT(*) AS cnt
"""


def run(model, _inputs) -> list[tuple[str, int, int]]:
    rows = model.execute_cypher(_CYPHER)
    return [(str(a), int(t), int(c)) for a, t, c in rows]


registry.register_impl("oc_perf_sync", "neo4j_strong", sys.modules[__name__])
