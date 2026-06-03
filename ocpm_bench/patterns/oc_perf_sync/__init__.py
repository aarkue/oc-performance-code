"""P3 / W1: per-event synchronization time, aggregated per activity.

For each event ``e`` and each related object, take ``e``'s immediate
directly-follows predecessor on that object. The per-event sync time is the span
between the earliest and latest of those predecessor timestamps, floored to whole
seconds. Events without predecessors are skipped.

Output is the set of ``(activity, total_sync_seconds, count)`` triples. The mean
per activity is ``total_sync_seconds / count``, kept as separate numerator and
denominator so cross-engine equality stays integer-only.
"""

from __future__ import annotations

from typing import Any

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OutputSchema, PatternContract

_OUTPUT = OutputSchema(
    kind="tuple_set",
    columns=["activity", "total_sync_seconds", "count"],
)


def _instances(_dataset) -> list[tuple[str, Any]]:
    return [("W1", None)]


def _post_process(raw, _inputs, model):
    if model.name in ("kuzu", "neo4j_strong"):
        translate = model.original_name
        return [(translate(act), total, count) for act, total, count in raw]
    return raw


CONTRACT = PatternContract(
    name="oc_perf_sync",
    output=_OUTPUT,
    instances=_instances,
    oracle_model="linked_ocel",
    post_process=_post_process,
)

registry.register_pattern(CONTRACT)
