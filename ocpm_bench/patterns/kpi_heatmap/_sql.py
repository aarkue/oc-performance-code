"""K1 (heatmap) via SQLite/DuckDB (shared with strong-rels variants)."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry

_K1_SQL = """
SELECT e.ocel_type AS activity, o.ocel_type AS object_type, COUNT(*) AS n
FROM event_object eo
JOIN event e  ON e.ocel_id = eo.ocel_event_id
JOIN object o ON o.ocel_id = eo.ocel_object_id
GROUP BY e.ocel_type, o.ocel_type
"""

# Strong-rels: types come from the view's constant columns, no event/object join.
_K1_SQL_STRONG_RELS = """
SELECT ocel_event_type AS activity, ocel_object_type AS object_type, COUNT(*) AS n
FROM event_object
GROUP BY ocel_event_type, ocel_object_type
"""


def run(model, _inputs) -> list[tuple[str, str, int]]:
    sql = _K1_SQL_STRONG_RELS if model.name.endswith("strong_rels") else _K1_SQL
    return [
        (str(a), str(t), int(n))
        for a, t, n in model.execute_sql(sql)
    ]


for _m in ("sqlite_mem", "duckdb", "sqlite_mem_strong_rels", "duckdb_strong_rels"):
    registry.register_impl("kpi_heatmap", _m, sys.modules[__name__])
