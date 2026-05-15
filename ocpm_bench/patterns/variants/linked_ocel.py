"""Variants via LinkedOCEL: r4pm's `get_variants_of_object_type`.

Engine-native path; see `patterns/dfg/linked_ocel.py` for the design note.
For the strict "same algorithm everywhere" comparison, use `variants_prim`.
"""

from __future__ import annotations

import sys

import r4pm

from ocpm_bench.harness import registry
from ocpm_bench.models.linked_ocel import LinkedOCELModel
from ocpm_bench.patterns.base import PerTypeInputs


def run(model: LinkedOCELModel, inputs: PerTypeInputs) -> list[tuple]:
    raw = r4pm.bindings.get_variants_of_object_type(model.ocel_id, inputs.object_type)
    return [(tuple(variant), int(count)) for variant, count in raw]


registry.register_impl("variants", "linked_ocel", sys.modules[__name__])
