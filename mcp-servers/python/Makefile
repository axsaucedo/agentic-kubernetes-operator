.PHONY: help build docker-build test clean run

IMG ?= agentic-mcp-servers:latest

help:
	@echo "MCP Servers build targets:"
	@echo "  build        - Install dependencies using UV"
	@echo "  docker-build - Build MCP servers Docker image"
	@echo "  test         - Run tests"
	@echo "  clean        - Clean build artifacts"
	@echo "  run          - Run MCP servers locally"

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

# Run MCP servers locally
run:
	uv run python -m uvicorn loader:app --reload --host 0.0.0.0 --port 9000
