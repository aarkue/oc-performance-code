"""OCPQ via Polars SQLContext.

Polars frames are registered under the r4pm strong-typed SQL schema names so
the corpus SQL runs unchanged: `event_object(ocel_event_id, ocel_object_id)`,
`object_object(ocel_source_id, ocel_target_id)`, `object_<type>(ocel_id)`,
`event_<activity>(ocel_id, ocel_time)`. Tables whose type/activity names
would break SQL identifiers (spaces, etc.) are skipped; the corpus only
references clean names.

Q6: Polars stores ocel_time as Datetime, so timestamp subtraction yields a
Duration; iter_rows() converts to timedelta, handled by _q6.to_milliseconds.
"""

from __future__ import annotations

import re
import sys

import polars as pl

from ocpm_bench.harness import registry
from ocpm_bench.models.polars import PolarsModel
from ocpm_bench.patterns.base import OCPQInputs

_SAFE_IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def _build_context(model: PolarsModel) -> pl.SQLContext:
    ctx = pl.SQLContext()
    ctx.register(
        "event_object",
        model.relations.select([
            pl.col("ocel:eid").alias("ocel_event_id"),
            pl.col("ocel:oid").alias("ocel_object_id"),
        ]),
    )
    ctx.register(
        "object_object",
        model.frames["o2o"].select([
            pl.col("ocel:oid").alias("ocel_source_id"),
            pl.col("ocel:oid_2").alias("ocel_target_id"),
        ]),
    )
    for otype in model.objects["ocel:type"].unique().to_list():
        if not _SAFE_IDENT.match(otype):
            continue
        ctx.register(
            f"object_{otype}",
            model.objects.filter(pl.col("ocel:type") == otype).select(
                pl.col("ocel:oid").alias("ocel_id")
            ),
        )
    for activity in model.events["ocel:activity"].unique().to_list():
        if not _SAFE_IDENT.match(activity):
            continue
        ctx.register(
            f"event_{activity}",
            model.events.filter(pl.col("ocel:activity") == activity).select([
                pl.col("ocel:eid").alias("ocel_id"),
                pl.col("ocel:timestamp").alias("ocel_time"),
            ]),
        )
    return ctx


def pre_run(model: PolarsModel) -> None:
    """Build the SQLContext once per cell (untimed)."""
    model._ocpq_ctx = _build_context(model)  # type: ignore[attr-defined]


def run(model: PolarsModel, inputs: OCPQInputs) -> list[tuple]:
    sql = inputs.query_body.get("sql-polars", inputs.query_body["sql"])
    ctx: pl.SQLContext = model._ocpq_ctx  # type: ignore[attr-defined]
    result = ctx.execute(sql, eager=True)
    return list(result.iter_rows())


registry.register_impl("ocpq", "polars", sys.modules[__name__])
