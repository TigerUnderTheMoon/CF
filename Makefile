.PHONY: install test coverage lint docker-core docker-pilot

install:
	poetry install

test:
	poetry run pytest -q

coverage:
	poetry run pytest -q --cov=src/fma --cov-report=term-missing --cov-report=xml --cov-fail-under=80

lint:
	poetry run ruff check .
	poetry run black --check .

docker-core:
	docker compose run --rm fma-core

docker-pilot:
	docker compose run --rm fma-pilot
