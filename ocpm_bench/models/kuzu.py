"""Kuzu graph model: r4pm exports a typed Kuzu DB (one NODE per OCEL type).

Tables: one NODE per event type, one NODE per object type, plus REL `E2O`
and REL `O2O`. Table labels are cleaned (spaces stripped, non-alphanumerics
to `_`); pattern impls map back via `model.original_name`.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import kuzu
import polars as pl
import r4pm

from ocpm_bench.datasets.base import Dataset
from ocpm_bench.harness import cache as _cache
from ocpm_bench.harness import registry
from ocpm_bench.models._versions import package_version, python_version
from ocpm_bench.models.primitives import clean_type_name, normalize_timestamp, thread_cap


def _export_typed(src: str, out_path: Path) -> None:
    locel_id = r4pm.import_item("SlimLinkedOCEL", src)
    try:
        r4pm.bindings.export_ocel_to_kuzudb_typed(str(out_path), locel_id)
    finally:
        r4pm.remove_item(locel_id)


def execute_cypher(
    conn: kuzu.Connection, query: str, params: dict | None = None
) -> list[tuple]:
    """Run a Cypher query and return rows as tuples. Shared by both Kuzu models."""
    result = conn.execute(query, parameters=params or {})
    if isinstance(result, list):
        if len(result) != 1:
            raise RuntimeError(
                f"execute_cypher: expected 1 result set, got {len(result)}"
            )
        result = result[0]
    return list(result.get_as_pl().iter_rows())


def path_size(path: Path) -> int:
    """Total bytes of a Kuzu DB path (directory or file). Shared by both Kuzu models."""
    if not path or not path.exists():
        return 0
    if path.is_dir():
        total = 0
        for root, _dirs, files in os.walk(path):
            for f in files:
                total += os.path.getsize(os.path.join(root, f))
        return total
    return os.path.getsize(path)


def _build_name_info(src: str) -> tuple[dict[str, str], list[str], list[str]]:
    """Return (cleaned_to_original_map, ev_types, ob_types) from the source OCEL."""
    locel_id = r4pm.import_item("SlimLinkedOCEL", src)
    try:
        ev_types: list[str] = list(r4pm.bindings.locel_get_ev_types(locel_id))
        ob_types: list[str] = list(r4pm.bindings.locel_get_ob_types(locel_id))
    finally:
        r4pm.remove_item(locel_id)
    name_map: dict[str, str] = {}
    for original in [*ev_types, *ob_types]:
        cleaned = clean_type_name(original)
        if cleaned in name_map and name_map[cleaned] != original:
            raise RuntimeError(
                f"Kuzu name-map collision: {name_map[cleaned]!r} and {original!r} "
                f"both clean to {cleaned!r}"
            )
        name_map[cleaned] = original
    return name_map, ev_types, ob_types


def _cleaned_labels(types: list[str]) -> list[str]:
    return [clean_type_name(t) for t in types]


def _kuzu_has_df(conn: kuzu.Connection) -> bool:
    names = {
        row[0]
        for row in conn.execute("CALL show_tables() RETURN name").get_as_pl().iter_rows()
    }
    return "DF" in names


def materialize_df_kuzu(conn: kuzu.Connection) -> None:
    """Materialize per-object directly-follows edges on the strong Kuzu DB.

    One ``:DF`` edge per consecutive event pair on an object, props ``id`` (object
    ocel_id) and ``EntityType`` (object type). Kuzu cannot ``CREATE`` rels from
    list elements, so pairs are computed in Python and bulk-``COPY``ed per
    (from-activity, to-activity) table pair. Untimed, persisted in the cached DB.
    """
    if _kuzu_has_df(conn):
        return
    rows = conn.execute(
        "MATCH (e)-[:E2O]->(o) "
        "RETURN o.id AS oid, LABEL(o) AS otype, e.id AS eid, "
        "LABEL(e) AS act, e.time AS t"
    ).get_as_pl()
    if rows.height == 0:
        return
    edges = (
        rows.sort(["oid", "t", "eid"])
        .with_columns(
            to_eid=pl.col("eid").shift(-1).over("oid"),
            to_act=pl.col("act").shift(-1).over("oid"),
        )
        .filter(pl.col("to_eid").is_not_null())
        .select([
            pl.col("act").alias("from_act"),
            pl.col("to_act"),
            pl.col("eid").alias("from"),
            pl.col("to_eid").alias("to"),
            pl.col("oid").alias("id"),
            pl.col("otype").alias("EntityType"),
        ])
    )
    pair_keys = [tuple(r) for r in edges.select(["from_act", "to_act"]).unique().iter_rows()]
    rel_pairs = ", ".join(f"FROM `{a}` TO `{b}`" for a, b in pair_keys)
    conn.execute(f"CREATE REL TABLE DF({rel_pairs}, id STRING, EntityType STRING)")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for key, grp in edges.group_by(["from_act", "to_act"]):
            a, b = key
            csv_path = tmp_dir / f"df_{a}__{b}.csv"
            grp.select(["from", "to", "id", "EntityType"]).write_csv(csv_path)
            conn.execute(
                f'COPY DF FROM "{csv_path}" (FROM="{a}", TO="{b}", HEADER=true)'
            )


class KuzuModel:
    name = "kuzu"

    def __init__(self) -> None:
        self._path: Path | None = None
        self._db: kuzu.Database | None = None
        self._conn: kuzu.Connection | None = None
        self._name_map: dict[str, str] = {}
        self._ev_types: list[str] = []
        self._ob_types: list[str] = []
        # Cleaned label lists for `LABEL(n) IN $labels` filters on untyped
        # MATCH. Kuzu typed Cypher doesn't accept `Label1|Label2` patterns.
        self._event_labels: list[str] = []
        self._object_labels: list[str] = []

    def setup(self, dataset: Dataset) -> None:
        dataset.fetch()
        src = dataset.resolved_path()
        self._path = _cache.get_or_export(
            dataset=dataset.name,
            model=self.name,
            source=src,
            payload_name=f"{dataset.name}-strong.kuzu",
            export=lambda out: _export_typed(str(src), out),
        )
        self._db = kuzu.Database(str(self._path), max_num_threads=thread_cap() or 0)
        self._conn = kuzu.Connection(self._db)
        self._name_map, self._ev_types, self._ob_types = _build_name_info(str(src))
        self._event_labels = _cleaned_labels(self._ev_types)
        self._object_labels = _cleaned_labels(self._ob_types)
        materialize_df_kuzu(self._conn)

    def teardown(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        if self._db is not None:
            self._db.close()
            self._db = None
        self._path = None  # cache directory is retained on disk

    def size_on_disk(self) -> int:
        return path_size(self._path) if self._path else 0

    def reset_caches(self) -> None:
        # Reopening the connection drops Kuzu's per-connection plan cache.
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

    def original_name(self, cleaned: str) -> str:
        """Translate a Kuzu table label back to the OCEL's original name."""
        return self._name_map.get(cleaned, cleaned)

    def execute_cypher(self, query: str, params: dict | None = None) -> list[tuple]:
        if self._conn is None:
            raise RuntimeError("KuzuModel.execute_cypher called before setup()")
        return execute_cypher(self._conn, query, params)

    # PrimitiveAccess. Returns OCEL-original names; Cypher uses the cleaned
    # form r4pm's typed exporter writes. Untyped MATCH `(n)` plus a
    # `LABEL(n) IN $labels` filter stands in for "any event" / "any object",
    # since Kuzu typed Cypher rejects `Label1|Label2` patterns. E2O/O2O
    # already constrain node types on relation traversal.

    def get_object_types(self) -> list[str]:
        return list(self._ob_types)

    def get_objects_of_type(self, object_type: str) -> list[str]:
        cleaned = clean_type_name(object_type)
        rows = self.execute_cypher(f"MATCH (o:`{cleaned}`) RETURN o.id")
        return [r[0] for r in rows]

    def get_object_type(self, object_id: str) -> str:
        rows = self.execute_cypher(
            "MATCH (o) WHERE o.id = $oid AND LABEL(o) IN $labels RETURN LABEL(o)",
            {"oid": object_id, "labels": self._object_labels},
        )
        return self.original_name(rows[0][0])

    def get_activity(self, event_id: str) -> str:
        rows = self.execute_cypher(
            "MATCH (e) WHERE e.id = $eid AND LABEL(e) IN $labels RETURN LABEL(e)",
            {"eid": event_id, "labels": self._event_labels},
        )
        return self.original_name(rows[0][0])

    def get_timestamp(self, event_id: str) -> str:
        rows = self.execute_cypher(
            "MATCH (e) WHERE e.id = $eid AND LABEL(e) IN $labels RETURN e.time",
            {"eid": event_id, "labels": self._event_labels},
        )
        return normalize_timestamp(rows[0][0].isoformat())

    def get_events_of_type(self, activity: str) -> list[str]:
        cleaned = clean_type_name(activity)
        rows = self.execute_cypher(f"MATCH (e:`{cleaned}`) RETURN e.id")
        return [r[0] for r in rows]

    def get_events_of_object(self, object_id: str) -> list[str]:
        rows = self.execute_cypher(
            "MATCH (e)-[:E2O]->(o) WHERE o.id = $oid RETURN e.id",
            {"oid": object_id},
        )
        return [r[0] for r in rows]

    def get_objects_of_event(self, event_id: str) -> list[str]:
        rows = self.execute_cypher(
            "MATCH (e)-[:E2O]->(o) WHERE e.id = $eid RETURN o.id",
            {"eid": event_id},
        )
        return [r[0] for r in rows]

    def get_related_objects(self, object_id: str) -> list[str]:
        rows = self.execute_cypher(
            "MATCH (o1)-[:O2O]->(o2) WHERE o1.id = $oid RETURN o2.id",
            {"oid": object_id},
        )
        return [r[0] for r in rows]


registry.register_model("kuzu", KuzuModel)
