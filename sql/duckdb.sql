-- DuckDB schema (reference; load_duckdb.py builds the table straight from the parquet).

CREATE TABLE quotes (
  symbol         VARCHAR,
  provider_ts_ms BIGINT,
  provider_ts    TIMESTAMP,
  bid            DOUBLE,
  ask            DOUBLE,
  capture_id     BIGINT
);

-- Optional retry-safe variant. A unique index makes DuckDB reject duplicate rows itself,
-- but it inflates the database file a lot (~19x in our tests). For DuckDB it is usually
-- cheaper to deduplicate in the loading code and keep the plain table.
-- ALTER TABLE quotes ADD PRIMARY KEY (symbol, provider_ts_ms, capture_id);
