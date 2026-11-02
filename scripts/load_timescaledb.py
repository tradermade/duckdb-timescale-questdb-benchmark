#!/usr/bin/env python3
"""Load the bundled sample Parquet into TimescaleDB.

    docker compose up -d        # start the server first
    python scripts/load_timescaledb.py

Reads the parquet with DuckDB (fast, no pandas) and streams it via COPY, then adds the
replay-safe unique constraint and the (symbol, provider_ts DESC) index AFTER the load.
Env: DATA_GLOB, TIMESCALE_DSN (default postgresql://bench:bench@localhost:5432/market).
"""
import os
import pathlib

import duckdb
import psycopg

HERE = pathlib.Path(__file__).resolve().parent.parent
DATA = os.environ.get("DATA_GLOB", str(HERE / "data" / "*.parquet"))
DSN = os.environ.get("TIMESCALE_DSN", "postgresql://bench:bench@localhost:5432/market")

SETUP = [
    "CREATE EXTENSION IF NOT EXISTS timescaledb",
    "DROP TABLE IF EXISTS quotes CASCADE",
    """CREATE TABLE quotes (symbol text NOT NULL, provider_ts_ms bigint NOT NULL,
       provider_ts timestamptz NOT NULL, bid double precision NOT NULL,
       ask double precision NOT NULL, capture_id bigint NOT NULL)""",
    "SELECT create_hypertable('quotes','provider_ts', chunk_time_interval => interval '1 day')",
]
FINALISE = [
    "ALTER TABLE quotes ADD CONSTRAINT quotes_uq UNIQUE (provider_ts, symbol, capture_id)",
    "CREATE INDEX quotes_sym_ts ON quotes (symbol, provider_ts DESC)",
    "ANALYZE quotes",
]


def main():
    con = psycopg.connect(DSN, autocommit=True)
    cur = con.cursor()
    cur.execute("SET TIME ZONE 'UTC'")   # store provider_ts as true UTC
    for stmt in SETUP:
        cur.execute(stmt)

    d = duckdb.connect()
    rel = d.execute(
        f"SELECT symbol, provider_ts_ms, make_timestamp(provider_ts_ms*1000) AS provider_ts, "
        f"bid, ask, capture_id FROM read_parquet('{DATA}') ORDER BY provider_ts_ms, capture_id")
    total = 0
    with cur.copy("COPY quotes (symbol, provider_ts_ms, provider_ts, bid, ask, capture_id) FROM STDIN") as cp:
        while True:
            rows = rel.fetchmany(100_000)
            if not rows:
                break
            for r in rows:
                cp.write_row(r)
            total += len(rows)

    for stmt in FINALISE:
        cur.execute(stmt)
    cur.execute("SELECT count(*) FROM quotes")
    print(f"TimescaleDB: loaded {cur.fetchone()[0]:,} rows")
    con.close()


if __name__ == "__main__":
    main()
