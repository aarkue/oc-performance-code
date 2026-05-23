"""Run one benchmark cell."""

from __future__ import annotations

import os
import time
from pathlib import Path

from ocpm_bench.harness import registry
from ocpm_bench.harness.results import ResultRow
from ocpm_bench.patterns.base import canonicalize


def _ms_since(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000.0


def _format_diff(got, want, schema, limit: int = 10) -> str:
    if schema.kind == "tuple_set":
        only_got = sorted(got - want, key=lambda r: tuple(map(str, r)))[:limit]
        only_want = sorted(want - got, key=lambda r: tuple(map(str, r)))[:limit]
        lines = [f"  size: got={len(got)} want={len(want)}"]
        lines.append(
            f"  only in got ({len(got - want)} rows, first {len(only_got)}):"
        )
        lines.extend(f"    {r!r}" for r in only_got)
        lines.append(
            f"  only in want ({len(want - got)} rows, first {len(only_want)}):"
        )
        lines.extend(f"    {r!r}" for r in only_want)
        return "\n".join(lines)
    if schema.kind == "tuple_list_ordered":
        for i, (a, b) in enumerate(zip(got, want)):  # noqa: B905
            if a != b:
                return (
                    f"  length: got={len(got)} want={len(want)}; first "
                    f"mismatch at index {i}: got={a!r} want={b!r}"
                )
        if len(got) != len(want):
            return f"  length differs: got={len(got)} want={len(want)} (prefix matches)"
        return "  (canonical equal yet correct=False; investigate canonicalize)"
    return f"  got={got!r} want={want!r}"


def _rss_bytes() -> int | None:
    statm = Path("/proc/self/statm")
    if not statm.exists():
        return None
    try:
        pages = int(statm.read_text().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, IndexError, ValueError):
        return None


def run_cell(
    *,
    model: str,
    pattern: str,
    dataset: str,
    repetitions: int = 10,
    matrix_pass: int = 1,
    strict_correctness: bool = True,
) -> list[ResultRow]:
    """Execute every query instance for one cell; return one ResultRow per instance."""
    spec = registry.resolve(model=model, pattern=pattern, dataset=dataset)

    model_obj = spec.model_cls()
    ds_obj = spec.dataset_cls()
    ds_obj.fetch()

    model_obj.setup(ds_obj)
    model_bytes = model_obj.size_on_disk()
    rss = _rss_bytes()
    lib_versions = model_obj.library_versions()
    model_obj.reset_caches()
    pre_run = getattr(spec.impl, "pre_run", None)
    if pre_run is not None:
        pre_run(model_obj)

    is_oracle = (model == spec.pattern.oracle_model)
    oracle_obj = None
    oracle_impl = None
    if not is_oracle:
        oracle_cls = registry.MODELS[spec.pattern.oracle_model]
        oracle_impl = registry.IMPLS[(pattern, spec.pattern.oracle_model)]
        oracle_obj = oracle_cls()
        oracle_obj.setup(ds_obj)

    rows: list[ResultRow] = []
    try:
        for instance_id, inputs in spec.pattern.instances(ds_obj):
            t0 = time.perf_counter()
            raw = spec.impl.run(model_obj, inputs)
            cold_ms = _ms_since(t0)

            warm: list[float] = []
            for _ in range(repetitions):
                t0 = time.perf_counter()
                spec.impl.run(model_obj, inputs)
                warm.append(_ms_since(t0))

            if spec.pattern.post_process is not None:
                raw = spec.pattern.post_process(raw, inputs, model_obj)
            canonical = canonicalize(raw, spec.pattern.output)
            if is_oracle:
                correct = True
            else:
                assert oracle_obj is not None and oracle_impl is not None
                raw_o = oracle_impl.run(oracle_obj, inputs)
                if spec.pattern.post_process is not None:
                    raw_o = spec.pattern.post_process(raw_o, inputs, oracle_obj)
                oracle_val = canonicalize(raw_o, spec.pattern.output)
                correct = (canonical == oracle_val)
                if strict_correctness and not correct:
                    diff = _format_diff(canonical, oracle_val, spec.pattern.output)
                    raise AssertionError(
                        f"incorrect result for {model}/{pattern}/{instance_id}/{dataset} "
                        f"against oracle {spec.pattern.oracle_model}\n{diff}"
                    )

            rows.append(ResultRow.from_observations(
                model=model, pattern=pattern,
                instance_id=instance_id, dataset=dataset,
                warm_ms=warm, cold_ms=cold_ms,
                model_bytes=model_bytes,
                rss_bytes_after_setup=rss,
                correct=correct, lib_versions=lib_versions,
                matrix_pass=matrix_pass,
                oracle_model=spec.pattern.oracle_model,
            ))
    finally:
        if oracle_obj is not None:
            oracle_obj.teardown()
        model_obj.teardown()
    return rows
