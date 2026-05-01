# AI DevOps Agent Platform

> **Transform natural language into production-ready cloud infrastructure**

An AI-powered multi-agent system that converts conversational intent into validated Terraform, CI/CD pipelines, and IAM policies. Features confidence-aware intent tracking, OPA security gates, Tree-of-Thought architecture evaluation, and smart error recovery.

[![Tests](https://img.shields.io/badge/tests-70%20passed-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

---

## Try It Now

```bash
git clone https://github.com/mirdattamir/AgenticDevops.git && cd AgenticDevops
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
make demo-quick   # Runs in < 2 minutes, no Docker required
```

<details>
<summary><b>Preview: What You'll See</b> (click to expand)</summary>

```
╔══════════════════════════════════════════════════════════════════════════════╗
║     █████╗ ██╗    ██████╗ ███████╗██╗   ██╗ ██████╗ ██████╗ ███████╗        ║
║    ██╔══██╗██║    ██╔══██╗██╔════╝██║   ██║██╔═══██╗██╔══██╗██╔════╝        ║
║    ███████║██║    ██║  ██║█████╗  ██║   ██║██║   ██║██████╔╝███████╗        ║
║    ██╔══██║██║    ██║  ██║██╔══╝  ╚██╗ ██╔╝██║   ██║██╔═══╝ ╚════██║        ║
║    ██║  ██║██║    ██████╔╝███████╗ ╚████╔╝ ╚██████╔╝██║     ███████║        ║
║              AI-Powered Infrastructure from Natural Language                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

SCENARIO 1: Intent → Infrastructure
  ┌─ User: "Deploy a scalable web app on AWS with EKS and CI/CD"
  │
  │  IntentSpec:
  │    ● cloud_provider: AWS [stated]
  │    ● compute_platform: EKS [stated]
  │    ○ region: us-east-1 [inferred]
  │
  │  OPA Security: ✓ ALLOWED
  │  Generated: main.tf, vpc.tf, .github/workflows/deploy.yml
  └─ ✓ COMPLETE

SCENARIO 2: Error Handling
  ┌─ Error: INVALID_REFERENCE (aws_security_group.missing)
  │  Classification: Automatic (1 of 15 types)
  │  Fix: Create missing security group
  └─ ✓ Fixed in 1 replan attempt

SCENARIO 3: FinOps Analysis
  ┌─ Budget: $100/month
  │  Evaluated: Lambda, ECS, EKS, EC2
  │  Recommendation: Lambda + API Gateway ($11.50/mo)
  └─ ✓ 88% under budget
```

[Full demo preview with screenshots →](docs/DEMO_PREVIEW.md)

</details>

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AI DevOps Agent Platform                            │
│                                                                             │
│  "Deploy a scalable web app on AWS with CI/CD"                             │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │   Intent    │───▶│  Conflict   │───▶│    OPA      │                     │
│  │   Parser    │    │  Detector   │    │  Security   │                     │
│  └─────────────┘    └─────────────┘    └─────────────┘                     │
│         │                                     │                             │
│         ▼                                     ▼                             │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │              IntentSpec (Canonical Intent)                   │           │
│  │  • Confidence: stated | confirmed | inferred | speculative  │           │
│  │  • Categories: task | meta | constraint                      │           │
│  └─────────────────────────────────────────────────────────────┘           │
│                              │                                              │
│         ┌────────────────────┼────────────────────┐                        │
│         ▼                    ▼                    ▼                        │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │   FinOps    │    │  Terraform  │    │   CI/CD     │                     │
│  │   Scorer    │    │  Generator  │    │  Generator  │                     │
│  │   (ToT)     │    └─────────────┘    └─────────────┘                     │
│  └─────────────┘           │                                               │
│                            ▼                                               │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │  Validation Loop (Error → Classify → Fix → Regenerate)      │           │
│  └─────────────────────────────────────────────────────────────┘           │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │  Approval Gate (Blast Radius + Cost Delta + Human Decision) │           │
│  └─────────────────────────────────────────────────────────────┘           │
│                              │                                              │
│                              ▼                                              │
│                     [Terraform Apply]                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Confidence Tracking** | 4-band confidence system prevents execution on uncertain intent |
| **OPA Security** | Blocks wildcard IAM, open security groups, prompt injection at intent layer |
| **Smart Replanning** | 15 error types with targeted fixes, not naive retry |
| **FinOps Scoring** | Tree-of-Thought evaluation of EKS vs ECS vs Lambda vs EC2 |
| **Human Approval** | Blast radius calculation + cost delta before destructive operations |
| **Multi-Tenant** | Session isolation ensures Tenant A cannot access Tenant B |
| **Full Observability** | 30+ Prometheus metrics, Jaeger traces, Grafana dashboards |

---

## Quick Demo (< 2 minutes)

### Option 1: Instant Demo (No Docker Required)

```bash
# Clone repository
git clone https://github.com/mirdattamir/AgenticDevops.git
cd AgenticDevops

# Setup Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run demo - shows all 3 scenarios instantly
make demo-quick
```

**What you'll see:**
1. **Intent → Infrastructure**: Natural language converted to Terraform + CI/CD
2. **Error Handling**: Terraform error → classification → smart replan → fix
3. **FinOps Analysis**: Tree-of-Thought cost comparison (Lambda vs EKS vs ECS)

### Option 2: Full Stack Demo (Docker Required)

```bash
# Start all services (API, Prometheus, Grafana, Jaeger, OPA, Redis)
make demo-up

# Services will be available at:
# • API:        http://localhost:8000
# • Grafana:    http://localhost:3010  (admin/devops123)
# • Prometheus: http://localhost:9090
# • Jaeger:     http://localhost:16686

# Stop services when done
make demo-down
```

### Demo Scenarios

| Scenario | Command | Description |
|----------|---------|-------------|
| **1. Intent → Infra** | `make demo-scenario-1` | Natural language to Terraform + CI/CD |
| **2. Error Handling** | `make demo-scenario-2` | Inject error → Classify → Smart replan |
| **3. FinOps Analysis** | `make demo-scenario-3` | Tree-of-Thought cost optimization |

### AWS Deployment (Optional)

```bash
# Deploy to AWS ECS Fargate (requires AWS credentials)
cp infra/terraform.tfvars.example infra/terraform.tfvars
# Edit terraform.tfvars with your API keys

make aws-up      # Deploy full stack to AWS
make aws-status  # Show endpoints
make aws-down    # Destroy infrastructure (avoid costs)
```

### Host Static Demo (Cloudflare Pages / Netlify)

Share the demo with recruiters via a static landing page:

| Platform | Method |
|----------|--------|
| **Cloudflare Pages** | Dashboard → Workers & Pages → Upload `docs/demo-site` |
| **Cloudflare CLI** | `cd docs/demo-site && wrangler pages deploy .` |
| **Netlify** | Drag `docs/demo-site` to [netlify.com](https://app.netlify.com) |

[Full deployment guide →](docs/DEMO_PREVIEW.md#hosting-the-demo-site)

---

## Installation

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- OPA CLI (for policy testing)

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
make install

# Configure environment
cp .env.example .env
# Edit .env with your API keys (ANTHROPIC_API_KEY, etc.)

# Start all services
make demo-up
```

### Services

| Service | URL | Purpose |
|---------|-----|---------|
| API | http://localhost:8000 | Main FastAPI application |
| API Docs | http://localhost:8000/docs | OpenAPI documentation |
| Grafana | http://localhost:3010 | Dashboards (admin/devops123) |
| Prometheus | http://localhost:9090 | Metrics collection |
| Jaeger | http://localhost:16686 | Distributed tracing |
| OPA | http://localhost:8182 | Policy engine |

---

## How It Works

### 1. Intent Parsing

```
User: "Deploy a scalable web app on AWS with EKS and CI/CD"
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│  IntentSpec                                             │
│  ├── cloud_provider: AWS [STATED]                       │
│  ├── compute_platform: EKS [STATED]                     │
│  ├── ci_cd: GitHub Actions [INFERRED]                   │
│  └── region: us-east-1 [SPECULATIVE]                    │
└─────────────────────────────────────────────────────────┘
```

### 2. Security Check (OPA)

```
✓ No wildcard IAM detected
✓ No open security groups (0.0.0.0/0)
✓ No prompt injection patterns
✓ Intent structure valid
→ ALLOWED
```

### 3. Generation + Validation

```
Generate Terraform → Validate → Error?
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
               [No Error]              [Error Detected]
                    │                           │
                    ▼                           ▼
              Approval Gate         Classify (15 types)
                                            │
                                            ▼
                                    Smart Replan
                                            │
                                            ▼
                                    Regenerate (targeted)
```

### 4. Human Approval

```
┌─────────────────────────────────────────────────────────┐
│  APPROVAL REQUIRED                                       │
│                                                          │
│  Blast Radius:                                           │
│  • Create: 12 resources                                  │
│  • Delete: 2 resources ⚠️                               │
│  • Risk Level: HIGH                                      │
│                                                          │
│  Cost Delta: +$100/month (+67%)                          │
│                                                          │
│  [APPROVE]  [REJECT]            Timeout: 5 minutes       │
└─────────────────────────────────────────────────────────┘
```

---

## Testing

```bash
# Run all tests (426 tests)
make test

# Run specific suites
make test-unit          # Unit tests
make test-adversarial   # OPA prompt injection tests

# With coverage
make test-coverage
```

---

## Project Structure

```
AgenticDevops/
├── agents/
│   ├── intent_parser/     # Semantic extraction
│   ├── planner/           # Smart replanning (CoT)
│   ├── generators/        # Terraform, IAM, CI/CD
│   ├── finops/            # FinOps scoring (ToT)
│   └── validator/         # Error intelligence
├── intent/
│   ├── schema.py          # IntentSpec models
│   ├── confidence.py      # State machine
│   └── session_manager.py # Multi-tenant sessions
├── security/
│   ├── opa_intent_gate.py # Python OPA client
│   └── policies/          # Rego policies
├── gates/
│   └── human_approval.py  # Approval gate
├── observability/
│   └── agent_tracer.py    # OpenTelemetry + Prometheus
├── demo/                  # Demo scripts
├── dashboards/            # Grafana JSON
└── architecture/          # Architecture docs
```

---

## Sprint Status

| Sprint | Focus | Status |
|--------|-------|--------|
| Sprint 0 | Foundation | ✅ Complete |
| Sprint 1 | Intent Engine | ✅ Complete |
| Sprint 2 | DAG + FinOps + Generators | ✅ Complete |
| Sprint 3 | Validation + Security | ✅ Complete |
| Sprint 4 | Observability + HITL | ✅ Complete |

**Total: 426 tests passing**

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](architecture/ARCHITECTURE.md) | System design and data flow |
| [FinOps Analysis](docs/FINOPS_ANALYSIS.md) | Cost optimization guide |
| [Sprint 3 Summary](docs/SPRINT_3_SUMMARY.md) | Validation + Security |
| [Sprint 4 Summary](docs/SPRINT_4_SUMMARY.md) | Observability + HITL |
| [CLAUDE.md](CLAUDE.md) | AI assistant guidance |

---

## Security

### OPA Policies (Intent Layer)

| Policy | Action |
|--------|--------|
| Wildcard IAM (`*`) | BLOCK |
| Open security groups (0.0.0.0/0) | BLOCK (except 80/443) |
| Prompt injection (15 patterns) | BLOCK |
| Invalid intent structure | BLOCK |

### Confidence-Based Execution

| Action | Minimum Confidence |
|--------|-------------------|
| Generate Terraform | `confirmed` |
| Terraform Apply | `confirmed` + approval |
| Delete Resources | `confirmed` + approval |

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

**Built with**: LangGraph, FastAPI, Terraform, OPA, OpenTelemetry, Prometheus, Grafana
