# E2E Tests - parallel by default
NPROC := $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

.PHONY: test test-seq install

test:
	python -m pytest e2e/ -v -n $(NPROC) --dist loadscope

test-seq:
	python -m pytest e2e/ -v

install:
	pip install -e ".[dev]"
