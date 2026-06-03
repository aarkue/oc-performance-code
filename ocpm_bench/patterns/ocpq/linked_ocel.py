"""OCPQ via LinkedOCEL: r4pm's `evaluate_ocpq` returns rows in Rust shape.

The pattern's `post_process` reshapes those rows to the SQL row shape
untimed, so engine timings reflect engine work only.
"""

from __future__ import annotations

import sys

# `evaluate_ocpq` is attached to the r4pm module, not the bindings submodule
from r4pm import r4pm as _native  # type: ignore[attr-defined]

from ocpm_bench.harness import registry
from ocpm_bench.models.linked_ocel import LinkedOCELModel
from ocpm_bench.patterns.base import OCPQInputs


def run(model: LinkedOCELModel, inputs: OCPQInputs) -> list[tuple]:
    return _native.evaluate_ocpq(inputs.query_body["tree_json"], model.ocel_id)


registry.register_impl("ocpq", "linked_ocel", sys.modules[__name__])
