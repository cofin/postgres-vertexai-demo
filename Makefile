SHELL := /bin/bash

# =============================================================================
# Configuration and Environment Variables
# =============================================================================

.DEFAULT_GOAL := help
.ONESHELL:
.EXPORT_ALL_VARIABLES:
MAKEFLAGS += --no-print-directory
FRONTEND_DIR := src/resources

# Detect Rodete and configure public package indexes
ifneq ($(shell grep -s -q "rodete" /etc/os-release && echo "yes"),)
export NPM_CONFIG_REGISTRY=https://registry.npmjs.org
export PIP_INDEX_URL=https://pypi.org/simple
export UV_INDEX_URL=https://pypi.org/simple
export UV_NO_CONFIG=1
endif

# ----------------------------------------------------------------------------
# Display Formatting and Colors
# ----------------------------------------------------------------------------
BLUE := $(shell printf "\033[1;34m")
GREEN := $(shell printf "\033[1;32m")
RED := $(shell printf "\033[1;31m")
YELLOW := $(shell printf "\033[1;33m")
NC := $(shell printf "\033[0m")
INFO := $(shell printf "$(BLUE)ℹ$(NC)")
OK := $(shell printf "$(GREEN)✓$(NC)")
WARN := $(shell printf "$(YELLOW)⚠$(NC)")
ERROR := $(shell printf "$(RED)✖$(NC)")

# =============================================================================
# Help and Documentation
# =============================================================================
.PHONY: help
help: ## Display this help text for Makefile
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

# =============================================================================
# Installation and Environment Setup
# =============================================================================
.PHONY: install-uv
install-uv: ## Install latest version of uv (idempotent)
	@if command -v uv >/dev/null 2>&1; then \
		echo "${OK} UV already installed: $$(uv --version)"; \
	else \
		echo "${INFO} Installing uv..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1; \
		echo "${OK} UV installed successfully"; \
	fi

.PHONY: install
install: destroy clean ## Install the project, dependencies, and pre-commit
	@echo "${INFO} Starting fresh installation..."
	@uv python pin 3.12 >/dev/null 2>&1
	@uv venv >/dev/null 2>&1
	@uv sync --all-extras --dev
	@echo "${OK} Installation complete! 🎉"

.PHONY: destroy
destroy: ## Remove venv and node_modules
	@echo "${INFO} Destroying virtual environment... 🗑️"
	@uv run pre-commit clean >/dev/null 2>&1 || true
	@rm -rf .venv
	@rm -rf node_modules
	@echo "${OK} Virtual environment destroyed 🗑️"

# =============================================================================
# Dependency Management
# =============================================================================
.PHONY: upgrade
upgrade: ## Upgrade all dependencies to latest stable versions
	@echo "${INFO} Updating all dependencies... 🔄"
	@uv lock --upgrade
	@echo "${OK} Dependencies updated 🔄"
	@uv run pre-commit autoupdate
	@echo "${OK} Updated Pre-commit hooks 🔄"

.PHONY: lock
lock: ## Rebuild lockfiles from scratch
	@echo "${INFO} Rebuilding lockfiles... 🔄"
	@uv lock --upgrade >/dev/null 2>&1
	@echo "${OK} Lockfiles updated"

# =============================================================================
# Build and Release
# =============================================================================
.PHONY: build
build: ## Build the package
	@echo "${INFO} Building package... 📦"
	@uv build >/dev/null 2>&1
	@echo "${OK} Package build complete"

# =============================================================================
# Cleaning and Maintenance
# =============================================================================
.PHONY: clean
clean: ## Cleanup temporary build artifacts
	@echo "${INFO} Cleaning working directory... 🧹"
	@rm -rf .pytest_cache .ruff_cache .hypothesis build/ -rf dist/ .eggs/ .coverage coverage.xml coverage.json htmlcov/ .pytest_cache tests/.pytest_cache tests/**/.pytest_cache .mypy_cache .unasyncd_cache/ .auto_pytabs_cache >/dev/null 2>&1
	@find . -name '*.egg-info' -exec rm -rf {} + >/dev/null 2>&1
	@find . -type f -name '*.egg' -exec rm -f {} + >/dev/null 2>&1
	@find . -name '*.pyc' -exec rm -f {} + >/dev/null 2>&1
	@find . -name '*.pyo' -exec rm -f {} + >/dev/null 2>&1
	@find . -name '*~' -exec rm -f {} + >/dev/null 2>&1
	@find . -name '__pycache__' -exec rm -rf {} + >/dev/null 2>&1
	@find . -name '.ipynb_checkpoints' -exec rm -rf {} + >/dev/null 2>&1
	@echo "${OK} Working directory cleaned"

# =============================================================================
# Tests, Linting, Coverage
# =============================================================================
.PHONY: test
test: ## Run the tests
	@echo "${INFO} Running test cases... 🧪"
	@uv run pytest -n 2 --dist=loadgroup tests
	@echo "${OK} Tests complete ✨"

.PHONY: coverage
coverage: ## Run tests with coverage report
	@echo "${INFO} Running tests with coverage... 📊"
	@uv run pytest --cov -n 2 --dist=loadgroup --quiet
	@uv run coverage html >/dev/null 2>&1
	@uv run coverage xml >/dev/null 2>&1
	@echo "${OK} Coverage report generated ✨"

.PHONY: lint
lint: ## Run all linting and type checking
	@echo "${INFO} Running pre-commit checks... 🔎"
	@uv run pre-commit run --color=always --all-files
	@echo "${OK} Pre-commit checks passed ✨"
	@echo "${INFO} Running type checkers... 🔍"
	@uv run mypy src/app tools manage.py
	@uv run pyright src/app tools manage.py
	@$(MAKE) frontend-typecheck
	@echo "${OK} All linting and type checks complete ✨"

