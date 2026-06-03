"""DFG via Kuzu."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models.primitives import clean_type_name
from ocpm_bench.patterns.base import PerTypeInputs

# Group-count over the materialized :DF edges of this EntityType.
_DFG_STRONG_CYPHER = """
MATCH (a)-[df:DF]->(b)
WHERE df.EntityType = $object_type
RETURN LABEL(a) AS src, LABEL(b) AS tgt, COUNT(*) AS cnt
"""

# Weak: same, activity from the node `type` column (single Event label).
_DFG_WEAK_CYPHER = """
MATCH (a:Event)-[df:DF]->(b:Event)
WHERE df.EntityType = $object_type
RETURN a.type AS src, b.type AS tgt, COUNT(*) AS cnt
"""


def run(model, inputs: PerTypeInputs) -> list[tuple]:
    if model.name == "kuzu_weak":
        rows = model.execute_cypher(_DFG_WEAK_CYPHER, {"object_type": inputs.object_type})
    else:
        rows = model.execute_cypher(
            _DFG_STRONG_CYPHER,
            {"object_type": clean_type_name(inputs.object_type)},
        )
    return [(src, tgt, int(cnt)) for src, tgt, cnt in rows]


registry.register_impl("dfg", "kuzu", sys.modules[__name__])
registry.register_impl("dfg", "kuzu_weak", sys.modules[__name__])
