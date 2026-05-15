"""DFG via PrimitiveAccess: same Python code for every model."""

from __future__ import annotations

import itertools
import sys
from collections import Counter
from typing import Any

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OutputSchema, PatternContract, PerTypeInputs


def run(model, inputs: PerTypeInputs) -> list[tuple[str, str, int]]:
    counts: Counter[tuple[str, str]] = Counter()
    for oid in model.get_objects_of_type(inputs.object_type):
        eids = model.get_events_of_object(oid)
        eids.sort(key=lambda e: (model.get_timestamp(e), e))
        trace = [model.get_activity(e) for e in eids]
        for a, b in itertools.pairwise(trace):
            counts[(a, b)] += 1
    return [(a, b, c) for (a, b), c in counts.items()]


def _instances(dataset) -> list[tuple[str, Any]]:
    return [(ot, PerTypeInputs(object_type=ot)) for ot in dataset.object_types()]


CONTRACT = PatternContract(
    name="dfg_prim",
    output=OutputSchema(kind="tuple_set", columns=["src", "tgt", "count"]),
    instances=_instances,
)

# kuzu_weak uses flat Event/Object node tables and does not implement PrimitiveAccess.
for _m in ("linked_ocel", "sqlite_mem", "duckdb", "sqlite_mem_strong_rels",
           "duckdb_strong_rels", "kuzu", "polars", "pandas"):
    registry.register_impl("dfg_prim", _m, sys.modules[__name__])

registry.register_pattern(CONTRACT)
