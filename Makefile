SHELL := /bin/bash
.DEFAULT_GOAL := check

.PHONY: check lint fmt test compose-validate preflight doctor help
.PHONY: verify extensions-list packs-list compose-gen compose-render
.PHONY: up down logs status clean install dev profile

# ──────────────────────────────────────────────────────────────────────────────
# Core targets
# ──────────────────────────────────────────────────────────────────────────────

help:
	@echo "AI Beast Makefile"
	@echo ""
	@echo "Core:"
	@echo "  make check          Run all quality gates"
	@echo "  make preflight      Run preflight checks"
	@echo "  make doctor         Diagnose environment issues"
	@echo "  make verify         Verify stack completeness"
	@echo ""
	@echo "Development:"
	@echo "  make lint           Run linters (ruff, shellcheck)"
	@echo "  make fmt            Format code"
	@echo "  make test           Run tests"
	@echo "  make dev            Start dev environment"
	@echo ""
	@echo "Docker/Compose:"
	@echo "  make compose-gen    Generate compose files"
	@echo "  make compose-render Render final compose"
	@echo "  make compose-validate Validate compose config"
	@echo "  make up             Start services"
	@echo "  make down           Stop services"
	@echo "  make logs           Tail service logs"
	@echo "  make status         Show service status"
	@echo ""
	@echo "Extensions & Packs:"
	@echo "  make extensions-list List available extensions"
	@echo "  make packs-list      List available packs"
	@echo "  make profile PROFILE=lite|full|prodish  Enable profile"
	@echo ""
	@echo "Maintenance:"
	@echo "  make install        Install dependencies"
	@echo "  make clean          Clean generated files"

preflight:
	./bin/beast preflight --verbose

doctor:
	./bin/beast doctor --verbose

verify:
	python3 scripts/00_verify_stack.py --verbose

check: preflight compose-validate lint test

# ──────────────────────────────────────────────────────────────────────────────
# Development targets
# ──────────────────────────────────────────────────────────────────────────────

lint:
	python3 -m ruff check .
	shellcheck -x bin/* scripts/*.sh scripts/lib/*.sh 2>/dev/null || true

fmt:
	python3 -m ruff format .

test:
	python3 -m pytest -q

dev:
	./bin/beast up --profile lite

install:
	pip3 install -r requirements.txt
	pip3 install -r requirements-dev.txt

# ──────────────────────────────────────────────────────────────────────────────
# Docker/Compose targets
# ──────────────────────────────────────────────────────────────────────────────

compose-gen:
	./scripts/25_compose_generate.sh --apply

compose-render:
	./scripts/24_compose_render.sh --apply

compose-validate:
	docker compose config >/dev/null 2>&1 || echo "WARN: docker compose config failed (may need generation)"

up:
	./bin/beast up

down:
	./bin/beast down

logs:
	./bin/beast logs -f

status:
	./bin/beast status

# ──────────────────────────────────────────────────────────────────────────────
# Extensions & Packs targets
# ──────────────────────────────────────────────────────────────────────────────

extensions-list:
	@echo "Available extensions:"
	@ls -1 extensions/ | grep -v README | while read ext; do \
		if [ -f "extensions/$$ext/enabled" ]; then \
			echo "  [✓] $$ext"; \
		else \
			echo "  [ ] $$ext"; \
		fi \
	done

packs-list:
	@echo "Available packs:"
	@ls -1 scripts/packs/*.sh 2>/dev/null | xargs -I{} basename {} .sh | while read pack; do \
		echo "  • $$pack"; \
	done

profile:
ifndef PROFILE
	@echo "Usage: make profile PROFILE=lite|full|prodish"
	@exit 1
endif
	./scripts/01_enable_profile.sh $(PROFILE) --apply

# ──────────────────────────────────────────────────────────────────────────────
# Maintenance targets
# ──────────────────────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache 2>/dev/null || true
	@echo "Cleaned generated files"
