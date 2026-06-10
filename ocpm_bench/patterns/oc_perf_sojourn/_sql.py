"""Sojourn via SQLite/DuckDB: per-event time since the latest predecessor.

Per object, the immediate predecessor of an event is found with ``LAG``. Per
event, the sojourn time is the event's own time minus its latest predecessor,
in integer microseconds since epoch.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.patterns._perf_topk import perf_top_k

_US_DUCKDB = "epoch_us(et.ocel_time)"
_US_SQLITE = (
    "unixepoch(substr(et.ocel_time, 1, 19)) * 1000000 + "
    "CASE WHEN substr(et.ocel_time, 20, 1) = '.' "
    "THEN CAST(substr(et.ocel_time, 21, 6) AS INTEGER) ELSE 0 END"
)

_SQL = """
WITH event_times AS ({union_cte}),
event_obj AS (
    SELECT eo.ocel_event_id AS eid, eo.ocel_object_id AS oid, {us} AS t_us
    FROM event_object eo
    JOIN event_times et ON et.ocel_id = eo.ocel_event_id
),
preds AS (
    SELECT eid, t_us AS e_us,
           LAG(t_us) OVER (PARTITION BY oid ORDER BY t_us, eid) AS pred_us
    FROM event_obj
)
SELECT eid, MAX(e_us) - MAX(pred_us) AS sojourn_us
FROM preds WHERE pred_us IS NOT NULL GROUP BY eid
"""


def pre_run(model) -> None:
    model._union_cte = model.event_times_union()


def run(model, _inputs) -> list[tuple[str, int]]:
    union_cte = getattr(model, "_union_cte", None) or model.event_times_union()
    us = _US_SQLITE if model.name.startswith("sqlite") else _US_DUCKDB
    sql = _SQL.format(union_cte=union_cte, us=us)
    k = perf_top_k()
    if k is not None:
        sql += f"\nORDER BY sojourn_us DESC, eid ASC\nLIMIT {k}"
    rows = model.execute_sql(sql)
    return [(str(eid), int(s)) for eid, s in rows]


for _m in ("sqlite_mem", "duckdb", "sqlite_mem_strong_rels", "duckdb_strong_rels",
           "sqlite_mem_weak", "duckdb_weak"):
    registry.register_impl("oc_perf_sojourn", _m, sys.modules[__name__])
