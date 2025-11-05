# Enterprise Testing Suite Makefile for Tools Package
# ===================================================
# 
# This Makefile provides a comprehensive set of commands for enterprise-level
# testing automation, quality assurance, and CI/CD integration.
# 
# Usage: make <target>
# For help: make help
#
# Philosophy: Modular, scalable, and enterprise-ready testing automation

.PHONY: help clean install test coverage lint security format check-format
.PHONY: test-unit test-integration test-api test-e2e test-performance test-stress
.PHONY: test-all test-quick test-smoke test-regression test-parallel
.PHONY: report-html report-json report-enterprise report-dashboard
.PHONY: generate-test-report generate-pdf-report test-report-all
.PHONY: setup-dev setup-ci setup-prod validate-env
.PHONY: docker-test docker-build docker-clean
.PHONY: benchmark profile monitor
.PHONY: pre-commit post-deploy health-check
.PHONY: enterprise-audit compliance-check license-check

# =============================================================================
# Configuration Variables
# =============================================================================

# Python Configuration
PYTHON := python3
PIP := pip3
PYTEST := pytest
VENV_DIR := venv

# Project Configuration
PROJECT_NAME := tools
PACKAGE_DIR := ice_pipeline
TEST_DIR := tests
SCRIPTS_DIR := scripts
REPORTS_DIR := reports
COVERAGE_DIR := $(REPORTS_DIR)/coverage
ARTIFACTS_DIR := artifacts

# Testing Configuration
TEST_TIMEOUT := 300
PARALLEL_WORKERS := auto
COVERAGE_THRESHOLD := 80
PERFORMANCE_THRESHOLD := 60.0

# Enterprise Configuration
ENTERPRISE_CONFIG := enterprise_config.yml
QUALITY_GATES_CONFIG := quality_gates.yml
COMPLIANCE_CONFIG := compliance.yml

# Docker Configuration
DOCKER_IMAGE := $(PROJECT_NAME):test
DOCKER_REGISTRY := your-registry.com

# CI/CD Configuration
CI_REPORTS_FORMAT := junit,html,json
ENTERPRISE_REPORTS_FORMAT := html,json,pdf

# =============================================================================
# Help Target
# =============================================================================

help: ## Display this help message
	@echo "🏢 Enterprise Testing Suite for $(PROJECT_NAME)"
	@echo "=================================================="
	@echo ""
	@echo "Available targets:"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Examples:"
	@echo "  make test-all          # Run complete test suite"
	@echo "  make test-quick        # Run quick validation tests"
	@echo "  make report-enterprise # Generate enterprise dashboard"
	@echo "  make test-report-all   # Run all tests with PDF report"
	@echo "  make generate-pdf-report # Generate PDF from existing results"
	@echo "  make setup-dev         # Setup development environment"
	@echo ""

# =============================================================================
# Environment Setup
# =============================================================================

setup-dev: clean install-dev setup-hooks validate-env ## Setup development environment
	@echo "🔧 Setting up development environment..."
	@$(PYTHON) -m venv $(VENV_DIR) || echo "Virtual environment already exists"
	@echo "✅ Development environment ready!"
	@echo ""
	@echo "To activate: source $(VENV_DIR)/bin/activate"
	@echo "To run tests: make test-quick"

setup-ci: clean install-ci validate-env ## Setup CI environment
	@echo "🚀 Setting up CI environment..."
	@$(PIP) install -r requirements-test.txt --no-cache-dir
	@echo "✅ CI environment ready!"

setup-prod: clean install-prod validate-env ## Setup production testing environment
	@echo "🏭 Setting up production testing environment..."
	@$(PIP) install -r requirements.txt -r requirements-test.txt --no-cache-dir
	@echo "✅ Production testing environment ready!"

install: ## Install dependencies
	@echo "📦 Installing dependencies..."
	@$(PIP) install -r requirements.txt

install-dev: ## Install development dependencies
	@echo "📦 Installing development dependencies..."
	@$(PIP) install -r requirements.txt -r requirements-test.txt

install-ci: ## Install CI dependencies with optimization
	@echo "📦 Installing CI dependencies..."
	@$(PIP) install --upgrade pip setuptools wheel
	@$(PIP) install -r requirements-test.txt --no-cache-dir

install-prod: ## Install production dependencies
	@echo "📦 Installing production dependencies..."
	@$(PIP) install -r requirements.txt --no-cache-dir

