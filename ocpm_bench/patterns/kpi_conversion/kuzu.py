"""K2 (conversion rate) via Kuzu (strong + weak).

Source -> O2O -> Target -> E2O <- Event with activity.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models.primitives import clean_type_name
from ocpm_bench.patterns.kpi_conversion import KPIConversionInputs

_STRONG_TPL = """
    MATCH (s:`{source_type}`)
    WITH COUNT(s) AS total
    MATCH (s:`{source_type}`)-[:O2O]->(t:`{target_type}`)<-[:E2O]-(e:`{activity}`)
    WITH total, COUNT(DISTINCT s) AS reached
    RETURN CASE WHEN total > 0
                THEN CAST(reached AS DOUBLE) / CAST(total AS DOUBLE)
                ELSE 0.0 END
"""

_WEAK = """
    MATCH (s:Object) WHERE s.type = $source_type
    WITH COUNT(s) AS total
    MATCH (s:Object)-[:O2O]->(t:Object)<-[:E2O]-(e:Event)
    WHERE s.type = $source_type
      AND t.type = $target_type
      AND e.type = $activity
    WITH total, COUNT(DISTINCT s) AS reached
    RETURN CASE WHEN total > 0
                THEN CAST(reached AS DOUBLE) / CAST(total AS DOUBLE)
                ELSE 0.0 END
"""


def run(model, inputs: KPIConversionInputs) -> float:
    if model.name == "kuzu_weak":
        rows = model.execute_cypher(_WEAK, {
            "source_type": inputs.source_type,
            "target_type": inputs.target_type,
            "activity": inputs.activity,
        })
    else:
        sql = _STRONG_TPL.format(
            source_type=clean_type_name(inputs.source_type),
            target_type=clean_type_name(inputs.target_type),
            activity=clean_type_name(inputs.activity),
        )
        rows = model.execute_cypher(sql)
    return float(rows[0][0]) if rows and rows[0][0] is not None else 0.0


registry.register_impl("kpi_conversion", "kuzu", sys.modules[__name__])
registry.register_impl("kpi_conversion", "kuzu_weak", sys.modules[__name__])
