"""Subprocess entry for one matrix cell.

Run as: `python -m ocpm_bench.run_one --model X --pattern Y ...`
"""

from __future__ import annotations

from pathlib import Path

import click

import ocpm_bench.registrations
from ocpm_bench.harness.results import write_jsonl
from ocpm_bench.harness.runner import run_cell


@click.command()
@click.option("--model", required=True)
@click.option("--pattern", required=True)
@click.option("--dataset", required=True)
@click.option("--repetitions", default=10, type=int)
@click.option("--matrix-pass", default=1, type=int)
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), required=True)
@click.option("--allow-incorrect", is_flag=True)
def main(model, pattern, dataset, repetitions, matrix_pass, out, allow_incorrect):
    rows = run_cell(
        model=model, pattern=pattern, dataset=dataset,
        repetitions=repetitions, matrix_pass=matrix_pass,
        strict_correctness=not allow_incorrect,
    )
    write_jsonl(out, rows)


if __name__ == "__main__":
    main()
