"""K1 via Neo4j (strong): mirror of Kuzu strong query."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models.primitives import clean_type_name

_CYPHER = """
MATCH (e)-[:E2O]->(o)
WHERE any(l IN labels(e) WHERE l IN $event_labels)
  AND any(l IN labels(o) WHERE l IN $object_labels)
RETURN labels(e)[0] AS activity, labels(o)[0] AS object_type, COUNT(*) AS cnt
"""


def run(model, _inputs) -> list[tuple[str, str, int]]:
    rows = model.execute_cypher(_CYPHER, {
        "event_labels": [clean_type_name(t) for t in model.get_event_types()],
        "object_labels": [clean_type_name(t) for t in model.get_object_types()],
    })
    return [
        (model.original_name(str(a)), model.original_name(str(t)), int(c))
        for a, t, c in rows
    ]


registry.register_impl("kpi_heatmap", "neo4j_strong", sys.modules[__name__])
