"""Variants via SQLite/DuckDB: GROUP_CONCAT vs STRING_AGG, otherwise identical."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models._sql_ocel import build_event_times_union, variants_sql_template
from ocpm_bench.patterns.base import PerTypeInputs
from ocpm_bench.patterns.variants import DELIM

_TEMPLATES = {
    "sqlite_mem": variants_sql_template("GROUP_CONCAT", DELIM),
    "duckdb":     variants_sql_template("STRING_AGG",   DELIM),
}


def pre_run(model) -> None:
    model._union_cte = build_event_times_union(model.execute_sql)


def run(model, inputs: PerTypeInputs) -> list[tuple]:
    sql = _TEMPLATES[model.name].format(union_cte=model._union_cte)
    rows = model.execute_sql(sql, {"object_type": inputs.object_type})
    return [(tuple(trace_str.split(DELIM)), int(cnt)) for trace_str, cnt in rows]


for _m in ("sqlite_mem", "duckdb"):
    registry.register_impl("variants", _m, sys.modules[__name__])
