.PHONY: help build docker-build deploy generate manifests test clean

# Configuration
IMG ?= agentic-operator:latest
CONTROLLER_GEN ?= $(shell pwd)/bin/controller-gen
CRD_OPTIONS ?= "crd:trivialVersions=true,preserveUnknownFields=false"

# Paths
ENVTEST ?= $(shell pwd)/bin/setup-envtest

help:
	@echo "Operator build targets:"
	@echo "  build           - Build operator binary"
	@echo "  docker-build    - Build operator Docker image"
	@echo "  deploy          - Deploy operator to K8s cluster"
	@echo "  generate        - Generate CRD code"
	@echo "  manifests       - Generate CRD manifests"
	@echo "  test            - Run controller tests"
	@echo "  clean           - Clean build artifacts"

# Build operator binary
build: generate manifests
	go build -o bin/manager main.go

# Build Docker image
docker-build: build
	docker build -t ${IMG} .

# Deploy to K8s cluster
deploy: manifests
	kubectl apply -f config/crd/
	kubectl apply -f config/rbac/
	kubectl apply -f config/manager/

# Generate CRD code
generate: controller-gen
	$(CONTROLLER_GEN) object:headerFile="hack/boilerplate.go.txt" paths="./..."

# Generate CRD manifests
manifests: controller-gen
	$(CONTROLLER_GEN) $(CRD_OPTIONS) rbac:roleName=agentic-operator paths="./..." output:crd:artifacts:config=config/crd/bases

# Run tests
test: generate manifests envtest
	KUBEBUILDER_ASSETS=$(shell $(ENVTEST) use 1.24 -p path) go test ./... -coverprofile cover.out

# Controller-gen tool
controller-gen:
	test -s $(CONTROLLER_GEN) || { curl -Ss "https://raw.githubusercontent.com/kubernetes-sigs/controller-tools/master/hack/install.sh" | sh -s -- $(subst v3,,$(CONTROLLER_GEN_VERSION)); }

# Envtest setup
envtest:
	test -s $(ENVTEST) || { mkdir -p $(dir $(ENVTEST)); curl -Ss -L https://go.kubebuilder.io/tools/setup-envtest | bash -s -- latest -p path > $(ENVTEST); }

# Clean artifacts
clean:
	rm -rf bin/ cover.out
	go clean -testcache
