.PHONY: install test lint docker-core docker-pilot

install:
	poetry install

test:
	poetry run pytest -q

lint:
	poetry run ruff check .
	poetry run black --check .

docker-core:
	docker compose run --rm fma-core

docker-pilot:
	docker compose run --rm fma-pilot
