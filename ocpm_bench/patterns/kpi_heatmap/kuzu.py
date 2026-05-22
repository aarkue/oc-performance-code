"""K1 (heatmap) via Kuzu (strong + weak)."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry

_STRONG = """
    MATCH (e)-[:E2O]->(o)
    WHERE LABEL(e) IN $event_labels AND LABEL(o) IN $object_labels
    RETURN LABEL(e), LABEL(o), COUNT(*)
"""

_WEAK = """
    MATCH (e:Event)-[:E2O]->(o:Object)
    RETURN e.type, o.type, COUNT(*)
"""


def run(model, _inputs) -> list[tuple[str, str, int]]:
    if model.name == "kuzu_weak":
        rows = model.execute_cypher(_WEAK)
        return [(str(a), str(t), int(c)) for a, t, c in rows]
    rows = model.execute_cypher(_STRONG, {
        "event_labels": model._event_labels,
        "object_labels": model._object_labels,
    })
    return [
        (model.original_name(str(a)), model.original_name(str(t)), int(c))
        for a, t, c in rows
    ]


registry.register_impl("kpi_heatmap", "kuzu", sys.modules[__name__])
registry.register_impl("kpi_heatmap", "kuzu_weak", sys.modules[__name__])
