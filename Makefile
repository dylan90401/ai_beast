SHELL := /bin/bash
.DEFAULT_GOAL := check

.PHONY: check lint fmt test compose-validate preflight doctor

preflight:
	./bin/beast preflight --verbose

doctor:
	./bin/beast doctor --verbose

compose-validate:
	docker compose config

lint:
	python -m ruff check .
	shellcheck -x bin/* scripts/*.sh scripts/lib/*.sh

fmt:
	python -m ruff format .

test:
	python -m pytest -q

check: preflight compose-validate lint test
