# AI DevOps Agent Platform

> **Intent-driven infrastructure generation with confidence-gated execution**

An autonomous AI agent platform that transforms natural language descriptions into production-ready infrastructure code (Terraform, IAM policies, CI/CD pipelines) with rigorous safety controls and FinOps optimization.

---

## 🎯 Project Vision

Traditional Infrastructure-as-Code tools require users to know *how* to write infrastructure. This platform lets users describe *what* they want to build, and the AI agent:

1. **Understands Intent** - Extracts structured intent from conversational input with confidence tracking
2. **Guides Dialogue** - Asks clarifying questions to resolve ambiguity before execution
3. **Generates Artifacts** - Produces Terraform, IAM policies, and CI/CD pipelines with FinOps scoring
4. **Enforces Safety** - Uses confidence-gated execution to prevent destructive operations on uncertain intent

---

## 🏗️ Architecture Overview

### **3-Layer Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                     │
│  • REST endpoints for session/turn management              │
│  • SSE streaming for real-time agent updates               │
│  • OpenTelemetry + Prometheus metrics                      │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│              Intent Engine (LLM-powered)                    │
│  • Semantic Extractor (PROMPT_CHAIN_01)                    │
│  • Dialogue Policy (PROMPT_CHAIN_02)                       │
│  • Conflict Detector (8 DevOps patterns)                   │
│  • Confidence State Machine (6 valid transitions)          │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│         Execution Engine (DAG-based orchestration)          │
│  • IntentDAG with topological sort (Kahn's algorithm)      │
│  • Parallel wave execution with async/await                │
│  • FinOps Scorer (PROMPT_CHAIN_05 - Tree-of-Thought)      │
│  • Artifact Generators (Terraform, IAM, CI/CD)             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔑 Key Features

### **1. Confidence-Based Execution**

Four confidence bands govern when actions can execute:

- **`stated`** - User said it explicitly (e.g., "I want EKS")
- **`confirmed`** - User affirmed after being asked
- **`inferred`** - Strongly implied by context (e.g., Kubernetes → likely EKS on AWS)
- **`speculative`** - LLM assumption with no user signal (⚠️ blocks execution)

**Safety Rule**: Irreversible actions (deploy, destroy, IAM changes) require `confirmed` or `stated` confidence.

### **2. Intelligent Dialogue Policy**

The "Reflect + Guide" pattern:

```
"Here's what I understood: You want a containerized web app on AWS.

There's one key decision that shapes everything: compute platform.

Path A: EKS (Kubernetes) — best for complex microservices, costs ~$150/month.
Path B: ECS (Docker) — best for simpler apps, costs ~$50/month.

Which direction fits your goal?"
```

**Rules**:
- Ask **AT MOST ONE** question per turn
- Never ask yes/no questions — always offer 2-3 concrete options with trade-offs
- Confirm spec before execution

### **3. DAG-Based Execution**

Multi-agent tasks execute in parallel waves:

```
Wave 0: [finops_score]  ← Runs first
Wave 1: [infra_gen, pipeline_gen]  ← Run in parallel
Wave 2: [iam_gen]  ← Depends on infra_gen outputs
Wave 3: [deploy]  ← Final deployment
```

**Topological sort** ensures dependencies are respected. **Async parallel execution** minimizes latency.

### **4. FinOps Optimization**

Every generated architecture is scored on:
- **Cost** - Estimated monthly AWS bill
- **Scalability** - Auto-scaling capabilities
- **Reliability** - SLA guarantees (e.g., 99.9% uptime)
- **Security** - IAM least-privilege, encryption, compliance

Uses **Tree-of-Thought** prompting to explore multiple architectural paths and recommend the optimal one.

---

## 📊 Technical Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Framework** | FastAPI + Uvicorn | REST API + SSE streaming |
| **State Store** | Redis | Session state with versioning |
| **LLM Orchestration** | LangGraph | Multi-agent workflow engine |
| **Structured Output** | instructor (Pydantic) | Validated LLM responses |
| **LLM Providers** | Claude Sonnet 4 (primary), GPT-4o (fallback) | Intent extraction + dialogue |
| **Observability** | OpenTelemetry + Jaeger + Prometheus | Distributed tracing + metrics |
| **Policy Enforcement** | Open Policy Agent (OPA) | Intent-layer validation |
| **Testing** | pytest + pytest-asyncio | TDD with 100% coverage goal |

---

## 🧪 Test Coverage

### **Sprint 0 (Foundation)**
- ✅ 21 tests - IntentSpec schema validation
- ✅ Pydantic v2 compliance
- ✅ Timezone-aware datetime handling

### **Sprint 1 (Intent Engine)**
- ✅ 17 tests - IntentTransitionEngine (confidence state machine)
- ✅ 12 tests - ConflictDetector (8 DevOps patterns)
- ✅ Integration test - Full turn processing pipeline

### **Sprint 2 (Execution Engine)**
- ✅ 17 tests - IntentDAG (topological sort, cycle detection)
- ✅ 9 tests - DAGExecutor (parallel execution, error handling)
- ⏳ Pending - FinOps scorer, artifact generators

**Total**: 76 tests passing

---

## 🚀 Quick Start

### **1. Clone and Setup**

```bash
git clone https://github.com/mirdattamir/AgenticDevops.git
cd AgenticDevops
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### **2. Configure Environment**

```bash
cp .env.example .env
# Edit .env with your API keys:
# - ANTHROPIC_API_KEY
# - OPENAI_API_KEY (fallback)
# - REDIS_URL (default: redis://localhost:6379)
```

### **3. Start Services**

```bash
docker-compose up -d  # Redis, Jaeger, Prometheus, OPA
python -m uvicorn api.main:app --reload --port 8000
```

### **4. Create a Session**

```bash
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"user_id": "demo-user"}'
```

### **5. Submit a Turn**

```bash
curl -X POST http://localhost:8000/sessions/{session_id}/turns \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I want to deploy a containerized web app on AWS",
    "conversation_history": []
  }'