setup-hooks: ## Setup git hooks for quality assurance
	@echo "🪝 Setting up git hooks..."
	@pre-commit install || echo "pre-commit not available, skipping hooks"
	@echo "✅ Git hooks configured!"

validate-env: ## Validate environment setup
	@echo "🔍 Validating environment..."
	@$(PYTHON) --version
	@$(PIP) --version
	@$(PYTEST) --version
	@echo "✅ Environment validation complete!"

# =============================================================================
# Core Testing Targets
# =============================================================================

test: test-unit ## Run default test suite (unit tests)

test-all: test-unit test-integration test-api test-e2e test-performance ## Run complete test suite
	@echo "🎯 Running complete test suite..."
	@echo "✅ All tests completed!"

test-quick: test-smoke ## Run quick validation tests
	@echo "⚡ Running quick validation tests..."
	@$(PYTEST) $(TEST_DIR)/unit/ -x --tb=short -q
	@echo "✅ Quick tests completed!"

test-smoke: ## Run smoke tests for basic validation
	@echo "💨 Running smoke tests..."
	@$(PYTEST) -m "smoke" --tb=short -q
	@echo "✅ Smoke tests completed!"

test-regression: ## Run regression test suite
	@echo "🔄 Running regression tests..."
	@$(PYTEST) -m "regression" --tb=short -v
	@echo "✅ Regression tests completed!"

test-parallel: ## Run tests in parallel for faster execution
	@echo "⚡ Running tests in parallel..."
	@$(PYTEST) $(TEST_DIR)/ -n $(PARALLEL_WORKERS) --tb=short
	@echo "✅ Parallel tests completed!"

# =============================================================================
# Specific Test Categories
# =============================================================================

test-unit: ## Run unit tests
	@echo "🔧 Running unit tests..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTEST) $(TEST_DIR)/unit/ \
		--cov=$(PACKAGE_DIR) \
		--cov-report=html:$(COVERAGE_DIR)/unit \
		--cov-report=xml:$(COVERAGE_DIR)/unit-coverage.xml \
		--cov-report=term-missing \
		--cov-fail-under=$(COVERAGE_THRESHOLD) \
		--junit-xml=$(REPORTS_DIR)/unit-tests.xml \
		--html=$(REPORTS_DIR)/unit-tests.html \
		--timeout=$(TEST_TIMEOUT) \
		-v

test-integration: ## Run integration tests
	@echo "🔗 Running integration tests..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTEST) $(TEST_DIR)/integration/ \
		--junit-xml=$(REPORTS_DIR)/integration-tests.xml \
		--html=$(REPORTS_DIR)/integration-tests.html \
		--timeout=$(TEST_TIMEOUT) \
		-v

test-api: ## Run API tests
	@echo "🌐 Running API tests..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTEST) $(TEST_DIR)/api/ \
		--junit-xml=$(REPORTS_DIR)/api-tests.xml \
		--html=$(REPORTS_DIR)/api-tests.html \
		--timeout=$(TEST_TIMEOUT) \
		-v

test-e2e: ## Run end-to-end tests
	@echo "🎭 Running end-to-end tests..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTEST) $(TEST_DIR)/e2e/ \
		--junit-xml=$(REPORTS_DIR)/e2e-tests.xml \
		--html=$(REPORTS_DIR)/e2e-tests.html \
		--timeout=600 \
		-v

test-performance: ## Run performance tests
	@echo "⚡ Running performance tests..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTEST) $(TEST_DIR)/performance/ \
		-m "not stress" \
		--junit-xml=$(REPORTS_DIR)/performance-tests.xml \
		--html=$(REPORTS_DIR)/performance-tests.html \
		--benchmark-json=$(REPORTS_DIR)/benchmark-results.json \
		--timeout=$(TEST_TIMEOUT) \
		-v

test-stress: ## Run stress tests (long-running)
	@echo "💪 Running stress tests..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTEST) $(TEST_DIR)/performance/ \
		-m "stress" \
		--junit-xml=$(REPORTS_DIR)/stress-tests.xml \
		--html=$(REPORTS_DIR)/stress-tests.html \
		--timeout=1800 \
		-v

test-business: ## Run business logic tests
	@echo "💼 Running business logic tests..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTEST) $(TEST_DIR)/business/ \
		--junit-xml=$(REPORTS_DIR)/business-tests.xml \
		--html=$(REPORTS_DIR)/business-tests.html \
		--timeout=$(TEST_TIMEOUT) \
		-v

