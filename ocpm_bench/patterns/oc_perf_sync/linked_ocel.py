"""W1 via LinkedOCEL.

Single call to the r4pm Rust binding `locel_oc_perf_sync`.
"""

from __future__ import annotations

import sys

import r4pm

from ocpm_bench.harness import registry
from ocpm_bench.models.linked_ocel import LinkedOCELModel


def run(model: LinkedOCELModel, _inputs) -> list[tuple[str, int, int]]:
    return [
        (str(a), int(t), int(c))
        for a, t, c in r4pm.bindings.locel_oc_perf_sync(model.ocel_id)
    ]


registry.register_impl("oc_perf_sync", "linked_ocel", sys.modules[__name__])
