-- QuestDB schema for the sample forex quotes (reference; load_questdb.py applies this).
-- WAL table, partitioned by day, with deduplication on (designated timestamp, symbol, capture_id):
-- replays collapse, but two genuine same-millisecond quotes (distinct capture_id) are both kept.

CREATE TABLE quotes (
  symbol         SYMBOL,
  provider_ts    TIMESTAMP,
  provider_ts_ms LONG,
  bid            DOUBLE,
  ask            DOUBLE,
  capture_id     LONG
) TIMESTAMP(provider_ts) PARTITION BY DAY WAL
  DEDUP UPSERT KEYS(provider_ts, symbol, capture_id);
