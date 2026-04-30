# =============================================================================
# AI DevOps Agent Platform - Makefile
# =============================================================================
#
# Quick Start:
#   make demo-up      # Start all services and run demo
#   make demo-down    # Stop all services
#   make test         # Run all tests
#
# =============================================================================

.PHONY: help install demo-up demo-down demo-scenario-1 demo-scenario-2 demo-scenario-3 \
        test test-unit test-integration test-adversarial lint type-check clean logs

# Default target
help:
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║          AI DevOps Agent Platform - Demo Commands                ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  make demo-up          Start services and run full demo          ║"
	@echo "║  make demo-down        Stop all services                         ║"
	@echo "║  make demo-quick       Quick demo (no services, mock mode)       ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  INDIVIDUAL SCENARIOS                                            ║"
	@echo "║  make demo-scenario-1  Intent → Infrastructure generation        ║"
	@echo "║  make demo-scenario-2  Error handling & smart replanning         ║"
	@echo "║  make demo-scenario-3  FinOps cost optimization                  ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  DEVELOPMENT                                                     ║"
	@echo "║  make install          Install dependencies                      ║"
	@echo "║  make test             Run all tests                             ║"
	@echo "║  make lint             Run linter                                ║"
	@echo "║  make logs             View service logs                         ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"

# =============================================================================
# Installation
# =============================================================================

install:
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt
	@echo "✅ Dependencies installed"

install-dev: install
	@echo "📦 Installing dev dependencies..."
	pip install -r requirements-dev.txt 2>/dev/null || true
	@echo "✅ Dev dependencies installed"

# =============================================================================
# Demo Commands
# =============================================================================

demo-up: demo-services-up demo-wait demo-run
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║  ✅ Demo Complete!                                               ║"
	@echo "║                                                                  ║"
	@echo "║  Services running at:                                            ║"
	@echo "║  • API:        http://localhost:8000                             ║"
	@echo "║  • Jaeger:     http://localhost:16686                            ║"
	@echo "║  • Prometheus: http://localhost:9090                             ║"
	@echo "║  • Grafana:    http://localhost:3000                             ║"
	@echo "║                                                                  ║"
	@echo "║  Run 'make demo-down' to stop services                           ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"

demo-services-up:
	@echo "🚀 Starting services..."
	docker-compose up -d
	@echo "✅ Services started"

demo-wait:
	@echo "⏳ Waiting for services to be ready..."
	@sleep 5
	@echo "✅ Services ready"

demo-run:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║  🎬 Running Demo Scenarios                                       ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"
	@echo ""
	@$(MAKE) demo-scenario-1
	@echo ""
	@$(MAKE) demo-scenario-2
	@echo ""
	@$(MAKE) demo-scenario-3

demo-down:
	@echo "🛑 Stopping services..."
	docker-compose down
	@echo "✅ Services stopped"

demo-quick:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║  🚀 Quick Demo (Mock Mode - No External Services)                ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"
	@echo ""
	python demo/run_demo.py --mock

# =============================================================================
# Individual Demo Scenarios
# =============================================================================

demo-scenario-1:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "📋 SCENARIO 1: Intent → Infrastructure"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "User Intent: 'Deploy a scalable web app on AWS with CI/CD'"
	@echo ""
	python demo/scenario_1_intent_to_infra.py

demo-scenario-2:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "📋 SCENARIO 2: Error Handling & Smart Replanning"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Injecting Terraform error → System classifies and fixes"
	@echo ""
	python demo/scenario_2_error_handling.py

demo-scenario-3:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "📋 SCENARIO 3: FinOps Cost Optimization"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Tree-of-Thought evaluation → Cost-aware architecture selection"
	@echo ""
	python demo/scenario_3_finops.py

# =============================================================================
# Testing
# =============================================================================

test:
	@echo "🧪 Running all tests..."
	pytest tests/ -v --tb=short
	@echo "✅ All tests passed"

test-unit:
	@echo "🧪 Running unit tests..."
	pytest tests/unit/ -v --tb=short

test-integration:
	@echo "🧪 Running integration tests..."
	pytest tests/integration/ -v --tb=short

test-adversarial:
	@echo "🧪 Running adversarial tests..."
	pytest tests/adversarial/ -v --tb=short

test-coverage:
	@echo "🧪 Running tests with coverage..."
	pytest tests/ --cov=agents --cov=intent --cov=execution --cov=security --cov-report=html
	@echo "📊 Coverage report: htmlcov/index.html"

# =============================================================================
# Code Quality
# =============================================================================

lint:
	@echo "🔍 Running linter..."
	ruff check .

lint-fix:
	@echo "🔧 Fixing lint issues..."
	ruff check --fix .

type-check:
	@echo "🔍 Running type checker..."
	mypy agents/ intent/ execution/ security/ gates/ observability/

format:
	@echo "🎨 Formatting code..."
	ruff format .

# =============================================================================
# Utilities
# =============================================================================

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

clean:
	@echo "🧹 Cleaning up..."
	rm -rf __pycache__ .pytest_cache .mypy_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned"

# =============================================================================
# Docker
# =============================================================================

docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t agentic-devops:latest .

docker-run:
	@echo "🐳 Running Docker container..."
	docker run -p 8000:8000 agentic-devops:latest
