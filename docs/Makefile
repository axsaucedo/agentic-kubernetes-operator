.PHONY: help install dev build preview clean rebuild-tags rebuild-tag list-tags

# Default target
help:
	@echo "KAOS Documentation Commands"
	@echo ""
	@echo "Local Development:"
	@echo "  make install        - Install npm dependencies"
	@echo "  make dev            - Start development server"
	@echo "  make build          - Build static site"
	@echo "  make preview        - Preview built site locally"
	@echo "  make clean          - Remove build artifacts"
	@echo ""
	@echo "Version Management:"
	@echo "  make list-tags      - List available version tags"
	@echo "  make rebuild-tag TAG=v1.0.0  - Trigger docs rebuild for specific tag"
	@echo "  make rebuild-tags   - Rebuild docs for all version tags (interactive)"
	@echo ""

# Install dependencies
install:
	npm install

# Start development server
dev:
	npm run dev

# Build static site
build:
	npm run build

# Preview built site
preview:
	npm run preview

# Clean build artifacts
clean:
	rm -rf .vitepress/dist .vitepress/cache node_modules/.vite

# List available version tags
list-tags:
	@echo "Available version tags (excluding v0.0.x test tags):"
	@git tag --list "v*" --sort=-v:refname | grep -v '^v0\.0\.' | head -20

# Rebuild docs for a specific tag by triggering workflow dispatch
# Usage: make rebuild-tag TAG=v1.0.0
rebuild-tag:
ifndef TAG
	$(error TAG is required. Usage: make rebuild-tag TAG=v1.0.0)
endif
	@echo "Triggering docs rebuild for tag: $(TAG)"
	@VERSION=$$(echo $(TAG) | sed 's/^v//'); \
	gh workflow run release.yaml --ref $(TAG) 2>/dev/null || \
	echo "Note: release.yaml workflow can only run on tag refs. Use rebuild-tags for bulk rebuilds."
	@echo ""
	@echo "Alternative: Create and push a lightweight commit to rebuild:"
	@echo "  1. Checkout the tag: git checkout $(TAG)"
	@echo "  2. Create a branch: git checkout -b docs-rebuild-$(TAG)"
	@echo "  3. Make a trivial change to docs/"
	@echo "  4. Commit and tag: git tag -f $(TAG) && git push --tags -f"
	@echo ""
	@echo "Or use the GitHub Actions UI to manually trigger the workflow."

# Interactive rebuild of all version tags
# This displays instructions for rebuilding all versions retrospectively
rebuild-tags:
	@echo "=== Retrospective Docs Rebuild ==="
	@echo ""
	@echo "To rebuild docs for all version tags with current config (e.g., mermaid support):"
	@echo ""
	@echo "Option 1: Re-run release workflow for each tag (via GitHub UI)"
	@echo "  1. Go to GitHub Actions > Release workflow"
	@echo "  2. Re-run for each version tag"
	@echo ""
	@echo "Option 2: Cherry-pick docs changes to version branches"
	@echo "  For each version tag that needs rebuilding:"
	@echo "  1. Create a temp branch from the tag"
	@echo "  2. Cherry-pick the docs config commits"
	@echo "  3. Force-push the tag"
	@echo "  4. This triggers the release workflow"
	@echo ""
	@echo "Option 3: Use the rebuild script (recommended for bulk updates)"
	@echo "  ./scripts/rebuild-version-docs.sh"
	@echo ""
	@echo "Available versions to rebuild:"
	@git tag --list "v*" --sort=-v:refname | grep -v '^v0\.0\.' | head -10
