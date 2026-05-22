"""K1 (heatmap) via Pandas."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models.pandas import PandasModel


def run(model: PandasModel, _inputs) -> list[tuple[str, str, int]]:
    counts = (
        model.relations
        .groupby(["ocel:activity", "ocel:type"], sort=False)
        .size()
        .reset_index(name="count")
    )
    return [(str(a), str(t), int(c)) for a, t, c in counts.itertuples(index=False, name=None)]


registry.register_impl("kpi_heatmap", "pandas", sys.modules[__name__])
