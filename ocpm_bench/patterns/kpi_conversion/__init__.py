"""P4 / K2: conversion rate of source objects whose linked target objects reach a given activity.

Fraction of source objects (type ``SOURCE_TYPE``) that have at least one
O2O-linked target object (type ``TARGET_TYPE``) with at least one event of
``ACTIVITY`` in its E2O list. Exercises O2O + E2O traversal -- the OC
funnel / conversion KPI. Output: float in [0, 1].

Default: fraction of Applications whose linked Offer was accepted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OutputSchema, PatternContract

ACTIVITY = "O_Accepted"
SOURCE_TYPE = "Application"
TARGET_TYPE = "Offer"


@dataclass(frozen=True)
class KPIConversionInputs:
    activity: str = ACTIVITY
    source_type: str = SOURCE_TYPE
    target_type: str = TARGET_TYPE


_OUTPUT = OutputSchema(kind="scalar", scalar_type=float)


def _instances(_dataset) -> list[tuple[str, Any]]:
    return [("K2", KPIConversionInputs())]


CONTRACT = PatternContract(
    name="kpi_conversion",
    output=_OUTPUT,
    instances=_instances,
)

registry.register_pattern(CONTRACT)
