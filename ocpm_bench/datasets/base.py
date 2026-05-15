"""Dataset base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class Dataset(ABC):
    name: str = ""
    source_path: str = ""

    def fetch(self) -> None:
        """Ensure the local source file exists."""
        self.resolved_path()

    @abstractmethod
    def object_types(self) -> list[str]:
        """Distinct object types present in the dataset."""

    def resolved_path(self) -> Path:
        p = Path(self.source_path)
        if not p.exists():
            raise FileNotFoundError(
                f"Dataset {self.name}: {p} not found."
            )
        return p
