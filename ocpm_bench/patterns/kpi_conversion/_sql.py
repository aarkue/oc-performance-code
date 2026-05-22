"""K2 (conversion rate) via SQLite/DuckDB (shared with strong-rels variants).

Source -> O2O -> Target -> E2O <- Event with `activity`. Returns fraction of
source objects whose linked target object reached `activity`.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.patterns.kpi_conversion import KPIConversionInputs

_K2_SQL = """
SELECT
  CAST(COUNT(DISTINCT a.ocel_id) AS DOUBLE)
  / CAST(NULLIF((SELECT COUNT(*) FROM object WHERE ocel_type = :source_type), 0) AS DOUBLE)
  AS conv_rate
FROM object a
JOIN object_object oo ON oo.ocel_source_id = a.ocel_id
JOIN object t         ON t.ocel_id = oo.ocel_target_id
JOIN event_object eo  ON eo.ocel_object_id = t.ocel_id
JOIN event e          ON e.ocel_id = eo.ocel_event_id
WHERE a.ocel_type = :source_type
  AND t.ocel_type = :target_type
  AND e.ocel_type = :activity
"""

# SQLite has no DOUBLE; REAL is equivalent.
_K2_SQL_SQLITE = _K2_SQL.replace("DOUBLE", "REAL")


def run(model, inputs: KPIConversionInputs) -> float:
    sql = _K2_SQL_SQLITE if model.name.startswith("sqlite") else _K2_SQL
    rows = model.execute_sql(sql, {
        "activity": inputs.activity,
        "source_type": inputs.source_type,
        "target_type": inputs.target_type,
    })
    return float(rows[0][0]) if rows and rows[0][0] is not None else 0.0


for _m in ("sqlite_mem", "duckdb", "sqlite_mem_strong_rels", "duckdb_strong_rels"):
    registry.register_impl("kpi_conversion", _m, sys.modules[__name__])
