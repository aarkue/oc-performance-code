"""Variants via SQLite/DuckDB on the strong-rels schema.

Same view-based approach as the DFG strong-rels impl: `event_object` is a
UNION-ALL view with `ocel_event_type` / `ocel_object_type` as constant
projections per branch.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models._sql_ocel import build_event_times_union
from ocpm_bench.patterns.base import PerTypeInputs
from ocpm_bench.patterns.variants import DELIM

_AGG_BY_MODEL = {
    "sqlite_mem_strong_rels": "GROUP_CONCAT",
    "duckdb_strong_rels":     "STRING_AGG",
}


def _template(agg_func: str, delim: str) -> str:
    return f"""
WITH event_times AS ({{union_cte}}),
ordered AS (
  SELECT
    eo.ocel_object_id  AS oid,
    eo.ocel_event_type AS activity,
    et.ocel_time       AS t,
    eo.ocel_event_id   AS eid
  FROM event_object eo
  JOIN event_times et ON et.ocel_id = eo.ocel_event_id
  WHERE eo.ocel_object_type = :object_type
),
traces AS (
  SELECT oid,
         {agg_func}(activity, '{delim}' ORDER BY t, eid) AS trace_str
  FROM ordered
  GROUP BY oid
)
SELECT trace_str, COUNT(*) AS cnt
FROM traces
GROUP BY trace_str
"""


def pre_run(model) -> None:
    model._union_cte = build_event_times_union(model.execute_sql)


def run(model, inputs: PerTypeInputs) -> list[tuple]:
    agg = _AGG_BY_MODEL[model.name]
    sql = _template(agg, DELIM).format(union_cte=model._union_cte)
    rows = model.execute_sql(sql, {"object_type": inputs.object_type})
    return [(tuple(trace_str.split(DELIM)), int(cnt)) for trace_str, cnt in rows]


for _m in ("sqlite_mem_strong_rels", "duckdb_strong_rels"):
    registry.register_impl("variants", _m, sys.modules[__name__])
