# Portfolio Demo & Deployment Directive

> **Reusable template for implementing demo infrastructure across portfolio projects**

This directive ensures all portfolio projects follow the same "always visible, instantly demoable" pattern.

---

## Core Principle

> **The system must be always visible, not always running, and instantly demoable**

- **Local Demo**: Works in < 2 minutes with no external dependencies
- **Full Stack Demo**: Docker Compose for complete observability
- **AWS Deployment**: Terraform for production realism (on-demand, not always-on)

---

## Implementation Checklist

### Phase 1: Local Demo (MUST HAVE)

- [ ] Create `demo/` directory with demo scripts
- [ ] Implement mock mode (no external services required)
- [ ] Add Makefile targets:
  ```makefile
  demo-quick    # Mock mode, instant
  demo-scenario-1/2/3  # Individual scenarios
  ```
- [ ] Ensure demo runs with only Python + pip install

### Phase 2: Full Stack Demo (SHOULD HAVE)

- [ ] Create `docker-compose.yml` with all services
- [ ] Add observability stack:
  - Prometheus (metrics)
  - Grafana (dashboards)
  - Jaeger (tracing)
- [ ] Add Makefile targets:
  ```makefile
  demo-up       # Start services + run demo
  demo-down     # Stop services
  logs          # View service logs
  ```
- [ ] Create Grafana dashboard JSON (`observability/grafana/dashboards/`)
- [ ] Create Prometheus config (`observability/prometheus.yml`)

### Phase 3: AWS Deployment (OPTIONAL)

- [ ] Create `infra/` directory with Terraform modules:
  ```
  infra/
  ├── main.tf
  ├── variables.tf
  ├── outputs.tf
  ├── terraform.tfvars.example
  └── modules/
      ├── vpc/
      ├── ecs/ (or eks/)
      ├── alb/
      ├── secrets/
      └── observability/
  ```
- [ ] Add Makefile targets:
  ```makefile
  aws-up        # Deploy to AWS
  aws-down      # Destroy infrastructure
  aws-status    # Show endpoints
  aws-logs      # Tail CloudWatch logs
  ```
- [ ] Create ECR push workflow:
  ```makefile
  ecr-create    # Create ECR repository
  ecr-push      # Build and push image
  ```

### Phase 4: Documentation (MUST HAVE)

- [ ] Update README with "Try It Now" section (3-line copy-paste)
- [ ] Add collapsible preview showing demo output
- [ ] Create `docs/DEMO_PREVIEW.md` with full screenshots
- [ ] Add terminal recording (`demo/recordings/`)

---

## Makefile Template

```makefile
# =============================================================================
# [PROJECT_NAME] - Makefile
# =============================================================================

.PHONY: help demo-quick demo-up demo-down aws-up aws-down

# Default target
help:
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║  [PROJECT_NAME] - Demo Commands                                  ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  LOCAL DEMO                                                      ║"
	@echo "║  make demo-quick       Quick demo (no services, mock mode)       ║"
	@echo "║  make demo-up          Start services and run full demo          ║"
	@echo "║  make demo-down        Stop all services                         ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  AWS DEPLOYMENT                                                  ║"
	@echo "║  make aws-up           Deploy to AWS                             ║"
	@echo "║  make aws-down         Destroy AWS infrastructure                ║"
	@echo "║  make aws-status       Show deployment endpoints                 ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"

# =============================================================================
# Local Demo
# =============================================================================

demo-quick:
	@python demo/run_demo.py --mock

demo-up:
	docker compose up -d
	@sleep 5
	@echo "Services ready:"
	@echo "  API:        http://localhost:8000"
	@echo "  Grafana:    http://localhost:3010"
	@echo "  Prometheus: http://localhost:9090"

demo-down:
	docker compose down

# =============================================================================
# AWS Deployment
# =============================================================================

aws-up:
	cd infra && terraform init && terraform apply -auto-approve
	@echo "✅ Deployment complete. Run 'make aws-status' to see endpoints."

aws-down:
	cd infra && terraform destroy -auto-approve

aws-status:
	@cd infra && terraform output

# =============================================================================
# Terminal Recordings
# =============================================================================

record-demo:
	@command -v asciinema >/dev/null || pip install asciinema
	asciinema rec demo/recordings/demo-quick.cast -c "make demo-quick" --overwrite
```

