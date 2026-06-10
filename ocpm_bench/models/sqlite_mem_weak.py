"""SQLite (in-memory) weak: single wide tables, per-type names re-exposed as views.

Derived from the cached OCEL 2.0 SQLite file by consolidating the per-activity /
per-object-type tables (see `_sql_weak`). The transformed file is cached on disk
and copied into a `:memory:` connection at setup time.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from ocpm_bench.datasets.base import Dataset
from ocpm_bench.harness import cache as _cache
from ocpm_bench.harness import registry
from ocpm_bench.models._sql_weak import build_weak_schema
from ocpm_bench.models.sqlite_mem import SQLiteMemModel, _export_sqlite


def _build_weak_sqlite(out_path: Path, hybrid_path: Path) -> None:
    shutil.copy(hybrid_path, out_path)
    con = sqlite3.connect(out_path)
    try:
        ev_types = [r[0] for r in con.execute(
            "SELECT ocel_type FROM event_map_type ORDER BY ocel_type"
        )]
        ob_types = [r[0] for r in con.execute(
            "SELECT ocel_type FROM object_map_type ORDER BY ocel_type"
        )]

        def _execute(sql: str, params: list | None = None) -> list[tuple]:
            cur = con.execute(sql, params or [])
            try:
                return cur.fetchall()
            finally:
                cur.close()

        def _columns(table: str) -> list[str]:
            ident = table.replace('"', '""')
            return [r[1] for r in con.execute(f'PRAGMA table_info("{ident}")').fetchall()]

        build_weak_schema(_execute, _columns, ev_types, ob_types)
        con.commit()
    finally:
        con.close()


class SQLiteMemWeakModel(SQLiteMemModel):
    name = "sqlite_mem_weak"

    def setup(self, dataset: Dataset) -> None:
        dataset.fetch()
        src = dataset.resolved_path()
        hybrid_path = _cache.get_or_export(
            dataset=dataset.name,
            model="sqlite_mem",
            source=src,
            payload_name=f"{dataset.name}-strong.sqlite",
            export=lambda out: _export_sqlite(src, out),
        )
        cached = _cache.get_or_export(
            dataset=dataset.name,
            model=self.name,
            source=src,
            payload_name=f"{dataset.name}-weak.sqlite",
            export=lambda out: _build_weak_sqlite(out, hybrid_path),
        )
        disk_conn = sqlite3.connect(cached)
        self._conn = sqlite3.connect(":memory:")
        try:
            disk_conn.backup(self._conn)
        finally:
            disk_conn.close()
        self._conn.commit()

    def event_times_union(self) -> str:
        return "SELECT ocel_id, ocel_time FROM event_attr"


registry.register_model("sqlite_mem_weak", SQLiteMemWeakModel)
