"""Sync via Kuzu (strong + weak): per-event span + delaying object.

Incoming ``:DF`` edges are an event's directly-preceding events (one per shared
object). The span is ``MAX - MIN`` of their times; the delaying object is the
``df.id`` of the latest one, picked with a ``list_reduce`` argmax (tie-break on
object ocel_id). All in-engine, no Python aggregation.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.patterns._perf_topk import perf_top_k

_PRED_US = "to_epoch_ms(e2.time)*1000 + date_part('microsecond',e2.time)%1000"

_STRONG = f"""
MATCH (e2)-[df:DF]->(e)
WITH e.id AS eid, df.id AS oid, {_PRED_US} AS pt
WITH eid, MIN(pt) AS mn, MAX(pt) AS mx, COLLECT({{pt: pt, oid: oid}}) AS c
WITH eid, mn, mx,
     list_reduce(c, (a, x) ->
        CASE WHEN x.pt > a.pt OR (x.pt = a.pt AND x.oid < a.oid) THEN x ELSE a END) AS best
RETURN eid, (mx - mn) AS sync_us, best.oid AS delaying_object
"""

_WEAK = f"""
MATCH (e2:Event)-[df:DF]->(e:Event)
WITH e.id AS eid, df.id AS oid, {_PRED_US} AS pt
WITH eid, MIN(pt) AS mn, MAX(pt) AS mx, COLLECT({{pt: pt, oid: oid}}) AS c
WITH eid, mn, mx,
     list_reduce(c, (a, x) ->
        CASE WHEN x.pt > a.pt OR (x.pt = a.pt AND x.oid < a.oid) THEN x ELSE a END) AS best
RETURN eid, (mx - mn) AS sync_us, best.oid AS delaying_object
"""


def run(model, _inputs) -> list[tuple[str, int, str]]:
    cypher = _WEAK if model.name == "kuzu_weak" else _STRONG
    k = perf_top_k()
    if k is not None:
        cypher += f"\nORDER BY sync_us DESC, eid ASC\nLIMIT {k}"
    rows = model.execute_cypher(cypher)
    return [(str(eid), int(s), str(o)) for eid, s, o in rows]


registry.register_impl("oc_perf_sync", "kuzu", sys.modules[__name__])
registry.register_impl("oc_perf_sync", "kuzu_weak", sys.modules[__name__])
