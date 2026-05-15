"""DuckDB model: r4pm exports the OCEL 2.0 strong-typed schema to `.duckdb`.

Shares the r4pm schema with SQLite, so SQL pattern impls are also shared
(see `models/_sql_ocel.py`).
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import r4pm

from ocpm_bench.datasets.base import Dataset
from ocpm_bench.harness import cache as _cache
from ocpm_bench.harness import registry
from ocpm_bench.models._sql_ocel import SQLOCELPrimitives
from ocpm_bench.models._versions import package_version, python_version

_PLACEHOLDER = re.compile(r":([A-Za-z_]\w*)")


def _export_duckdb(src: Path, out_path: Path) -> None:
    ocel_id = r4pm.import_item("OCEL", str(src))
    try:
        r4pm.bindings.export_ocel_duckdb_to_path(ocel_id, str(out_path))
    finally:
        r4pm.remove_item(ocel_id)


class DuckDBModel(SQLOCELPrimitives):
    name = "duckdb"

    def __init__(self) -> None:
        self._path: Path | None = None
        self._conn: duckdb.DuckDBPyConnection | None = None

    def setup(self, dataset: Dataset) -> None:
        dataset.fetch()
        src = dataset.resolved_path()
        self._path = _cache.get_or_export(
            dataset=dataset.name,
            model=self.name,
            source=src,
            payload_name=f"{dataset.name}-strong.duckdb",
            export=lambda out: _export_duckdb(src, out),
        )
        self._conn = self._connect()

    def teardown(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        # The cached file is intentionally retained.
        self._path = None

    def size_on_disk(self) -> int:
        return self._path.stat().st_size if self._path else 0

    def reset_caches(self) -> None:
        if self._conn is not None and self._path is not None:
            self._conn.close()
            self._conn = self._connect()

    def library_versions(self) -> dict[str, str]:
        return {
            "duckdb": duckdb.__version__,
            "r4pm": package_version("r4pm"),
            "python": python_version(),
        }

    def execute_sql(self, query: str, params: dict | None = None) -> list[tuple]:
        if self._conn is None:
            raise RuntimeError("DuckDBModel.execute_sql called before setup()")
        if not params:
            return self._conn.execute(query).fetchall()
        # Rewrite sqlite3-style :name placeholders to DuckDB positional ?,
        # in source order so duplicates and ordering are preserved.
        ordered: list = []
        def _sub(m: re.Match[str]) -> str:
            ordered.append(params[m.group(1)])
            return "?"
        sql = _PLACEHOLDER.sub(_sub, query)
        return self._conn.execute(sql, ordered).fetchall()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        assert self._path is not None
        return duckdb.connect(str(self._path))


registry.register_model("duckdb", DuckDBModel)
