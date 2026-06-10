"""Sojourn via Kuzu (strong + weak): per-event time since the latest predecessor.

``MAX`` of the incoming ``:DF`` predecessor times, subtracted from the event's
own time. In integer microseconds, all in-engine.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.patterns._perf_topk import perf_top_k

_PRED_US = "to_epoch_ms(e2.time)*1000 + date_part('microsecond',e2.time)%1000"
_EVENT_US = "to_epoch_ms(e.time)*1000 + date_part('microsecond',e.time)%1000"

_STRONG = f"""
MATCH (e2)-[:DF]->(e)
WITH e, MAX({_PRED_US}) AS latest
RETURN e.id AS eid, ({_EVENT_US} - latest) AS sojourn_us
"""

_WEAK = f"""
MATCH (e2:Event)-[:DF]->(e:Event)
WITH e, MAX({_PRED_US}) AS latest
RETURN e.id AS eid, ({_EVENT_US} - latest) AS sojourn_us
"""


def run(model, _inputs) -> list[tuple[str, int]]:
    cypher = _WEAK if model.name == "kuzu_weak" else _STRONG
    k = perf_top_k()
    if k is not None:
        cypher += f"\nORDER BY sojourn_us DESC, eid ASC\nLIMIT {k}"
    rows = model.execute_cypher(cypher)
    return [(str(eid), int(s)) for eid, s in rows]


registry.register_impl("oc_perf_sojourn", "kuzu", sys.modules[__name__])
registry.register_impl("oc_perf_sojourn", "kuzu_weak", sys.modules[__name__])
