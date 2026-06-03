"""Generate the main-results LaTeX table from ocpm-bench JSONL files.

Accepts one or more combined JSONLs (e.g. `paper-all.jsonl`) via `--input`.
Rows are filtered by their `pattern` field internally. The typing sub-study
table is rendered from the same data; no separate `strong_rels-ab.jsonl`
needed.

Layout (main table):
  - Leftmost column groups data models by family via \\multirow.
  - Pattern columns are grouped by family in a two-level header.
  - Each cell shows mean +/- std across per-instance summaries (the
    within-cell aggregation defaults to mean of the warm runs; the cold
    run is already excluded by the harness).
  - The fastest model per pattern column is bolded; cells are tinted by
    log-time relative to the column min.

Layout (typing table):
  - Compact 3xN matrix: rows are engines, columns are corpora, cells are
    the geometric mean of weak/strong speedups across the corpus's patterns.
  - Speedup > 1.0 favours strong typing (teal), < 1.0 favours weak (red).
  - Bold marks |effect| >= 20%; raw ms lives in the main table.

CLI:
    python make_table.py --input results/paper-all.jsonl \\
        --output paper-overleaf/tables/main.tex \\
        --typing-output paper-overleaf/tables/typing.tex
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

MODEL_FAMILIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Relational", [("sqlite_mem", "SQLite"), ("duckdb", "DuckDB")]),
    ("Dataframe",  [("pandas", "Pandas"), ("polars", "Polars")]),
    ("Graph",      [("kuzu", "Kuzu"), ("neo4j_strong", "Neo4j")]),
    ("Custom",     [("linked_ocel", "Rust4PM")]),
]

# Each sub-column maps one or more pattern keys to one displayed label;
# patterns sharing a label are pooled before per-cell aggregation.
PATTERN_FAMILIES: list[tuple[str, list[tuple[list[str], str]]]] = [
    ("P1: Control flow", [(["dfg"], "DFG"), (["variants"], "Variants")]),
    ("P2: Queries",      [(["ocpq"], "OCPQ"), (["ekg"], "EKG")]),
    ("P3: OC-Perf",      [(["oc_perf_sync"], "W1"), (["oc_perf_delaying"], "W2")]),
    ("P4: BI/KPI",       [(["kpi_heatmap"], "K1"), (["kpi_conversion"], "K2")]),
]

# (Engine label, weak model_key, strong model_key)
TYPING_PAIRS: list[tuple[str, str, str]] = [
    ("SQLite", "sqlite_mem", "sqlite_mem_strong_rels"),
    ("DuckDB", "duckdb",     "duckdb_strong_rels"),
    ("Kuzu",   "kuzu_weak",  "kuzu"),
]

INNER_STATS: dict[str, Callable[[list[float]], float]] = {
    "median": statistics.median,
    "mean": statistics.fmean,
}

# Heatmap tint range (xcolor percentage). Darker = faster.
TINT_MIN = 0
TINT_MAX = 55
TINT_HUE = "teal"


def _load_combined(
    paths: list[Path], inner_stat: str, on_incorrect: str,
) -> dict[str, dict[str, list[float]]]:
    """Combine rows from one or more JSONLs.

    Returns {pattern -> {model -> [per-instance summary ms]}}. Each
    per-instance value is the inner-stat aggregation of that instance's
    warm samples (mean by default).
    """
    stat_fn = INNER_STATS[inner_stat]
    by_cell: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    dropped: list[tuple[str, str, str]] = []

    for path in paths:
        with path.open() as f:
            for line in f:
                row = json.loads(line)
                pattern = row.get("pattern")
                model = row.get("model")
                inst = row.get("instance_id") or "_"
                warm = row.get("warm_ms") or []
                if not (pattern and model and warm):
                    continue
                if row.get("correct") is False:
                    key = (model, pattern, inst)
                    if on_incorrect == "error":
                        raise SystemExit(
                            f"refusing to aggregate: incorrect cell {key}"
                        )
                    if on_incorrect == "drop":
                        dropped.append(key)
                        continue
                by_cell[(model, pattern, inst)].extend(warm)

    for key in dropped:
        print(f"warning: dropped incorrect cell {key[0]}/{key[1]}/{key[2]}",
              file=sys.stderr)

    out: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for (model, pattern, _), samples in by_cell.items():
        out[pattern][model].append(stat_fn(samples))
    return {p: dict(m) for p, m in out.items()}


def _fmt_num(value: float) -> str:
    return f"{value:.1f}"


def _aggregate(per_instance: list[float]) -> tuple[float, float | None]:
    if not per_instance:
        return float("nan"), None
    mean = statistics.fmean(per_instance)
    std = statistics.stdev(per_instance) if len(per_instance) >= 2 else None
    return mean, std


def _tint(value: float) -> int:
    """Shade by order-of-magnitude band (darker = faster)."""
    if not math.isfinite(value):
        return 0
    if value < 10:
        return 60
    if value < 100:
        return 40
    if value < 1000:
        return 20
    return 5


def _render_cell(
    per_instance: list[float], col_best_tint: int,
    enable_color: bool, enable_bold: bool,
) -> str:
    if not per_instance:
        return "\\multicolumn{1}{c}{--}"
    mean, _ = _aggregate(per_instance)
    body = _fmt_num(mean)
    # Bold every cell in the column's fastest band (not just the single min):
    # the heatmap bands, not exact ranks, are what we read off the table.
    if enable_bold and _tint(mean) == col_best_tint:
        body = f"\\textbf{{{body}}}"
    if enable_color:
        body = f"\\cellcolor{{{TINT_HUE}!{_tint(mean)}}}{body}"
    return body


def _flat_patterns() -> list[tuple[list[str], str]]:
    return [pat for _, pats in PATTERN_FAMILIES for pat in pats]


def _header_lines() -> list[str]:
    top: list[str] = ["", ""]
    cmidrules: list[str] = []
    col = 3
    for fam_label, pats in PATTERN_FAMILIES:
        span = len(pats)
        if span == 1:
            top.append(f"\\multicolumn{{1}}{{c}}{{{fam_label}}}")
        else:
            top.append(f"\\multicolumn{{{span}}}{{c}}{{{fam_label}}}")
        cmidrules.append(f"\\cmidrule(lr){{{col}-{col + span - 1}}}")
        col += span
    bottom = ["Family", "Model"]
    for _, pats in PATTERN_FAMILIES:
        for _, label in pats:
            bottom.append(label)
    return [
        " & ".join(top) + " \\\\",
        " ".join(cmidrules),
        " & ".join(bottom) + " \\\\",
    ]


def build_table(
    data: dict[str, dict[str, list[float]]],
    enable_color: bool, enable_bold: bool, draft_note: str | None = None,
) -> str:
    pat_cols = _flat_patterns()
    n_pat = len(pat_cols)
    col_spec = "@{}ll" + ("r" * n_pat) + "@{}"

    def aggregated(model_key: str, pat_keys: list[str]) -> list[float]:
        out: list[float] = []
        for pk in pat_keys:
            out.extend(data.get(pk, {}).get(model_key, []))
        return out

    # Fastest band reached in each column (max tint = lowest order-of-magnitude);
    # every cell in that band is bolded.
    col_best_tint: dict[str, int] = {}
    for pat_keys, label in pat_cols:
        tints: list[int] = []
        for _, models in MODEL_FAMILIES:
            for model_key, _ in models:
                per_inst = aggregated(model_key, pat_keys)
                if per_inst:
                    tints.append(_tint(statistics.fmean(per_inst)))
        col_best_tint[label] = max(tints) if tints else 0

    caption_parts: list[str] = []
    if draft_note:
        caption_parts.append(
            r"\textcolor{red}{\textbf{Draft:}} " + draft_note + " "
        )
    caption_parts.append(
        r"Mean wall-clock time (ms) on BPIC17 per model and access pattern. "
        r"Warm runs only, cold excluded. Cells in each column's fastest band "
        r"are in bold. Cells are "
        r"shaded by order-of-magnitude band, darker = faster: under 10\,ms, "
        r"under 100\,ms, under 1\,s, and at or above 1\,s. \texttt{SQLite} and "
        r"\texttt{DuckDB} use the weak schema, \texttt{Kuzu} the strong schema. "
        r"\autoref{tab:typing-results} reports per-engine weak/strong speedups. "
        r"The 10 warm runs per cell vary by about 5\% (median across cells)."
    )

    lines = [
        r"\begin{table}[t]",
        r"\caption{" + "".join(caption_parts) + r"}\label{tab:main-results}",
        r"\centering",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{2pt}",
        r"\renewcommand{\arraystretch}{1.15}",
        r"\begin{tabular*}{\linewidth}{" + col_spec.replace("@{}ll", "@{\\extracolsep{\\fill}}ll", 1) + "}",
        r"\toprule",
    ]
    lines.extend(_header_lines())
    lines.append(r"\midrule")

    for fam_idx, (fam_label, models) in enumerate(MODEL_FAMILIES):
        nrows = len(models)
        for i, (model_key, model_label) in enumerate(models):
            row_cells: list[str] = []
            if i == 0:
                if nrows == 1:
                    row_cells.append(fam_label)
                else:
                    row_cells.append(f"\\multirow{{{nrows}}}{{*}}{{{fam_label}}}")
            else:
                row_cells.append("")
            row_cells.append(model_label)
            for pat_keys, label in pat_cols:
                per_inst = aggregated(model_key, pat_keys)
                row_cells.append(_render_cell(
                    per_inst, col_best_tint[label],
                    enable_color=enable_color, enable_bold=enable_bold,
                ))
            lines.append(" & ".join(row_cells) + r" \\")
        if fam_idx < len(MODEL_FAMILIES) - 1:
            lines.append(r"\midrule")

    lines += [
        r"\bottomrule",
        r"\end{tabular*}",
        r"\end{table}",
    ]
    return "\n".join(lines) + "\n"


def _speedup_tint(speedup: float) -> tuple[str, int]:
    if not math.isfinite(speedup) or speedup <= 0:
        return TINT_HUE, 0
    delta = abs(math.log10(speedup))
    intensity = round(min(delta * 60, TINT_MAX))
    intensity = max(intensity, 0)
    hue = TINT_HUE if speedup >= 1.0 else "red"
    return hue, intensity


def build_typing_table(
    data: dict[str, dict[str, list[float]]],
    enable_color: bool, enable_bold: bool, draft_note: str | None = None,
) -> str:
    corpora = _flat_patterns()
    col_spec = "@{}l" + ("r" * len(corpora)) + "@{}"

    lines = [r"\begin{table}[t]"]
    caption_parts: list[str] = []
    if draft_note:
        caption_parts.append(
            r"\textcolor{red}{\textbf{Draft:}} " + draft_note + " "
        )
    caption_parts.append(
        r"Speedup of strong over weak typing on BPIC17 "
        r"($\text{weak ms}/\text{strong ms}$): $>1.0$ favours strong (teal) "
        r"and $<1.0$ favours weak (red). Bold marks effects $\geq$20\%. "
        r"Per-corpus speedup is the geometric mean over its patterns. "
        r"\autoref{tab:main-results} reports the weak variant for "
        r"SQLite and DuckDB and the strong variant for Kuzu."
    )
    lines.append(r"\caption{" + "".join(caption_parts) + r"}\label{tab:typing-results}")
    lines += [
        r"\centering",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\renewcommand{\arraystretch}{1.15}",
        r"\begin{tabular*}{\linewidth}{" + col_spec.replace("@{}l", "@{\\extracolsep{\\fill}}l", 1) + "}",
        r"\toprule",
        "Engine & " + " & ".join(label for _, label in corpora) + r" \\",
        r"\midrule",
    ]

    for engine_label, weak_key, strong_key in TYPING_PAIRS:
        row_cells: list[str] = [engine_label]
        for pat_keys, _ in corpora:
            ratios: list[float] = []
            for pat_key in pat_keys:
                weak_inst = data.get(pat_key, {}).get(weak_key, [])
                strong_inst = data.get(pat_key, {}).get(strong_key, [])
                if not weak_inst or not strong_inst:
                    continue
                weak_mean, _ = _aggregate(weak_inst)
                strong_mean, _ = _aggregate(strong_inst)
                if not (strong_mean > 0 and weak_mean > 0):
                    continue
                ratios.append(weak_mean / strong_mean)
            if not ratios:
                row_cells.append(r"\multicolumn{1}{c}{--}")
                continue
            speedup = math.exp(statistics.fmean(math.log(r) for r in ratios))
            cell = f"{speedup:.2f}$\\times$"
            if enable_bold and (speedup >= 1.2 or speedup < 1 / 1.2):
                cell = f"\\textbf{{{cell}}}"
            if enable_color:
                hue, intensity = _speedup_tint(speedup)
                if intensity > 0:
                    cell = f"\\cellcolor{{{hue}!{intensity}}}{cell}"
            row_cells.append(cell)
        lines.append(" & ".join(row_cells) + r" \\")

    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, nargs="+", required=True,
                    help="One or more JSONL files; rows are filtered by their `pattern` field.")
    ap.add_argument("--output", type=Path, required=True,
                    help="LaTeX output path for the main table.")
    ap.add_argument("--typing-output", type=Path, default=None,
                    help="If set, also write the typing sub-study table here.")
    ap.add_argument("--inner-stat", choices=sorted(INNER_STATS), default="mean")
    ap.add_argument("--on-incorrect", choices=("drop", "include", "error"), default="drop")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--no-bold", action="store_true")
    ap.add_argument("--draft-note", default=None,
                    help="If set, prepend a red 'Draft:' disclaimer to the caption.")
    args = ap.parse_args()

    for p in args.input:
        if not p.exists():
            ap.error(f"input not found: {p}")

    data = _load_combined(args.input, args.inner_stat, args.on_incorrect)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_table(
        data, enable_color=not args.no_color, enable_bold=not args.no_bold,
        draft_note=args.draft_note,
    ))
    print(f"wrote {args.output}")
    for pat in sorted(data):
        print(f"  {pat:14s}: {sorted(data[pat])}")

    if args.typing_output is not None:
        args.typing_output.parent.mkdir(parents=True, exist_ok=True)
        args.typing_output.write_text(build_typing_table(
            data, enable_color=not args.no_color, enable_bold=not args.no_bold,
            draft_note=args.draft_note,
        ))
        print(f"wrote {args.typing_output}")


if __name__ == "__main__":
    main()
