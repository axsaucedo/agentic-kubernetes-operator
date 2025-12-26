.PHONY: help build docker-build docker-build-operator docker-build-runtime docker-build-mcp-servers test deploy clean

# Default target
help:
	@echo "Agentic Kubernetes Operator - Build Orchestration"
	@echo ""
	@echo "Available targets:"
	@echo "  build                    - Build all components"
	@echo "  docker-build             - Build all Docker images"
	@echo "  docker-build-operator    - Build operator Docker image"
	@echo "  docker-build-runtime     - Build runtime Docker image"
	@echo "  docker-build-mcp-servers - Build MCP servers Docker image"
	@echo "  test                     - Run all tests"
	@echo "  deploy                   - Deploy operator to K8s cluster"
	@echo "  clean                    - Clean all build artifacts"
	@echo "  help                     - Show this help message"

# Build all components
build:
	@echo "Building all components..."
	cd operator && make build
	cd runtime/server && make build
	cd mcp-servers/python && make build

# Docker builds
docker-build: docker-build-operator docker-build-runtime docker-build-mcp-servers
	@echo "All Docker images built successfully"

docker-build-operator:
	@echo "Building operator Docker image..."
	cd operator && make docker-build

docker-build-runtime:
	@echo "Building runtime Docker image..."
	cd runtime/server && make docker-build

docker-build-mcp-servers:
	@echo "Building MCP servers Docker image..."
	cd mcp-servers/python && make docker-build

# Test all components
test:
	@echo "Running all tests..."
	cd operator && make test
	cd runtime/server && make test
	cd mcp-servers/python && make test
	python -m pytest tests/ -v

# Deploy operator to K8s
deploy:
	@echo "Deploying operator to Kubernetes..."
	cd operator && make deploy

# Clean all build artifacts
clean:
	@echo "Cleaning all build artifacts..."
	cd operator && make clean
	cd runtime/server && make clean
	cd mcp-servers/python && make clean
	rm -rf build/ dist/ *.egg-info/

# Development setup
setup-dev:
	@echo "Setting up local development environment..."
	./scripts/setup-local-dev.sh
