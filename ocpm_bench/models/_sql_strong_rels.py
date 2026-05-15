"""Schema builder for the strong-rels SQL variant."""

from __future__ import annotations

from collections.abc import Callable

from ocpm_bench.models.primitives import clean_type_name


def build_strong_rels_schema(
    execute: Callable[..., list[tuple]],
    ev_types: list[str],
    ob_types: list[str],
    placeholder: str = "?",
) -> None:
    """Create per-pair rel tables in an existing OCEL 2.0 DB.

    `execute(sql, params=None)` runs one statement. `placeholder` is the
    engine's positional parameter marker (`?` for SQLite/DuckDB).
    """
    p = placeholder

    execute(
        "CREATE TABLE event_object_typed_index ("
        " event_type VARCHAR NOT NULL,"
        " object_type VARCHAR NOT NULL,"
        " table_name VARCHAR NOT NULL,"
        " PRIMARY KEY (event_type, object_type)"
        ")"
    )
    execute(
        "CREATE TABLE object_object_typed_index ("
        " source_type VARCHAR NOT NULL,"
        " target_type VARCHAR NOT NULL,"
        " table_name VARCHAR NOT NULL,"
        " PRIMARY KEY (source_type, target_type)"
        ")"
    )

    e2o_pairs: set[tuple[str, str]] = {
        (r[0], r[1])
        for r in execute(
            "SELECT DISTINCT e.ocel_type, o.ocel_type "
            "FROM event_object eo "
            "JOIN event e ON e.ocel_id = eo.ocel_event_id "
            "JOIN object o ON o.ocel_id = eo.ocel_object_id"
        )
    }
    o2o_pairs: set[tuple[str, str]] = {
        (r[0], r[1])
        for r in execute(
            "SELECT DISTINCT o1.ocel_type, o2.ocel_type "
            "FROM object_object oo "
            "JOIN object o1 ON o1.ocel_id = oo.ocel_source_id "
            "JOIN object o2 ON o2.ocel_id = oo.ocel_target_id"
        )
    }

    for ev_t in ev_types:
        for ob_t in ob_types:
            if (ev_t, ob_t) not in e2o_pairs:
                continue
            tbl = f"event_object_{clean_type_name(ev_t)}__{clean_type_name(ob_t)}"
            execute(
                f'CREATE TABLE "{tbl}" ('
                " ocel_event_id VARCHAR NOT NULL,"
                " ocel_object_id VARCHAR NOT NULL,"
                " ocel_qualifier VARCHAR NOT NULL,"
                " PRIMARY KEY (ocel_event_id, ocel_object_id, ocel_qualifier)"
                ")"
            )
            execute(
                f'INSERT INTO "{tbl}" (ocel_event_id, ocel_object_id, ocel_qualifier) '
                "SELECT eo.ocel_event_id, eo.ocel_object_id, eo.ocel_qualifier "
                "FROM event_object eo "
                "JOIN event e ON e.ocel_id = eo.ocel_event_id "
                "JOIN object o ON o.ocel_id = eo.ocel_object_id "
                f"WHERE e.ocel_type = {p} AND o.ocel_type = {p}",
                [ev_t, ob_t],
            )
            execute(
                f"INSERT INTO event_object_typed_index VALUES ({p}, {p}, {p})",
                [ev_t, ob_t, tbl],
            )

    for s_t in ob_types:
        for t_t in ob_types:
            if (s_t, t_t) not in o2o_pairs:
                continue
            tbl = f"object_object_{clean_type_name(s_t)}__{clean_type_name(t_t)}"
            execute(
                f'CREATE TABLE "{tbl}" ('
                " ocel_source_id VARCHAR NOT NULL,"
                " ocel_target_id VARCHAR NOT NULL,"
                " ocel_qualifier VARCHAR NOT NULL,"
                " PRIMARY KEY (ocel_source_id, ocel_target_id, ocel_qualifier)"
                ")"
            )
            execute(
                f'INSERT INTO "{tbl}" (ocel_source_id, ocel_target_id, ocel_qualifier) '
                "SELECT oo.ocel_source_id, oo.ocel_target_id, oo.ocel_qualifier "
                "FROM object_object oo "
                "JOIN object o1 ON o1.ocel_id = oo.ocel_source_id "
                "JOIN object o2 ON o2.ocel_id = oo.ocel_target_id "
                f"WHERE o1.ocel_type = {p} AND o2.ocel_type = {p}",
                [s_t, t_t],
            )
            execute(
                f"INSERT INTO object_object_typed_index VALUES ({p}, {p}, {p})",
                [s_t, t_t, tbl],
            )

    execute("DROP TABLE event_object")
    execute("DROP TABLE object_object")

    # Generic views keep the shared SQL implementations usable.
    eo_branches = []
    for ev_t in ev_types:
        for ob_t in ob_types:
            if (ev_t, ob_t) not in e2o_pairs:
                continue
            tbl = f"event_object_{clean_type_name(ev_t)}__{clean_type_name(ob_t)}"
            ev_t_sq = ev_t.replace("'", "''")
            ob_t_sq = ob_t.replace("'", "''")
            eo_branches.append(
                f"SELECT '{ev_t_sq}' AS ocel_event_type, "
                f"'{ob_t_sq}' AS ocel_object_type, "
                "ocel_event_id, ocel_object_id, ocel_qualifier "
                f'FROM "{tbl}"'
            )
    if eo_branches:
        execute("CREATE VIEW event_object AS " + " UNION ALL ".join(eo_branches))
    else:
        execute(
            "CREATE VIEW event_object AS "
            "SELECT '' AS ocel_event_type, '' AS ocel_object_type, "
            "'' AS ocel_event_id, '' AS ocel_object_id, '' AS ocel_qualifier "
            "WHERE 1=0"
        )

    oo_branches = []
    for s_t in ob_types:
        for t_t in ob_types:
            if (s_t, t_t) not in o2o_pairs:
                continue
            tbl = f"object_object_{clean_type_name(s_t)}__{clean_type_name(t_t)}"
            s_t_sq = s_t.replace("'", "''")
            t_t_sq = t_t.replace("'", "''")
            oo_branches.append(
                f"SELECT '{s_t_sq}' AS ocel_source_type, "
                f"'{t_t_sq}' AS ocel_target_type, "
                "ocel_source_id, ocel_target_id, ocel_qualifier "
                f'FROM "{tbl}"'
            )
    if oo_branches:
        execute("CREATE VIEW object_object AS " + " UNION ALL ".join(oo_branches))
    else:
        execute(
            "CREATE VIEW object_object AS "
            "SELECT '' AS ocel_source_type, '' AS ocel_target_type, "
            "'' AS ocel_source_id, '' AS ocel_target_id, '' AS ocel_qualifier "
            "WHERE 1=0"
        )
