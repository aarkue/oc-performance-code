"""Pandas model: reads the cached parquet frames and converts to pandas.

Same source schema and cache as `PolarsModel` so the comparison is engine-only.
"""

from __future__ import annotations

import pandas as pd

from ocpm_bench.datasets.base import Dataset
from ocpm_bench.harness import registry
from ocpm_bench.models._versions import package_version, python_version
from ocpm_bench.models.polars import cached_polars_frames
from ocpm_bench.models.primitives import normalize_timestamp


class PandasModel:
    name = "pandas"

    def __init__(self) -> None:
        self._frames: dict[str, pd.DataFrame] | None = None

    def setup(self, dataset: Dataset) -> None:
        dataset.fetch()
        self._frames = {k: v.to_pandas() for k, v in cached_polars_frames(dataset).items()}

    def teardown(self) -> None:
        self._frames = None

    def size_on_disk(self) -> int:
        """Total deep pandas memory usage of all frames, in bytes."""
        if self._frames is None:
            return 0
        return sum(int(df.memory_usage(deep=True).sum()) for df in self._frames.values())

    def reset_caches(self) -> None:
        pass

    def library_versions(self) -> dict[str, str]:
        return {
            "pandas": package_version("pandas"),
            "r4pm": package_version("r4pm"),
            "python": python_version(),
        }

    @property
    def frames(self) -> dict[str, pd.DataFrame]:
        if self._frames is None:
            raise RuntimeError("PandasModel.frames accessed before setup()")
        return self._frames

    @property
    def relations(self) -> pd.DataFrame:
        return self.frames["relations"]

    @property
    def events(self) -> pd.DataFrame:
        return self.frames["events"]

    @property
    def objects(self) -> pd.DataFrame:
        return self.frames["objects"]

    # PrimitiveAccess.

    def get_object_types(self) -> list[str]:
        return self.objects["ocel:type"].unique().tolist()

    def get_objects_of_type(self, object_type: str) -> list[str]:
        return self.objects.loc[self.objects["ocel:type"] == object_type, "ocel:oid"].tolist()

    def get_object_type(self, object_id: str) -> str:
        return self.objects.loc[self.objects["ocel:oid"] == object_id, "ocel:type"].iloc[0]

    def get_activity(self, event_id: str) -> str:
        return self.events.loc[self.events["ocel:eid"] == event_id, "ocel:activity"].iloc[0]

    def get_timestamp(self, event_id: str) -> str:
        dt = self.events.loc[self.events["ocel:eid"] == event_id, "ocel:timestamp"].iloc[0]
        return normalize_timestamp(dt.isoformat())

    def get_events_of_type(self, activity: str) -> list[str]:
        return self.events.loc[self.events["ocel:activity"] == activity, "ocel:eid"].tolist()

    def get_events_of_object(self, object_id: str) -> list[str]:
        return self.relations.loc[self.relations["ocel:oid"] == object_id, "ocel:eid"].tolist()

    def get_objects_of_event(self, event_id: str) -> list[str]:
        return self.relations.loc[self.relations["ocel:eid"] == event_id, "ocel:oid"].tolist()

    def get_related_objects(self, object_id: str) -> list[str]:
        o2o = self.frames["o2o"]
        return o2o.loc[o2o["ocel:oid"] == object_id, "ocel:oid_2"].tolist()


registry.register_model("pandas", PandasModel)
