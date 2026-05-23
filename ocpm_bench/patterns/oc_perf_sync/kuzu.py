"""W1 via Kuzu (strong + weak).

Kuzu rejects nested aggregation, so per-event predecessor timestamps are
emitted as flat rows and aggregated (min/max -> span) in Python.
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
UNWIND range(2, size(eids)) AS i
RETURN eids[i] AS eid,
       types[i] AS activity,
       (to_epoch_ms(times[i - 1]) / 1000) * 1000000
         + (date_part('microsecond', times[i - 1]) % 1000000) AS pred_us
"""

_WEAK_CYPHER = """
MATCH (o:Object)<-[:E2O]-(e:Event)
WITH o, e ORDER BY e.time, e.id
LIMIT 9223372036854775807
WITH o,
     COLLECT(e.id) AS eids,
     COLLECT(e.time) AS times,
     COLLECT(e.type) AS types
UNWIND range(2, size(eids)) AS i
RETURN eids[i] AS eid,
       types[i] AS activity,
       (to_epoch_ms(times[i - 1]) / 1000) * 1000000
         + (date_part('microsecond', times[i - 1]) % 1000000) AS pred_us
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
    per_event_min: dict[str, int] = {}
    per_event_max: dict[str, int] = {}
    per_event_act: dict[str, str] = {}
    for eid, activity, pred_us in rows:
        if eid in per_event_min:
            if pred_us < per_event_min[eid]:
                per_event_min[eid] = pred_us
            if pred_us > per_event_max[eid]:
                per_event_max[eid] = pred_us
        else:
            per_event_min[eid] = pred_us
            per_event_max[eid] = pred_us
            per_event_act[eid] = activity
    totals: dict[str, int] = defaultdict(int)
    counts: dict[str, int] = defaultdict(int)
    for eid, act in per_event_act.items():
        span_s = (per_event_max[eid] - per_event_min[eid]) // 1_000_000
        totals[act] += span_s
        counts[act] += 1
    return [(str(a), totals[a], counts[a]) for a in totals]


registry.register_impl("oc_perf_sync", "kuzu", sys.modules[__name__])
registry.register_impl("oc_perf_sync", "kuzu_weak", sys.modules[__name__])
