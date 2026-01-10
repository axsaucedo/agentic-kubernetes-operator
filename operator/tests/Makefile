# E2E Tests - parallel by default (4 workers)
.PHONY: test test-seq clean

test:
	python -m pytest e2e/ -v -n 4 --dist loadscope

test-seq:
	python -m pytest e2e/ -v

clean:
	@echo "Cleaning up test resources..."
	-helm uninstall agentic-e2e -n agentic-e2e-system 2>/dev/null || true
	-kubectl delete namespace agentic-e2e-system --wait=false 2>/dev/null || true
	-kubectl get ns -o name | grep e2e | xargs -I{} kubectl delete {} --wait=false 2>/dev/null || true
	@sleep 3