---

## Docker Compose Template

```yaml
version: '3.8'

services:
  # Main Application
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - OTLP_ENDPOINT=http://jaeger:4317
    depends_on:
      - redis

  # State Store
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # Observability
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./observability/prometheus.yml:/etc/prometheus/prometheus.yml:ro

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3010:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_AUTH_ANONYMOUS_ENABLED=true
    volumes:
      - ./observability/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./observability/grafana/dashboards:/var/lib/grafana/dashboards:ro

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"
      - "4317:4317"
```

---

## README Template

```markdown
# [Project Name]

> One-line description of what this project does

## Try It Now

\`\`\`bash
git clone https://github.com/[user]/[repo].git && cd [repo]
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
make demo-quick   # Runs in < 2 minutes
\`\`\`

<details>
<summary><b>Preview: What You'll See</b></summary>

\`\`\`
[ASCII art / demo output preview]
\`\`\`

</details>

## Demo Options

| Command | Requirements | What It Does |
|---------|--------------|--------------|
| `make demo-quick` | Python only | Mock demo (instant) |
| `make demo-up` | Docker | Full stack with observability |
| `make aws-up` | AWS + Terraform | Production deployment |

## Services (Full Stack)

| Service | URL | Purpose |
|---------|-----|---------|
| API | http://localhost:8000 | Main application |
| Grafana | http://localhost:3010 | Dashboards |
| Prometheus | http://localhost:9090 | Metrics |
| Jaeger | http://localhost:16686 | Tracing |
```

---

## Terminal Recording Workflow

### 1. Install asciinema
```bash
pip install asciinema
```

### 2. Record Demo
```bash
make record-demo
# Or manually:
asciinema rec demo/recordings/demo-quick.cast -c "make demo-quick"
```

### 3. Upload to asciinema.org
```bash
asciinema upload demo/recordings/demo-quick.cast
```

### 4. Embed in README
```markdown
[![asciicast](https://asciinema.org/a/YOUR_ID.svg)](https://asciinema.org/a/YOUR_ID)
```

### 5. Convert to GIF (Optional)
```bash
# Install agg
cargo install --git https://github.com/asciinema/agg

# Convert
agg demo/recordings/demo-quick.cast demo/recordings/demo-quick.gif
```

---

## Terraform Module Structure

```
infra/
├── main.tf                 # Root module
├── variables.tf            # Input variables
├── outputs.tf              # Output values
├── terraform.tfvars.example
└── modules/
    ├── vpc/
    │   └── main.tf         # VPC, subnets, NAT, IGW
    ├── ecs/
    │   └── main.tf         # ECS cluster, task definitions, services
    ├── alb/
    │   └── main.tf         # ALB, target groups, listeners
    ├── secrets/
    │   └── main.tf         # Secrets Manager for API keys
    └── observability/
        └── main.tf         # CloudWatch dashboard, alarms
```

---

## Interview Script

When asked "Is this deployed?":

> "Yes. I designed it to run locally for fast demos using Docker, and I also have a Terraform-based AWS deployment for production scenarios. I don't keep it always running to avoid cost and reliability issues, but I can spin it up quickly if needed."

This signals:
- Practicality
- Cost awareness
- Production thinking

---

## Quick Reference

| Task | Command |
|------|---------|
| Quick demo (mock) | `make demo-quick` |
| Full stack demo | `make demo-up` |
| Stop services | `make demo-down` |
| Deploy to AWS | `make aws-up` |
| Destroy AWS | `make aws-down` |
| Show AWS endpoints | `make aws-status` |
| Record terminal | `make record-demo` |
| View recording | `asciinema play demo/recordings/demo-quick.cast` |

---

## Projects Using This Directive

- [x] AgenticDevops - AI DevOps Agent Platform
- [ ] LLMOps Control Plane
- [ ] (Other portfolio projects)
