"""PrimitiveAccess: lowest-common-denominator OCEL data-access protocol.

Mirrors r4pm's LinkedOCELAccess trait. Every model implements this so
the same per-pattern Python code can run identically across all
backings, isolating data-access cost from engine-native pushdown.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable


def thread_cap() -> int | None:
    """Thread cap from ``OCPM_THREADS`` (set by the runner), or None if unset.

    Engines that auto-detect cores (DuckDB, Kuzu) ignore the process CPU
    affinity and would oversubscribe the pinned cores; this caps them to match
    the affinity-aware engines (Polars, rayon) for a fair comparison.
    """
    v = os.environ.get("OCPM_THREADS")
    return int(v) if v else None


def clean_type_name(name: str) -> str:
    """Strip spaces and replace non-alphanumeric characters with underscores.

    Matches r4pm's Kuzu label-cleaning and the strong-rels SQL identifier rule.
    """
    no_spaces = name.replace(" ", "")
    return "".join(c if c.isalnum() else "_" for c in no_spaces)


@runtime_checkable
class PrimitiveAccess(Protocol):
    """Lowest-common-denominator data access for OCEL models."""

    def get_object_types(self) -> list[str]:
        """All distinct object type names."""
        ...

    def get_objects_of_type(self, object_type: str) -> list[str]:
        """Object IDs of the given type."""
        ...

    def get_object_type(self, object_id: str) -> str:
        """Type name of the given object."""
        ...

    def get_activity(self, event_id: str) -> str:
        """Activity name of the given event."""
        ...

    def get_timestamp(self, event_id: str) -> str:
        """Sortable timestamp string. Lexicographic == chronological."""
        ...

    def get_events_of_type(self, activity: str) -> list[str]:
        """Event IDs with the given activity name."""
        ...

    def get_events_of_object(self, object_id: str) -> list[str]:
        """Event IDs related to the given object (arbitrary order)."""
        ...

    def get_objects_of_event(self, event_id: str) -> list[str]:
        """Object IDs related to the given event (e2o reverse)."""
        ...

    def get_related_objects(self, object_id: str) -> list[str]:
        """Object IDs linked via o2o relations from the given object."""
        ...


def normalize_timestamp(iso: str) -> str:
    """Normalize an ISO 8601 timestamp for correct lexicographic sorting.

    Strips trailing `Z` / `+00:00` and pads fractional seconds to 6 digits
    so mixed-precision timestamps sort correctly.
    """
    s = iso
    if s.endswith("Z"):
        s = s[:-1]
    elif s.endswith("+00:00"):
        s = s[:-6]
    if "." not in s:
        s += ".000000"
    else:
        base, frac = s.rsplit(".", 1)
        s = base + "." + frac.ljust(6, "0")
    return s
