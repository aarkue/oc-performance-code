"""Pattern protocol primitives: OutputSchema and canonicalize."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

SchemaKind = Literal["tuple_set", "tuple_list_ordered", "scalar"]


@dataclass(frozen=True)
class OutputSchema:
    """Declarative description of a pattern's output shape; drives `canonicalize`."""

    kind: SchemaKind
    columns: list[str] = field(default_factory=list)
    scalar_type: type | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("tuple_set", "tuple_list_ordered", "scalar"):
            raise ValueError(
                f"unknown OutputSchema kind: {self.kind!r}"
            )


def _row_to_tuple(row: Any, columns: list[str]) -> tuple:
    if isinstance(row, dict):
        return tuple(row[c] for c in columns)
    if isinstance(row, (tuple, list)):
        return tuple(row)
    raise TypeError(f"canonicalize: unsupported row type {type(row).__name__}")


def canonicalize(raw: Any, schema: OutputSchema):
    """Normalize raw model output into a canonical, comparable value.

    Untimed: only called after `run()` returns.
    """
    if schema.kind == "tuple_set":
        rows: Iterable = raw
        return frozenset(_row_to_tuple(r, schema.columns) for r in rows)
    if schema.kind == "tuple_list_ordered":
        rows = raw
        return tuple(_row_to_tuple(r, schema.columns) for r in rows)
    if schema.kind == "scalar":
        if schema.scalar_type is None:
            return raw
        return schema.scalar_type(raw)
    raise ValueError(f"canonicalize: unknown kind {schema.kind!r}")


@dataclass(frozen=True)
class PerTypeInputs:
    """Inputs for patterns parameterized by object type (DFG, variants)."""

    object_type: str


@dataclass
class OCPQInputs:
    """Inputs for OCPQ queries."""

    query_id: str
    query_body: dict[str, Any]


@dataclass(frozen=True)
class PatternContract:
    """Declarative contract for one access-pattern slot.

    `post_process` runs untimed after `run()`; it covers cross-engine
    type canonicalization and any engine-specific reshaping that should
    not be charged to engine timings. It receives the live model
    instance so it can use engine-specific helpers (e.g. Kuzu's
    cleaned-label-to-original-name map).
    """

    name: str
    output: OutputSchema
    instances: Callable[[Any], list[tuple[str, Any]]]
    oracle_model: str = "linked_ocel"
    post_process: Callable[[Any, Any, Any], Any] | None = None
