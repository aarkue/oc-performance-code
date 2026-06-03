"""EKG via LinkedOCEL: r4pm's native ``evaluate_ocpq`` over the OCPQ tree.

This is the oracle. It is also the custom-native data point for the EKG
workload: ``evaluate_ocpq`` is Rust4PM's compiled OCPQ engine, the same path
the OCPQ Q1-Q7 workload uses.
"""

from __future__ import annotations

import sys

# `evaluate_ocpq` is attached to the r4pm pymodule via `m.add_function(...)`,
# so it is not in the `r4pm.bindings.*` stubs.
from r4pm import r4pm as _native  # type: ignore[attr-defined]

from ocpm_bench.harness import registry
from ocpm_bench.models.linked_ocel import LinkedOCELModel
from ocpm_bench.patterns.base import OCPQInputs


def run(model: LinkedOCELModel, inputs: OCPQInputs) -> list[tuple]:
    return _native.evaluate_ocpq(inputs.query_body["tree_json"], model.ocel_id)


registry.register_impl("ekg", "linked_ocel", sys.modules[__name__])
