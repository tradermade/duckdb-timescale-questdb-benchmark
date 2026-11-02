# Convenience targets. See README.md for details.
.PHONY: up down install load-duckdb load-timescaledb load-questdb load-all verify

up:            ## start TimescaleDB + QuestDB
	docker compose up -d

down:          ## stop and remove containers (keeps volumes)
	docker compose down

install:       ## install python deps
	pip install -r requirements.txt

load-duckdb:
	python scripts/load_duckdb.py

load-timescaledb:
	python scripts/load_timescaledb.py

load-questdb:
	python scripts/load_questdb.py

load-all: load-duckdb load-timescaledb load-questdb

verify:        ## print reference (ground-truth) answers from the parquet
	python scripts/reference.py
