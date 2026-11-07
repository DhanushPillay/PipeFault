SHELL := /bin/sh

.PHONY: install data audit baseline lint format typecheck test ci smoke reproduce-check docker-build clean help
install:
	uv sync --all-extras

data:
	uv run pipefault data download

audit:
	uv run pipefault data audit

baseline:
	uv run pipefault baseline

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy src

test:
	uv run pytest

ci: lint typecheck test

smoke:
	uv run python scripts/make_tlc_fixture.py --out tests/fixtures --rows-per-month 200
	PIPEFAULT_DATA_DIR=tests/fixtures uv run pipefault data manifest
	PIPEFAULT_DATA_DIR=tests/fixtures uv run pipefault data audit --dataset tlc
	PIPEFAULT_DATA_DIR=tests/fixtures uv run python scripts/smoke_experiment.py --rounds 50

reproduce-check:
	uv run python scripts/make_tlc_fixture.py --out tests/fixtures --rows-per-month 200
	PIPEFAULT_DATA_DIR=tests/fixtures uv run pipefault data manifest
	PIPEFAULT_DATA_DIR=tests/fixtures uv run pipefault baseline --seed 42 --train-size 200 --val-size 100 --test-size 100 --rounds 50 --no-mlflow
	cp artifacts/baseline/tlc.json /tmp/run1.json
	PIPEFAULT_DATA_DIR=tests/fixtures uv run pipefault baseline --seed 42 --train-size 200 --val-size 100 --test-size 100 --rounds 50 --no-mlflow
	uv run python -c "import json; a=json.load(open('/tmp/run1.json')); b=json.load(open('artifacts/baseline/tlc.json')); [(__import__('sys').exit(f'non-det {s}/{m}/{k}') if abs(a['metrics'][s][m][k]-b['metrics'][s][m][k])>1e-6*max(1,abs(a['metrics'][s][m][k])) else None) for s in ('validation','test') for m in ('global_median','zone_median','lightgbm') for k in ('rmse','mae','r2')]; print('reproducibility: OK')"
docker-build:
	docker build -t pipefault:dev .

clean:
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	rm -rf data/audit artifacts mlruns mlflow.db*

help:
	@echo "make install | data | audit | baseline | lint | format | typecheck | test | ci | smoke | reproduce-check | docker-build | clean"