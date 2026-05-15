"""SQLite (in-memory) strong-rels: per-pair `event_object` / `object_object` tables.

Derived from the cached OCEL 2.0 SQLite file by replacing the generic relation
tables with one PK'd table per typed pair. The transformed file is cached on
disk and copied into a `:memory:` connection at setup time.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from ocpm_bench.datasets.base import Dataset
from ocpm_bench.harness import cache as _cache
from ocpm_bench.harness import registry
from ocpm_bench.models._sql_strong_rels import build_strong_rels_schema
from ocpm_bench.models.sqlite_mem import SQLiteMemModel, _export_sqlite


def _build_strong_rels_sqlite(out_path: Path, hybrid_path: Path) -> None:
    shutil.copy(hybrid_path, out_path)
    con = sqlite3.connect(out_path)
    try:
        ev_types = [r[0] for r in con.execute(
            "SELECT ocel_type FROM event_map_type ORDER BY ocel_type"
        ).fetchall()]
        ob_types = [r[0] for r in con.execute(
            "SELECT ocel_type FROM object_map_type ORDER BY ocel_type"
        ).fetchall()]

        def _execute(sql: str, params: list | None = None) -> list[tuple]:
            cur = con.execute(sql, params or [])
            try:
                return cur.fetchall()
            finally:
                cur.close()

        build_strong_rels_schema(_execute, ev_types, ob_types, placeholder="?")
        con.commit()
    finally:
        con.close()


class SQLiteMemStrongRelsModel(SQLiteMemModel):
    name = "sqlite_mem_strong_rels"

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
            payload_name=f"{dataset.name}-strong_rels.sqlite",
            export=lambda out: _build_strong_rels_sqlite(out, hybrid_path),
        )
        disk_conn = sqlite3.connect(cached)
        self._conn = sqlite3.connect(":memory:")
        try:
            disk_conn.backup(self._conn)
        finally:
            disk_conn.close()
        self._conn.commit()


registry.register_model("sqlite_mem_strong_rels", SQLiteMemStrongRelsModel)
