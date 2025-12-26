.PHONY: help setup run test clean

help:
	@echo "Multi-Agent Coordination - Local Example"
	@echo ""
	@echo "Available targets:"
	@echo "  setup      - Setup local environment (copy .env file)"
	@echo "  run        - Run multi-agent coordination test"
	@echo "  test       - Run tests (placeholder)"
	@echo "  clean      - Clean up"

setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env file from .env.example"; \
		echo "Edit .env to configure agent endpoints"; \
	else \
		echo ".env file already exists"; \
	fi

run: setup
	@echo "Running multi-agent coordination test..."
	@python3 orchestrate.py

test:
	@echo "Tests not yet implemented"

clean:
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "Cleaned up"
