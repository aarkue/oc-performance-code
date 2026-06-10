"""P3 / Sojourn: per-event sojourn time.

For each event, the sojourn time is the elapsed time since its latest preceding
event (the latest immediate predecessor across its shared objects), in integer
microseconds. One row per event that has at least one predecessor.
"""

from __future__ import annotations

from typing import Any

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OutputSchema, PatternContract

_OUTPUT = OutputSchema(kind="tuple_set", columns=["event_id", "sojourn_us"])


def _instances(_dataset) -> list[tuple[str, Any]]:
    return [("sojourn", None)]


CONTRACT = PatternContract(
    name="oc_perf_sojourn",
    output=_OUTPUT,
    instances=_instances,
    oracle_model="linked_ocel",
)

registry.register_pattern(CONTRACT)
