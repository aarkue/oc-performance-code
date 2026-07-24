"""Convert the OCEL 1.0 BPIC17 log (Khayatbashi et al., 4TU 2023) to the OCEL 2.0 encoding used in the benchmark, adding object-to-object relations.
Events are grouped by their `case`: each Application links to its case's Offers (`offer`) and Workflow (`workflow`).

    python scripts/convert_ocel1_to_ocel2.py BPIC17.jsonocel out.json
    python scripts/canonicalize.py out.json data/bpic17/bpic2017-ocel2.canonical.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import ijson


def _events(path: Path):
    with open(path, "rb") as fh:
        yield from ijson.kvitems(fh, "ocel:events")


def _write_array(out, items) -> None:
    out.write("[")
    for i, item in enumerate(items):
        out.write("," if i else "")
        json.dump(item, out)
    out.write("]")


def convert(src: Path, dst: Path) -> None:
    with open(src, "rb") as fh:
        obj_type = {oid: o["ocel:type"] for oid, o in ijson.kvitems(fh, "ocel:objects")}

    offers: dict[str, set[str]] = defaultdict(set)
    workflow: dict[str, str] = {}
    app_case: dict[str, str] = {}
    attrs: dict[str, dict[str, str]] = defaultdict(dict)
    for _, ev in _events(src):
        vmap = ev.get("ocel:vmap", {})
        for name, value in vmap.items():
            attrs[ev["ocel:activity"]].setdefault(
                name, "float" if isinstance(value, (int, float)) else "string"
            )
        case = vmap.get("case")
        if case is None:
            continue
        for oid in ev["ocel:omap"]:
            t = obj_type.get(oid)
            if t == "Application":
                app_case[oid] = case
            elif t == "Offer":
                offers[case].add(oid)
            elif t == "Workflow":
                workflow[case] = oid

    def o2o(app: str) -> list[dict[str, str]]:
        case = app_case.get(app)
        if case is None:
            return []
        rels = [{"objectId": o, "qualifier": "offer"} for o in sorted(offers.get(case, ()))]
        if case in workflow:
            rels.append({"objectId": workflow[case], "qualifier": "workflow"})
        return rels

    def events():
        for eid, ev in _events(src):
            vmap = ev.get("ocel:vmap", {})
            yield {
                "id": eid,
                "type": ev["ocel:activity"],
                "time": ev["ocel:timestamp"][:19] + "Z",
                "attributes": [{"name": n, "value": v} for n, v in vmap.items()],
                "relationships": [{"objectId": o, "qualifier": "-"} for o in ev["ocel:omap"]],
            }

    def objects():
        for oid, t in obj_type.items():
            yield {
                "id": oid,
                "type": t,
                "attributes": [],
                "relationships": o2o(oid) if t == "Application" else [],
            }

    object_types = [{"name": t, "attributes": []} for t in sorted(set(obj_type.values()))]
    event_types = [
        {"name": t, "attributes": [{"name": n, "type": ty} for n, ty in sorted(a.items())]}
        for t, a in sorted(attrs.items())
    ]
    with open(dst, "w", encoding="utf-8") as out:
        out.write('{"objectTypes":')
        json.dump(object_types, out)
        out.write(',"eventTypes":')
        json.dump(event_types, out)
        out.write(',"events":')
        _write_array(out, events())
        out.write(',"objects":')
        _write_array(out, objects())
        out.write("}")


def _main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("src", type=Path, help="OCEL 1.0 .jsonocel input")
    p.add_argument("dst", type=Path, help="OCEL 2.0 JSON output")
    args = p.parse_args()
    convert(args.src, args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
