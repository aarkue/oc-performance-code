"""DFG via LinkedOCEL: r4pm's `get_dfg_of_object_type`.

`dfg` and `variants` are engine-native patterns: each engine uses its own
idiomatic path. The Rust helper IS the access primitive for LinkedOCEL the
same way SQL is for DuckDB. For the strict "same algorithm on every model"
comparison, use `dfg_prim`.
"""

from __future__ import annotations

import sys

import r4pm

from ocpm_bench.harness import registry
from ocpm_bench.models.linked_ocel import LinkedOCELModel
from ocpm_bench.patterns.base import PerTypeInputs


def run(model: LinkedOCELModel, inputs: PerTypeInputs) -> list[tuple[str, str, int]]:
    raw = r4pm.bindings.get_dfg_of_object_type(model.ocel_id, inputs.object_type)
    return [(a, b, int(c)) for [[a, b], c] in raw]


registry.register_impl("dfg", "linked_ocel", sys.modules[__name__])
