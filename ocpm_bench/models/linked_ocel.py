"""LinkedOCEL model: thin wrapper over r4pm's `SlimLinkedOCEL` handle.

Also serves as the oracle for every access pattern.
"""

from __future__ import annotations

import os

import r4pm

from ocpm_bench.datasets.base import Dataset
from ocpm_bench.harness import registry
from ocpm_bench.models._versions import package_version, python_version
from ocpm_bench.models.primitives import normalize_timestamp


class LinkedOCELModel:
    name = "linked_ocel"

    def __init__(self) -> None:
        self._ocel_id: str | None = None
        self._source_path: str | None = None

    def setup(self, dataset: Dataset) -> None:
        dataset.fetch()
        self._source_path = str(dataset.resolved_path())
        self._ocel_id = r4pm.import_item("SlimLinkedOCEL", self._source_path)

    def teardown(self) -> None:
        if self._ocel_id is not None:
            try:
                r4pm.remove_item(self._ocel_id)
            except Exception:
                pass
            self._ocel_id = None

    def size_on_disk(self) -> int:
        return os.path.getsize(self._source_path) if self._source_path else 0

    def reset_caches(self) -> None:
        # r4pm holds no engine-side cache; the subprocess boundary supplies
        # the cold state for repetitions.
        pass

    def library_versions(self) -> dict[str, str]:
        return {"r4pm": package_version("r4pm"), "python": python_version()}

    @property
    def ocel_id(self) -> str:
        if self._ocel_id is None:
            raise RuntimeError("LinkedOCELModel.ocel_id accessed before setup()")
        return self._ocel_id

    # PrimitiveAccess. Every method below maps to one r4pm FFI call.

    def get_object_types(self) -> list[str]:
        return r4pm.bindings.locel_get_ob_types(self.ocel_id)

    def get_objects_of_type(self, object_type: str) -> list[str]:
        return r4pm.bindings.get_object_ids_of_type(self.ocel_id, object_type)

    def get_object_type(self, object_id: str) -> str:
        return r4pm.bindings.get_object_type_of_id(self.ocel_id, object_id)

    def get_activity(self, event_id: str) -> str:
        return r4pm.bindings.get_event_type_of_id(self.ocel_id, event_id)

    def get_timestamp(self, event_id: str) -> str:
        return normalize_timestamp(
            r4pm.bindings.get_event_timestamp_of_id(self.ocel_id, event_id)
        )

    def get_events_of_type(self, activity: str) -> list[str]:
        return r4pm.bindings.get_event_ids_of_type(self.ocel_id, activity)

    def get_events_of_object(self, object_id: str) -> list[str]:
        return r4pm.bindings.get_e2o_rev_ids(self.ocel_id, object_id)

    def get_objects_of_event(self, event_id: str) -> list[str]:
        return r4pm.bindings.get_e2o_ids(self.ocel_id, event_id)

    def get_related_objects(self, object_id: str) -> list[str]:
        return r4pm.bindings.get_o2o_ids(self.ocel_id, object_id)


registry.register_model("linked_ocel", LinkedOCELModel)
