SHELL := /usr/bin/env bash

.PHONY: all server loader proto widgets codegen test format clean build help kill

all: server loader proto widgets codegen resources  ## Build everything

server:         ## Build Java gRPC server
	cd server && ./gradlew shadowJar -q

loader:         ## Build C loader
	$(MAKE) -C loader

proto:          ## Generate proto stubs (Python)
	buf generate

widgets:        ## Generate widget field constants from proto enum
	uv run python scripts/widget_generator.py

codegen:        ## Generate constants from RuneLite gameval
	uv run python scripts/constant_generator.py

resources:      ## Download game resources (varps, objects, graph)
	uv run python scripts/resource_generator.py

test:           ## Run all checks (ruff, basedpyright, pytest)
	uv run ruff check escape/ tests/ && uv run ruff format escape/ tests/ && uv run basedpyright escape/ && uv run pytest -q

format:         ## Auto-format code and fix linting issues
	uv run ruff format escape/ tests/ && uv run ruff check --fix --unsafe-fixes escape/ tests/ || true

clean:          ## Remove caches and build artifacts
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name htmlcov -o -name "*.egg-info" \) -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .coverage coverage.xml .grimp_cache 2>/dev/null || true
	cd server && ./gradlew clean -q
	rm -rf server/bin/
	rm -rf escape/_proto/
	rm -f escape/constants/*.py escape/constants/.version
	$(MAKE) -C loader clean
	rm -rf .venv

kill:           ## Kill RuneLite and clean up socket
	@pkill -9 -f 'runelite' 2>/dev/null || true
	@pkill -9 -f 'net.runelite' 2>/dev/null || true
	@rm -f "$${BRIDGE_SOCKET:-$$XDG_RUNTIME_DIR/bridge.sock}" 2>/dev/null || true
	@echo "RuneLite killed, socket removed"

build:          ## Build distribution packages
	uv run python -m build

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
