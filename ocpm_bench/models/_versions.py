"""Shared helpers for `Model.library_versions`."""

from __future__ import annotations

import importlib.metadata
import sys


def package_version(pkg: str) -> str:
    try:
        return importlib.metadata.version(pkg)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def python_version() -> str:
    v = sys.version_info
    return f"{v.major}.{v.minor}.{v.micro}"
