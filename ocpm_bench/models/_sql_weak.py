"""Schema builder for the weak (generic-table) SQL variant.

Consolidates the OCEL 2.0 strong-typed per-activity / per-object-type tables into
single wide tables (type as a column, attributes nullable), then re-exposes each
per-type table as a view over the consolidated table. Base pattern SQL that
references ``event_<type>`` / ``object_<type>`` runs unchanged, but per-type
access becomes a filtered scan of one wide table -- the weak node-typing access
pattern.

The generic ``event`` / ``object`` list tables are kept as-is (they back foreign
keys the engine enforces). The per-type attribute/timestamp tables are
consolidated into ``event_attr`` / ``object_attr``, and each per-type table
becomes a view over its wide table. Weak ``event_times`` reads ``event_attr``.
"""

from __future__ import annotations

from collections.abc import Callable


def _lit(value: str) -> str:
    return value.replace("'", "''")


def _consolidate(
    execute: Callable[..., list[tuple]],
    list_columns: Callable[[str], list[str]],
    *,
    src_prefix: str,
    wide_table: str,
    types: list[str],
    id_col: str,
) -> None:
    """Union every ``<src_prefix>_<t>`` table into ``wide_table`` (adding an
    ``ocel_type`` column), then replace each source table with a view over it.

    ``id_col`` is present in every source table and is never nullable.
    """
    cols_per: dict[str, list[str]] = {}
    for t in types:
        cols = list_columns(f"{src_prefix}_{t}")
        if cols:
            cols_per[t] = cols
    present = [t for t in types if t in cols_per]
    if not present:
        return

    # Attribute columns = every non-id column across all source tables, first-seen.
    attrs: list[str] = []
    seen = {id_col}
    for t in present:
        for c in cols_per[t]:
            if c not in seen:
                seen.add(c)
                attrs.append(c)

    def _branch(t: str) -> str:
        have = set(cols_per[t])
        parts = [f'"{id_col}"', f"'{_lit(t)}' AS ocel_type"]
        parts += [f'"{a}"' if a in have else f'NULL AS "{a}"' for a in attrs]
        return f'SELECT {", ".join(parts)} FROM "{src_prefix}_{t}"'

    union = " UNION ALL ".join(_branch(t) for t in present)
    execute(f'CREATE TABLE "{wide_table}" AS {union}')

    for t in present:
        proj = ", ".join(f'"{c}"' for c in cols_per[t])
        execute(f'DROP TABLE "{src_prefix}_{t}"')
        execute(
            f'CREATE VIEW "{src_prefix}_{t}" AS '
            f'SELECT {proj} FROM "{wide_table}" WHERE ocel_type = \'{_lit(t)}\''
        )


def build_weak_schema(
    execute: Callable[..., list[tuple]],
    list_columns: Callable[[str], list[str]],
    ev_types: list[str],
    ob_types: list[str],
) -> None:
    """Transform a strong-typed OCEL 2.0 DB into the weak (generic-table) variant.

    ``execute(sql)`` runs one statement; ``list_columns(table)`` returns a table's
    column names in order (empty if the table is absent).
    """
    _consolidate(
        execute, list_columns,
        src_prefix="event", wide_table="event_attr", types=ev_types,
        id_col="ocel_id",
    )
    _consolidate(
        execute, list_columns,
        src_prefix="object", wide_table="object_attr", types=ob_types,
        id_col="ocel_id",
    )
