"""ocpm-bench CLI: single-cell `run`, multi-cell `matrix`, and cache helpers."""

from __future__ import annotations

import random
import subprocess
import sys
import time
from pathlib import Path

import click
import yaml

import ocpm_bench.registrations  # populates the harness registry
from ocpm_bench.harness import registry
from ocpm_bench.harness.results import write_jsonl
from ocpm_bench.harness.runner import run_cell


@click.group()
def main() -> None:
    """ocpm-bench: benchmark harness for object-centric data-access patterns."""


def _prepare_pairs(cells: list[dict]) -> None:
    """Untimed model.setup() once per unique (model, dataset) pair."""
    seen: set[tuple[str, str]] = set()
    pairs: list[tuple[str, str]] = []
    for c in cells:
        key = (c["model"], c["dataset"])
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)

    for i, (model, dataset) in enumerate(pairs, 1):
        if model not in registry.MODELS:
            click.echo(f"[prepare {i}/{len(pairs)}] skip: unknown model {model!r}", err=True)
            continue
        if dataset not in registry.DATASETS:
            click.echo(f"[prepare {i}/{len(pairs)}] skip: unknown dataset {dataset!r}", err=True)
            continue
        click.echo(f"[prepare {i}/{len(pairs)}] {model}/{dataset} ...", err=True)
        t0 = time.perf_counter()
        model_obj = registry.MODELS[model]()
        ds_obj = registry.DATASETS[dataset]()
        ds_obj.fetch()
        try:
            model_obj.setup(ds_obj)
        finally:
            model_obj.teardown()
        click.echo(
            f"[prepare {i}/{len(pairs)}] {model}/{dataset} ok in "
            f"{time.perf_counter() - t0:.1f}s",
            err=True,
        )


@main.command()
@click.option("--spec", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
def prepare(spec: Path) -> None:
    """Untimed setup for every (model, dataset) pair in SPEC."""
    cfg = yaml.safe_load(spec.read_text())
    _prepare_pairs(list(cfg["cells"]))


@main.command()
@click.option("--model", required=True)
@click.option("--pattern", required=True)
@click.option("--dataset", required=True)
@click.option("--repetitions", default=10, type=int)
@click.option("--allow-incorrect", is_flag=True, help="Record incorrect cells instead of failing.")
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path),
              default=Path("results") / "runs.jsonl",
              show_default=True)
def run(
    model: str,
    pattern: str,
    dataset: str,
    repetitions: int,
    allow_incorrect: bool,
    out: Path,
) -> None:
    """Run one cell in-process and append JSONL rows to OUT."""
    rows = run_cell(
        model=model, pattern=pattern, dataset=dataset,
        repetitions=repetitions,
        strict_correctness=not allow_incorrect,
    )
    write_jsonl(out, rows)
    click.echo(f"wrote {len(rows)} rows -> {out}")


@main.command()
@click.option("--spec", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--prepare", "do_prepare", is_flag=True,
              help="Run untimed prepare phase (model.setup) for each (model, dataset) pair before measuring.")
def matrix(spec: Path, do_prepare: bool) -> None:
    """Run every cell in SPEC, one subprocess per cell, in randomized order."""
    cfg = yaml.safe_load(spec.read_text())
    if do_prepare:
        _prepare_pairs(list(cfg["cells"]))
    out_path = Path(cfg["results_path"])
    repetitions = int(cfg.get("repetitions", 10))
    passes = int(cfg.get("matrix_passes", 2))
    randomize = bool(cfg.get("randomize_cell_order", True))
    cells = list(cfg["cells"])
    default_timeout = cfg.get("cell_timeout_seconds")
    default_timeout = float(default_timeout) if default_timeout is not None else None
    allow_incorrect = bool(cfg.get("allow_incorrect", False))

    if out_path.exists():
        out_path.unlink()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total_cells = passes * len(cells)
    done = 0
    failed: list[tuple[int, str, int]] = []
    overall_t0 = time.perf_counter()
    for p in range(1, passes + 1):
        order = list(cells)
        if randomize:
            # Per-pass deterministic seed so each pass shuffles distinctly
            # but reproducibly.
            rng = random.Random(p)
            rng.shuffle(order)
        for c in order:
            done += 1
            label = f"{c['model']}/{c['pattern']}/{c['dataset']}"
            elapsed_so_far = time.perf_counter() - overall_t0
            click.echo(
                f"[pass {p}/{passes}][{done}/{total_cells}] {label} "
                f"(elapsed {elapsed_so_far:.0f}s) ...",
                err=True,
            )
            cell_t0 = time.perf_counter()
            argv = [
                sys.executable, "-m", "ocpm_bench.run_one",
                "--model", c["model"],
                "--pattern", c["pattern"],
                "--dataset", c["dataset"],
                "--repetitions", str(repetitions),
                "--matrix-pass", str(p),
                "--out", str(out_path),
            ]
            if allow_incorrect:
                argv.append("--allow-incorrect")
            cell_timeout = c.get("timeout_seconds", default_timeout)
            cell_timeout = float(cell_timeout) if cell_timeout is not None else None
            timed_out = False
            try:
                result = subprocess.run(
                    argv, check=False, timeout=cell_timeout,
                )
            except subprocess.TimeoutExpired:
                timed_out = True
                result = None
            cell_secs = time.perf_counter() - cell_t0
            if timed_out:
                failed.append((p, label, -1))
                click.echo(
                    f"  [timeout] {label} after {cell_secs:.1f}s "
                    f"(limit {cell_timeout}s)",
                    err=True,
                )
            elif result is not None and result.returncode == 0:
                click.echo(f"  [ok] {label} done in {cell_secs:.1f}s", err=True)
            else:
                rc = -2 if result is None else result.returncode
                failed.append((p, label, rc))
                click.echo(
                    f"  [fail] {label} (exit={rc}) after {cell_secs:.1f}s",
                    err=True,
                )
    click.echo(
        f"matrix done -> {out_path} ({time.perf_counter() - overall_t0:.0f}s total)",
        err=True,
    )
    if failed:
        click.echo(f"{len(failed)} cell(s) failed:", err=True)
        for p, label, rc in failed:
            click.echo(f"  pass {p}: {label} (exit={rc})", err=True)
        sys.exit(1)

@main.group()
def cache() -> None:
    """Inspect or clean cached model exports under code/cache/."""


@cache.command(name="list")
def cache_list() -> None:
    """List all cached model exports."""
    from ocpm_bench.harness import cache as _cache
    rows = _cache.list_entries()
    if not rows:
        click.echo("(empty)")
        return
    for r in rows:
        raw_size = r.get("size_bytes")
        size_bytes = int(raw_size) if isinstance(raw_size, (int, float)) else 0
        size_mb = size_bytes / (1024 * 1024)
        click.echo(
            f"{r['dataset']}/{r['model']}  "
            f"{size_mb:>8.1f} MiB  {r['payload']}  (source={r['source']})"
        )


@cache.command(name="clean")
@click.option("--dataset", default=None, help="Limit to a single dataset.")
@click.option("--model", default=None, help="Limit to a single model (requires --dataset).")
def cache_clean(dataset: str | None, model: str | None) -> None:
    """Remove cached model exports; the next run will regenerate them."""
    from ocpm_bench.harness import cache as _cache
    n = _cache.invalidate(dataset=dataset, model=model)
    click.echo(f"removed {n} cached entries")


if __name__ == "__main__":
    main()
