# Financial Time-Series DB Benchmark — DuckDB vs TimescaleDB vs QuestDB

Load the **same** two weeks of real forex tick data into **DuckDB**, **TimescaleDB** and
**QuestDB**, run the same four queries every market app actually needs, and see for yourself
how the three behave. Everything here is reproducible: the sample data is in the repo, the
loaders set each engine up the way you would in production, and a pure-Python reference script
gives you ground-truth answers to check every result against.

> Companion to the TraderMade article **“Best Database for Financial Time-Series Data”**.
> Link: `<ARTICLE_URL>` *(replace with the published URL)*.

## What's inside

```
data/                 2-week EURUSD + USDJPY tick sample (Parquet) + data dictionary
docker-compose.yml    TimescaleDB + QuestDB, versions pinned to the article
sql/                  the schema each engine uses, as plain reference SQL
scripts/
  load_duckdb.py        load the sample into DuckDB (embedded, no server)
  load_timescaledb.py   load into TimescaleDB (COPY, then index)
  load_questdb.py       load into QuestDB (native ILP ingest)
  run_queries.py        run + time two signature queries against one engine
  reference.py          ground-truth answers computed in pure Python (no DB)
  download_tradermade.py  pull your OWN ticks into the same schema (optional)
Makefile              up / install / load-all / verify shortcuts
```

The sample is ~6.2M ticks: **EURUSD 3,199,137** and **USDJPY 3,047,038** rows, 2026-09-27 →
2026-10-09 UTC. Schema and terms are in [`data/README.md`](data/README.md).

## Quickstart

Requires Python 3.10+ and (for TimescaleDB/QuestDB) Docker. **DuckDB needs no server.**

```bash
pip install -r requirements.txt
cp .env.example .env            # defaults already match docker-compose.yml
```

**DuckDB — embedded, nothing to start:**

```bash
python scripts/load_duckdb.py
python scripts/run_queries.py duckdb
```

**TimescaleDB and QuestDB — start the servers first:**

```bash
docker compose up -d            # or: make up
python scripts/load_timescaledb.py && python scripts/run_queries.py timescaledb
python scripts/load_questdb.py  && python scripts/run_queries.py questdb
```

Check any engine's answers against the independent reference:

```bash
python scripts/reference.py     # or: make verify
```

## The four queries

The benchmark centres on what a quote-serving backend does all day:

1. **Latest price per symbol** — the current bid/ask right now.
2. **Candles (OHLC)** — first/high/low/last bid over a time bucket (e.g. 1-minute bars).
3. **As-of lookup** — the quote in effect at an arbitrary instant (latest at-or-before, max 60s old).
4. **History page** — a time-ordered slice for charting/backfill (keyset pagination).

Every query orders and de-duplicates by `(provider_ts_ms, capture_id)` so same-millisecond
ticks stay distinct and replays collapse. `scripts/reference.py` implements all of this in
~60 lines of plain Python, independent of the databases, so you can trust the comparison.

## How each engine is set up (and why)

- **DuckDB** — embedded, one file. Loaded straight from Parquet. Plain table (no unique index:
  a unique index inflated the file ~19× in testing; de-dup in code instead).
- **TimescaleDB** — hypertable on `provider_ts` (a real `timestamptz`, **not** the int-ms copy).
  Data is COPY-loaded first, then the `(symbol, provider_ts DESC)` index and the replay-safe
  `UNIQUE(provider_ts, symbol, capture_id)` constraint are added. Durable commits on
  (`fsync=on`, `synchronous_commit=on`).
- **QuestDB** — WAL table partitioned by day with `DEDUP UPSERT KEYS(provider_ts, symbol,
  capture_id)`, ingested over the native line protocol (ILP). ILP commits to the WAL and
  applies to the table asynchronously, so the loader waits for the row count to catch up.

See `sql/` for the exact DDL.

## Use your own data

Point the loaders at any Parquet matching the sample schema via `DATA_GLOB`. To fetch fresh
ticks from TraderMade (free key at <https://tradermade.com/signup>):

```bash
export TRADERMADE_API_KEY=your_key
python scripts/download_tradermade.py EURUSD 2026-10-20 2026-10-24
DATA_GLOB='data/downloaded/*.parquet' python scripts/load_duckdb.py
```

## Honest caveats

- This is a **comparison harness, not a leaderboard**. Numbers depend on your hardware, your
  queries and your data; run it on yours. Each engine shines at different jobs — the article
  spells out which, and when.
- The pinned image versions are what the article measured; newer releases may behave differently.
- The results reflect **this sample** (two symbols, two weeks). Scale the data up before drawing
  conclusions about billions of rows.

## License

Code: **MIT** (see [`LICENSE`](LICENSE)). Sample data under `data/`: evaluation/educational use,
sourced from TraderMade — see [`data/README.md`](data/README.md).
