#!/usr/bin/env python3
"""Load the bundled sample Parquet into DuckDB. DuckDB is embedded — no server needed.

    python scripts/load_duckdb.py

Env: DATA_GLOB (default data/*.parquet), DUCKDB_PATH (default market.duckdb).
"""
import os
import pathlib
import duckdb

HERE = pathlib.Path(__file__).resolve().parent.parent
DATA = os.environ.get("DATA_GLOB", str(HERE / "data" / "*.parquet"))
DBP = os.environ.get("DUCKDB_PATH", str(HERE / "market.duckdb"))


def main():
    con = duckdb.connect(DBP)
    con.execute("DROP TABLE IF EXISTS quotes")
    con.execute(
        f"""CREATE TABLE quotes AS
            SELECT symbol,
                   provider_ts_ms,
                   make_timestamp(provider_ts_ms * 1000) AS provider_ts,  -- micros
                   bid, ask, capture_id
            FROM read_parquet('{DATA}')
            ORDER BY symbol, provider_ts_ms, capture_id"""
    )
    n = con.execute("SELECT count(*) FROM quotes").fetchone()[0]
    print(f"DuckDB: loaded {n:,} rows into {DBP}")
    con.close()


if __name__ == "__main__":
    main()
