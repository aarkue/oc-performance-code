"""W1 via Kuzu (strong + weak).

Kuzu rejects nested aggregation, so per-event predecessor timestamps are
emitted as flat rows and aggregated (min/max -> span) in Python.
"""

from __future__ import annotations

import sys
from collections import defaultdict

from ocpm_bench.harness import registry

# Incoming :DF edges = directly-preceding events (one per shared object).
_STRONG_CYPHER = """
MATCH (e2)-[:DF]->(e)
RETURN e.id AS eid,
       LABEL(e) AS activity,
       (to_epoch_ms(e2.time) / 1000) * 1000000
         + (date_part('microsecond', e2.time) % 1000000) AS pred_us
"""

# Weak: same, activity from the node `type` column (single Event label).
_WEAK_CYPHER = """
MATCH (e2:Event)-[:DF]->(e:Event)
RETURN e.id AS eid,
       e.type AS activity,
       (to_epoch_ms(e2.time) / 1000) * 1000000
         + (date_part('microsecond', e2.time) % 1000000) AS pred_us
"""


def run(model, _inputs) -> list[tuple[str, int, int]]:
    if model.name == "kuzu_weak":
        rows = model.execute_cypher(_WEAK_CYPHER)
    else:
        rows = model.execute_cypher(_STRONG_CYPHER)
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
