"""Export a Kuzu DB to per-table CSV files (for sharing or Neo4j import)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import kuzu


def _table_props(conn: kuzu.Connection, table: str) -> list[dict]:
    rows = conn.execute(f"CALL table_info('{table}') RETURN *;").get_as_pl()
    props: list[dict] = []
    cols = rows.columns
    pk_col = "primary key" if "primary key" in cols else None
    for r in rows.iter_rows(named=True):
        props.append(
            {
                "name": r["name"],
                "type": r["type"],
                "pk": bool(r[pk_col]) if pk_col else False,
            }
        )
    return props


def _connections(conn: kuzu.Connection, rel: str) -> list[tuple[str, str]]:
    rows = conn.execute(f"CALL show_connection('{rel}') RETURN *;").get_as_pl()
    return [(r[0], r[1]) for r in rows.iter_rows()]


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in name)


def export_nodes(
    conn: kuzu.Connection, tables: list[str], out_dir: Path
) -> dict[str, dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    info: dict[str, dict] = {}
    for t in sorted(tables):
        props = _table_props(conn, t)
        prop_names = [p["name"] for p in props]
        select = ", ".join(f"n.`{p}` AS `{p}`" for p in prop_names)
        df = conn.execute(f"MATCH (n:`{t}`) RETURN {select};").get_as_pl()
        path = out_dir / f"{_safe(t)}.csv"
        df.write_csv(path)
        has_time = any(p["name"] == "time" for p in props)
        kind = "event" if has_time else ("attributes" if t.endswith("Attributes") else "object")
        info[t] = {
            "csv": f"nodes/{path.name}",
            "rows": df.height,
            "properties": props,
            "kind": kind,
        }
        print(f"node  {t:32s} {df.height:>10d} rows -> {path.relative_to(out_dir.parent)}")
    return info


def export_rels(
    conn: kuzu.Connection, tables: list[str], out_dir: Path
) -> dict[str, dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    info: dict[str, dict] = {}
    for rt in sorted(tables):
        rel_props = _table_props(conn, rt)
        rel_prop_names = [p["name"] for p in rel_props]
        rel_select_extra = (
            ", " + ", ".join(f"r.`{p}` AS `{p}`" for p in rel_prop_names)
            if rel_prop_names
            else ""
        )
        pairs_info: list[dict] = []
        for src, dst in _connections(conn, rt):
            q = (
                f"MATCH (a:`{src}`)-[r:`{rt}`]->(b:`{dst}`) "
                f"RETURN a.id AS start_id, b.id AS end_id{rel_select_extra};"
            )
            df = conn.execute(q).get_as_pl()
            fname = f"{_safe(rt)}__{_safe(src)}__{_safe(dst)}.csv"
            path = out_dir / fname
            df.write_csv(path)
            pairs_info.append(
                {"src": src, "dst": dst, "csv": f"rels/{fname}", "rows": df.height}
            )
            print(f"rel   {rt:8s} {src:32s} -> {dst:32s} {df.height:>10d} rows")
        info[rt] = {"properties": rel_props, "pairs": pairs_info}
    return info


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Export a Kuzu DB to per-table CSV files."
    )
    ap.add_argument("db", type=Path, help="Path to Kuzu DB directory")
    ap.add_argument("outdir", type=Path, help="Output directory for CSVs")
    args = ap.parse_args()

    if not args.db.exists():
        print(f"error: {args.db} does not exist", file=sys.stderr)
        return 2

    args.outdir.mkdir(parents=True, exist_ok=True)
    db = kuzu.Database(str(args.db), read_only=True)
    conn = kuzu.Connection(db)

    tabs = conn.execute("CALL show_tables() RETURN name, type;").get_as_pl()
    node_tables = [r[0] for r in tabs.iter_rows() if r[1] == "NODE"]
    rel_tables = [r[0] for r in tabs.iter_rows() if r[1] == "REL"]

    print(f"Found {len(node_tables)} NODE tables, {len(rel_tables)} REL tables.\n")

    nodes_info = export_nodes(conn, node_tables, args.outdir / "nodes")
    print()
    rels_info = export_rels(conn, rel_tables, args.outdir / "rels")

    schema = {
        "source_db": str(args.db),
        "kuzu_version": kuzu.__version__,
        "nodes": nodes_info,
        "rels": rels_info,
    }
    (args.outdir / "schema.json").write_text(json.dumps(schema, indent=2))
    print(f"\nschema.json written to {args.outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
