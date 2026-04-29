# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **AI DevOps Agent Platform** - a multi-agent system that transforms natural language conversations into production-ready cloud infrastructure. The system uses:

- **Intent-driven architecture**: Builds a canonical `IntentSpec` from conversation with confidence tracking
- **LangGraph multi-agent orchestration**: DAG-based execution with dependency resolution
- **Smart validation loops**: Terraform error intelligence with targeted replanning
- **OPA security gates**: Policy enforcement at the intent layer (before code generation)
- **Human-in-the-loop approval**: Gated execution for irreversible operations

**Core principle**: The system implements the `intentctl` library pattern - a confidence-aware intent specification that prevents executing cloud operations on uncertain or inferred user intent.

## Implementation Directives

### Primary Directive: Sprint 0 Foundation

You are implementing the AI DevOps Agent Platform described in `ai_devops_agent_implementation_handoff.md`.

**Start with Sprint 0:**
1. Scaffold the repository structure from PART 4 of the handoff document
2. Create the Docker Compose file with: FastAPI + Redis + OPA + Prometheus + Jaeger
3. Implement the base IntentSpec Pydantic schema from SPEC-02
4. Use **TDD (Test-Driven Development)** - write tests before implementation

### Secondary Directive: Sprint 1 Execution

After Sprint 0 is complete, implement Sprint 1 tickets **S1-01 through S1-05** in order:

- **S1-01**: IntentSpec Pydantic schema (complete)
- **S1-02**: IntentTransitionEngine - all 6 transition paths
- **S1-03**: ConflictDetector - 8 known DevOps conflict patterns
- **S1-04**: Semantic Extractor - extraction prompt + Instructor schema validation
- **S1-05**: Dialogue Policy Engine - Reflect+Guide response generation

**Reference documents:**
- SPEC-02 for data contracts and interfaces
- PROMPT_CHAIN_01 for the extraction prompt template
- PROMPT_CHAIN_02 for dialogue policy

**CRITICAL**: Do not proceed to S1-06 until the Sprint 1 integration test passes:
> User says "build me a scalable AWS app with CI/CD" → 4 turns → IntentSpec reaches `confirmed` for compute platform, cloud provider, and IaC tool → `check_gate` allows infra generation.

## Development Commands

### Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Start all services (FastAPI, Redis, OPA, Prometheus, Jaeger)
docker-compose up -d

# View logs
docker-compose logs -f api
```

### Testing

```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/unit/test_intent_confidence.py
pytest tests/integration/test_sprint1.py

# Run with coverage
pytest --cov=agents --cov=intent --cov=execution --cov-report=html

# Run type checking
mypy agents/ intent/ execution/ security/ gates/ observability/

# Run linting
ruff check .
```

### Development Workflow

```bash
# Run single test during development
pytest tests/unit/test_confidence.py::test_transition_speculative_to_confirmed -v

# Auto-reload API server during development
uvicorn api.main:app --reload --port 8000

# Check OPA policy syntax
docker-compose exec opa opa test policies/

# View Jaeger traces (after starting services)
# Navigate to: http://localhost:16686

# Query Prometheus metrics
# Navigate to: http://localhost:9090
```

### API Endpoints

```bash
# Create new session
curl -X POST http://localhost:8000/sessions

# Submit user turn
curl -X POST http://localhost:8000/sessions/{session_id}/turns \
  -H "Content-Type: application/json" \
  -d '{"message": "build me a scalable AWS app"}'

# Get current IntentSpec
curl http://localhost:8000/sessions/{session_id}/intent

