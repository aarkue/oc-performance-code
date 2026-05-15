"""DFG via SQLite/DuckDB: shared LEAD/UNION/JOIN query (template in `_sql_ocel`)."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models._sql_ocel import DFG_SQL_TEMPLATE, build_event_times_union
from ocpm_bench.patterns.base import PerTypeInputs


def pre_run(model) -> None:
    model._union_cte = build_event_times_union(model.execute_sql)


def run(model, inputs: PerTypeInputs) -> list[tuple[str, str, int]]:
    sql = DFG_SQL_TEMPLATE.format(union_cte=model._union_cte)
    rows = model.execute_sql(sql, {"object_type": inputs.object_type})
    return [(src, tgt, int(cnt)) for src, tgt, cnt in rows]


for _m in ("sqlite_mem", "duckdb"):
    registry.register_impl("dfg", _m, sys.modules[__name__])
