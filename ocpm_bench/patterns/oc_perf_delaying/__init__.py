"""P3 / W2: per event, the latest directly-preceding event's (activity, object
type), counted. A custom bottleneck-frequency measure, not an OPerA metric.

For each event, over its df-edges ``(p, o)`` with ``p.time < e.time``, pick the
one with the latest ``p.time``, tie-broken on ``o.ocel_id`` ascending, and emit
``(p.activity, o.type)``. Output is the set of
``(predecessor_activity, object_type, count)`` triples. Events without
predecessors are skipped.
"""

from __future__ import annotations

from typing import Any

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OutputSchema, PatternContract

_OUTPUT = OutputSchema(
    kind="tuple_set",
    columns=["predecessor_activity", "object_type", "count"],
)


def _instances(_dataset) -> list[tuple[str, Any]]:
    return [("W2", None)]


def _post_process(raw, _inputs, model):
    if model.name in ("kuzu", "neo4j_strong"):
        translate = model.original_name
        return [
            (translate(pred_act), translate(o_type), count)
            for pred_act, o_type, count in raw
        ]
    return raw


CONTRACT = PatternContract(
    name="oc_perf_delaying",
    output=_OUTPUT,
    instances=_instances,
    oracle_model="linked_ocel",
    post_process=_post_process,
)

registry.register_pattern(CONTRACT)
