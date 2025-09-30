SHELL := /bin/bash
# =============================================================================
# Variables
# =============================================================================

.DEFAULT_GOAL:=help
.ONESHELL:
.EXPORT_ALL_VARIABLES:
MAKEFLAGS += --no-print-directory

# Define colors and formatting
BLUE := $(shell printf "\033[1;34m")
GREEN := $(shell printf "\033[1;32m")
RED := $(shell printf "\033[1;31m")
YELLOW := $(shell printf "\033[1;33m")
NC := $(shell printf "\033[0m")
INFO := $(shell printf "$(BLUE)ℹ$(NC)")
OK := $(shell printf "$(GREEN)✓$(NC)")
WARN := $(shell printf "$(YELLOW)⚠$(NC)")
ERROR := $(shell printf "$(RED)✖$(NC)")

.PHONY: help
help:                                               ## Display this help text for Makefile
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

# =============================================================================
# Developer Utils
# =============================================================================
.PHONY: install
install:                                           ## Install the project dependencies
	@echo "${INFO} Installing dependencies..."
	@uv sync --all-extras --dev
	@echo "${OK} Installation complete! 🎉"

.PHONY: upgrade
upgrade:                                           ## Upgrade all dependencies
	@echo "${INFO} Updating all dependencies... 🔄"
	@uv lock --upgrade
	@echo "${OK} Dependencies updated 🔄"

.PHONY: clean
clean:                                             ## Cleanup temporary build artifacts
	@echo "${INFO} Cleaning working directory..."
	@rm -rf .pytest_cache .ruff_cache .hypothesis build/ dist/ .eggs/ .coverage coverage.xml coverage.json htmlcov/ .mypy_cache >/dev/null 2>&1
	@find . -name '*.egg-info' -exec rm -rf {} + >/dev/null 2>&1
	@find . -name '*.pyc' -exec rm -f {} + >/dev/null 2>&1
	@find . -name '__pycache__' -exec rm -rf {} + >/dev/null 2>&1
	@echo "${OK} Working directory cleaned"

# =============================================================================
# Tests, Linting, Coverage
# =============================================================================
.PHONY: lint
lint:                                              ## Run ruff linting
	@echo "${INFO} Running linting checks... 🔎"
	@uv run ruff check
	@echo "${OK} Linting checks passed ✨"

.PHONY: format
format:                                            ## Run code formatting
	@echo "${INFO} Running code formatters... 🔧"
	@uv run ruff format
	@uv run ruff check --fix
	@echo "${OK} Code formatting complete ✨"

.PHONY: typecheck
typecheck:                                         ## Run mypy type checking
	@echo "${INFO} Running type checks... 🔍"
	@uv run mypy app
	@echo "${OK} Type checks passed ✨"

.PHONY: test
test:                                              ## Run the tests
	@echo "${INFO} Running test cases... 🧪"
	@uv run pytest tests --quiet
	@echo "${OK} Tests passed ✨"

# =============================================================================
# Local Infrastructure
# =============================================================================
.PHONY: start-infra
start-infra:                                       ## Start local containers (AlloyDB Omni + Valkey)
	@echo "${INFO} Starting local infrastructure... 🚀"
	@docker compose -f tools/deploy/docker/docker-compose.infra.yml up -d --force-recreate
	@echo "${OK} Infrastructure is ready"

.PHONY: stop-infra
stop-infra:                                        ## Stop local containers
	@echo "${INFO} Stopping infrastructure... 🛑"
	@docker compose -f tools/deploy/docker/docker-compose.infra.yml down
	@echo "${OK} Infrastructure stopped"

.PHONY: wipe-infra
wipe-infra:                                        ## Remove local container info
	@echo "${INFO} Wiping infrastructure... 🧹"
	@docker compose -f tools/deploy/docker/docker-compose.infra.yml down -v --remove-orphans
	@echo "${OK} Infrastructure wiped clean"

.PHONY: infra-logs
infra-logs:                                        ## Tail development infrastructure logs
	@echo "${INFO} Tailing infrastructure logs... 📋"
	@docker compose -f tools/deploy/docker/docker-compose.infra.yml logs -f

# =============================================================================
# Database Operations
# =============================================================================
.PHONY: db-init
db-init:                                           ## Initialize database migrations
	@echo "${INFO} Initializing database migrations... 🗃️"
	@uv run app db init
	@echo "${OK} Database migrations initialized"

.PHONY: db-migrate
db-migrate:                                        ## Create new migration
	@echo "${INFO} Creating database migration... 📝"
	@uv run app db make-migrations --message "$(message)"
	@echo "${OK} Migration created"

.PHONY: db-upgrade
db-upgrade:                                        ## Apply database migrations
	@echo "${INFO} Applying database migrations... ⬆️"
	@uv run app db upgrade
	@echo "${OK} Database migrations applied"

.PHONY: db-reset
db-reset: wipe-infra start-infra                   ## Reset database (wipe and recreate)
	@echo "${INFO} Resetting database... 🔄"
	@sleep 5  # Wait for container to be ready
	@uv run app db upgrade
	@echo "${OK} Database reset complete"

# =============================================================================
# Application Operations
# =============================================================================
.PHONY: dev
dev:                                               ## Run development server
	@echo "${INFO} Starting development server... 🚀"
	@uv run app --reload

.PHONY: shell
shell:                                             ## Open application shell
	@echo "${INFO} Opening application shell... 💻"
	@uv run python -c "from app.main import create_app; app = create_app(); import IPython; IPython.embed()"