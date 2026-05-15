"""Polars model: r4pm.df.import_ocel returns a dict of polars DataFrames.

The frames are cached on disk as parquet under
`code/cache/<dataset>/dataframes/`; pandas reuses the same cache.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import r4pm.df

from ocpm_bench.datasets.base import Dataset
from ocpm_bench.harness import cache as _cache
from ocpm_bench.harness import registry
from ocpm_bench.models._versions import package_version, python_version
from ocpm_bench.models.primitives import normalize_timestamp

# All frames returned by r4pm.df.import_ocel.
_FRAME_NAMES = ("events", "objects", "relations", "o2o", "object_changes")


def _export_frames(src: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = r4pm.df.import_ocel(str(src))
    for name in _FRAME_NAMES:
        if name in frames:
            frames[name].write_parquet(out_dir / f"{name}.parquet")


def cached_polars_frames(dataset: Dataset) -> dict[str, pl.DataFrame]:
    """Return the cached frames for `dataset`, regenerating if stale.

    Shared by `PolarsModel` and `PandasModel`; cache key is `dataframes`.
    """
    src = dataset.resolved_path()
    cache_dir = _cache.get_or_export(
        dataset=dataset.name,
        model="dataframes",
        source=src,
        payload_name=f"{dataset.name}-frames",
        export=lambda out: _export_frames(src, out),
    )
    return {
        name: pl.read_parquet(cache_dir / f"{name}.parquet")
        for name in _FRAME_NAMES
        if (cache_dir / f"{name}.parquet").exists()
    }


class PolarsModel:
    name = "polars"

    def __init__(self) -> None:
        self._frames: dict[str, pl.DataFrame] | None = None

    def setup(self, dataset: Dataset) -> None:
        dataset.fetch()
        self._frames = cached_polars_frames(dataset)

    def teardown(self) -> None:
        self._frames = None

    def size_on_disk(self) -> int:
        """Total estimated in-memory size of all frames, in bytes."""
        if self._frames is None:
            return 0
        return int(sum(df.estimated_size() for df in self._frames.values()))

    def reset_caches(self) -> None:
        pass

    def library_versions(self) -> dict[str, str]:
        return {
            "polars": package_version("polars"),
            "r4pm": package_version("r4pm"),
            "python": python_version(),
        }

    @property
    def frames(self) -> dict[str, pl.DataFrame]:
        if self._frames is None:
            raise RuntimeError("PolarsModel.frames accessed before setup()")
        return self._frames

    @property
    def relations(self) -> pl.DataFrame:
        return self.frames["relations"]

    @property
    def events(self) -> pl.DataFrame:
        return self.frames["events"]

    @property
    def objects(self) -> pl.DataFrame:
        return self.frames["objects"]

    # PrimitiveAccess.

    def get_object_types(self) -> list[str]:
        return self.objects["ocel:type"].unique().to_list()

    def get_objects_of_type(self, object_type: str) -> list[str]:
        return self.objects.filter(pl.col("ocel:type") == object_type)["ocel:oid"].to_list()

    def get_object_type(self, object_id: str) -> str:
        return self.objects.filter(pl.col("ocel:oid") == object_id)["ocel:type"].item()

    def get_activity(self, event_id: str) -> str:
        return self.events.filter(pl.col("ocel:eid") == event_id)["ocel:activity"].item()

    def get_timestamp(self, event_id: str) -> str:
        dt = self.events.filter(pl.col("ocel:eid") == event_id)["ocel:timestamp"].item()
        return normalize_timestamp(dt.isoformat())

    def get_events_of_type(self, activity: str) -> list[str]:
        return self.events.filter(pl.col("ocel:activity") == activity)["ocel:eid"].to_list()

    def get_events_of_object(self, object_id: str) -> list[str]:
        return self.relations.filter(pl.col("ocel:oid") == object_id)["ocel:eid"].to_list()

    def get_objects_of_event(self, event_id: str) -> list[str]:
        return self.relations.filter(pl.col("ocel:eid") == event_id)["ocel:oid"].to_list()

    def get_related_objects(self, object_id: str) -> list[str]:
        o2o = self.frames["o2o"]
        return o2o.filter(pl.col("ocel:oid") == object_id)["ocel:oid_2"].to_list()


registry.register_model("polars", PolarsModel)
