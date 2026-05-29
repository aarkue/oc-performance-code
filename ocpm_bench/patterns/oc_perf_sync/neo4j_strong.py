"""W1 via Neo4j (strong): mirror of Kuzu strong query.

Subtract at microsecond resolution then floor; ``epochSeconds`` first
truncates sub-second fractions and drifts per-event spans.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry

_CYPHER = """
MATCH (o)<-[:E2O]-(e)
WITH o, e ORDER BY e.time, e.id
WITH o, COLLECT({eid: e.id,
                 us: e.time.epochSeconds * 1000000 + e.time.nanosecond / 1000,
                 type: labels(e)[0]}) AS evs
UNWIND range(1, size(evs) - 1) AS i
WITH evs[i].eid AS eid, evs[i].type AS activity, evs[i - 1].us AS pred_us
WITH eid, activity, MIN(pred_us) AS us_min, MAX(pred_us) AS us_max
WITH activity, (us_max - us_min) / 1000000 AS span_s
RETURN activity, toInteger(SUM(span_s)) AS total_sync_seconds, COUNT(*) AS cnt
"""

_CYPHER_WITH_DF_EDGES = """
MATCH (e2) -[df:DF]-> (e) 
WITH e, MIN(e2.time) AS enablingTime, MAX(e2.time) AS delayingTime
RETURN MAX(duration.inSeconds(enablingTime,delayingTime)),labels(e)[0]
"""

_CYPHER_WITH_EVENTS_AND_DF_EDGES = """
MATCH (e2:Event) -[df:DF]-> (e:Event) 
WITH e, MIN(e2.time) AS enablingTime, MAX(e2.time) AS delayingTime
RETURN MAX(duration.inSeconds(enablingTime,delayingTime)),labels(e)[0]
"""


def run(model, _inputs) -> list[tuple[str, int, int]]:
    rows = model.execute_cypher(_CYPHER)
    return [(str(a), int(t), int(c)) for a, t, c in rows]


registry.register_impl("oc_perf_sync", "neo4j_strong", sys.modules[__name__])