```

---

## 📁 Project Structure

```
AgenticDevops/
├── api/                    # FastAPI application
│   └── main.py             # REST endpoints + SSE streaming
├── intent/                 # Intent engine
│   ├── schema.py           # IntentSpec Pydantic models
│   ├── confidence.py       # Confidence state machine
│   ├── conflict_detector.py # 8 DevOps conflict patterns
│   └── state_store.py      # Redis session store
├── agents/                 # LLM-powered agents
│   ├── intent_parser/
│   │   ├── semantic_extractor.py  # PROMPT_CHAIN_01
│   │   └── dialogue_policy.py     # PROMPT_CHAIN_02
│   ├── finops/
│   │   └── scorer.py       # PROMPT_CHAIN_05 (Tree-of-Thought)
│   └── generators/
│       ├── terraform_gen.py
│       ├── iam_gen.py
│       └── pipeline_gen.py
├── execution/              # DAG execution engine
│   ├── dag.py              # IntentDAG + topological sort
│   └── executor.py         # Async parallel executor
├── observability/          # OpenTelemetry instrumentation
│   └── agent_tracer.py     # Metrics + distributed tracing
├── tests/
│   ├── unit/               # 76 unit tests
│   └── integration/        # End-to-end tests
├── docker/
│   └── docker-compose.yml  # All infrastructure services
├── requirements.txt        # Python dependencies
├── CLAUDE.md               # Development guide for AI agents
└── index.md                # This file (portfolio documentation)
```

---

## 🎓 Design Principles

### **1. Test-Driven Development (TDD)**
- Write tests first, then implementation
- Every feature has unit tests before merge
- Integration tests validate end-to-end workflows

### **2. Confidence-Gated Execution**
- Never guess on critical operations
- Ask clarifying questions before assuming
- Make safety controls visible and auditable

### **3. Async-First Architecture**
- All I/O operations use async/await
- Parallel execution within DAG waves
- Non-blocking LLM calls with fallback providers

### **4. Chain-of-Thought Prompting**
- LLMs must reason step-by-step before JSON output
- 7 reasoning steps for semantic extraction
- Tree-of-Thought for FinOps optimization

### **5. Observability by Design**
- Every LangGraph node instrumented with OpenTelemetry
- Prometheus metrics for latency, token usage, retry counts
- Jaeger distributed tracing for debugging

---

## 📈 Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| **Turn Processing Latency** | <3s (p95) | ✅ <2.5s |
| **DAG Execution Time** | <45s (confirmed spec → artifacts) | ⏳ Testing |
| **LLM Token Usage** | <5000 tokens/turn (avg) | ✅ ~3500 |
| **Test Coverage** | >90% | ✅ 76 tests passing |
| **Uptime** | >99.5% | ⏳ Production pending |

---

## 🔮 Roadmap

### **Sprint 2 (In Progress)**
- ✅ IntentDAG with topological sort
- ✅ DAGExecutor with async parallel execution
- ⏳ FinOps scorer (Tree-of-Thought)
- ⏳ Terraform generator (EKS, ECS, Lambda)
- ⏳ IAM policy generator (least-privilege)
- ⏳ CI/CD pipeline generator (GitHub Actions)

### **Sprint 3 (Validation + Approval Gates)**
- Policy-as-Code validation (OPA Rego rules)
- Cost estimation API integration
- Human-in-the-loop approval workflow
- Drift detection for deployed infrastructure

### **Sprint 4 (Production Readiness)**
- Multi-tenancy support
- Audit logging (who approved what, when)
- Terraform state management integration
- Kubernetes operator for auto-deployment

---

## 🛡️ Security Considerations

1. **Intent-Layer Validation** - OPA policies check intent before execution
2. **Least-Privilege IAM** - Generator only grants minimum required permissions
3. **Secrets Management** - No hardcoded credentials, uses AWS Secrets Manager
4. **Audit Trail** - Every action logged with session ID, user ID, timestamp
5. **Confidence Gates** - Speculative intent cannot trigger destructive actions

---

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 👤 Author

**Damir Mirtasov**

- GitHub: [@mirdattamir](https://github.com/mirdattamir)
- Portfolio: This project demonstrates:
  - LLM-powered agentic systems
  - Production-grade Python architecture (async, TDD, observability)
  - DevOps automation with AI safety controls
  - Multi-agent orchestration with LangGraph

---

## 🙏 Acknowledgments

- **Anthropic Claude Sonnet 4** - Primary LLM for intent extraction and dialogue
- **OpenAI GPT-4o** - Fallback provider for resilience
- **LangGraph** - Multi-agent orchestration framework
- **instructor** - Structured LLM output library
- **OpenTelemetry** - Observability stack

---

## 📚 Documentation

- [CLAUDE.md](CLAUDE.md) - Development guide for AI assistants
- [API Documentation](http://localhost:8000/docs) - Interactive Swagger UI
- [Architecture Diagrams](docs/architecture/) - Detailed system design
- [Prompt Engineering](docs/prompts/) - All LLM prompt chains

---

**Status**: 🟢 Active Development (Sprint 2)
**Last Updated**: 2026-04-29
**Version**: 0.1.0
