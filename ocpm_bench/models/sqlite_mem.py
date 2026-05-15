"""In-memory SQLite model.

Setup: r4pm exports the OCEL 2.0 strong-typed schema to a cached
on-disk file (under `code/cache/<dataset>/sqlite_mem/`); we then copy
that file into a `:memory:` connection.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import r4pm

from ocpm_bench.datasets.base import Dataset
from ocpm_bench.harness import cache as _cache
from ocpm_bench.harness import registry
from ocpm_bench.models._sql_ocel import SQLOCELPrimitives
from ocpm_bench.models._versions import python_version


def _export_sqlite(src: Path, out_path: Path) -> None:
    ocel_id = r4pm.import_item("OCEL", str(src))
    try:
        r4pm.export_item(ocel_id, str(out_path))
    finally:
        r4pm.remove_item(ocel_id)


class SQLiteMemModel(SQLOCELPrimitives):
    name = "sqlite_mem"

    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None

    def setup(self, dataset: Dataset) -> None:
        dataset.fetch()
        src = dataset.resolved_path()
        cached = _cache.get_or_export(
            dataset=dataset.name,
            model=self.name,
            source=src,
            payload_name=f"{dataset.name}-strong.sqlite",
            export=lambda out: _export_sqlite(src, out),
        )
        disk_conn = sqlite3.connect(cached)
        self._conn = sqlite3.connect(":memory:")
        try:
            disk_conn.backup(self._conn)
        finally:
            disk_conn.close()
        self._conn.commit()

    def teardown(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def size_on_disk(self) -> int:
        """Memory-resident page bytes (page_count * page_size)."""
        if self._conn is None:
            return 0
        page_count = self._conn.execute("PRAGMA page_count").fetchone()[0]
        page_size = self._conn.execute("PRAGMA page_size").fetchone()[0]
        return page_count * page_size

    def reset_caches(self) -> None:
        # :memory: connection holds the data; reopening would discard it.
        pass

    def library_versions(self) -> dict[str, str]:
        return {"sqlite": sqlite3.sqlite_version, "python": python_version()}

    def execute_sql(self, query: str, params: dict | None = None) -> list[tuple]:
        if self._conn is None:
            raise RuntimeError("SQLiteMemModel.execute_sql called before setup()")
        cur = self._conn.execute(query, params or {})
        try:
            return list(cur.fetchall())
        finally:
            cur.close()


registry.register_model("sqlite_mem", SQLiteMemModel)
