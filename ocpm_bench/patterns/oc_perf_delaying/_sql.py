"""W2 via SQLite/DuckDB: df-edge based via LAG OVER PARTITION BY object.

For each (event, related object) the immediate predecessor on that object
is found with LAG window functions. Per event, the latest df-predecessor
(ties broken on object ocel_id, ascending) is selected via ROW_NUMBER over
the (small) set of per-object df-edges of that event. Result: counts per
(predecessor activity, object type) pair.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models._sql_ocel import build_event_times_union

_W2_SQL = """
WITH event_times AS ({union_cte}),
event_obj AS (
    SELECT
        eo.ocel_event_id AS eid,
        eo.ocel_object_id AS oid,
        e.ocel_type AS activity,
        et.ocel_time AS t,
        o.ocel_type AS o_type
    FROM event_object eo
    JOIN event e ON e.ocel_id = eo.ocel_event_id
    JOIN event_times et ON et.ocel_id = eo.ocel_event_id
    JOIN object o ON o.ocel_id = eo.ocel_object_id
),
df_edges AS (
    SELECT
        eid, oid, o_type,
        LAG(t) OVER (PARTITION BY oid ORDER BY t, eid) AS pred_t,
        LAG(activity) OVER (PARTITION BY oid ORDER BY t, eid) AS pred_activity
    FROM event_obj
),
winners AS (
    SELECT
        pred_activity, o_type,
        ROW_NUMBER() OVER (
            PARTITION BY eid
            ORDER BY pred_t DESC, oid ASC
        ) AS rn
    FROM df_edges
    WHERE pred_t IS NOT NULL
)
SELECT pred_activity, o_type, COUNT(*) AS cnt
FROM winners
WHERE rn = 1
GROUP BY pred_activity, o_type
"""


def pre_run(model) -> None:
    model._union_cte = build_event_times_union(model.execute_sql)


def run(model, _inputs) -> list[tuple[str, str, int]]:
    union_cte = getattr(model, "_union_cte", None) or build_event_times_union(
        model.execute_sql
    )
    sql = _W2_SQL.format(union_cte=union_cte)
    rows = model.execute_sql(sql)
    return [(str(a), str(t), int(c)) for a, t, c in rows]


for _m in ("sqlite_mem", "duckdb", "sqlite_mem_strong_rels", "duckdb_strong_rels"):
    registry.register_impl("oc_perf_delaying", _m, sys.modules[__name__])
