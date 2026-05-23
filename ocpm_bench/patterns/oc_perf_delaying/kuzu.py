"""W2 via Kuzu (strong + weak).

Kuzu rejects nested aggregation over COLLECT-derived values, so the query
emits per-df-edge rows and Python picks the latest predecessor per event
(tie-break: object ocel_id ascending) and aggregates.
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
UNWIND range(2, size(eids)) AS i
RETURN eids[i] AS eid,
       (to_epoch_ms(times[i - 1]) / 1000) * 1000000
         + (date_part('microsecond', times[i - 1]) % 1000000) AS pred_us,
       types[i - 1] AS pred_activity,
       o.id AS o_id,
       LABEL(o) AS o_type
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
       (to_epoch_ms(times[i - 1]) / 1000) * 1000000
         + (date_part('microsecond', times[i - 1]) % 1000000) AS pred_us,
       types[i - 1] AS pred_activity,
       o.id AS o_id,
       o.type AS o_type
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
    # Per-event argmax: maximise pred_us; tie-break on o_id ascending.
    best: dict[str, tuple[int, str, str, str]] = {}
    for eid, pred_us, pred_activity, o_id, o_type in rows:
        cand = (pred_us, o_id, pred_activity, o_type)
        cur = best.get(eid)
        if cur is None:
            best[eid] = cand
        else:
            if pred_us > cur[0] or (pred_us == cur[0] and o_id < cur[1]):
                best[eid] = cand
    counts: Counter[tuple[str, str]] = Counter()
    for _eid, (_pt, _oid, pred_activity, o_type) in best.items():
        counts[(pred_activity, o_type)] += 1
    return [(str(a), str(t), c) for (a, t), c in counts.items()]


registry.register_impl("oc_perf_delaying", "kuzu", sys.modules[__name__])
registry.register_impl("oc_perf_delaying", "kuzu_weak", sys.modules[__name__])