# =============================================================================
# Code Quality & Security
# =============================================================================

lint: ## Run linting checks
	@echo "🔍 Running linting checks..."
	@flake8 $(PACKAGE_DIR) $(TEST_DIR) --count --statistics
	@mypy $(PACKAGE_DIR) --install-types --non-interactive || true
	@echo "✅ Linting completed!"

format: ## Format code with black and isort
	@echo "🎨 Formatting code..."
	@black $(PACKAGE_DIR) $(TEST_DIR) $(SCRIPTS_DIR)
	@isort $(PACKAGE_DIR) $(TEST_DIR) $(SCRIPTS_DIR)
	@echo "✅ Code formatting completed!"

check-format: ## Check code formatting without making changes
	@echo "🔍 Checking code formatting..."
	@black --check --diff $(PACKAGE_DIR) $(TEST_DIR) $(SCRIPTS_DIR)
	@isort --check-only --diff $(PACKAGE_DIR) $(TEST_DIR) $(SCRIPTS_DIR)
	@echo "✅ Format check completed!"

security: ## Run security scans
	@echo "🔒 Running security scans..."
	@mkdir -p $(REPORTS_DIR)/security
	@bandit -r $(PACKAGE_DIR) -f json -o $(REPORTS_DIR)/security/bandit-report.json || true
	@bandit -r $(PACKAGE_DIR) -ll
	@safety check --json --output $(REPORTS_DIR)/security/safety-report.json || true
	@safety check
	@echo "✅ Security scan completed!"

# =============================================================================
# Coverage Analysis
# =============================================================================

coverage: ## Generate comprehensive coverage report
	@echo "📊 Generating coverage report..."
	@mkdir -p $(COVERAGE_DIR)
	@$(PYTEST) $(TEST_DIR)/ \
		--cov=$(PACKAGE_DIR) \
		--cov-report=html:$(COVERAGE_DIR) \
		--cov-report=xml:$(COVERAGE_DIR)/coverage.xml \
		--cov-report=json:$(COVERAGE_DIR)/coverage.json \
		--cov-report=term-missing \
		--cov-fail-under=$(COVERAGE_THRESHOLD)
	@echo "✅ Coverage report generated!"
	@echo "📁 HTML Report: $(COVERAGE_DIR)/index.html"

coverage-xml: ## Generate XML coverage report for CI
	@echo "📊 Generating XML coverage report..."
	@mkdir -p $(COVERAGE_DIR)
	@$(PYTEST) $(TEST_DIR)/ \
		--cov=$(PACKAGE_DIR) \
		--cov-report=xml:$(COVERAGE_DIR)/coverage.xml \
		--quiet
	@echo "✅ XML coverage report generated!"

# =============================================================================
# Enterprise Reporting
# =============================================================================

report-html: ## Generate HTML test report
	@echo "📊 Generating HTML test report..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTEST) $(TEST_DIR)/ \
		--html=$(REPORTS_DIR)/test-report.html \
		--self-contained-html

report-json: ## Generate JSON test report for API consumption
	@echo "📊 Generating JSON test report..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTEST) $(TEST_DIR)/ \
		--json-report --json-report-file=$(REPORTS_DIR)/test-report.json

report-enterprise: security coverage ## Generate enterprise dashboard report
	@echo "🏢 Generating enterprise test report..."
	@mkdir -p $(REPORTS_DIR) $(ARTIFACTS_DIR)
	# Run all test categories and collect artifacts
	@$(MAKE) test-all --ignore-errors
	@$(MAKE) security --ignore-errors
	# Generate enterprise report
	@$(PYTHON) $(SCRIPTS_DIR)/enterprise_test_reporter.py \
		--artifacts-dir $(REPORTS_DIR) \
		--output-dir $(REPORTS_DIR)/enterprise \
		--format $(ENTERPRISE_REPORTS_FORMAT) \
		--include-metrics \
		--include-trends
	@echo "✅ Enterprise report generated!"
	@echo "📁 Dashboard: $(REPORTS_DIR)/enterprise/enterprise_test_report.html"

report-dashboard: ## Update enterprise dashboard with latest results
	@echo "📈 Updating enterprise dashboard..."
	@$(PYTHON) $(SCRIPTS_DIR)/update_enterprise_dashboard.py \
		--reports-dir $(REPORTS_DIR)/enterprise \
		--dashboard-config $(ENTERPRISE_CONFIG)
	@echo "✅ Dashboard updated!"

