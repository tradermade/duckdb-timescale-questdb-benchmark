#!/usr/bin/env python3
"""Download your OWN tick data from TraderMade into a Parquet matching the bundled sample schema.

    export TRADERMADE_API_KEY=...        # free key: https://tradermade.com/signup
    python scripts/download_tradermade.py EURUSD 2026-10-20 2026-10-24

Writes data/downloaded/<SYMBOL>_<start>_<end>.parquet with columns:
    symbol, provider_ts_ms (int64 epoch ms), bid, ask, capture_id (1..N in time order)

Notes about the tick_historical endpoint:
  * The URL is   .../tick_historical/<SYMBOL>/<start>/<end>  and the dates use a SPACE
    between day and time (YYYY-MM-DD HH:MM). The dash form returns HTTP 500.
  * Each quote has integer-ms `time`, plus `bid` and `ask`.
  * Ticks are only available for roughly the last ~30 days, FX / crypto / metals only.
  * We fetch in 1-hour windows to stay within per-request limits and sleep between calls.
"""
import datetime as dt
import json
import os
import pathlib
import sys
import time
from decimal import Decimal

import pyarrow as pa
import pyarrow.parquet as pq
import requests

BASE = "https://marketdata.tradermade.com/api/v1/tick_historical"
FMT = "%Y-%m-%d %H:%M"          # space form — the live endpoint requires it
HERE = pathlib.Path(__file__).resolve().parent.parent
OUT = HERE / "data" / "downloaded"


def windows(start, end, step=dt.timedelta(hours=1)):
    t = start
    while t < end:
        yield t, min(t + step, end)
        t += step


def main():
    key = os.environ.get("TRADERMADE_API_KEY", "").strip()
    if not key:
        sys.exit("Set TRADERMADE_API_KEY (free key: https://tradermade.com/signup)")
    if len(sys.argv) != 4:
        sys.exit("usage: download_tradermade.py <SYMBOL> <start YYYY-MM-DD> <end YYYY-MM-DD>")
    sym = sys.argv[1].upper()
    start = dt.datetime.fromisoformat(sys.argv[2]).replace(tzinfo=dt.timezone.utc)
    end = dt.datetime.fromisoformat(sys.argv[3]).replace(tzinfo=dt.timezone.utc)
    dec = 3 if sym.endswith("JPY") else 5

    sess = requests.Session()
    rows = []  # (ts_ms, bid, ask)
    for a, b in windows(start, end):
        url = f"{BASE}/{sym}/{a.strftime(FMT)}/{b.strftime(FMT)}"
        r = sess.get(url, params={"api_key": key, "format": "json"}, timeout=120)
        if r.status_code != 200:
            print(f"  skip {a:%Y-%m-%d %H:%M}  HTTP {r.status_code} {r.text[:100]}")
            continue
        # parse_float=Decimal so float rounding never touches the canonical price
        payload = json.loads(r.text, parse_float=Decimal)
        for q in payload.get("quotes", []):
            rows.append((int(q["time"]), round(float(q["bid"]), dec), round(float(q["ask"]), dec)))
        print(f"  {a:%Y-%m-%d %H:%M}  +{len(payload.get('quotes', [])):>6} (total {len(rows):,})")
        time.sleep(0.25)

    rows.sort()  # by (ts_ms, bid, ask) — stable, matches the sample's capture_id ordering
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{sym}_{sys.argv[2]}_{sys.argv[3]}.parquet"
    pq.write_table(pa.table({
        "symbol": [sym] * len(rows),
        "provider_ts_ms": [x[0] for x in rows],
        "bid": [x[1] for x in rows],
        "ask": [x[2] for x in rows],
        "capture_id": list(range(1, len(rows) + 1)),
    }), out, compression="zstd")
    print(f"wrote {len(rows):,} rows to {out}")


if __name__ == "__main__":
    main()
