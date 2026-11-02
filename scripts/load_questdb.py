#!/usr/bin/env python3
"""Load the bundled sample Parquet into QuestDB via its native line protocol (ILP over HTTP /write).

    docker compose up -d        # start the server first
    python scripts/load_questdb.py

Creates a WAL table with DEDUP first, then streams ILP lines in batches. ILP is QuestDB's
fast ingestion path — much faster than row-by-row SQL INSERT.
Env: DATA_GLOB, QUESTDB_HTTP (default http://localhost:9000).
"""
import os
import pathlib
import time

import duckdb
import requests

HERE = pathlib.Path(__file__).resolve().parent.parent
DATA = os.environ.get("DATA_GLOB", str(HERE / "data" / "*.parquet"))
HTTP = os.environ.get("QUESTDB_HTTP", "http://localhost:9000")


def exec_sql(q, timeout=120):
    r = requests.get(f"{HTTP}/exec", params={"query": q}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def main():
    exec_sql("DROP TABLE IF EXISTS quotes")
    exec_sql(
        """CREATE TABLE quotes (symbol SYMBOL, provider_ts TIMESTAMP, provider_ts_ms LONG,
           bid DOUBLE, ask DOUBLE, capture_id LONG)
           TIMESTAMP(provider_ts) PARTITION BY DAY WAL
           DEDUP UPSERT KEYS(provider_ts, symbol, capture_id)""")

    d = duckdb.connect()
    rel = d.execute(f"SELECT symbol, provider_ts_ms, bid, ask, capture_id FROM read_parquet('{DATA}')")
    sess = requests.Session()
    total = 0
    while True:
        rows = rel.fetchmany(50_000)
        if not rows:
            break
        lines = []
        for symbol, ts_ms, bid, ask, cap in rows:
            # tags (symbol) then fields; the line timestamp (ns) sets the designated provider_ts.
            lines.append(f"quotes,symbol={symbol} provider_ts_ms={ts_ms}i,bid={bid},ask={ask},"
                         f"capture_id={cap}i {ts_ms * 1_000_000}")
        resp = sess.post(f"{HTTP}/write", data=("\n".join(lines) + "\n").encode(), timeout=120)
        resp.raise_for_status()
        total += len(rows)

    # ILP commits to the WAL immediately but applies to the table asynchronously; wait for it.
    for _ in range(240):
        if exec_sql("SELECT count() FROM quotes")["dataset"][0][0] >= total:
            break
        time.sleep(0.5)
    print(f"QuestDB: loaded {exec_sql('SELECT count() FROM quotes')['dataset'][0][0]:,} rows")


if __name__ == "__main__":
    main()
