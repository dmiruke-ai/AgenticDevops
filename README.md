# AI DevOps Agent Platform

**Intent-driven infrastructure generation with LangGraph multi-agent orchestration**

A production-ready AI agent system that transforms natural language conversations into validated, secure cloud infrastructure. Uses confidence-aware intent tracking, OPA security gates, and smart validation loops to prevent errors before deployment.

## 🎯 Core Principles

- **Intent-First**: Builds a canonical `IntentSpec` from conversation with confidence tracking
- **Never Execute on Uncertainty**: Blocks irreversible actions on `speculative` or `inferred` intent
- **Security at Intent Layer**: OPA policies prevent vulnerabilities before code generation
- **Smart Error Recovery**: Typed error classification with targeted replanning, not naive retry
- **Human-in-the-Loop**: Approval gate for destructive operations with blast radius analysis

## 🏗️ Architecture

```
User Message → Intent Parser → IntentSpec (confidence bands)
                    ↓
                FinOps Scorer (Tree-of-Thought platform eval)
                    ↓
                Planner (DAG-based artifact generation)
                    ↓
                Validator (Terraform plan + error intelligence)
                    ↓
             Approval Gate (blast radius + cost delta)
                    ↓
                Executor (terraform apply)
```

### Key Components

- **IntentSpec**: Canonical intent representation with 4 confidence bands
- **Confidence State Machine**: Governs transitions from `speculative` → `inferred` → `confirmed` → `stated`
- **DAG Executor**: Dependency-aware topological execution with true async parallelism
- **OPA Security Layer**: Blocks wildcard IAM, open security groups, unencrypted storage at intent level
- **Error Intelligence**: 15 typed Terraform errors with structured fix hints

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git

### Installation

```bash
# Clone repository
git clone <repo-url>
cd AgenticDevops

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Run with Docker Compose

```bash
# Start all services (FastAPI, Redis, OPA, Prometheus, Jaeger)
cd docker
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

### Services

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Metrics**: http://localhost:8000/metrics
- **Jaeger UI**: http://localhost:16686
- **Prometheus**: http://localhost:9090

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=agents --cov=intent --cov=execution --cov-report=html

# Run specific test suite
pytest tests/unit/
pytest tests/integration/
pytest tests/adversarial/

# Run single test
pytest tests/unit/test_intent_schema.py::TestIntentSpec::test_create_empty_intent_spec -v
```

## 📋 Development

### Code Quality

```bash
# Lint with Ruff
ruff check .

# Format with Ruff
ruff format .

# Type check with MyPy
mypy agents/ intent/ execution/ security/ gates/ observability/ api/
```

### Project Structure

```
agents/
  intent_parser/     # Semantic extraction, dialogue policy
  planner/           # Smart replanning after validation errors
  generators/        # Terraform, IAM, CI/CD YAML
  finops/           # FinOps scoring (Tree-of-Thought)
  validator/        # Error intelligence, terraform runner

intent/
  schema.py         # IntentSpec Pydantic models
  confidence.py     # State machine, transitions, gates
  conflict_detector.py  # 8 DevOps conflict patterns

execution/
  dag.py           # Topological DAG executor

security/
  opa_intent_gate.py   # Python OPA client
  policies/           # Rego policy bundle

gates/
  human_approval.py    # Approval gate for terraform apply

observability/
  agent_tracer.py      # OpenTelemetry + Prometheus

api/
  main.py             # FastAPI application
```

## 📊 Sprint Status

### ✅ Sprint 0 - Foundation (COMPLETED)

- [x] Repository structure
- [x] Docker Compose with all services
- [x] GitHub Actions CI pipeline
- [x] Base IntentSpec Pydantic models
- [x] Observability tracer decorator
- [x] Stub LangGraph nodes
- [x] Unit tests for IntentSpec

### 🔄 Sprint 1 - Intent Engine Core (IN PROGRESS)

Implements:
- IntentTransitionEngine (6 confidence transition paths)
- ConflictDetector (8 DevOps conflict patterns)
- Semantic Extractor (PROMPT_CHAIN_01)
- Dialogue Policy (PROMPT_CHAIN_02)
- Session state store (Redis)

### 📅 Sprint 2 - DAG + FinOps + Artifact Generation

Implements:
- IntentDAG with topological sort
- DAGExecutor with async parallelism
- FinOps scoring (Tree-of-Thought)
- Terraform generator
- IAM policy generator
- CI/CD pipeline generator

### 📅 Sprint 3 - Validation Loop + Security

Implements:
- Terraform error intelligence (15 error types)
- Smart replanning with targeted fixes
- OPA security layer
- Adversarial test suite (prompt injection)

### 📅 Sprint 4 - Observability + HITL + Hardening

Implements:
- Full OpenTelemetry instrumentation
- Grafana dashboard
- Approval gate with blast radius
- Multi-tenancy isolation
- Load testing

## 🔒 Security

### OPA Policies (Intent Layer)

Blocks at intent extraction (before code generation):
- ✋ Wildcard IAM policies (`*`)
- ✋ Open security groups (`0.0.0.0/0`)
- ✋ Unencrypted storage
- ✋ Public S3 buckets
- ⚠️  Production without MFA (warning)

### Confidence-Based Execution

| Action | Minimum Confidence |
|--------|-------------------|
| `generate_terraform` | `confirmed` |
| `terraform_apply` | `confirmed` + human approval |
| `delete_resource` | `confirmed` + human approval |
| `modify_iam` | `confirmed` |

## 📖 Documentation

- **Implementation Handoff**: `ai_devops_agent_implementation_handoff.md`
- **CLAUDE.md**: Guidance for Claude Code instances
- **Component Specs**: See handoff document PART 1 (SPEC-01 through SPEC-06)
- **Prompt Chains**: See handoff document PART 2 (PROMPT_CHAIN_01 through PROMPT_CHAIN_06)

## 🤝 Contributing

This project follows TDD (Test-Driven Development):

1. Write tests that validate acceptance criteria
2. Implement minimal code to pass tests
3. Refactor
4. Submit PR with passing CI

## 📄 License

[Specify license]

## 🙏 Acknowledgments

Built on the `intentctl` library pattern for confidence-aware intent specification.

---

**Status**: Sprint 0 Complete ✅ | Sprint 1 In Progress 🔄

For detailed sprint plans and acceptance criteria, see the implementation handoff document.
