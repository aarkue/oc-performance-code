"""W1 via Kuzu (strong + weak): per-object COLLECT + per-event span.

Kuzu rejects multi-stage aggregation in a single query
(`Expression contains nested aggregation`), so the per-event span is
returned as a flat list `(activity, span_seconds)` and aggregated in
Python (Counter-style sum/count). The per-activity aggregation step is
negligible compared with the per-object COLLECT + LAG-style index.
"""

from __future__ import annotations

import sys
from collections import defaultdict

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
WITH eids[i] AS eid, types[i] AS activity, times[i - 1] AS pred_t
LIMIT 9223372036854775807
WITH eid, activity, to_epoch_ms(pred_t) AS pred_ms
LIMIT 9223372036854775807
WITH eid, activity, MAX(pred_ms) AS ms_max, MIN(pred_ms) AS ms_min
RETURN activity, CAST((ms_max - ms_min) / 1000 AS INT64) AS span_s
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
WITH eids[i] AS eid, types[i] AS activity, times[i - 1] AS pred_t
LIMIT 9223372036854775807
WITH eid, activity, to_epoch_ms(pred_t) AS pred_ms
LIMIT 9223372036854775807
WITH eid, activity, MAX(pred_ms) AS ms_max, MIN(pred_ms) AS ms_min
RETURN activity, CAST((ms_max - ms_min) / 1000 AS INT64) AS span_s
"""


def run(model, _inputs) -> list[tuple[str, int, int]]:
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
    totals: dict[str, int] = defaultdict(int)
    counts: dict[str, int] = defaultdict(int)
    for activity, span_s in rows:
        totals[activity] += int(span_s)
        counts[activity] += 1
    return [(str(a), totals[a], counts[a]) for a in totals]


registry.register_impl("oc_perf_sync", "kuzu", sys.modules[__name__])
registry.register_impl("oc_perf_sync", "kuzu_weak", sys.modules[__name__])
