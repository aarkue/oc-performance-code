"""P4 / K1: activity x object-type frequency heatmap.

For each (activity, object_type) pair, count the number of ``event_object``
rows linking an event of that activity to an object of that type. Output is
the unordered set of ``(activity, object_type, count)`` triples.
"""

from __future__ import annotations

from typing import Any

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OutputSchema, PatternContract

_OUTPUT = OutputSchema(kind="tuple_set", columns=["activity", "object_type", "count"])


def _instances(_dataset) -> list[tuple[str, Any]]:
    return [("K1", None)]


CONTRACT = PatternContract(
    name="kpi_heatmap",
    output=_OUTPUT,
    instances=_instances,
)

registry.register_pattern(CONTRACT)
