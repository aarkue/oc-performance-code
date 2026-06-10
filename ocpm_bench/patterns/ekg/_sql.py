"""EKG via SQLite/DuckDB: execute corpus SQL, preferring engine-specific override."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OCPQInputs


def pre_run(model) -> None:
    # Build the event-times union once per cell (untimed), like the oc_perf impls.
    model._ekg_union_cte = model.event_times_union()


def run(model, inputs: OCPQInputs) -> list[tuple]:
    sql = inputs.query_body.get(f"sql-{model.name}", inputs.query_body["sql"])
    if "{union_cte}" in sql:
        union_cte = getattr(model, "_ekg_union_cte", None) or model.event_times_union()
        sql = sql.replace("{union_cte}", union_cte)
    return model.execute_sql(sql)


for _m in ("sqlite_mem", "duckdb", "sqlite_mem_strong_rels", "duckdb_strong_rels",
           "sqlite_mem_weak", "duckdb_weak"):
    registry.register_impl("ekg", _m, sys.modules[__name__])
