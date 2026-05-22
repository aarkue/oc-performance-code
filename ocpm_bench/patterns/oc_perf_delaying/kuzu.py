"""W2 via Kuzu (strong + weak): per-event argmax + Python count.

Kuzu rejects nested aggregation (`COUNT(*)` over a column derived from
`COLLECT(...)`), so the per-event winning df-edge is emitted as a flat
list of `(pred_activity, object_type)` rows; Python aggregates the
counts.
"""

from __future__ import annotations

import sys
from collections import Counter

from ocpm_bench.harness import registry

_STRONG_CYPHER = """
MATCH (o)<-[:E2O]-(e)
WHERE LABEL(o) IN $object_labels AND LABEL(e) IN $event_labels
WITH o, e ORDER BY e.time, e.id
LIMIT 9223372036854775807
WITH o,
     COLLECT(e.id) AS eids,
     COLLECT(e.time) AS times,
     COLLECT(LABEL(e)) AS types
UNWIND range(1, size(eids) - 1) AS i
WITH eids[i] AS eid,
     times[i - 1] AS pred_t,
     types[i - 1] AS pred_activity,
     o.id AS o_id,
     LABEL(o) AS o_type
ORDER BY pred_t DESC, o_id ASC
LIMIT 9223372036854775807
WITH eid, COLLECT(pred_activity) AS acts, COLLECT(o_type) AS otypes
RETURN acts[0] AS pred_activity, otypes[0] AS o_type
"""

_WEAK_CYPHER = """
MATCH (o:Object)<-[:E2O]-(e:Event)
WITH o, e ORDER BY e.time, e.id
LIMIT 9223372036854775807
WITH o,
     COLLECT(e.id) AS eids,
     COLLECT(e.time) AS times,
     COLLECT(e.type) AS types
UNWIND range(1, size(eids) - 1) AS i
WITH eids[i] AS eid,
     times[i - 1] AS pred_t,
     types[i - 1] AS pred_activity,
     o.id AS o_id,
     o.type AS o_type
ORDER BY pred_t DESC, o_id ASC
LIMIT 9223372036854775807
WITH eid, COLLECT(pred_activity) AS acts, COLLECT(o_type) AS otypes
RETURN acts[0] AS pred_activity, otypes[0] AS o_type
"""


def run(model, _inputs) -> list[tuple[str, str, int]]:
    if model.name == "kuzu_weak":
        rows = model.execute_cypher(_WEAK_CYPHER)
    else:
        rows = model.execute_cypher(
            _STRONG_CYPHER,
            {
                "object_labels": model._object_labels,
                "event_labels": model._event_labels,
            },
        )
    counts = Counter((str(a), str(t)) for a, t in rows)
    return [(a, t, c) for (a, t), c in counts.items()]


registry.register_impl("oc_perf_delaying", "kuzu", sys.modules[__name__])
registry.register_impl("oc_perf_delaying", "kuzu_weak", sys.modules[__name__])
