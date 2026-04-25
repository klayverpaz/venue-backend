.PHONY: install install-postgres install-mssql install-ai run test lint \
        migrate-new migrate-up migrate-down migrate-history redis-dev clean

PYTHON  ?= .venv/bin/python
PIP     ?= .venv/bin/pip
ALEMBIC ?= .venv/bin/alembic
PYTEST  ?= .venv/bin/pytest

install:
	uv venv --seed --python 3.12
	$(PIP) install -r requirements.txt -r requirements-dev.txt

install-postgres:
	$(PIP) install -r requirements-postgres.txt

install-mssql:
	$(PIP) install -r requirements-mssql.txt

install-ai:
	$(PIP) install -r requirements-ai.txt

run:
	$(PYTHON) -m app.main

redis-dev:
	docker run -d --name redis-dev -p 6379:6379 redis/redis-stack-server:latest

test:
	$(PYTEST)

lint:
	$(PYTHON) -m ruff check app tests
	$(PYTHON) -m mypy app

migrate-new:
	@test -n "$(msg)" || (echo "Uso: make migrate-new msg='descricao'" && exit 1)
	$(ALEMBIC) revision --autogenerate -m "$(msg)"

migrate-up:
	$(ALEMBIC) upgrade head

migrate-down:
	$(ALEMBIC) downgrade -1

migrate-history:
	$(ALEMBIC) history

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
