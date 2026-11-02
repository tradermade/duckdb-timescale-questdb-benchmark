#!/usr/bin/env python3
"""Independent reference answers, computed in pure Python with PyArrow — NOT via any of the
three databases. Use these to confirm DuckDB / TimescaleDB / QuestDB return the same results.

    python scripts/reference.py              # prints a few ground-truth answers

Rules (match the tutorial):
  * Ordering / tie-break: (provider_ts_ms, capture_id).
  * Candle for [t, t+60s): open/close = first/last bid in that order; high/low = max/min bid.
  * As-of: the latest quote at or before the probe, within a 60-second max age.
"""
import bisect
import glob
import os
import pathlib

import pyarrow.parquet as pq

HERE = pathlib.Path(__file__).resolve().parent.parent
DATA = os.environ.get("DATA_GLOB", str(HERE / "data" / "*.parquet"))
AGE_MS = 60_000


def load():
    """Return {symbol: [(ts_ms, capture_id, bid, ask), ...]} sorted by (ts, capture_id)."""
    by = {}
    for f in sorted(glob.glob(DATA)):
        t = pq.read_table(f, columns=["symbol", "provider_ts_ms", "bid", "ask", "capture_id"]).to_pydict()
        for i in range(len(t["symbol"])):
            by.setdefault(t["symbol"][i], []).append(
                (t["provider_ts_ms"][i], t["capture_id"][i], t["bid"][i], t["ask"][i]))
    for s in by:
        by[s].sort()
    return by


def latest(by, symbol):
    rows = by.get(symbol)
    if not rows:
        return None
    ts, cap, bid, ask = rows[-1]
    return {"provider_ts_ms": ts, "capture_id": cap, "bid": bid, "ask": ask}


def candle(by, symbol, minute_start_ms, width_ms=60_000):
    rows = by.get(symbol) or []
    lo = bisect.bisect_left(rows, (minute_start_ms,))
    hi = bisect.bisect_left(rows, (minute_start_ms + width_ms,))
    seg = rows[lo:hi]
    if not seg:
        return None
    bids = [r[2] for r in seg]
    return {"open": seg[0][2], "high": max(bids), "low": min(bids), "close": seg[-1][2], "count": len(seg)}


def asof(by, symbol, probe_ms, max_age_ms=AGE_MS):
    rows = by.get(symbol)
    if not rows:
        return None
    idx = bisect.bisect_right(rows, (probe_ms, float("inf"))) - 1
    if idx < 0:
        return None
    ts, cap, bid, ask = rows[idx]
    if probe_ms - ts > max_age_ms:
        return None
    return {"provider_ts_ms": ts, "capture_id": cap, "bid": bid, "ask": ask}


if __name__ == "__main__":
    by = load()
    print("symbols:", {s: len(v) for s, v in by.items()})
    for s in by:
        lt = latest(by, s)
        start = (by[s][len(by[s]) // 2][0] // 60_000) * 60_000   # a minute in the middle of the data
        c = candle(by, s, start)
        a = asof(by, s, lt["provider_ts_ms"])
        print(f"\n{s}")
        print(f"  latest        : {lt}")
        print(f"  candle @ {start}: {c}")
        print(f"  as-of @ latest : {a}")
