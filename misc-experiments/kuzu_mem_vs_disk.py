"""Same DFG query on Kuzu, on-disk vs in-memory, both built from one import."""
import statistics
import tempfile
import time
from pathlib import Path

import kuzu

SRC = Path(__file__).resolve().parents[1] / "cache/bpic17/kuzu/bpic17-strong.kuzu"
QUERY = (
    "MATCH (a)-[df:DF]->(b) WHERE df.EntityType = 'Case_R' "
    "RETURN LABEL(a), LABEL(b), COUNT(*)"
)
N = 10


def bench(db):
    c = kuzu.Connection(db)
    c.execute(QUERY)  # warmup (cold run)
    t = []
    for _ in range(N):
        s = time.perf_counter()
        c.execute(QUERY)
        t.append((time.perf_counter() - s) * 1000)
    c.close()
    return min(t), statistics.median(t), t


with tempfile.TemporaryDirectory() as tmp:
    exp = Path(tmp) / "export"
    src = kuzu.Database(str(SRC), read_only=True)
    kuzu.Connection(src).execute(f"EXPORT DATABASE '{exp}' (format='parquet')")
    src.close()

    for name, path in [("on-disk  ", str(Path(tmp) / "disk.kuzu")), ("in-memory", ":memory:")]:
        db = kuzu.Database(path)
        kuzu.Connection(db).execute(f"IMPORT DATABASE '{exp}'")
        lo, med, res = bench(db)
        print(f"{name}  min={lo:7.2f} ms  median={med:7.2f} ms  all={res}")
        db.close()