# Approve deployment
curl -X POST http://localhost:8000/sessions/{session_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approval_id": "..."}'
```

## Architecture Overview

### Three-Layer Intent Taxonomy

The system builds a structured `IntentSpec` with three categories:

1. **Task Intent**: What to build (compute platform, networking, CI/CD)
2. **Meta Intent**: Why and how (cost optimization, security posture, reliability)
3. **Constraint Intent**: Hard requirements (region, compliance, budget)

### Confidence State Machine

Every `SpecItem` has a confidence band that governs what actions can execute:

- **`speculative`**: LLM inferred with no user signal (CANNOT execute irreversible actions)
- **`inferred`**: Reasonable inference from context (CANNOT execute irreversible actions)
- **`confirmed`**: User explicitly affirmed (CAN execute most actions)
- **`stated`**: User said it verbatim (highest confidence)

**Valid transitions** are defined in `VALID_TRANSITIONS` dict in `intent/confidence.py`. Invalid transitions are silently rejected - the system never raises exceptions on confidence violations.

### DAG Execution Model

Infrastructure generation follows a dependency DAG (SPEC-03):

```
finops_score (runs first)
    ↓
infra_gen (needs platform decision)
    ↓
    ├→ iam_gen (needs resource ARNs)
    ├→ observability_gen (needs cluster endpoint)
    └→ pipeline_gen (needs cluster + IAM role)
        ↓
    validation (pulls all artifacts)
        ↓
    human_approval (if output_mode == "deploy")
        ↓
    terraform_apply
```

Nodes in the same wave execute in **true async parallel** using `asyncio.gather()`.

### Error Intelligence (SPEC-01)

The validation loop uses **typed error classification** instead of naive retry:

1. Terraform plan fails
2. `TerraformErrorClassifier` parses stderr → 1 of 15 error types
3. Error type maps to `fix_hint` + `intent_spec_mutation` + `planner_instruction`
4. System performs **targeted replanning** (only regenerates failing modules)
5. Retry limit: 3 attempts, then escalate to user

**Never regenerates the same broken Terraform** - each retry has structured fix context.

### OPA Security Layer (SPEC-04)

OPA policies run at the **intent layer**, not just on generated Terraform:

- Blocks wildcard IAM before it enters IntentSpec
- Blocks `0.0.0.0/0` ingress before code generation
- Prevents prompt injection attacks from corrupting canonical spec
- All checks audited with `session_id` + `turn` number

Policy location: `security/policies/intent_security.rego`

### Output Modes

Three modes control execution depth:

- **`design`**: Only returns FinOps score + architecture recommendation (no code)
- **`artifacts`**: Generates Terraform + CI/CD YAML (no deployment)
- **`deploy`**: Full pipeline including `terraform apply` (requires human approval)

## Critical Specifications

### SPEC-01: Terraform Error Intelligence
- **Module**: `agents/validator/error_intelligence.py`
- **Key classes**: `TerraformErrorClassifier`, `TerraformError`, `ErrorClassificationResult`
- **Acceptance criteria**: 14 error types classified, LLM fallback for UNKNOWN, tested against 20 real terraform failures

### SPEC-02: Intent Confidence Transition Engine
- **Module**: `intent/confidence.py`
- **Key classes**: `IntentTransitionEngine`, `ConflictDetector`, `TransitionEvent`
- **State machine**: 6 valid transition paths defined in `VALID_TRANSITIONS`
- **Gate enforcement**: `check_gate` blocks IRREVERSIBLE_ACTIONS on low-confidence items

### SPEC-03: Intent DAG Execution Engine
- **Module**: `execution/dag.py`
- **Key classes**: `IntentDAG`, `DAGExecutor`, `TaskNode`
- **Algorithm**: Kahn's topological sort with cycle detection
- **Parallelism**: True async execution for same-wave nodes

### SPEC-04: OPA Security Layer
- **Module**: `security/opa_intent_gate.py`
- **Policy file**: `security/policies/intent_security.rego`
- **Integration point**: Runs BEFORE ExtractionResult merges into IntentSpec
- **Raises**: `IntentPolicyViolation` on deny rules

### SPEC-05: Human-in-the-Loop Approval Gate
- **Module**: `gates/human_approval.py`
- **Key classes**: `ApprovalGate`, `BlastRadius`, `ApprovalRequest`
- **Timeout**: 300s default (configurable)
- **Surfaces**: Terraform diff, cost delta, resources to destroy

### SPEC-06: Agent Observability Layer
- **Module**: `observability/agent_tracer.py`
- **Instrumentation**: `@trace_agent_node` decorator on all LangGraph nodes
- **Exports**: OpenTelemetry → Jaeger, Prometheus metrics on `/metrics`
- **Dashboard**: `dashboards/grafana_devops_agent.json`

## Prompt Chains

All LLM calls use the `instructor` library for structured output with automatic schema validation retry.

### PROMPT_CHAIN_01: Semantic Intent Extraction
- **Model**: claude-sonnet-4 (primary), gpt-4o (fallback)
- **Style**: Chain-of-Thought with 7 reasoning steps before JSON output
- **Output**: `ExtractionResult` with new_items, updated_items, open_questions, conflicts

### PROMPT_CHAIN_02: Dialogue Policy (Reflect + Guide)
- **Model**: claude-sonnet-4
- **Pattern**: "Here's what I understood... [one key question with 2-3 options]"
- **Rule**: Ask AT MOST ONE question per turn, always with trade-offs

### PROMPT_CHAIN_03: Terraform Error Classification
- **Model**: claude-haiku-4 (fast, cheap classifier)
- **Fallback**: Used only for UNKNOWN error types after regex patterns fail
- **Output**: `TerraformError` with fix_hint and planner_instruction

### PROMPT_CHAIN_04: Smart Replanning
- **Model**: claude-sonnet-4
- **Input**: Error classification + previous artifacts + IntentSpec
- **Constraint**: Only regenerates failing modules, preserves passing modules

### PROMPT_CHAIN_05: FinOps Platform Scoring
- **Model**: claude-sonnet-4
- **Style**: Tree-of-Thought (evaluates EKS, ECS Fargate, Lambda, ECS EC2 in parallel)
- **Output**: Platform recommendation with cost breakdown + flip points

### PROMPT_CHAIN_06: Intent Conflict Resolution
- **Model**: claude-haiku-4
- **Output**: 2-3 resolution options with infrastructure implications

## Repository Structure

```
agents/
  intent_parser/     # Semantic extraction, dialogue policy
  planner/           # Smart replanning after validation errors
  generators/        # Terraform, IAM, CI/CD YAML, observability
  finops/           # FinOps scoring engine (ToT)
  validator/        # Error intelligence, terraform runner

