"""W1 via SQLite/DuckDB: df-edge based via LAG OVER PARTITION BY object.

For each (event, related object), the immediate predecessor on that object
is computed with ``LAG(t) OVER (PARTITION BY oid ORDER BY t, eid)``. Per
event, the predecessor set is the (non-NULL) lagged times across its
objects. Sync time = ``MAX - MIN`` of those, summed per activity.

Registered for both weak and strong-rels variants of SQLite and DuckDB
(same query; both schemas expose the base ``event_object`` / ``event`` /
per-activity event tables).
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models._sql_ocel import build_event_times_union

_W1_SQL_DUCKDB = """
WITH event_times AS ({union_cte}),
event_obj AS (
    SELECT
        eo.ocel_event_id AS eid,
        eo.ocel_object_id AS oid,
        e.ocel_type AS activity,
        et.ocel_time AS t
    FROM event_object eo
    JOIN event e ON e.ocel_id = eo.ocel_event_id
    JOIN event_times et ON et.ocel_id = eo.ocel_event_id
),
df_edges AS (
    SELECT
        eid, activity,
        LAG(t) OVER (PARTITION BY oid ORDER BY t, eid) AS pred_t
    FROM event_obj
),
per_event AS (
    SELECT eid, activity, MIN(pred_t) AS t_min, MAX(pred_t) AS t_max
    FROM df_edges
    WHERE pred_t IS NOT NULL
    GROUP BY eid, activity
)
SELECT
    activity,
    CAST(SUM((epoch_us(t_max) - epoch_us(t_min)) // 1000000) AS BIGINT) AS total_sync_seconds,
    COUNT(*) AS cnt
FROM per_event
GROUP BY activity
"""

_W1_SQL_SQLITE = """
WITH event_times AS ({union_cte}),
event_obj AS (
    SELECT
        eo.ocel_event_id AS eid,
        eo.ocel_object_id AS oid,
        e.ocel_type AS activity,
        -- Integer microseconds since epoch. SQLite's `unixepoch(t, 'subsec')`
        -- truncates the microsecond field at double precision (~13 sig
        -- digits); compute the fractional part by string parsing to keep
        -- exact micros, then all arithmetic stays in int64.
        unixepoch(substr(et.ocel_time, 1, 19)) * 1000000 +
        CASE WHEN substr(et.ocel_time, 20, 1) = '.'
             THEN CAST(substr(et.ocel_time, 21, 6) AS INTEGER)
             ELSE 0 END AS t_us
    FROM event_object eo
    JOIN event e ON e.ocel_id = eo.ocel_event_id
    JOIN event_times et ON et.ocel_id = eo.ocel_event_id
),
df_edges AS (
    SELECT
        eid, activity,
        LAG(t_us) OVER (PARTITION BY oid ORDER BY t_us, eid) AS pred_us
    FROM event_obj
),
per_event AS (
    SELECT eid, activity, MIN(pred_us) AS us_min, MAX(pred_us) AS us_max
    FROM df_edges
    WHERE pred_us IS NOT NULL
    GROUP BY eid, activity
)
SELECT
    activity,
    CAST(SUM((us_max - us_min) / 1000000) AS INTEGER) AS total_sync_seconds,
    COUNT(*) AS cnt
FROM per_event
GROUP BY activity
"""


def pre_run(model) -> None:
    model._union_cte = build_event_times_union(model.execute_sql)


def run(model, _inputs) -> list[tuple[str, int, int]]:
    union_cte = getattr(model, "_union_cte", None) or build_event_times_union(
        model.execute_sql
    )
    is_sqlite = model.name.startswith("sqlite")
    template = _W1_SQL_SQLITE if is_sqlite else _W1_SQL_DUCKDB
    sql = template.format(union_cte=union_cte)
    rows = model.execute_sql(sql)
    return [(str(a), int(t), int(c)) for a, t, c in rows]


for _m in ("sqlite_mem", "duckdb", "sqlite_mem_strong_rels", "duckdb_strong_rels"):
    registry.register_impl("oc_perf_sync", _m, sys.modules[__name__])
