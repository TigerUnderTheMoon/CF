.PHONY: install test coverage lint docker-core docker-pilot

install:
	poetry install

test:
	python -m pytest -q tests

coverage:
	python -m pytest -q tests --cov=src/fma --cov-report=term-missing --cov-report=xml --cov-fail-under=80

lint:
	python -m ruff check .
	python -m black --check .

docker-core:
	docker compose run --rm fma-core

docker-pilot:
	docker compose run --rm fma-pilot