quality-analysis: ## Perform comprehensive quality analysis
	@echo "🎯 Performing quality analysis..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) $(SCRIPTS_DIR)/analyze_test_quality.py \
		--artifacts-dir $(REPORTS_DIR) \
		--output $(REPORTS_DIR)/quality_analysis.json \
		--config $(QUALITY_GATES_CONFIG)
	@echo "✅ Quality analysis completed!"
	@echo "📁 Analysis: $(REPORTS_DIR)/quality_analysis.json"

generate-test-report: ## Generate comprehensive test report with PDF output
	@echo "📑 Generating comprehensive test report..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) $(SCRIPTS_DIR)/test_report_generator.py \
		--project-name "$(PROJECT_NAME)"
	@echo "✅ Test report generated!"
	@echo "📁 HTML Report: $(REPORTS_DIR)/test_report.html"
	@echo "📄 PDF Report: $(REPORTS_DIR)/test_report.pdf"

generate-pdf-report: ## Generate PDF report without running tests (uses existing artifacts)
	@echo "📄 Generating PDF report from existing test artifacts..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) $(SCRIPTS_DIR)/test_report_generator.py \
		--project-name "$(PROJECT_NAME)" \
		--no-run
	@echo "✅ PDF report generated!"
	@echo "📄 PDF Report: $(REPORTS_DIR)/test_report.pdf"

test-report-all: test-all generate-test-report ## Run all tests and generate comprehensive report
	@echo "🎯 Complete test execution with reporting..."
	@echo "✅ All tests completed with comprehensive reporting!"

# =============================================================================
# Performance & Profiling
# =============================================================================

benchmark: ## Run performance benchmarks
	@echo "⚡ Running performance benchmarks..."
	@$(PYTEST) $(TEST_DIR)/performance/ \
		--benchmark-only \
		--benchmark-json=$(REPORTS_DIR)/benchmark-results.json \
		--benchmark-histogram=$(REPORTS_DIR)/benchmark-histogram

profile: ## Profile test execution for optimization
	@echo "🔍 Profiling test execution..."
	@$(PYTHON) -m cProfile -o $(REPORTS_DIR)/profile.stats \
		-m pytest $(TEST_DIR)/unit/ -q
	@$(PYTHON) -c "import pstats; pstats.Stats('$(REPORTS_DIR)/profile.stats').sort_stats('cumtime').print_stats(20)"

monitor: ## Monitor system resources during test execution
	@echo "📊 Monitoring system resources..."
	@$(PYTHON) $(SCRIPTS_DIR)/monitor_resources.py \
		--output $(REPORTS_DIR)/resource_usage.json &
	@$(MAKE) test-all
	@pkill -f monitor_resources.py || true
	@echo "✅ Resource monitoring completed!"

# =============================================================================
# Docker Support
# =============================================================================

docker-build: ## Build Docker image for testing
	@echo "🐳 Building Docker test image..."
	@docker build -t $(DOCKER_IMAGE) -f Dockerfile.test .
	@echo "✅ Docker image built!"

docker-test: docker-build ## Run tests in Docker container
	@echo "🐳 Running tests in Docker..."
	@docker run --rm -v $(PWD):/workspace $(DOCKER_IMAGE) make test-all
	@echo "✅ Docker tests completed!"

docker-clean: ## Clean Docker test artifacts
	@echo "🧹 Cleaning Docker artifacts..."
	@docker rmi $(DOCKER_IMAGE) || true
	@docker system prune -f
	@echo "✅ Docker cleanup completed!"

# =============================================================================
# Enterprise Compliance
# =============================================================================

enterprise-audit: ## Run comprehensive enterprise audit
	@echo "🔍 Running enterprise audit..."
	@$(MAKE) security
	@$(MAKE) license-check
	@$(MAKE) compliance-check
	@$(MAKE) quality-analysis
	@echo "✅ Enterprise audit completed!"

compliance-check: ## Check compliance with enterprise standards
	@echo "📋 Checking compliance..."
	@$(PYTHON) $(SCRIPTS_DIR)/compliance_checker.py \
		--config $(COMPLIANCE_CONFIG) \
		--reports-dir $(REPORTS_DIR) \
		--output $(REPORTS_DIR)/compliance_report.json
	@echo "✅ Compliance check completed!"

license-check: ## Check license compliance
	@echo "⚖️  Checking license compliance..."
	@pip-licenses --format json --output-file $(REPORTS_DIR)/licenses.json
	@pip-licenses --format table
	@echo "✅ License check completed!"