intent/
  schema.py         # IntentSpec Pydantic models
  confidence.py     # State machine, transitions, gate enforcement
  conflict_detector.py  # 8 DevOps conflict patterns

execution/
  dag.py           # Topological DAG executor

security/
  opa_intent_gate.py   # Python OPA client
  policies/intent_security.rego  # Rego policies

gates/
  human_approval.py    # Approval gate for terraform apply

observability/
  agent_tracer.py      # OpenTelemetry + Prometheus

api/
  main.py             # FastAPI application

tests/
  unit/              # Per-spec acceptance criteria
  integration/       # End-to-end per sprint
  adversarial/       # OPA prompt injection suite
```

## Configuration

All tunables in `config.py`:

```python
primary_model = "claude-sonnet-4-20250514"
classifier_model = "claude-haiku-4-5-20251001"  # cheap, fast
max_retry_count = 3
confidence_floor_for_irreversible = "confirmed"
default_output_mode = "artifacts"
approval_timeout_seconds = 300
```

## Critical Rules

### DO NOT
- Generate Terraform without a **confirmed** IntentSpec
- Execute `terraform apply` without human approval
- Merge `ExtractionResult` before OPA gate passes
- Retry validation with the same artifact that failed (must use targeted replanning)
- Skip hooks (--no-verify) or use force push
- Ask more than ONE clarifying question per dialogue turn

### ALWAYS
- Write tests BEFORE implementation (TDD)
- Use `instructor` library for all LLM calls (structured output + auto-retry)
- Run adversarial test suite in Sprint 3 from day 1
- Check acceptance criteria before marking sprint ticket complete
- Instrument all LangGraph nodes with `@trace_agent_node`
- Audit log every OPA policy check with session_id + turn

## Sprint Acceptance Criteria

### Sprint 0 (Foundation)
- [ ] Repository structure matches PART 4 layout
- [ ] Docker Compose starts all services (FastAPI, Redis, OPA, Prometheus, Jaeger)
- [ ] Base IntentSpec Pydantic models validate + JSON round-trip
- [ ] All 6 LangGraph nodes stubbed with `@trace_agent_node` decorator
- [ ] CI pipeline runs: ruff, mypy, pytest, docker build

### Sprint 1 (Intent Engine Core)
- [ ] All 6 confidence transition paths implemented and tested
- [ ] `check_gate` blocks all IRREVERSIBLE_ACTIONS on speculative/inferred items
- [ ] ConflictDetector catches 8 known DevOps conflict patterns
- [ ] Semantic Extractor validates schema on 20 test inputs
- [ ] Dialogue Policy generates valid Reflect+Guide responses
- [ ] **Integration test passes**: 4-turn conversation → confirmed IntentSpec → gate allows generation

### Sprint 2 (DAG + FinOps + Artifact Generation)
- [ ] `topological_sort` handles 3-level dependency chains + detects cycles
- [ ] `DAGExecutor` achieves true async parallel execution (timing test confirms)
- [ ] FinOps ToT evaluates 4 platform branches, produces recommendation
- [ ] Valid Terraform HCL generated for EKS, ECS, Lambda
- [ ] IAM policies validated by OPA (no wildcards)
- [ ] **Integration test passes**: Confirmed IntentSpec → DAG execution → Terraform + YAML in <45s

### Sprint 3 (Validation Loop + Security)
- [ ] All 14 error patterns match on sample errors
- [ ] LLM fallback classifies 5 novel errors correctly
- [ ] Smart replanning fixes errors without reproducing original failure
- [ ] All 4 OPA blocking policies implemented
- [ ] **Integration test passes**: Adversarial input blocked at OPA → IAM error → targeted replan → retry 2 succeeds

### Sprint 4 (Observability + HITL + Hardening)
- [ ] All 6 LangGraph nodes instrumented, traces appear in Jaeger
- [ ] Grafana dashboard shows: session duration, LLM latency, token cost, retry rate
- [ ] Approval gate timeout returns rejected decision after 300s
- [ ] Session isolation: Tenant A cannot read Tenant B spec
- [ ] **Integration test passes**: 10 concurrent users, no cross-contamination, approval gate fires correctly

## Testing Strategy

Every SPEC has explicit acceptance criteria - these become test cases.

**TDD workflow:**
1. Read acceptance criteria from SPEC
2. Write test that validates the criteria
3. Run test (it should fail)
4. Implement the minimal code to pass
5. Refactor
6. Move to next AC

**Adversarial testing (Sprint 3):**
- 15 prompt injection attempts targeting each OPA policy
- All must be blocked BEFORE entering IntentSpec
- Audit log must record every attempt

## Reference Documents

- **Full specification**: `ai_devops_agent_implementation_handoff.md`
- **Architecture section**: PART 0 (Principal Engineer Review)
- **Component specs**: PART 1 (SPEC-01 through SPEC-06)
- **Prompt templates**: PART 2 (PROMPT_CHAIN_01 through PROMPT_CHAIN_06)
- **Sprint plan**: PART 3 (Sprint 0 through Sprint 4)
- **Repository layout**: PART 4
- **Configuration**: PART 5

## Next Steps

1. **Run Sprint 0 tickets S0-01 through S0-06** to scaffold the foundation
2. **Verify Docker Compose** brings up all services successfully
3. **Write base IntentSpec tests** following SPEC-02 acceptance criteria
4. **Implement IntentSpec Pydantic models** to pass the tests
5. **Proceed to Sprint 1** only after all Sprint 0 ACs are met

The system is architected correctly. The implementation requires operational rigor, not design changes. Follow the sprint plan in order, validate acceptance criteria, and use TDD throughout.