.PHONY: format
format: ## Run code formatters
	@echo "${INFO} Running code formatters... 🔧"
	@uv run ruff check --fix --unsafe-fixes
	@echo "${OK} Code formatting complete ✨"

.PHONY: mypy
mypy: ## Run mypy type checker using local packages
	@echo "${INFO} Running mypy type checker... 🔍"
	@uv run mypy src/app tools manage.py
	@echo "${OK} Mypy type checking complete ✨"

.PHONY: pyright
pyright: ## Run pyright type checker using local packages
	@echo "${INFO} Running pyright type checker... 🔍"
	@uv run pyright src/app tools manage.py
	@echo "${OK} Pyright type checking complete ✨"

.PHONY: typecheck
typecheck: mypy pyright ## Run all type checkers
	@echo "${OK} All type checks complete ✨"

# =============================================================================
# Local Infrastructure (PostgreSQL/AlloyDB Docker)
# =============================================================================
.PHONY: start-infra
start-infra: ## Start local PostgreSQL/AlloyDB container
	@echo "${INFO} Starting local PostgreSQL instance..."
	@uv run python manage.py infra start --recreate
	@echo "${OK} Infrastructure started"

.PHONY: stop-infra
stop-infra: ## Stop local PostgreSQL container
	@echo "${INFO} Stopping local PostgreSQL instance..."
	@uv run python manage.py infra stop
	@echo "${OK} Infrastructure stopped"

.PHONY: restart-infra
restart-infra: ## Restart local PostgreSQL container
	@echo "${INFO} Restarting local PostgreSQL instance..."
	@uv run python manage.py infra restart
	@echo "${OK} Infrastructure restarted"

.PHONY: infra-status
infra-status: ## Check PostgreSQL container status
	@echo "${INFO} Checking PostgreSQL container status..."
	@uv run python manage.py infra status

.PHONY: wipe-infra
wipe-infra: ## Remove local PostgreSQL container and data
	@echo "${WARN} Wiping local PostgreSQL instance..."
	@uv run python manage.py infra wipe
	@echo "${OK} Infrastructure wiped"

.PHONY: infra-logs
infra-logs: ## Tail development infrastructure logs
	@echo "${INFO} Tailing logs for local PostgreSQL instance..."
	@uv run python manage.py infra logs --follow

.PHONY: infra-health
infra-health: ## Check health of PostgreSQL deployment
	@echo "${INFO} Checking PostgreSQL health..."
	@uv run python manage.py database health

.PHONY: infra-verify
infra-verify: ## Verify AlloyDB extensions and engine parameters
	@echo "${INFO} Checking extensions..."
	@docker exec -i cymbal_coffee_pg-db-1 psql -U app -d app -c "\dx" | grep -E "scann|vector|google_ml"
	@echo "${INFO} Checking columnar engine..."
	@docker exec -i cymbal_coffee_pg-db-1 psql -U app -d app -c "SHOW google_columnar_engine.enabled;"
	@echo "${INFO} Checking ML Agent process..."
	@docker exec -i cymbal_coffee_pg-db-1 psql -U app -d app -c "SHOW omni_enable_ml_agent_process;"
	@echo "${INFO} Checking registered models..."
	@docker exec -i cymbal_coffee_pg-db-1 psql -U app -d app -c "SELECT id, provider, model_type FROM google_ml.models;"

# =============================================================================
# Database Operations
# =============================================================================
.PHONY: db-migrate
db-migrate: ## Create new migration
	@echo "${INFO} Creating database migration... 📝"
	@uv run python manage.py database create-migration --message "$(message)"
	@echo "${OK} Migration created"

.PHONY: db-upgrade
db-upgrade: ## Apply database migrations
	@echo "${INFO} Applying database migrations... ⬆️"
	@uv run python manage.py database upgrade --no-prompt
	@echo "${OK} Database migrations applied"

.PHONY: db-downgrade
db-downgrade: ## Rollback database migration
	@echo "${INFO} Rolling back database migration... ⬇️"
	@uv run python manage.py database downgrade -1
	@echo "${OK} Database migration rolled back"

.PHONY: db-reset
db-reset: wipe-infra start-infra ## Reset database (wipe and recreate)
	@echo "${INFO} Resetting database... 🔄"
	@sleep 5
	@uv run python manage.py database upgrade --no-prompt
	@echo "${OK} Database reset complete"

.PHONY: db-connect-test
db-connect-test: ## Test database connection
	@echo "${INFO} Testing database connection..."
	@uv run python manage.py database connect test

.PHONY: db-connect-info
db-connect-info: ## Display database connection information
	@uv run python manage.py database connect info

# =============================================================================
# Frontend and Assets
# =============================================================================
.PHONY: assets-build
assets-build: ## Build assets via Litestar assets CLI
	@echo "${INFO} Building assets via manage.py... 📦"
	@uv run python manage.py assets build
	@echo "${OK} Assets build complete ✨"

.PHONY: frontend-typecheck
frontend-typecheck: ## Run frontend TypeScript type checks
	@echo "${INFO} Running frontend type checks... 🔍"
	@cd $(FRONTEND_DIR) && npx tsc --noEmit
	@echo "${OK} Frontend type checks complete ✨"

# =============================================================================
# Application Operations
# =============================================================================
.PHONY: dev
dev: ## Run development server
	@echo "${INFO} Starting development server... 🚀"
	@uv run app --reload

.PHONY: shell
shell: ## Open application shell
	@echo "${INFO} Opening application shell... 💻"
	@uv run python -c "from app.main import create_app; app = create_app(); import IPython; IPython.embed()"
