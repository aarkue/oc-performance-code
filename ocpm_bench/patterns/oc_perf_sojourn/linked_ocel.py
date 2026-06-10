"""Sojourn via LinkedOCEL: native per-event r4pm binding.

Calls ``locel_oc_perf_sojourn_per_event`` (one ``(event_id, sojourn_us)`` row per event).
"""

from __future__ import annotations

import sys

import r4pm

from ocpm_bench.harness import registry
from ocpm_bench.models.linked_ocel import LinkedOCELModel
from ocpm_bench.patterns._perf_topk import perf_top_k


def run(model: LinkedOCELModel, _inputs) -> list[tuple[str, int]]:
    fn = getattr(r4pm.bindings, "locel_oc_perf_sojourn_per_event", None)
    if fn is None:
        raise NotImplementedError(
            "per-event Sojourn needs the r4pm binding locel_oc_perf_sojourn_per_event; "
            "rebuild r4pm with the per-event OC-Perf functions"
        )
    k = perf_top_k()
    rows = fn(model.ocel_id, k) if k is not None else fn(model.ocel_id)
    return [(str(eid), int(s)) for eid, s in rows]


registry.register_impl("oc_perf_sojourn", "linked_ocel", sys.modules[__name__])
