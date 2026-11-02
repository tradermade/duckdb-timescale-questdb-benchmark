-- TimescaleDB schema for the sample forex quotes (reference; load_timescaledb.py applies this).
-- Load the data BEFORE adding the unique constraint + index for a faster COPY.

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE quotes (
  symbol         text              NOT NULL,
  provider_ts_ms bigint            NOT NULL,
  provider_ts    timestamptz       NOT NULL,   -- the hypertable's time dimension (index this, not the ms int)
  bid            double precision  NOT NULL,
  ask            double precision  NOT NULL,
  capture_id     bigint            NOT NULL
);

SELECT create_hypertable('quotes', 'provider_ts', chunk_time_interval => interval '1 day');

-- ...COPY the rows here...

-- Replay-safe uniqueness. capture_id keeps two genuine same-millisecond quotes distinct,
-- while a true replayed row collapses. Keying on (provider_ts, symbol) alone would drop real ticks.
ALTER TABLE quotes ADD CONSTRAINT quotes_uq UNIQUE (provider_ts, symbol, capture_id);

-- Fast "latest per symbol" and history-page queries:
CREATE INDEX quotes_sym_ts ON quotes (symbol, provider_ts DESC);
ANALYZE quotes;
