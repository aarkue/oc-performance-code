"""Trace-variants pattern: distinct time-ordered activity sequences per object type, counted.

Each engine's `run()` materializes canonical `(tuple[str,...], int)` rows
inside the timed region. The only untimed work is the cleaned-label-to-
OCEL-name translation for Kuzu and Neo4j, which is benchmark-induced.
"""

from __future__ import annotations

from typing import Any

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OutputSchema, PatternContract, PerTypeInputs

_OUTPUT = OutputSchema(kind="tuple_set", columns=["variant", "count"])

# Delimiter for engines whose native trace representation is a joined string
# (DuckDB STRING_AGG, SQLite GROUP_CONCAT, Polars list.join). Unit separator.
DELIM = "\x1f"


def _instances(dataset) -> list[tuple[str, Any]]:
    return [(ot, PerTypeInputs(object_type=ot)) for ot in dataset.object_types()]


def _post_process(raw, inputs: PerTypeInputs, model):
    if model.name in ("kuzu", "neo4j_strong"):
        translate = model.original_name
        return [(tuple(map(translate, trace)), count) for trace, count in raw]
    return raw


CONTRACT = PatternContract(
    name="variants",
    output=_OUTPUT,
    instances=_instances,
    post_process=_post_process,
)

registry.register_pattern(CONTRACT)
