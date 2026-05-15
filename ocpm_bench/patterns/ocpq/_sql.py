"""OCPQ via SQLite/DuckDB: execute corpus SQL, preferring engine-specific override."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OCPQInputs


def run(model, inputs: OCPQInputs) -> list[tuple]:
    sql = inputs.query_body.get(f"sql-{model.name}", inputs.query_body["sql"])
    return model.execute_sql(sql)


for _m in ("sqlite_mem", "duckdb", "sqlite_mem_strong_rels", "duckdb_strong_rels"):
    registry.register_impl("ocpq", _m, sys.modules[__name__])
