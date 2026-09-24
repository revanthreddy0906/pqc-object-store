PYTHON_BIN ?= python3.12
VENV := .venv
PY := $(VENV)/bin/python
export OQS_INSTALL_PATH := $(CURDIR)/.local/liboqs

.PHONY: help setup venv liboqs env minio-build services-up services-down services-logs \
        doctor s3-smoke soak gc test test-unit test-integration lint docs clean

help:  ## list targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

setup: liboqs venv env  ## build liboqs, create the venv, create .env

venv:  ## create .venv and install the package with dev extras
	test -d $(VENV) || $(PYTHON_BIN) -m venv $(VENV)
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -e ".[dev]"

liboqs:  ## build the pinned liboqs into .local/liboqs
	bash scripts/install_liboqs.sh

env:  ## create .env with a random local MinIO password (never committed)
	@test -f .env || { sed "s/^MINIO_ROOT_PASSWORD=.*/MINIO_ROOT_PASSWORD=$$(openssl rand -hex 24)/" \
		.env.example > .env && chmod 600 .env && echo "created .env"; }

minio-build:  ## build the MinIO image from source (slow the first time)
	docker compose build minio

services-up:  ## start MinIO and wait until healthy
	docker compose up -d --wait minio

services-down:  ## stop MinIO (data volume is kept)
	docker compose down

services-logs:
	docker compose logs --tail=100 minio

doctor:  ## print and check the environment
	$(PY) -m pqcstore.cli doctor

s3-smoke:  ## raw 1 MiB upload/download SHA-256 check
	$(PY) -m pqcstore.cli s3-smoke

soak:  ## 100 consecutive encrypted round trips + orphan audit (Phase 3 exit check)
	$(PY) -m pqcstore.cli soak --runs 100

gc:  ## report and remove uncommitted data older than 60 minutes
	$(PY) -m pqcstore.cli gc

test:  ## all tests (integration tests skip if MinIO is down)
	$(PY) -m pytest

test-unit:
	$(PY) -m pytest -m "not integration"

test-integration:  ## integration tests; fail if MinIO is down
	PQC_REQUIRE_MINIO=1 $(PY) -m pytest -m integration

lint:
	$(VENV)/bin/ruff check src tests

docs:  ## rebuild docs/source-of-truth.pdf (macOS fonts; needs the docs extra)
	$(PY) -m pip install --quiet -e ".[docs]"
	cd docs && ../$(PY) build_sot.py

clean:
	rm -rf .pytest_cache .ruff_cache build dist src/*.egg-info
