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
from ocpm_bench.models.kuzu import _kuzu_has_df, execute_cypher, path_size
from ocpm_bench.models.polars import cached_polars_frames


def _build_weak_kuzu(out_path: Path, frames: dict[str, pl.DataFrame]) -> None:
    """Materialize a weak-typed Kuzu DB at `out_path` from OCEL polars frames.

    Schema:
        Event(id PK, type, time, <event attrs...>)
        Object(id PK, type)
        E2O(FROM Event, TO Object, qualifier)
        O2O(FROM Object, TO Object, qualifier)

    Every non-``ocel:`` column of the events frame becomes a STRING property on
    the single ``Event`` table (the union of all event types' attributes, null
    where an attribute does not apply). This keeps node typing weak while still
    carrying event attributes (e.g. ``LoanGoal``) so the EKG corpus is runnable.
    """
    # Union of attribute columns across all event types. The three `ocel:`
    # columns become the structural id/type/time below; everything else is an
    # event attribute carried verbatim (cast to STRING; only id/type/time are
    # ever read with their native type).
    _CORE = {"ocel:eid", "ocel:activity", "ocel:timestamp"}
    attr_cols = [c for c in frames["events"].columns if c not in _CORE]

    db = kuzu.Database(str(out_path))
    conn = kuzu.Connection(db)
    try:
        attr_ddl = "".join(f", `{c}` STRING" for c in attr_cols)
        conn.execute(
            f"CREATE NODE TABLE Event(id STRING, type STRING, time TIMESTAMP"
            f"{attr_ddl}, PRIMARY KEY(id))"
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
            *[pl.col(c).cast(pl.Utf8).alias(c) for c in attr_cols],
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


def _materialize_df_weak(conn: kuzu.Connection) -> None:
    """Materialize per-object directly-follows edges on the weak Kuzu DB.

    One ``Event``-``Event`` ``:DF`` edge per consecutive event pair on an object,
    matching the strong model's ``:DF`` so the weak-vs-strong comparison isolates
    node typing. Props: object id (``id``) and object type (``EntityType``). A
    one-time, untimed model-build step, persisted in the cached DB.
    """
    if _kuzu_has_df(conn):
        return
    rows = conn.execute(
        "MATCH (e:Event)-[:E2O]->(o:Object) "
        "RETURN o.id AS oid, o.type AS otype, e.id AS eid, e.time AS t"
    ).get_as_pl()
    if rows.height == 0:
        return
    edges = (
        rows.sort(["oid", "t", "eid"])
        .with_columns(to_eid=pl.col("eid").shift(-1).over("oid"))
        .filter(pl.col("to_eid").is_not_null())
        .select([
            pl.col("eid").alias("from"),
            pl.col("to_eid").alias("to"),
            pl.col("oid").alias("id"),
            pl.col("otype").alias("EntityType"),
        ])
    )
    conn.execute(
        "CREATE REL TABLE DF(FROM Event TO Event, id STRING, EntityType STRING)"
    )
    with tempfile.TemporaryDirectory() as tmp:
        csv = Path(tmp) / "df_weak.csv"
        edges.write_csv(csv)
        conn.execute(f'COPY DF FROM "{csv}" (HEADER=true)')


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
        _materialize_df_weak(self._conn)

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
