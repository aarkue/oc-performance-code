"""PrimitiveAccess mixin and SQL helpers for the relational OCEL 2.0 schema.

The two relational backings (sqlite_mem, duckdb) read the same r4pm-exported
strong-typed schema, so PrimitiveAccess only differs in `execute_sql` and
`get_timestamp`. The DFG SQL template is also identical (LEAD / UNION ALL /
JOIN are portable across SQLite and DuckDB).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from ocpm_bench.models.primitives import normalize_timestamp


class _SQLConn(Protocol):
    def execute_sql(self, query: str, params: dict | None = None) -> list[tuple]: ...


class SQLOCELPrimitives:
    """Mixin: PrimitiveAccess methods for r4pm's strong-typed OCEL 2.0 SQL schema.

    Concrete subclasses must provide `execute_sql(query, params=None)`.
    Optionally override `_normalize_timestamp_value` to coerce the engine's
    native timestamp type before stringification (DuckDB returns a
    `datetime`; SQLite returns a string).
    """

    def _normalize_timestamp_value(self, value: Any) -> str:
        if hasattr(value, "isoformat"):
            return normalize_timestamp(value.isoformat())
        return normalize_timestamp(value)

    def get_object_types(self: _SQLConn) -> list[str]:
        return [r[0] for r in self.execute_sql(
            "SELECT DISTINCT ocel_type FROM object ORDER BY ocel_type"
        )]

    def get_objects_of_type(self: _SQLConn, object_type: str) -> list[str]:
        return [r[0] for r in self.execute_sql(
            "SELECT ocel_id FROM object WHERE ocel_type = :t", {"t": object_type}
        )]

    def get_object_type(self: _SQLConn, object_id: str) -> str:
        return self.execute_sql(
            "SELECT ocel_type FROM object WHERE ocel_id = :o", {"o": object_id}
        )[0][0]

    def get_activity(self: _SQLConn, event_id: str) -> str:
        return self.execute_sql(
            "SELECT ocel_type FROM event WHERE ocel_id = :e", {"e": event_id}
        )[0][0]

    def get_timestamp(self, event_id: str) -> str:
        activity = self.get_activity(event_id)  # type: ignore[attr-defined]
        rows = self.execute_sql(  # type: ignore[attr-defined]
            f'SELECT ocel_time FROM "event_{activity}" WHERE ocel_id = :e',
            {"e": event_id},
        )
        return self._normalize_timestamp_value(rows[0][0])

    def get_events_of_type(self: _SQLConn, activity: str) -> list[str]:
        return [r[0] for r in self.execute_sql(
            f'SELECT ocel_id FROM "event_{activity}"'
        )]

    def get_events_of_object(self: _SQLConn, object_id: str) -> list[str]:
        return [r[0] for r in self.execute_sql(
            "SELECT ocel_event_id FROM event_object WHERE ocel_object_id = :o",
            {"o": object_id},
        )]

    def get_objects_of_event(self: _SQLConn, event_id: str) -> list[str]:
        return [r[0] for r in self.execute_sql(
            "SELECT ocel_object_id FROM event_object WHERE ocel_event_id = :e",
            {"e": event_id},
        )]

    def get_related_objects(self: _SQLConn, object_id: str) -> list[str]:
        return [r[0] for r in self.execute_sql(
            "SELECT ocel_target_id FROM object_object WHERE ocel_source_id = :o",
            {"o": object_id},
        )]

    def event_times_union(self) -> str:
        """CTE body yielding ``(ocel_id, ocel_time)`` for every event.

        The strong schema unions the per-activity timestamp tables; the weak
        schema overrides this to read the consolidated ``event`` table directly.
        """
        return build_event_times_union(self.execute_sql)  # type: ignore[attr-defined]


def build_event_times_union(execute_sql: Callable[[str], list[tuple]]) -> str:
    """Return a UNION ALL CTE over each `event_<type>(ocel_id, ocel_time)` table.

    The strong-typed exporter splits event timestamps across per-activity
    tables; the DFG and variants impls join against a unified view.
    """
    types = [row[0] for row in execute_sql(
        "SELECT ocel_type FROM event_map_type ORDER BY ocel_type"
    )]
    parts = [f'SELECT ocel_id, ocel_time FROM "event_{t}"' for t in types]
    return " UNION ALL ".join(parts)


# Shared DFG query: LEAD over per-object timestamp-ordered events.
DFG_SQL_TEMPLATE = """
WITH event_times AS ({union_cte}),
ordered AS (
  SELECT
    e.ocel_type         AS activity,
    eo.ocel_object_id   AS object_id,
    et.ocel_time        AS t,
    LEAD(e.ocel_type) OVER (
      PARTITION BY eo.ocel_object_id
      ORDER BY et.ocel_time, e.ocel_id
    ) AS next_activity
  FROM event_object eo
  JOIN object ob     ON ob.ocel_id  = eo.ocel_object_id
  JOIN event e       ON e.ocel_id   = eo.ocel_event_id
  JOIN event_times et ON et.ocel_id = e.ocel_id
  WHERE ob.ocel_type = :object_type
)
SELECT activity AS src, next_activity AS tgt, COUNT(*) AS cnt
FROM ordered
WHERE next_activity IS NOT NULL
GROUP BY activity, next_activity
"""


def variants_sql_template(agg_func: str, delim: str) -> str:
    """SQLite uses GROUP_CONCAT; DuckDB uses STRING_AGG. Otherwise identical."""
    return f"""
WITH event_times AS ({{union_cte}}),
ordered AS (
  SELECT
    eo.ocel_object_id AS oid,
    e.ocel_type       AS activity,
    et.ocel_time      AS t,
    e.ocel_id         AS eid
  FROM event_object eo
  JOIN object ob      ON ob.ocel_id  = eo.ocel_object_id
  JOIN event e        ON e.ocel_id   = eo.ocel_event_id
  JOIN event_times et ON et.ocel_id  = e.ocel_id
  WHERE ob.ocel_type = :object_type
),
traces AS (
  SELECT oid,
         {agg_func}(activity, '{delim}' ORDER BY t, eid) AS trace_str
  FROM ordered
  GROUP BY oid
)
SELECT trace_str, COUNT(*) AS cnt
FROM traces
GROUP BY trace_str
"""
