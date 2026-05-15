"""BPIC17 dataset backed by a local OCEL file."""

from __future__ import annotations

import os
from functools import cached_property
from pathlib import Path

import r4pm

from ocpm_bench.datasets.base import Dataset
from ocpm_bench.harness import registry

_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _ROOT / "data" / "bpic17"
_DEFAULT_SOURCE = _DATA_DIR / "bpic2017-ocel2.canonical.json.gz"


class BPIC17Dataset(Dataset):
    name = "bpic17"
    source_path = os.environ.get("OCPM_BPIC17_PATH", str(_DEFAULT_SOURCE))

    def fetch(self) -> None:
        p = Path(self.source_path)
        if p.exists():
            return
        raise FileNotFoundError(
            f"BPIC17 OCEL not found at {p}. Place the OCEL file there or set "
            "OCPM_BPIC17_PATH."
        )

    @cached_property
    def _object_types(self) -> list[str]:
        self.fetch()
        oid = r4pm.import_item("SlimLinkedOCEL", self.source_path)
        try:
            return list(r4pm.bindings.locel_get_ob_types(oid))
        finally:
            r4pm.remove_item(oid)

    def object_types(self) -> list[str]:
        return list(self._object_types)


registry.register_dataset("bpic17", BPIC17Dataset)
