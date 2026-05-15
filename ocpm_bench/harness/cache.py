"""Disk cache for expensive model exports (Kuzu DB directories, parquet, etc.).

Key: (dataset, model, payload_name). Freshness: source size+sha256 match.
Layout: `<root>/<dataset>/<model>/<payload_name>` plus a sibling
`.cache_meta.json`.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

_DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "cache"


def default_root() -> Path:
    return _DEFAULT_ROOT


def _meta_path(payload: Path) -> Path:
    return payload.with_name(payload.name + ".cache_meta.json")


@lru_cache(maxsize=16)
def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _source_fingerprint(src: Path) -> dict[str, object]:
    st = src.stat()
    path = str(src.resolve())
    return {
        "mtime_ns": st.st_mtime_ns,
        "size": st.st_size,
        "sha256": _sha256(path),
        "source": path,
    }


def _is_fresh(meta_path: Path, want: dict[str, object]) -> bool:
    if not meta_path.exists():
        return False
    try:
        have = json.loads(meta_path.read_text())
    except (OSError, ValueError):
        return False
    return (
        have.get("size") == want["size"]
        and have.get("sha256") == want["sha256"]
    )


def _remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink()


def get_or_export(
    *,
    dataset: str,
    model: str,
    source: Path,
    payload_name: str,
    export: Callable[[Path], None],
    root: Path | None = None,
) -> Path:
    """Return the path of a cached export, regenerating if missing or stale.

    `export(tmp_path)` must produce a file or directory at `tmp_path`; on
    success it is renamed into the cache atomically.
    """
    root = root or _DEFAULT_ROOT
    out = root / dataset / model / payload_name
    meta = _meta_path(out)
    want = _source_fingerprint(source)

    if out.exists() and _is_fresh(meta, want):
        return out

    _remove(out)
    _remove(meta)

    out.parent.mkdir(parents=True, exist_ok=True)
    print(
        f"[cache] generating {model}/{dataset}/{payload_name} from {source}",
        file=sys.stderr,
    )
    with tempfile.TemporaryDirectory(prefix=f"ocpm_export_{model}_", dir=out.parent) as tmp:
        tmp_payload = Path(tmp) / payload_name
        export(tmp_payload)
        if not tmp_payload.exists():
            raise RuntimeError(f"cache: export callable did not produce {tmp_payload}")
        os.rename(tmp_payload, out)
    meta.write_text(json.dumps(want))
    return out


def invalidate(
    *,
    dataset: str | None = None,
    model: str | None = None,
    root: Path | None = None,
) -> int:
    """Remove cached exports; return the number of payloads removed."""
    root = root or _DEFAULT_ROOT
    if model is not None and dataset is None:
        raise ValueError("invalidate(model=...) requires dataset=...")

    if dataset is None:
        target = root
    elif model is None:
        target = root / dataset
    else:
        target = root / dataset / model

    if not target.exists():
        return 0

    n_payloads = sum(1 for _ in target.rglob("*.cache_meta.json"))
    shutil.rmtree(target)
    return n_payloads


def list_entries(root: Path | None = None) -> list[dict[str, object]]:
    """One row per cached payload, used by `ocpm-bench cache list`."""
    root = root or _DEFAULT_ROOT
    rows: list[dict[str, object]] = []
    if not root.exists():
        return rows
    for meta in sorted(root.rglob("*.cache_meta.json")):
        try:
            data = json.loads(meta.read_text())
        except (OSError, ValueError):
            continue
        payload = meta.with_name(meta.name.removesuffix(".cache_meta.json"))
        rel = payload.relative_to(root)
        parts = rel.parts
        ds = parts[0] if len(parts) >= 1 else "?"
        mdl = parts[1] if len(parts) >= 2 else "?"
        rows.append({
            "dataset": ds,
            "model": mdl,
            "payload": str(payload),
            "size_bytes": _payload_size(payload),
            "source": data.get("source"),
            "source_size": data.get("size"),
            "source_mtime_ns": data.get("mtime_ns"),
        })
    return rows


def _payload_size(payload: Path) -> int:
    if payload.is_dir():
        total = 0
        for r, _d, files in os.walk(payload):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(r, f))
                except OSError:
                    pass
        return total
    if payload.exists():
        try:
            return os.path.getsize(payload)
        except OSError:
            return 0
    return 0
