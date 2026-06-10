"""DuckDB weak: single wide tables, per-type names re-exposed as views.

Derived from the cached OCEL 2.0 DuckDB by consolidating the per-activity /
per-object-type tables (see `_sql_weak`).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb

from ocpm_bench.datasets.base import Dataset
from ocpm_bench.harness import cache as _cache
from ocpm_bench.harness import registry
from ocpm_bench.models._sql_weak import build_weak_schema
from ocpm_bench.models.duckdb import DuckDBModel, _export_duckdb


def _build_weak_duckdb(out_path: Path, hybrid_path: Path) -> None:
    shutil.copy(hybrid_path, out_path)
    con = duckdb.connect(str(out_path))
    try:
        ev_types = [r[0] for r in con.execute(
            "SELECT ocel_type FROM event_map_type ORDER BY ocel_type"
        ).fetchall()]
        ob_types = [r[0] for r in con.execute(
            "SELECT ocel_type FROM object_map_type ORDER BY ocel_type"
        ).fetchall()]

        def _execute(sql: str, params: list | None = None) -> list[tuple]:
            cur = con.execute(sql) if params is None else con.execute(sql, params)
            return cur.fetchall()

        def _columns(table: str) -> list[str]:
            lit = table.replace("'", "''")
            return [r[1] for r in con.execute(f"PRAGMA table_info('{lit}')").fetchall()]

        build_weak_schema(_execute, _columns, ev_types, ob_types)
        con.commit()
    finally:
        con.close()


class DuckDBWeakModel(DuckDBModel):
    name = "duckdb_weak"

    def setup(self, dataset: Dataset) -> None:
        dataset.fetch()
        src = dataset.resolved_path()
        hybrid_path = _cache.get_or_export(
            dataset=dataset.name,
            model="duckdb",
            source=src,
            payload_name=f"{dataset.name}-strong.duckdb",
            export=lambda out: _export_duckdb(src, out),
        )
        self._path = _cache.get_or_export(
            dataset=dataset.name,
            model=self.name,
            source=src,
            payload_name=f"{dataset.name}-weak.duckdb",
            export=lambda out: _build_weak_duckdb(out, hybrid_path),
        )
        self._conn = self._connect()

    def event_times_union(self) -> str:
        return "SELECT ocel_id, ocel_time FROM event_attr"


registry.register_model("duckdb_weak", DuckDBWeakModel)
