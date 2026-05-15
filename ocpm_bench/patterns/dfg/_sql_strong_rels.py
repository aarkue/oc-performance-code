"""DFG via SQLite/DuckDB on the strong-rels schema.

Queries the `event_object` VIEW (one UNION-ALL branch per typed pair, with
the activity and object_type as constant projections). The view replaces
the OCEL 2.0 generic `event_object` table, so the WHERE clause filters on
the projected `ocel_object_type` column directly, with no JOIN to `object` or
`event` needed. On engines that prune branches via constant folding
through UNION ALL, only the typed sub-tables for the requested object_type
are read.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models._sql_ocel import build_event_times_union
from ocpm_bench.patterns.base import PerTypeInputs

_DFG_SQL = """
WITH event_times AS ({union_cte}),
ordered AS (
  SELECT
    eo.ocel_event_type AS activity,
    eo.ocel_object_id  AS object_id,
    et.ocel_time       AS t,
    LEAD(eo.ocel_event_type) OVER (
      PARTITION BY eo.ocel_object_id
      ORDER BY et.ocel_time, eo.ocel_event_id
    ) AS next_activity
  FROM event_object eo
  JOIN event_times et ON et.ocel_id = eo.ocel_event_id
  WHERE eo.ocel_object_type = :object_type
)
SELECT activity AS src, next_activity AS tgt, COUNT(*) AS cnt
FROM ordered
WHERE next_activity IS NOT NULL
GROUP BY activity, next_activity
"""


def pre_run(model) -> None:
    model._union_cte = build_event_times_union(model.execute_sql)


def run(model, inputs: PerTypeInputs) -> list[tuple[str, str, int]]:
    sql = _DFG_SQL.format(union_cte=model._union_cte)
    rows = model.execute_sql(sql, {"object_type": inputs.object_type})
    return [(src, tgt, int(cnt)) for src, tgt, cnt in rows]


for _m in ("sqlite_mem_strong_rels", "duckdb_strong_rels"):
    registry.register_impl("dfg", _m, sys.modules[__name__])
