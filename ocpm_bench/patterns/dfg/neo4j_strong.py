"""DFG via Neo4j (strong): group-count over the materialized per-type ``:DF`` edges."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models.primitives import clean_type_name
from ocpm_bench.patterns.base import PerTypeInputs

_DFG_CYPHER = """
MATCH (a)-[df:DF {{EntityType: '{object_type}'}}]->(b)
RETURN labels(a)[0] AS src, labels(b)[0] AS tgt, COUNT(*) AS cnt
"""


def run(model, inputs: PerTypeInputs) -> list[tuple]:
    cypher = _DFG_CYPHER.format(object_type=clean_type_name(inputs.object_type))
    rows = model.execute_cypher(cypher)
    return [(src, tgt, int(cnt)) for src, tgt, cnt in rows]


registry.register_impl("dfg", "neo4j_strong", sys.modules[__name__])