# =============================================================================
# CI/CD Integration
# =============================================================================

pre-commit: lint check-format security ## Run pre-commit quality checks
	@echo "🔍 Running pre-commit checks..."
	@$(MAKE) test-smoke
	@echo "✅ Pre-commit checks passed!"

post-deploy: ## Run post-deployment validation
	@echo "🚀 Running post-deployment validation..."
	@$(MAKE) test-smoke
	@$(MAKE) health-check
	@echo "✅ Post-deployment validation completed!"

health-check: ## Perform system health check
	@echo "🏥 Performing health check..."
	@$(PYTHON) $(SCRIPTS_DIR)/health_checker.py
	@echo "✅ Health check completed!"

ci-test: ## Run CI-optimized test suite
	@echo "🚀 Running CI test suite..."
	@$(MAKE) setup-ci
	@$(MAKE) lint
	@$(MAKE) security
	@$(MAKE) test-parallel
	@$(MAKE) coverage-xml
	@$(MAKE) report-enterprise
	@echo "✅ CI test suite completed!"

# =============================================================================
# Maintenance & Cleanup
# =============================================================================

clean: ## Clean up generated files and caches
	@echo "🧹 Cleaning up..."
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name ".coverage" -delete
	@rm -rf $(REPORTS_DIR) $(ARTIFACTS_DIR) $(COVERAGE_DIR) .pytest_cache
	@rm -rf build/ dist/ .tox/ .mypy_cache/
	@echo "✅ Cleanup completed!"

clean-all: clean docker-clean ## Complete cleanup including Docker artifacts

reset: clean-all setup-dev ## Reset development environment

# =============================================================================
# Advanced Features
# =============================================================================

test-changed: ## Run tests only for changed files
	@echo "🔄 Running tests for changed files..."
	@$(PYTEST) --picked --tb=short -v

test-failed: ## Re-run only failed tests from last run
	@echo "🔄 Re-running failed tests..."
	@$(PYTEST) --lf --tb=short -v

test-watch: ## Watch files and run tests automatically
	@echo "👀 Watching for changes..."
	@$(PYTEST) --looponfail $(TEST_DIR)/

load-test: ## Run load tests against the system
	@echo "⚡ Running load tests..."
	@locust -f $(TEST_DIR)/load/locustfile.py --headless -u 10 -r 2 -t 30s

mutation-test: ## Run mutation testing for test quality
	@echo "🧬 Running mutation tests..."
	@mutmut run --paths-to-mutate=$(PACKAGE_DIR)
	@mutmut results

# =============================================================================
# Development Utilities
# =============================================================================

deps-update: ## Update dependencies to latest versions
	@echo "📦 Updating dependencies..."
	@pip-compile --upgrade requirements.in
	@pip-compile --upgrade requirements-test.in
	@echo "✅ Dependencies updated!"

deps-check: ## Check for outdated dependencies
	@echo "📦 Checking for outdated dependencies..."
	@pip list --outdated

test-matrix: ## Run tests across multiple Python versions (requires tox)
	@echo "🐍 Running test matrix..."
	@tox

docs-test: ## Test documentation examples
	@echo "📚 Testing documentation..."
	@$(PYTHON) -m doctest $(PACKAGE_DIR)/*.py
	@sphinx-build -b doctest docs docs/_build/doctest

# =============================================================================
# Enterprise Metrics
# =============================================================================

metrics: ## Generate comprehensive metrics report
	@echo "📊 Generating metrics report..."
	@$(MAKE) coverage
	@$(MAKE) benchmark
	@$(MAKE) quality-analysis
	@$(PYTHON) $(SCRIPTS_DIR)/generate_metrics_dashboard.py \
		--reports-dir $(REPORTS_DIR) \
		--output $(REPORTS_DIR)/metrics_dashboard.html
	@echo "✅ Metrics report generated!"

trend-analysis: ## Analyze testing trends over time
	@echo "📈 Analyzing trends..."
	@$(PYTHON) $(SCRIPTS_DIR)/trend_analyzer.py \
		--historical-data $(REPORTS_DIR)/historical \
		--current-data $(REPORTS_DIR) \
		--output $(REPORTS_DIR)/trend_analysis.json
	@echo "✅ Trend analysis completed!"

# =============================================================================
# Default Target
# =============================================================================

.DEFAULT_GOAL := help