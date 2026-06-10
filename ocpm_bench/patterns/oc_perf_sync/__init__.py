"""P3 / Sync: per-event synchronization time and the delaying object.

For each event, take the events directly preceding it (the immediate predecessor
on each shared object). The synchronization time is the span between the earliest
and latest of these predecessors, in integer microseconds. The delaying object is
the shared object linking the latest predecessor. One row per event that has at
least one predecessor.
"""

from __future__ import annotations

from typing import Any

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OutputSchema, PatternContract

_OUTPUT = OutputSchema(
    kind="tuple_set",
    columns=["event_id", "sync_us", "delaying_object"],
)


def _instances(_dataset) -> list[tuple[str, Any]]:
    return [("sync", None)]


CONTRACT = PatternContract(
    name="oc_perf_sync",
    output=_OUTPUT,
    instances=_instances,
    oracle_model="linked_ocel",
)

registry.register_pattern(CONTRACT)
