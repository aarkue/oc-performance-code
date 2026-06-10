"""Variants via SQLite/DuckDB: GROUP_CONCAT vs STRING_AGG, otherwise identical."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models._sql_ocel import variants_sql_template
from ocpm_bench.patterns.base import PerTypeInputs
from ocpm_bench.patterns.variants import DELIM

_TEMPLATES = {
    "sqlite": variants_sql_template("GROUP_CONCAT", DELIM),
    "duckdb": variants_sql_template("STRING_AGG",   DELIM),
}


def pre_run(model) -> None:
    model._union_cte = model.event_times_union()


def run(model, inputs: PerTypeInputs) -> list[tuple]:
    dialect = "sqlite" if model.name.startswith("sqlite") else "duckdb"
    sql = _TEMPLATES[dialect].format(union_cte=model._union_cte)
    rows = model.execute_sql(sql, {"object_type": inputs.object_type})
    return [(tuple(trace_str.split(DELIM)), int(cnt)) for trace_str, cnt in rows]


for _m in ("sqlite_mem", "duckdb", "sqlite_mem_weak", "duckdb_weak"):
    registry.register_impl("variants", _m, sys.modules[__name__])
