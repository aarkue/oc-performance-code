"""Plot ocpm-bench JSONL results.

The figure shows grouped bars for each query instance and a trailing
summary boxplot with all warm samples pooled per model.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

_PALETTE: dict[str, str] = {
    "linked_ocel": "#0077bb",
    "duckdb": "#ee7733",
    "duckdb_strong_rels": "#aa4499",
    "kuzu": "#009988",
    "kuzu_weak": "#117733",
    "sqlite_mem": "#cc3311",
    "sqlite_mem_strong_rels": "#882255",
    "polars": "#ee3377",
    "pandas": "#33bbee",
}
_DISPLAY_NAME = {
    "linked_ocel": "LinkedOCEL",
    "duckdb": "DuckDB",
    "duckdb_strong_rels": "DuckDB strong rels",
    "kuzu": "Kuzu",
    "kuzu_weak": "Kuzu weak",
    "sqlite_mem": "SQLite mem",
    "sqlite_mem_strong_rels": "SQLite mem strong rels",
    "polars": "Polars",
    "pandas": "pandas",
}
_SERIF = "Latin Modern Roman, Computer Modern, Times New Roman, Times, serif"
_DEFAULT_COLOR = "#999999"

_AGG = {
    "median": statistics.median,
    "mean": statistics.mean,
    "min": min,
    "max": max,
}


def _model_order(model: str) -> int:
    try:
        return list(_PALETTE).index(model)
    except ValueError:
        return 999


def _fmt_ms(value: float) -> str:
    if value >= 100:
        return f"{value:.0f}"
    if value >= 10:
        return f"{value:.1f}"
    return f"{value:.2f}"


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"




def load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def group_rows(
    rows: list[dict[str, Any]],
    *,
    allow_incorrect: bool,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        if row.get("correct") is not True and not allow_incorrect:
            raise ValueError(
                "incorrect benchmark cell in input: "
                f"{row.get('model')}/{row.get('pattern')}/{row.get('instance_id')}"
            )
        key = (row["pattern"], row["model"], row["instance_id"])
        cell = grouped.setdefault(
            key,
            {
                "warm_ms": [],
                "correct": True,
                "passes": set(),
                "rows": 0,
            },
        )
        cell["warm_ms"].extend(row.get("warm_ms") or [])
        cell["correct"] = cell["correct"] and row.get("correct") is True
        if row.get("matrix_pass") is not None:
            cell["passes"].add(row["matrix_pass"])
        cell["rows"] += 1
    return grouped


def _auto_log(rows: list[dict[str, Any]]) -> bool:
    values = [v for row in rows for v in (row.get("warm_ms") or []) if v > 0]
    return bool(values) and max(values) / min(values) > 100


def _add_pattern_subplot(
    fig: go.Figure,
    *,
    grouped: dict[tuple[str, str, str], dict[str, Any]],
    pattern: str,
    col: int,
    metric: str,
    log_y: bool,
    seen_legend: set[str],
) -> None:
    cells = {
        (model, instance): cell
        for (pat, model, instance), cell in grouped.items()
        if pat == pattern
    }
    models = sorted({model for model, _ in cells}, key=_model_order)
    instances = sorted({instance for _, instance in cells})
    agg = _AGG[metric]

    for model in models:
        color = _PALETTE.get(model, _DEFAULT_COLOR)
        x: list[str] = []
        y: list[float | None] = []
        err_low: list[float] = []
        err_high: list[float] = []
        labels: list[str] = []
        hatch: list[str] = []

        for instance in instances:
            cell = cells.get((model, instance))
            x.append(instance)
            if not cell or not cell["warm_ms"]:
                y.append(None)
                err_low.append(0)
                err_high.append(0)
                labels.append("")
                hatch.append("")
                continue
            samples = cell["warm_ms"]
            value = agg(samples)
            y.append(value)
            err_low.append(max(0.0, value - min(samples)))
            err_high.append(max(0.0, max(samples) - value))
            labels.append(_fmt_ms(value))
            hatch.append("" if cell["correct"] else "x")

        show_legend = model not in seen_legend
        seen_legend.add(model)
        fig.add_trace(
            go.Bar(
                name=_DISPLAY_NAME.get(model, model),
                x=x,
                y=y,
                marker=dict(color=color, pattern=dict(shape=hatch), line=dict(width=0)),
                error_y=dict(
                    type="data",
                    symmetric=False,
                    array=err_high,
                    arrayminus=err_low,
                    width=0,
                    thickness=1.0,
                    color=_rgba(color, 0.40),
                ),
                text=labels,
                textposition="outside",
                textfont=dict(family=_SERIF, size=9, color="#444"),
                cliponaxis=False,
                legendgroup=model,
                offsetgroup=model,
                alignmentgroup=f"pattern-{col}",
                showlegend=show_legend,
            ),
            row=1,
            col=col,
        )

        pooled: list[float] = []
        for instance in instances:
            cell = cells.get((model, instance))
            if cell and cell["correct"]:
                pooled.extend(cell["warm_ms"])
        if pooled:
            pooled_top = max(pooled)
            fig.add_trace(
                go.Box(
                    name=_DISPLAY_NAME.get(model, model),
                    x=[metric] * len(pooled),
                    y=pooled,
                    boxpoints="all",
                    pointpos=0,
                    jitter=0.35,
                    marker=dict(color=color, size=4, opacity=0.55, line=dict(width=0)),
                    fillcolor=_rgba(color, 0.12),
                    line=dict(color=_rgba(color, 0.85), width=1),
                    whiskerwidth=0,
                    boxmean=True,
                    legendgroup=model,
                    offsetgroup=model,
                    alignmentgroup=f"pattern-{col}",
                    showlegend=False,
                ),
                row=1,
                col=col,
            )
            pooled_value = agg(pooled)
            fig.add_trace(
                go.Bar(
                    name=_DISPLAY_NAME.get(model, model),
                    x=[metric],
                    y=[pooled_top],
                    marker=dict(color="rgba(0,0,0,0)", line=dict(width=0)),
                    text=[_fmt_ms(pooled_value)],
                    textposition="outside",
                    textfont=dict(family=_SERIF, size=9, color=color, weight="bold"),
                    cliponaxis=False,
                    hoverinfo="skip",
                    legendgroup=model,
                    offsetgroup=model,
                    alignmentgroup=f"pattern-{col}",
                    showlegend=False,
                ),
                row=1,
                col=col,
            )

    categories = [instance for instance in instances] + [metric]
    fig.update_xaxes(
        type="category",
        categoryorder="array",
        categoryarray=categories,
        tickfont=dict(size=10, family=_SERIF),
        showline=True,
        linecolor="#bbb",
        linewidth=1,
        ticks="outside",
        tickcolor="#bbb",
        ticklen=3,
        showgrid=False,
        row=1,
        col=col,
    )

    y_axis: dict[str, Any] = {
        "tickfont": dict(size=10, family=_SERIF),
        "showgrid": True,
        "gridcolor": "rgba(0,0,0,0.06)",
        "gridwidth": 1,
        "zeroline": False,
        "showline": True,
        "linecolor": "#bbb",
        "linewidth": 1,
        "ticks": "outside",
        "tickcolor": "#bbb",
        "ticklen": 3,
    }
    if log_y:
        y_axis["type"] = "log"
    if col == 1:
        y_axis["title"] = dict(text=f"warm time, ms ({metric})", font=dict(size=12))
    fig.update_yaxes(**y_axis, row=1, col=col)

    if instances:
        xref = "x" if col == 1 else f"x{col}"
        yref = "y" if col == 1 else f"y{col}"
        fig.add_shape(
            type="line",
            xref=xref,
            yref=f"{yref} domain",
            x0=len(instances) - 0.5,
            x1=len(instances) - 0.5,
            y0=0,
            y1=1,
            line=dict(color="rgba(0,0,0,0.12)", width=1, dash="dot"),
            layer="below",
        )


def build_figure(
    rows: list[dict[str, Any]],
    *,
    metric: str,
    log_y: bool,
    title: str,
    allow_incorrect: bool,
) -> go.Figure:
    grouped = group_rows(rows, allow_incorrect=allow_incorrect)
    patterns = sorted({key[0] for key in grouped})
    fig = make_subplots(
        rows=1,
        cols=len(patterns),
        subplot_titles=[p.upper() for p in patterns],
        horizontal_spacing=0.06 if len(patterns) > 1 else 0.02,
    )

    seen_legend: set[str] = set()
    for col, pattern in enumerate(patterns, start=1):
        _add_pattern_subplot(
            fig,
            grouped=grouped,
            pattern=pattern,
            col=col,
            metric=metric,
            log_y=log_y,
            seen_legend=seen_legend,
        )

    rep_counts = sorted({len(row.get("warm_ms") or []) for row in rows})
    pass_counts = sorted({row.get("matrix_pass") for row in rows if row.get("matrix_pass")})
    n_passes = max(pass_counts) if pass_counts else 1
    rep_label = (
        f"{rep_counts[0]} warm reps x {n_passes} pass{'es' if n_passes != 1 else ''}"
        if len(rep_counts) == 1
        else f"{min(rep_counts)}-{max(rep_counts)} warm reps x {n_passes} passes"
    )
    scale_label = " log scale" if log_y else ""
    fig.update_layout(
        title=dict(
            text=f"{title}<br><span style='font-size:11px;color:#666'>{rep_label}{scale_label}</span>",
            x=0.5,
            xanchor="center",
            y=0.97,
            font=dict(family=_SERIF, size=15, color="#1a1a1a"),
        ),
        barmode="group",
        boxmode="group",
        bargap=0.22,
        bargroupgap=0.06,
        boxgap=0.22,
        boxgroupgap=0.10,
        font=dict(family=_SERIF, size=12, color="#1a1a1a"),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(255,255,255,0)",
            font=dict(size=11, family=_SERIF),
        ),
        margin=dict(l=66, r=18, t=112, b=50),
    )
    title_texts = {p.upper() for p in patterns}
    for ann in fig.layout.annotations:
        if ann.text in title_texts:
            ann.font = dict(family=_SERIF, size=12, color="#444")
    return fig


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--metric", choices=list(_AGG), default="mean")
    parser.add_argument("--log", dest="log_y", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    parser.add_argument("--allow-incorrect", action="store_true")
    parser.add_argument("--title", default=None)
    parser.add_argument("--width", type=int, default=900)
    parser.add_argument("--height", type=int, default=460)
    parser.add_argument("--scale", type=int, default=2)
    args = parser.parse_args(argv)

    if not args.jsonl.is_file():
        print(f"error: {args.jsonl} not found", file=sys.stderr)
        return 2
    rows = load_rows(args.jsonl)
    if not rows:
        print(f"error: {args.jsonl} is empty", file=sys.stderr)
        return 2

    log_y = args.log_y or (not args.no_log and _auto_log(rows))
    dataset = str(rows[0].get("dataset", "?")).upper()
    patterns = sorted({row.get("pattern", "?") for row in rows})
    if args.title:
        title = args.title
    elif len(patterns) == 1:
        title = f"{patterns[0].upper()} on {dataset}: warm {args.metric}"
    else:
        title = f"OCPM benchmark on {dataset}: warm {args.metric}"

    fig = build_figure(
        rows,
        metric=args.metric,
        log_y=log_y,
        title=title,
        allow_incorrect=args.allow_incorrect,
    )
    width = args.width if args.width != 900 else max(900, 500 * len(patterns))
    out_png = args.jsonl.with_suffix(".png")
    out_pdf = args.jsonl.with_suffix(".pdf")
    fig.write_image(out_png, width=width, height=args.height, scale=args.scale)
    fig.write_image(out_pdf, width=width, height=args.height, format="pdf")
    print(f"wrote {out_png}")
    print(f"wrote {out_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
