"""Neo4j strongly-typed model: one NODE label per OCEL event/object type,
REL labels `E2O` and `O2O`. Setup builds a typed Kuzu DB, exports per-table
CSVs, then `LOAD CSV` into the live Neo4j instance.

Env: OCPM_NEO4J_{URI,USER,PASSWORD,DATABASE,IMPORT_DIR,STORE_DIR}.
IMPORT_DIR is required (LOAD CSV reads `file:///` from there).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from neo4j import Driver, GraphDatabase

from ocpm_bench.datasets.base import Dataset
from ocpm_bench.harness import cache as _cache
from ocpm_bench.harness import registry
from ocpm_bench.models._versions import package_version, python_version
from ocpm_bench.models.kuzu import _build_name_info, _export_typed, path_size
from ocpm_bench.models.primitives import clean_type_name, normalize_timestamp

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_EXPORT_SCRIPT = _PROJECT_ROOT / "scripts" / "export_kuzu_csv.py"


def _q_create_index(label: str, attr: str) -> str:
    return f"CREATE INDEX {label}_{attr} IF NOT EXISTS FOR (n:`{label}`) ON (n.`{attr}`)"


def _q_delete_relations() -> str:
    return "MATCH ()-[r]->() CALL (r) { DELETE r } IN TRANSACTIONS OF 1000 ROWS;"


def _q_delete_nodes() -> str:
    return "MATCH (n) CALL (n) { DELETE n } IN TRANSACTIONS OF 1000 ROWS;"

def _q_materialize_df_relations(object_type: str) -> str:
    return f"""
        MATCH ( n : `{object_type}` )"

        CALL (n) {{
            MATCH ( n ) <-[:E2O]- ( e )
       
            WITH n , e as nodes ORDER BY e.timestamp,elementId(e)
            WITH n , collect ( nodes ) as nodeList
            UNWIND range(0,size(nodeList)-2) AS i
            WITH n , nodeList[i] as first, nodeList[i+1] as second

            MERGE ( first ) -[df:DF {{ id:n.id, EntityType: '`{object_type}`' }}]->( second )
        }} IN TRANSACTIONS OF 1000 ROWS;
    """


def _q_load_csv_as_nodes(file_name: str, header: list[str], node_label: str) -> str:
    parts: list[str] = []
    for col in header:
        if col in ("time", "timestamp", "start", "end"):
            value = f"datetime(line.`{col}`)"
        else:
            value = f"line.`{col}`"
        parts.append(f" `{col}`: {value}")
    create_props = ", ".join(parts)
    return (
        f'LOAD CSV WITH HEADERS FROM "file:///{file_name}" AS line\n'
        f"CALL (line) {{\n"
        f" WITH line\n"
        f" CREATE (e:`{node_label}` {{{create_props} }})\n"
        f"}} IN TRANSACTIONS OF 1000 ROWS;"
    )


def _q_load_csv_as_relation(
    file_name: str,
    source_label: str,
    target_label: str,
    rel_label: str,
) -> str:
    return (
        f'LOAD CSV WITH HEADERS FROM "file:///{file_name}" AS line\n'
        f"CALL (line) {{\n"
        f" WITH line\n"
        f"  MATCH (s:`{source_label}` {{ id: line.start_id }})\n"
        f"  MATCH (n:`{target_label}` {{ id: line.end_id }})\n"
        f"  MERGE (s)-[r:`{rel_label}`]->(n)\n"
        f"  ON CREATE SET r.qualifier = line.qualifier\n"
        f"}} IN TRANSACTIONS OF 1000 ROWS;"
    )


def _run_kuzu_csv_export(kuzu_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(_EXPORT_SCRIPT), str(kuzu_path), str(out_dir)],
        check=True,
    )


def _read_csv_header(path: Path) -> list[str]:
    import csv as _csv
    with path.open() as f:
        return list(next(_csv.reader(f)))


class Neo4jModelStrong:
    name = "neo4j_strong"

    def __init__(self) -> None:
        self._driver: Driver | None = None
        self._database: str = "neo4j"
        self._import_dir: Path | None = None
        self._store_dir: Path | None = None
        self._name_map: dict[str, str] = {}
        self._ev_types: list[str] = []
        self._ob_types: list[str] = []

    def setup(self, dataset: Dataset) -> None:
        dataset.fetch()
        src = dataset.resolved_path()

        uri = os.environ.get("OCPM_NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("OCPM_NEO4J_USER", "neo4j")
        password = os.environ.get("OCPM_NEO4J_PASSWORD", "neo4j")
        self._database = os.environ.get("OCPM_NEO4J_DATABASE", "neo4j")

        import_dir = os.environ.get("OCPM_NEO4J_IMPORT_DIR")
        if not import_dir:
            raise RuntimeError(
                "Neo4jModelStrong: set OCPM_NEO4J_IMPORT_DIR to the absolute "
                "path of your Neo4j instance's import/ directory."
            )
        self._import_dir = Path(import_dir)
        self._import_dir.mkdir(parents=True, exist_ok=True)

        store_dir = os.environ.get("OCPM_NEO4J_STORE_DIR")
        self._store_dir = Path(store_dir) if store_dir else None

        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        self._driver = driver

        kuzu_path = _cache.get_or_export(
            dataset=dataset.name,
            model="kuzu",
            source=src,
            payload_name=f"{dataset.name}-strong.kuzu",
            export=lambda out: _export_typed(str(src), out),
        )

        csv_dir = _cache.get_or_export(
            dataset=dataset.name,
            model=self.name,
            source=src,
            payload_name=f"{dataset.name}-strong-csv",
            export=lambda out: _run_kuzu_csv_export(kuzu_path, out),
        )

        if self._needs_load():
            self._wipe_and_load(csv_dir)

        self._name_map, self._ev_types, self._ob_types = _build_name_info(str(src))

    def _needs_load(self) -> bool:
        try:
            rows = self.execute_cypher(
                "MATCH ()-[r:E2O]->() RETURN count(r) AS n"
            )
        except Exception:
            return True
        return not rows or rows[0][0] == 0

    def teardown(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def size_on_disk(self) -> int:
        return path_size(self._store_dir) if self._store_dir else 0

    def reset_caches(self) -> None:
        try:
            self._run_write("CALL db.clearQueryCaches();")
        except Exception:
            pass

    def library_versions(self) -> dict[str, str]:
        versions = {
            "neo4j": package_version("neo4j"),
            "r4pm": package_version("r4pm"),
            "python": python_version(),
        }
        try:
            rows = self.execute_cypher(
                "CALL dbms.components() YIELD name, versions "
                "RETURN name, versions[0] AS version"
            )
            for name, version in rows:
                versions[f"neo4j_{name.lower().replace(' ', '_')}"] = str(version)
        except Exception:
            pass
        return versions

    def _session(self):
        if self._driver is None:
            raise RuntimeError("Neo4jModelStrong.session called before setup()")
        return self._driver.session(database=self._database)

    def _run_write(self, query: str, params: dict | None = None) -> None:
        with self._session() as s:
            s.run(query, parameters=params or {}).consume()

    def execute_cypher(
        self, query: str, params: dict | None = None
    ) -> list[tuple]:
        with self._session() as s:
            result = s.run(query, parameters=params or {})
            return [tuple(record.values()) for record in result]

    def original_name(self, cleaned: str) -> str:
        return self._name_map.get(cleaned, cleaned)

    def get_event_types(self) -> list[str]:
        return list(self._ev_types)

    def _wipe_and_load(self, csv_dir: Path) -> None:
        import json as _json

        assert self._import_dir is not None

        self._run_write(_q_delete_relations())
        self._run_write(_q_delete_nodes())

        nodes_dir = csv_dir / "nodes"
        rels_dir = csv_dir / "rels"
        schema_path = csv_dir / "schema.json"
        if not nodes_dir.is_dir() or not rels_dir.is_dir():
            raise RuntimeError(
                f"CSV export at {csv_dir} is missing nodes/ or rels/ subdir"
            )
        if not schema_path.is_file():
            raise RuntimeError(
                f"CSV export at {csv_dir} is missing schema.json"
            )
        schema = _json.loads(schema_path.read_text())

        loaded: list[Path] = []
        try:
            for csv_file in sorted(nodes_dir.glob("*.csv")):
                dest = self._import_dir / csv_file.name
                shutil.copy(csv_file, dest)
                loaded.append(dest)

                label = csv_file.stem
                header = _read_csv_header(csv_file)

                self._run_write(_q_create_index(label, "id"))
                self._run_write(_q_load_csv_as_nodes(csv_file.name, header, label))

            # Drive rel loading from schema.json instead of parsing filenames:
            # cleaned type names ending in `_` produce `___` in
            # `E2O__<Src>__<Dst>.csv`, breaking `split('__')`.
            for rel_label, rel_info in schema.get("rels", {}).items():
                for pair in rel_info.get("pairs", []):
                    csv_rel = pair["csv"]
                    csv_file = csv_dir / csv_rel
                    if not csv_file.is_file():
                        raise RuntimeError(
                            f"schema.json references missing rel CSV {csv_file}"
                        )
                    dest = self._import_dir / csv_file.name
                    shutil.copy(csv_file, dest)
                    loaded.append(dest)
                    self._run_write(
                        _q_load_csv_as_relation(
                            csv_file.name, pair["src"], pair["dst"], rel_label
                        )
                    )

            # materiali DF relations
            for o_type in self._ob_types:
                self._run_write(_q_materialize_df_relations(o_type))

        finally:
            for p in loaded:
                try:
                    p.unlink()
                except OSError:
                    pass

    def get_object_types(self) -> list[str]:
        return list(self._ob_types)

    def get_objects_of_type(self, object_type: str) -> list[str]:
        cleaned = clean_type_name(object_type)
        rows = self.execute_cypher(f"MATCH (o:`{cleaned}`) RETURN o.id")
        return [r[0] for r in rows]

    def get_object_type(self, object_id: str) -> str:
        rows = self.execute_cypher(
            "MATCH (o) WHERE o.id = $oid AND any(l IN labels(o) WHERE l IN $labels) "
            "RETURN labels(o)[0]",
            {"oid": object_id, "labels": [clean_type_name(t) for t in self._ob_types]},
        )
        return self.original_name(rows[0][0])

    def get_activity(self, event_id: str) -> str:
        rows = self.execute_cypher(
            "MATCH (e) WHERE e.id = $eid AND any(l IN labels(e) WHERE l IN $labels) "
            "RETURN labels(e)[0]",
            {"eid": event_id, "labels": [clean_type_name(t) for t in self._ev_types]},
        )
        return self.original_name(rows[0][0])

    def get_timestamp(self, event_id: str) -> str:
        rows = self.execute_cypher(
            "MATCH (e) WHERE e.id = $eid AND any(l IN labels(e) WHERE l IN $labels) "
            "RETURN toString(e.time)",
            {"eid": event_id, "labels": [clean_type_name(t) for t in self._ev_types]},
        )
        return normalize_timestamp(rows[0][0])

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


registry.register_model("neo4j_strong", Neo4jModelStrong)
