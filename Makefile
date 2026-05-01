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
        test test-unit test-integration test-adversarial lint type-check clean logs \
        aws-init aws-plan aws-up aws-down aws-status aws-logs ecr-create ecr-login ecr-push

# Default target
help:
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║          AI DevOps Agent Platform - Demo Commands                ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  LOCAL DEMO                                                      ║"
	@echo "║  make demo-up          Start services and run full demo          ║"
	@echo "║  make demo-down        Stop all services                         ║"
	@echo "║  make demo-quick       Quick demo (no services, mock mode)       ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  AWS DEPLOYMENT (ECS Fargate)                                    ║"
	@echo "║  make aws-up           Deploy to AWS (full stack)                ║"
	@echo "║  make aws-down         Destroy AWS infrastructure                ║"
	@echo "║  make aws-status       Show deployment endpoints                 ║"
	@echo "║  make aws-logs         Tail CloudWatch logs                      ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  INDIVIDUAL SCENARIOS                                            ║"
	@echo "║  make demo-scenario-1  Intent -> Infrastructure generation       ║"
	@echo "║  make demo-scenario-2  Error handling & smart replanning         ║"
	@echo "║  make demo-scenario-3  FinOps cost optimization                  ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  EXPOSE TO WEB (Headless Server)                                 ║"
	@echo "║  make expose           Show expose options                       ║"
	@echo "║  make expose-api       Expose API to public URL                  ║"
	@echo "║  make expose-grafana   Expose Grafana to public URL              ║"
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
	docker compose up -d
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
	docker compose down
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
	docker compose logs -f

logs-api:
	docker compose logs -f api

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

# =============================================================================
# AWS Deployment (ECS Fargate)
# =============================================================================

.PHONY: aws-init aws-plan aws-up aws-down aws-status aws-logs

aws-init:
	@echo "🔧 Initializing Terraform..."
	cd infra && terraform init

aws-plan:
	@echo "📋 Planning AWS infrastructure..."
	cd infra && terraform plan

aws-up: aws-init
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║  🚀 Deploying to AWS (ECS Fargate)                               ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"
	@echo ""
	cd infra && terraform apply -auto-approve
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║  ✅ AWS Deployment Complete!                                     ║"
	@echo "║                                                                  ║"
	@echo "║  Run 'make aws-status' to see endpoints                          ║"
	@echo "║  Run 'make aws-down' to destroy infrastructure                   ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"

aws-down:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║  🛑 Destroying AWS Infrastructure                                ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"
	@echo ""
	cd infra && terraform destroy -auto-approve
	@echo ""
	@echo "✅ AWS infrastructure destroyed"

aws-status:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║  📊 AWS Deployment Status                                        ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"
	@echo ""
	@cd infra && terraform output 2>/dev/null || echo "Run 'make aws-up' first"

aws-logs:
	@echo "📜 Fetching CloudWatch logs..."
	@cd infra && aws logs tail /ecs/$$(terraform output -raw ecs_cluster_name 2>/dev/null || echo "devops-agent-demo") --follow

# =============================================================================
# ECR (Container Registry)
# =============================================================================

.PHONY: ecr-login ecr-push

ECR_REPO ?= agentic-devops-api
AWS_REGION ?= us-east-1
AWS_ACCOUNT_ID ?= $(shell aws sts get-caller-identity --query Account --output text 2>/dev/null)

ecr-create:
	@echo "📦 Creating ECR repository..."
	aws ecr create-repository --repository-name $(ECR_REPO) --region $(AWS_REGION) || true

ecr-login:
	@echo "🔐 Logging into ECR..."
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com

ecr-push: docker-build ecr-login
	@echo "📤 Pushing to ECR..."
	docker tag agentic-devops:latest $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO):latest
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO):latest
	@echo "✅ Image pushed to ECR"
	@echo "   Update infra/terraform.tfvars with:"
	@echo "   api_image = \"$(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO):latest\""

# =============================================================================
# Terminal Recordings (asciinema)
# =============================================================================

.PHONY: record-demo-quick record-demo-up record-all

record-demo-quick:
	@echo "🎬 Recording demo-quick..."
	@command -v asciinema >/dev/null 2>&1 || { echo "Install asciinema: pip install asciinema"; exit 1; }
	asciinema rec demo/recordings/demo-quick.cast -c "make demo-quick" --overwrite
	@echo "✅ Recording saved to demo/recordings/demo-quick.cast"

record-demo-up:
	@echo "🎬 Recording demo-up..."
	@command -v asciinema >/dev/null 2>&1 || { echo "Install asciinema: pip install asciinema"; exit 1; }
	asciinema rec demo/recordings/demo-up.cast -c "make demo-up" --overwrite
	@echo "✅ Recording saved to demo/recordings/demo-up.cast"

record-demo-scenarios:
	@echo "🎬 Recording all scenarios..."
	@command -v asciinema >/dev/null 2>&1 || { echo "Install asciinema: pip install asciinema"; exit 1; }
	asciinema rec demo/recordings/scenarios.cast -c "make demo-scenario-1 && sleep 2 && make demo-scenario-2 && sleep 2 && make demo-scenario-3" --overwrite
	@echo "✅ Recording saved to demo/recordings/scenarios.cast"

record-all: record-demo-quick record-demo-scenarios
	@echo "✅ All recordings complete"

# Upload recording to asciinema.org
upload-recordings:
	@echo "📤 Uploading recordings to asciinema.org..."
	@command -v asciinema >/dev/null 2>&1 || { echo "Install asciinema: pip install asciinema"; exit 1; }
	asciinema upload demo/recordings/demo-quick.cast
	@echo "✅ Upload complete - add the URL to README.md"

# =============================================================================
# Expose Services to Web (Cloudflare Tunnel)
# =============================================================================

.PHONY: expose expose-api expose-grafana expose-all

expose-api:
	@echo "🌐 Exposing API to web via localhost.run..."
	@echo "URL will appear below (Ctrl+C to stop)"
	ssh -R 80:localhost:8000 localhost.run

expose-grafana:
	@echo "🌐 Exposing Grafana to web via localhost.run..."
	@echo "URL will appear below (Ctrl+C to stop)"
	ssh -R 80:localhost:3010 localhost.run

expose-jaeger:
	@echo "🌐 Exposing Jaeger to web via localhost.run..."
	@echo "URL will appear below (Ctrl+C to stop)"
	ssh -R 80:localhost:16686 localhost.run

expose-ngrok:
	@echo "🌐 Exposing API via ngrok..."
	@command -v ngrok >/dev/null 2>&1 || { echo "Install: snap install ngrok"; exit 1; }
	ngrok http 8000

expose:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║  Expose Services to Web (No Account Needed)                      ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  Uses localhost.run (SSH-based, no install required)             ║"
	@echo "║                                                                  ║"
	@echo "║  Run in separate terminals:                                      ║"
	@echo "║  make expose-api      Expose API (port 8000)                     ║"
	@echo "║  make expose-grafana  Expose Grafana (port 3010)                 ║"
	@echo "║  make expose-jaeger   Expose Jaeger (port 16686)                 ║"
	@echo "║                                                                  ║"
	@echo "║  Output: https://xxxxx.localhost.run                             ║"
	@echo "║                                                                  ║"
	@echo "║  Alternatives:                                                   ║"
	@echo "║  make expose-ngrok    Use ngrok (requires install)               ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"
