#!/usr/bin/env python3
"""Quick smoke test / usage example: run two signature queries against one engine and time them.

    python scripts/run_queries.py duckdb        # (after load_duckdb.py)
    python scripts/run_queries.py timescaledb   # (after docker compose up + load_timescaledb.py)
    python scripts/run_queries.py questdb       # (after docker compose up + load_questdb.py)

This is a demonstration, not the full benchmark from the article. Cross-check the output
against scripts/reference.py (the pure-Python ground truth).
"""
import datetime as dt
import os
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent.parent
DUCKDB_PATH = os.environ.get("DUCKDB_PATH", str(HERE / "market.duckdb"))
DSN = os.environ.get("TIMESCALE_DSN", "postgresql://bench:bench@localhost:5432/market")
HTTP = os.environ.get("QUESTDB_HTTP", "http://localhost:9000")

EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
MINUTE_MS = round((dt.datetime(2026, 10, 1, 12, 0, tzinfo=dt.timezone.utc) - EPOCH).total_seconds() * 1000)
SYM = "EURUSD"


def duckdb_run():
    import duckdb
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    t = time.perf_counter()
    latest = con.execute("SELECT symbol, arg_max(bid, provider_ts_ms), arg_max(ask, provider_ts_ms), "
                         "max(provider_ts_ms) FROM quotes GROUP BY symbol ORDER BY symbol").fetchall()
    tl = (time.perf_counter() - t) * 1000
    t = time.perf_counter()
    candle = con.execute(
        "SELECT arg_min(bid, provider_ts_ms) o, max(bid) h, min(bid) l, arg_max(bid, provider_ts_ms) c, count(*) n "
        "FROM quotes WHERE symbol=? AND provider_ts_ms>=? AND provider_ts_ms<?",
        [SYM, MINUTE_MS, MINUTE_MS + 60000]).fetchall()
    tc = (time.perf_counter() - t) * 1000
    return latest, tl, candle, tc


def timescaledb_run():
    import psycopg
    con = psycopg.connect(DSN); cur = con.cursor()
    t = time.perf_counter()
    cur.execute("SELECT DISTINCT ON (symbol) symbol, bid, ask, provider_ts_ms "
                "FROM quotes ORDER BY symbol, provider_ts DESC, capture_id DESC")
    latest = cur.fetchall(); tl = (time.perf_counter() - t) * 1000
    t = time.perf_counter()
    cur.execute("SELECT first(bid, provider_ts_ms), max(bid), min(bid), last(bid, provider_ts_ms), count(*) "
                "FROM quotes WHERE symbol=%s AND provider_ts >= to_timestamp(%s/1000.0) "
                "AND provider_ts < to_timestamp(%s/1000.0)", [SYM, MINUTE_MS, MINUTE_MS + 60000])
    candle = cur.fetchall(); tc = (time.perf_counter() - t) * 1000
    con.close()
    return latest, tl, candle, tc


def questdb_run():
    import requests
    def q(sql):
        r = requests.get(f"{HTTP}/exec", params={"query": sql}, timeout=60); r.raise_for_status()
        return r.json()["dataset"]
    t = time.perf_counter()
    latest = q("SELECT symbol, bid, ask, provider_ts_ms FROM quotes LATEST ON provider_ts PARTITION BY symbol")
    tl = (time.perf_counter() - t) * 1000
    t = time.perf_counter()
    candle = q(f"SELECT first(bid), max(bid), min(bid), last(bid), count() FROM quotes "
               f"WHERE symbol='{SYM}' AND provider_ts_ms>={MINUTE_MS} AND provider_ts_ms<{MINUTE_MS + 60000}")
    tc = (time.perf_counter() - t) * 1000
    return latest, tl, candle, tc


RUN = {"duckdb": duckdb_run, "timescaledb": timescaledb_run, "questdb": questdb_run}

if __name__ == "__main__":
    eng = sys.argv[1] if len(sys.argv) > 1 else "duckdb"
    if eng not in RUN:
        sys.exit(f"usage: run_queries.py [{'|'.join(RUN)}]")
    latest, tl, candle, tc = RUN[eng]()
    print(f"[{eng}] latest price per symbol — {len(latest)} rows in {tl:.1f} ms")
    for row in latest:
        print("   ", row)
    print(f"[{eng}] {SYM} 1-minute bid candle @ 2026-10-01 12:00 UTC — {tc:.1f} ms")
    print("   open/high/low/close/count:", candle)
