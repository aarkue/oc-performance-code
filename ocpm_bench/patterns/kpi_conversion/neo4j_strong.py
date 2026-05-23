"""K2 via Neo4j (strong): mirror of Kuzu strong query."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models.primitives import clean_type_name
from ocpm_bench.patterns.kpi_conversion import KPIConversionInputs

_CYPHER_TPL = """
MATCH (s:`{source_type}`)
WITH COUNT(s) AS total
MATCH (s:`{source_type}`)-[:O2O]->(t:`{target_type}`)<-[:E2O]-(e:`{activity}`)
WITH total, COUNT(DISTINCT s) AS reached
RETURN CASE WHEN total > 0
            THEN toFloat(reached) / toFloat(total)
            ELSE 0.0 END AS rate
"""


def run(model, inputs: KPIConversionInputs) -> float:
    cypher = _CYPHER_TPL.format(
        source_type=clean_type_name(inputs.source_type),
        target_type=clean_type_name(inputs.target_type),
        activity=clean_type_name(inputs.activity),
    )
    rows = model.execute_cypher(cypher)
    return float(rows[0][0]) if rows and rows[0][0] is not None else 0.0


registry.register_impl("kpi_conversion", "neo4j_strong", sys.modules[__name__])
