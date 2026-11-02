# Sample tick data

Two Parquet files of real forex quote ticks, provided so you can load the exact same
data into DuckDB, TimescaleDB and QuestDB and reproduce the comparison yourself.

| File | Symbol | Rows | Period (UTC) |
|------|--------|-----:|--------------|
| `EURUSD_2026-09-27_2026-10-09.parquet` | EURUSD | 3,199,137 | 2026-09-27 21:00 → 2026-10-09 21:00 |
| `GBPJPY_2026-09-27_2026-10-09.parquet` | GBPJPY | 5,486,036 | 2026-09-27 21:00 → 2026-10-09 21:00 |

About 12 calendar days each (two full trading weeks, weekends naturally empty), ~8.7M ticks total.

## Columns

| Column | Type | Meaning |
|--------|------|---------|
| `symbol` | string | Instrument, e.g. `EURUSD`. |
| `provider_ts_ms` | int64 | Quote timestamp as **epoch milliseconds, UTC** (the provider's own `time`). |
| `bid` | double | Best bid. Rounded to the instrument's convention (5 dp for EURUSD, 3 dp for GBPJPY). |
| `ask` | double | Best ask, same rounding. |
| `capture_id` | int64 | 1..N in `(provider_ts_ms, bid, ask)` order. Breaks ties when two quotes share a millisecond so every row stays uniquely identifiable — important for replay-safe de-duplication. |

The loaders derive a real timestamp type from `provider_ts_ms` (`provider_ts`): DuckDB and
TimescaleDB with `make_timestamp`/`to_timestamp`, QuestDB from the ILP line timestamp.

## The tie-break rule (why `capture_id` exists)

Ticks can arrive in the same millisecond. If you de-duplicate on `(timestamp, symbol)` alone,
you silently drop genuine quotes. Keying on `(provider_ts, symbol, capture_id)` instead means a
true replay of the same row collapses, while two real same-millisecond quotes are both kept.
Every query and the reference answers in `scripts/reference.py` order by `(provider_ts_ms, capture_id)`.

## Data source and terms

The ticks were captured from [TraderMade](https://tradermade.com)'s `tick_historical` API and
are redistributed here, in rounded form, as a small sample for benchmarking and learning.

- The **code** in this repository is MIT-licensed (see `../LICENSE`).
- The **sample data** under `data/` is **not** MIT. It is provided for evaluation and
  educational use. For production use, redistribution, or larger histories, get the data
  directly from TraderMade under their terms: <https://tradermade.com>.

To pull your own fresh ticks into the same schema, use a free TraderMade API key and
`../scripts/download_tradermade.py` (see the top-level README).
