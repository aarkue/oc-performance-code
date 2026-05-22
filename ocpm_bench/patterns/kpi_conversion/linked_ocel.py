"""K2 (conversion rate) via LinkedOCEL.

Single call to the r4pm Rust binding `locel_conversion_rate`.
"""

from __future__ import annotations

import sys

import r4pm

from ocpm_bench.harness import registry
from ocpm_bench.models.linked_ocel import LinkedOCELModel
from ocpm_bench.patterns.kpi_conversion import KPIConversionInputs


def run(model: LinkedOCELModel, inputs: KPIConversionInputs) -> float:
    return float(r4pm.bindings.locel_conversion_rate(
        model.ocel_id, inputs.activity, inputs.source_type, inputs.target_type,
    ))


registry.register_impl("kpi_conversion", "linked_ocel", sys.modules[__name__])
