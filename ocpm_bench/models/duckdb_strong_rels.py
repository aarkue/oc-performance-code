"""DuckDB strong-rels: OCEL 2.0 schema with per-pair `event_object` / `object_object`.

Derived from the cached OCEL 2.0 DuckDB. Generic relation tables are dropped;
one PK'd per-pair table is created per typed (event_type, object_type) and
(source_type, target_type) combination.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb

from ocpm_bench.datasets.base import Dataset
from ocpm_bench.harness import cache as _cache
from ocpm_bench.harness import registry
from ocpm_bench.models._sql_strong_rels import build_strong_rels_schema
from ocpm_bench.models.duckdb import DuckDBModel, _export_duckdb


def _build_strong_rels_duckdb(out_path: Path, hybrid_path: Path) -> None:
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

        build_strong_rels_schema(_execute, ev_types, ob_types, placeholder="?")
    finally:
        con.close()


class DuckDBStrongRelsModel(DuckDBModel):
    name = "duckdb_strong_rels"

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
            payload_name=f"{dataset.name}-strong_rels.duckdb",
            export=lambda out: _build_strong_rels_duckdb(out, hybrid_path),
        )
        self._conn = self._connect()


registry.register_model("duckdb_strong_rels", DuckDBStrongRelsModel)
