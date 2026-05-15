"""DFG pattern: per-object-type directly-follows pairs.

Each engine's `run()` materializes canonical `(str, str, int)` rows inside
the timed region. The only untimed work is Kuzu's cleaned-label-to-OCEL-name
translation, which is benchmark-induced (Kuzu mangles type labels).
"""

from __future__ import annotations

from typing import Any

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OutputSchema, PatternContract, PerTypeInputs

_OUTPUT = OutputSchema(kind="tuple_set", columns=["src", "tgt", "count"])


def _instances(dataset) -> list[tuple[str, Any]]:
    return [
        (ot, PerTypeInputs(object_type=ot))
        for ot in dataset.object_types()
    ]


def _post_process(raw, inputs: PerTypeInputs, model):
    if model.name == "kuzu":
        translate = model.original_name
        return [(translate(src), translate(tgt), cnt) for src, tgt, cnt in raw]
    return raw


CONTRACT = PatternContract(
    name="dfg",
    output=_OUTPUT,
    instances=_instances,
    post_process=_post_process,
)

registry.register_pattern(CONTRACT)
