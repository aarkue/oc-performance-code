"""Kuzu weak: single `Event` / `Object` NODE tables, generic `E2O` / `O2O` REL tables.

Built in Python by transforming the cached Polars frames into a fresh Kuzu
DB with a supertype schema. No r4pm dependency beyond what `PolarsModel`
already triggers for the parquet cache.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import kuzu
import polars as pl

from ocpm_bench.datasets.base import Dataset
from ocpm_bench.harness import cache as _cache
from ocpm_bench.harness import registry
from ocpm_bench.models._versions import package_version, python_version
from ocpm_bench.models.kuzu import execute_cypher, path_size
from ocpm_bench.models.polars import cached_polars_frames


def _build_weak_kuzu(out_path: Path, frames: dict[str, pl.DataFrame]) -> None:
    """Materialize a weak-typed Kuzu DB at `out_path` from OCEL polars frames.

    Schema:
        Event(id PK, type, time)
        Object(id PK, type)
        E2O(FROM Event, TO Object, qualifier)
        O2O(FROM Object, TO Object, qualifier)
    """
    db = kuzu.Database(str(out_path))
    conn = kuzu.Connection(db)
    try:
        conn.execute(
            "CREATE NODE TABLE Event(id STRING, type STRING, time TIMESTAMP, PRIMARY KEY(id))"
        )
        conn.execute(
            "CREATE NODE TABLE Object(id STRING, type STRING, PRIMARY KEY(id))"
        )
        conn.execute("CREATE REL TABLE E2O(FROM Event TO Object, qualifier STRING)")
        conn.execute("CREATE REL TABLE O2O(FROM Object TO Object, qualifier STRING)")

        # Use CSV rather than parquet: Kuzu 0.11 ignores the parquet TIMESTAMP
        # logical type and tries to cast INT64 -> TIMESTAMP, which fails. CSV
        # is unambiguous; Kuzu parses ISO timestamps directly.
        events = frames["events"].select([
            pl.col("ocel:eid").alias("id"),
            pl.col("ocel:activity").alias("type"),
            pl.col("ocel:timestamp")
              .cast(pl.Datetime("us"))
              .dt.strftime("%Y-%m-%dT%H:%M:%S.%6f")
              .alias("time"),
        ])
        objects = frames["objects"].select([
            pl.col("ocel:oid").alias("id"),
            pl.col("ocel:type").alias("type"),
        ])
        # REL CSV column order: (FROM_pk, TO_pk, props...).
        e2o = frames["relations"].select([
            pl.col("ocel:eid").alias("from"),
            pl.col("ocel:oid").alias("to"),
            pl.col("ocel:qualifier").fill_null("").alias("qualifier"),
        ])
        o2o_src = frames["o2o"]
        qualifier_expr = (
            pl.col("ocel:qualifier").fill_null("")
            if "ocel:qualifier" in o2o_src.columns
            else pl.lit("")
        )
        o2o = o2o_src.select([
            pl.col("ocel:oid").alias("from"),
            pl.col("ocel:oid_2").alias("to"),
            qualifier_expr.alias("qualifier"),
        ])

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            for tbl, df in (
                ("Event", events),
                ("Object", objects),
                ("E2O", e2o),
                ("O2O", o2o),
            ):
                if df.height == 0:
                    continue
                csv = tmp_dir / f"{tbl}.csv"
                df.write_csv(csv)
                conn.execute(f'COPY {tbl} FROM "{csv}" (HEADER=true);')
    finally:
        conn.close()
        db.close()


class KuzuWeakModel:
    name = "kuzu_weak"

    def __init__(self) -> None:
        self._path: Path | None = None
        self._db: kuzu.Database | None = None
        self._conn: kuzu.Connection | None = None

    def setup(self, dataset: Dataset) -> None:
        dataset.fetch()
        src = dataset.resolved_path()
        frames = cached_polars_frames(dataset)
        self._path = _cache.get_or_export(
            dataset=dataset.name,
            model=self.name,
            source=src,
            payload_name=f"{dataset.name}-weak.kuzu",
            export=lambda out: _build_weak_kuzu(out, frames),
        )
        self._db = kuzu.Database(str(self._path))
        self._conn = kuzu.Connection(self._db)

    def teardown(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        if self._db is not None:
            self._db.close()
            self._db = None
        self._path = None

    def size_on_disk(self) -> int:
        return path_size(self._path) if self._path else 0

    def reset_caches(self) -> None:
        if self._db is not None:
            if self._conn is not None:
                self._conn.close()
            self._conn = kuzu.Connection(self._db)

    def library_versions(self) -> dict[str, str]:
        return {
            "kuzu": str(kuzu.__version__),
            "r4pm": package_version("r4pm"),
            "python": python_version(),
        }

    def execute_cypher(self, query: str, params: dict | None = None) -> list[tuple]:
        if self._conn is None:
            raise RuntimeError("KuzuWeakModel.execute_cypher called before setup()")
        return execute_cypher(self._conn, query, params)


registry.register_model("kuzu_weak", KuzuWeakModel)
