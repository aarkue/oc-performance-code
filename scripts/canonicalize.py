"""Canonicalize an OCEL file so every event has a unique timestamp.

Tied timestamps are disambiguated by sorting on `ocel:eid` ascending and
bumping the later events by `rank * 1us`. Downstream models can then
sort by `ocel:timestamp` alone.

Usage:

    python scripts/canonicalize.py INPUT.json OUTPUT.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl
import r4pm


def canonicalize_events_df(events: pl.DataFrame) -> pl.DataFrame:
    """Return events with unique per-log `ocel:timestamp` values."""
    sorted_df = events.sort(["ocel:timestamp", "ocel:eid"])
    ranks: list[int] = []
    prev_ts = None
    rank = 0
    for ts in sorted_df["ocel:timestamp"]:
        if ts == prev_ts:
            rank += 1
        else:
            rank = 0
            prev_ts = ts
        ranks.append(rank)
    with_rank = sorted_df.with_columns(pl.Series("_rank", ranks, dtype=pl.Int64))
    return (
        with_rank
        .with_columns(
            (pl.col("ocel:timestamp") + pl.duration(microseconds=pl.col("_rank")))
            .alias("ocel:timestamp")
        )
        .drop("_rank")
    )


def canonicalize_ocel_file(src_path: Path, dst_path: Path) -> None:
    """Load src OCEL, canonicalize timestamps, export to dst."""
    src_id = r4pm.import_item("OCEL", str(src_path))
    try:
        dfs = r4pm.item_to_df(src_id)
        events = canonicalize_events_df(dfs["events"])

        # Propagate the new per-event timestamps into relations (which
        # carries its own ocel:timestamp column mirroring events).
        ts_map = events.select(["ocel:eid", "ocel:timestamp"])
        relations = (
            dfs["relations"]
            .drop("ocel:timestamp")
            .join(ts_map, on="ocel:eid", how="left")
            .select([
                "ocel:eid", "ocel:activity", "ocel:timestamp",
                "ocel:oid", "ocel:type", "ocel:qualifier",
            ])
        )

        new_id = r4pm.import_item_from_df("OCEL", {
            "events": events,
            "objects": dfs["objects"],
            "relations": relations,
            "o2o": dfs["o2o"],
            "object_changes": dfs["object_changes"],
        })
        try:
            r4pm.export_item(new_id, str(dst_path))
        finally:
            r4pm.remove_item(new_id)
    finally:
        r4pm.remove_item(src_id)


def _main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("src", type=Path, help="source OCEL file (JSON/XML/SQLite)")
    p.add_argument("dst", type=Path, help="canonical OCEL output")
    args = p.parse_args()
    canonicalize_ocel_file(args.src, args.dst)
    print(f"canonicalized {args.src} -> {args.dst} ({args.dst.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
