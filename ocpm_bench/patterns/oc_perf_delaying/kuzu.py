"""W2 via Kuzu (strong + weak).

Kuzu rejects nested aggregation over COLLECT-derived values, so the query
emits per-df-edge rows and Python picks the latest predecessor per event
(tie-break: object ocel_id ascending) and aggregates.
"""

from __future__ import annotations

import sys
from collections import Counter

from ocpm_bench.harness import registry

# df.id = object ocel_id, df.EntityType = object type. Python picks the latest
# predecessor per event (tie-break: object ocel_id ascending).
_STRONG_CYPHER = """
MATCH (e2)-[df:DF]->(e)
RETURN e.id AS eid,
       (to_epoch_ms(e2.time) / 1000) * 1000000
         + (date_part('microsecond', e2.time) % 1000000) AS pred_us,
       LABEL(e2) AS pred_activity,
       df.id AS o_id,
       df.EntityType AS o_type
"""

# Weak: same, activity from the node `type` column.
_WEAK_CYPHER = """
MATCH (e2:Event)-[df:DF]->(e:Event)
RETURN e.id AS eid,
       (to_epoch_ms(e2.time) / 1000) * 1000000
         + (date_part('microsecond', e2.time) % 1000000) AS pred_us,
       e2.type AS pred_activity,
       df.id AS o_id,
       df.EntityType AS o_type
"""


def run(model, _inputs) -> list[tuple[str, str, int]]:
    if model.name == "kuzu_weak":
        rows = model.execute_cypher(_WEAK_CYPHER)
    else:
        rows = model.execute_cypher(_STRONG_CYPHER)
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
