"""Registry for models, datasets, patterns, and pattern implementations.

Modules self-register on import; see `ocpm_bench.registrations`.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType

from ocpm_bench.patterns.base import PatternContract

MODELS: dict[str, type] = {}
DATASETS: dict[str, type] = {}
PATTERNS: dict[str, PatternContract] = {}
IMPLS: dict[tuple[str, str], ModuleType] = {}


@dataclass(frozen=True)
class CellSpec:
    """One benchmark cell: (model, pattern, dataset)."""

    model_cls: type
    dataset_cls: type
    pattern: PatternContract
    impl: ModuleType


def register_model(name: str, cls: type) -> None:
    if name in MODELS:
        raise ValueError(f"model {name!r} already registered")
    MODELS[name] = cls


def register_dataset(name: str, cls: type) -> None:
    if name in DATASETS:
        raise ValueError(f"dataset {name!r} already registered")
    DATASETS[name] = cls


def register_pattern(contract: PatternContract) -> None:
    if contract.name in PATTERNS:
        raise ValueError(f"pattern {contract.name!r} already registered")
    PATTERNS[contract.name] = contract


def register_impl(pattern: str, model: str, module: ModuleType) -> None:
    key = (pattern, model)
    if key in IMPLS:
        raise ValueError(f"impl {pattern}/{model} already registered")
    IMPLS[key] = module


def resolve(model: str, pattern: str, dataset: str) -> CellSpec:
    if model not in MODELS:
        raise KeyError(f"unknown model: {model!r}")
    if pattern not in PATTERNS:
        raise KeyError(f"unknown pattern: {pattern!r}")
    if dataset not in DATASETS:
        raise KeyError(f"unknown dataset: {dataset!r}")
    key = (pattern, model)
    if key not in IMPLS:
        raise KeyError(f"no impl registered for ({pattern}, {model})")
    return CellSpec(
        model_cls=MODELS[model],
        dataset_cls=DATASETS[dataset],
        pattern=PATTERNS[pattern],
        impl=IMPLS[key],
    )
