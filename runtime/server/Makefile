.PHONY: help build docker-build test clean run run-example-simple run-example-multi

IMG ?= agentic-runtime:latest

help:
	@echo "Runtime server build targets:"
	@echo "  build               - Install dependencies using UV"
	@echo "  docker-build        - Build runtime Docker image"
	@echo "  test                - Run tests"
	@echo "  clean               - Clean build artifacts"
	@echo "  run                 - Run server locally"
	@echo "  run-example-simple  - Run simple math agent example"
	@echo "  run-example-multi   - Run multi-agent example"

# Install dependencies
build:
	uv pip install -e .

# Build Docker image
docker-build: build
	docker build -t ${IMG} .

# Run tests
test:
	uv run pytest tests/ -v --cov=.

# Clean artifacts
clean:
	rm -rf build/ dist/ *.egg-info/ __pycache__ .pytest_cache .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Run server locally
run:
	uv run python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000

# Run simple math agent example
run-example-simple:
	cd examples/simple-math-agent && uv run python agent.py

# Run multi-agent example
run-example-multi:
	cd examples/multi-agent-coordination && uv run python -m pytest ../../tests/e2e_local_test.py
