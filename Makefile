SHELL := /bin/sh

.PHONY: install data audit baseline lint format typecheck test ci docker-build clean help

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

docker-build:
	docker build -t pipefault:dev .

clean:
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	rm -rf data/audit artifacts mlruns mlflow.db*

help:
	@echo "make install | data | audit | baseline | lint | format | typecheck | test | ci | docker-build | clean"
