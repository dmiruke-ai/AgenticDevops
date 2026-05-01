# Demo Preview

This document shows exactly what you'll see when running the demos.

## Terminal Recording

Watch the full demo (90 seconds):
```bash
# Play the recording locally
pip install asciinema
asciinema play demo/recordings/demo-quick.cast
```

---

## Screenshot: Scenario 1 - Intent to Infrastructure

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║     █████╗ ██╗    ██████╗ ███████╗██╗   ██╗ ██████╗ ██████╗ ███████╗        ║
║    ██╔══██╗██║    ██╔══██╗██╔════╝██║   ██║██╔═══██╗██╔══██╗██╔════╝        ║
║    ███████║██║    ██║  ██║█████╗  ██║   ██║██║   ██║██████╔╝███████╗        ║
║    ██╔══██║██║    ██║  ██║██╔══╝  ╚██╗ ██╔╝██║   ██║██╔═══╝ ╚════██║        ║
║    ██║  ██║██║    ██████╔╝███████╗ ╚████╔╝ ╚██████╔╝██║     ███████║        ║
║    ╚═╝  ╚═╝╚═╝    ╚═════╝ ╚══════╝  ╚═══╝   ╚═════╝ ╚═╝     ╚══════╝        ║
║                                                                              ║
║              AI-Powered Infrastructure from Natural Language                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

══════════════════════════════════════════════════════════════════════════════
  SCENARIO 1: Intent → Infrastructure
──────────────────────────────────────────────────────────────────────────────

  ┌─ Step 1: User Intent (Natural Language)
  │
  │    "Deploy a scalable web application on AWS with EKS, auto-scaling,
  │     and a CI/CD pipeline using GitHub Actions"
  └──────────────────────────────────────────────────────────────────────

  ┌─ Step 2: Intent Parsing → IntentSpec
  │
  │    IntentSpec created:
  │      Session: demo-88959b1d
  │      Version: 1
  │      Items: 6
  │
  │    Extracted Items:
  │      ● cloud_provider: AWS [stated]
  │      ● compute_platform: EKS [stated]
  │      ● scaling: auto-scaling [stated]
  │      ● ci_cd_platform: GitHub Actions [stated]
  │      ○ region: us-east-1 [inferred]
  │      ○ node_count: 3 [inferred]
  └──────────────────────────────────────────────────────────────────────

  ┌─ Step 3: OPA Security Policy Check
  │
  │    Checking policies:
  │      ✓ No wildcard IAM detected
  │      ✓ No open security groups (0.0.0.0/0 on sensitive ports)
  │      ✓ No prompt injection patterns
  │      ✓ Intent structure valid
  │
  │    Result: ALLOWED
  └──────────────────────────────────────────────────────────────────────

  ┌─ Step 4: Terraform Generation
  │
  │    Generated: main.tf
  │    ──────────────────────────────────────────────────
  │    terraform {
  │      required_version = ">= 1.0"
  │      required_providers {
  │        aws = {
  │          source  = "hashicorp/aws"
  │          version = "~> 5.0"
  │        }
  │      }
  │    }
  │
  │    module "eks" {
  │      source          = "terraform-aws-modules/eks/aws"
  │      cluster_name    = "demo-cluster"
  │      cluster_version = "1.28"
  │      ...
  │    }
  └──────────────────────────────────────────────────────────────────────

  ╔═══════════════════════════════════════════════════════════════╗
  ║  SCENARIO 1 COMPLETE                                          ║
  ╠═══════════════════════════════════════════════════════════════╣
  ║  Input:  Natural language intent                              ║
  ║  Output: Validated Terraform + CI/CD pipeline                 ║
  ║                                                               ║
  ║  Artifacts Generated:                                         ║
  ║  • main.tf (EKS cluster configuration)                        ║
  ║  • vpc.tf (VPC with private subnets)                          ║
  ║  • .github/workflows/deploy.yml (CI/CD)                       ║
  ╚═══════════════════════════════════════════════════════════════╝
```

---

## Screenshot: Scenario 2 - Error Handling

```
══════════════════════════════════════════════════════════════════════════════
  SCENARIO 2: Error Handling & Smart Replanning
──────────────────────────────────────────────────────────────────────────────

  ┌─ Step 1: Initial Terraform (Contains Error)
  │
  │    resource "aws_instance" "web" {
  │      ami           = "ami-12345678"
  │      instance_type = "t3.medium"
  │
  │      # ERROR: References non-existent security group
  │      vpc_security_group_ids = [aws_security_group.missing.id]
  │    }
  └──────────────────────────────────────────────────────────────────────

  ┌─ Step 2: Terraform Validation Fails
  │
  │    ❌ Error: Reference to undeclared resource
  │
  │      on main.tf line 6:
  │       6:   vpc_security_group_ids = [aws_security_group.missing.id]
  │
  │    A managed resource "aws_security_group" "missing" has not been
  │    declared in the root module.
  └──────────────────────────────────────────────────────────────────────

  ┌─ Step 3: Error Classification (NOT naive retry)
  │
  │    Classification Result:
  │    ──────────────────────────────────────────────────
  │      Error Type:    INVALID_REFERENCE
  │      Severity:      HIGH
  │      Resource:      aws_security_group.missing
  │
  │    Fix Strategy:
  │      → Add missing security group resource
  │      → Or reference existing security group
  │
  │    Available Error Types (15 total):
  │      • MISSING_PROVIDER      • INVALID_REFERENCE
  │      • INVALID_ATTRIBUTE     • CYCLE_DETECTED
  │      • SYNTAX_ERROR          • TYPE_MISMATCH
  │      • MISSING_REQUIRED      • ... and 8 more
  └──────────────────────────────────────────────────────────────────────

  ┌─ Step 4: Smart Replanning (Chain-of-Thought)
  │
  │    Reasoning:
  │      1. Error: INVALID_REFERENCE to aws_security_group.missing
  │      2. Context: EC2 instance needs security group for VPC
  │      3. Options:
  │         a) Create new security group resource
  │         b) Use existing security group from VPC module
  │         c) Use default VPC security group
  │      4. Decision: Create new security group (most explicit)
  │      5. Additional: Add ingress rules for HTTP/HTTPS
  └──────────────────────────────────────────────────────────────────────

  ┌─ Step 5: Re-validation (Attempt 2 of 3)
  │
  │    ✓ Success! The configuration is valid.
  │
  │    Validation Loop:
  │      Attempt 1: ❌ INVALID_REFERENCE
  │      Attempt 2: ✓ Passed
  │      Attempts remaining: 1
  └──────────────────────────────────────────────────────────────────────

  ╔═══════════════════════════════════════════════════════════════╗
  ║  SCENARIO 2 COMPLETE                                          ║
  ╠═══════════════════════════════════════════════════════════════╣
  ║  Error Injected:  INVALID_REFERENCE                           ║
  ║  Classification:  Automatic (regex + LLM fallback)            ║
  ║  Fix Strategy:    Targeted regeneration (not full retry)      ║
  ║  Result:          Fixed in 1 replan attempt                   ║
  ╚═══════════════════════════════════════════════════════════════╝
```

---

## Screenshot: Scenario 3 - FinOps Cost Optimization

```
══════════════════════════════════════════════════════════════════════════════
  SCENARIO 3: FinOps Cost Optimization
──────────────────────────────────────────────────────────────────────────────

  ┌─ Step 1: User Intent (Cost-Sensitive)
  │
  │    "I need to deploy a REST API service.
  │     Budget is tight - keep costs under $100/month if possible."
  │
  │    Extracted Priority: COST
  │    Budget Constraint: $100/month
  └──────────────────────────────────────────────────────────────────────

  ┌─ Step 2: Tree-of-Thought Reasoning
  │
  │    Paths to Explore:
  │      Path A: Lambda + API Gateway + DynamoDB
  │      Path B: ECS Fargate + ALB + RDS
  │      Path C: EKS + ALB + Aurora
  │      Path D: EC2 + ALB + RDS
  └──────────────────────────────────────────────────────────────────────

  ┌─ Step 3: Multi-Dimensional Scoring
  │
  │    ┌─────────────────────────┬────────┬──────┬───────┬──────────┐
  │    │ Architecture            │ $/mo   │ Cost │ Scale │ Composite│
  │    ├─────────────────────────┼────────┼──────┼───────┼──────────┤
  │    │ Lambda + API GW + Dynamo│ $25    │ 9.5  │ 9.0   │ 9.05 ★   │
  │    │ ECS Fargate + ALB + RDS │ $150   │ 7.0  │ 8.0   │ 7.80     │
  │    │ EKS + ALB + Aurora      │ $350   │ 5.0  │ 9.5   │ 7.95     │
  │    │ EC2 + ALB + RDS         │ $120   │ 7.5  │ 7.0   │ 7.40     │
  │    └─────────────────────────┴────────┴──────┴───────┴──────────┘
  │
  │    ★ = Recommended (highest composite score within budget)
  └──────────────────────────────────────────────────────────────────────

  ┌─ Step 4: Cost Breakdown (Recommended)
  │
  │    Lambda + API Gateway + DynamoDB
  │    ──────────────────────────────────────────────────
  │      AWS Lambda:      $1.87
  │      API Gateway:     $3.50
  │      DynamoDB:        $1.13
  │      CloudWatch:      $5.00
  │      ─────────────────────────────────────────
  │      TOTAL:           $11.50/month (88% under budget)
  │
  │      ✓ Well within $100/month budget
  │      ✓ Scales to zero when not in use
  │      ✓ No server management required
  └──────────────────────────────────────────────────────────────────────

  ┌─ Step 5: Flip Point Analysis
  │
  │    When should you switch architectures?
  │
  │    Lambda → ECS Fargate:
  │      Flip Point: ~3 million requests/month
  │
  │    Your load:    1M requests/month
  │    Flip point:   3M requests/month
  │    Headroom:     200% growth before switch needed
  └──────────────────────────────────────────────────────────────────────

  ╔═══════════════════════════════════════════════════════════════╗
  ║  SCENARIO 3 COMPLETE                                          ║
  ╠═══════════════════════════════════════════════════════════════╣
  ║  User Priority:    COST ($100/month budget)                   ║
  ║  Paths Evaluated:  4 (Lambda, ECS, EKS, EC2)                  ║
  ║  Recommendation:   Lambda + API Gateway + DynamoDB            ║
  ║  Estimated Cost:   $11.50/month (88% under budget)            ║
  ╚═══════════════════════════════════════════════════════════════╝
```

---

## Full Stack Demo (`make demo-up`)

When you run `make demo-up`, you get:

### Live Services

| Service | URL | What It Shows |
|---------|-----|---------------|
| **API** | http://localhost:8000 | FastAPI with OpenAPI docs |
| **Grafana** | http://localhost:3010 | Real-time metrics dashboard |
| **Prometheus** | http://localhost:9090 | Raw metrics queries |
| **Jaeger** | http://localhost:16686 | Distributed traces |

### Grafana Dashboard

The Grafana dashboard shows:
- **Active Sessions**: Number of concurrent users
- **LLM Latency (p95)**: Response time for AI calls
- **Validation Retry Rate**: % of Terraform errors requiring replan
- **LLM Cost (1h)**: Estimated API costs
- **Request Rate by Endpoint**: Traffic patterns
- **Terraform Errors by Type**: Error classification breakdown

---

## AWS Deployment (`make aws-up`)

```
╔══════════════════════════════════════════════════════════════════╗
║  🚀 Deploying to AWS (ECS Fargate)                               ║
╚══════════════════════════════════════════════════════════════════╝

Terraform will perform the following actions:

  + aws_vpc.main
  + aws_subnet.public[0]
  + aws_subnet.public[1]
  + aws_subnet.private[0]
  + aws_subnet.private[1]
  + aws_nat_gateway.main
  + aws_ecs_cluster.main
  + aws_ecs_service.api
  + aws_ecs_service.grafana
  + aws_ecs_service.prometheus
  + aws_ecs_service.jaeger
  + aws_lb.main
  + aws_cloudwatch_dashboard.main
  ... (25 resources total)

Apply complete! Resources: 25 added, 0 changed, 0 destroyed.

╔══════════════════════════════════════════════════════════════════╗
║  ✅ AWS Deployment Complete!                                     ║
╚══════════════════════════════════════════════════════════════════╝

Outputs:

  api_url     = "http://devops-agent-demo-alb-xxx.us-east-1.elb.amazonaws.com"
  grafana_url = "http://devops-agent-demo-alb-xxx.us-east-1.elb.amazonaws.com:3000"
  cloudwatch_dashboard_url = "https://console.aws.amazon.com/cloudwatch/..."
```

### AWS Architecture Deployed

```
┌─────────────────────────────────────────────────────────────────────┐
│                           AWS (us-east-1)                           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                        VPC (10.0.0.0/16)                      │  │
│  │  ┌─────────────────┐    ┌─────────────────┐                   │  │
│  │  │  Public Subnet  │    │  Public Subnet  │                   │  │
│  │  │   (10.0.0.0/24) │    │   (10.0.1.0/24) │                   │  │
│  │  │       ALB       │    │       NAT       │                   │  │
│  │  └────────┬────────┘    └─────────────────┘                   │  │
│  │           │                                                    │  │
│  │  ┌────────┴────────────────────────────────────────────────┐  │  │
│  │  │                    Private Subnets                       │  │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │  │  │
│  │  │  │   API    │ │  Grafana │ │Prometheus│ │  Jaeger  │    │  │  │
│  │  │  │ (Fargate)│ │ (Fargate)│ │ (Fargate)│ │ (Fargate)│    │  │  │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │  │  │
│  │  │  ┌──────────┐ ┌──────────┐                               │  │  │
│  │  │  │  Redis   │ │   OPA    │                               │  │  │
│  │  │  │ (Fargate)│ │ (Fargate)│                               │  │  │
│  │  │  └──────────┘ └──────────┘                               │  │  │
│  │  └──────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  CloudWatch Dashboard + Alarms + X-Ray Tracing                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Hosting the Demo Site

The project includes a static demo landing page that can be hosted on various platforms for easy sharing with recruiters and stakeholders.

### Files Included

```
docs/demo-site/
├── index.html        # Landing page with embedded asciinema player
├── demo-quick.cast   # Terminal recording (asciinema format)
└── netlify.toml      # Netlify configuration (CORS headers)
```

### Deployment Options

#### Option 1: Cloudflare Pages (Recommended)

**Via Cloudflare Dashboard:**

1. Go to https://dash.cloudflare.com → **Workers & Pages**
2. Click **Create application** → **Pages** → **Upload assets**
3. Name your project (e.g., `devops-agent-demo`)
4. Drag the `docs/demo-site` folder or select files to upload
5. Click **Deploy site**

Your site will be live at: `https://devops-agent-demo.pages.dev`

**Via Wrangler CLI:**

```bash
# Install Wrangler CLI
npm install -g wrangler

# Login to Cloudflare
wrangler login

# Deploy
cd docs/demo-site
wrangler pages deploy . --project-name=devops-agent-demo
```

**Connect to GitHub (Auto-Deploy):**

1. Go to https://dash.cloudflare.com → **Workers & Pages** → **Create application**
2. Click **Pages** → **Connect to Git**
3. Select repository: `mirdattamir/AgenticDevops`
4. Configure build settings:
   - **Build command**: (leave empty)
   - **Build output directory**: `docs/demo-site`
5. Click **Save and Deploy**

---

#### Option 2: Netlify CLI

Best for quick one-time deployments:

```bash
# Install Netlify CLI (if not installed)
npm install -g netlify-cli

# Deploy from the demo-site directory
cd docs/demo-site
netlify deploy --prod --dir=.

# Or use npx without global install
npx netlify-cli deploy --prod --dir=.
```

You'll get a URL like: `https://random-name-12345.netlify.app`

#### Option 2: Drag & Drop (No CLI Required)

Fastest method for non-technical users:

1. Go to https://app.netlify.com (sign up/login with GitHub)
2. On the dashboard, you'll see "Want to deploy a new site without connecting to Git?"
3. Drag and drop the `docs/demo-site` folder onto the page
4. Site is live instantly at a random `.netlify.app` URL
5. Optionally rename to a custom subdomain in Site Settings

#### Option 3: Connect to GitHub (Auto-Deploy)

Best for ongoing updates - auto-deploys when you push changes:

1. Go to https://app.netlify.com/start
2. Click "Import from Git" → Select GitHub
3. Authorize Netlify and select repository: `mirdattamir/AgenticDevops`
4. Configure build settings:
   - **Base directory**: `docs/demo-site`
   - **Build command**: (leave empty - static site)
   - **Publish directory**: `docs/demo-site`
5. Click "Deploy site"

Your site will:
- Deploy automatically on every push to main
- Have a permanent URL (customizable subdomain)
- Show deploy previews for pull requests

### What the Demo Site Shows

The static demo page includes:

| Section | Description |
|---------|-------------|
| **Header** | Project title, tagline, badges (tests, Python, Terraform, license) |
| **Live Demo** | Embedded asciinema player - click to play terminal recording |
| **What It Does** | 3 core capabilities with brief descriptions |
| **Key Features** | Confidence tracking, OPA security, smart replanning, observability |
| **Try It Yourself** | Git clone + quick start commands |
| **Architecture** | ASCII diagram of the system flow |

### Customizing the Site

Edit `docs/demo-site/index.html` to:

- Change colors: Modify CSS variables in `:root`
- Update badges: Edit the `<img>` tags in `.badges`
- Add new sections: Copy existing `<section class="section">` blocks
- Update recording: Replace `demo-quick.cast` and adjust player settings

### Player Configuration

The asciinema player is configured in `index.html`:

```javascript
AsciinemaPlayer.create(
    'demo-quick.cast',
    document.getElementById('player'),
    {
        cols: 100,          // Terminal width
        rows: 30,           // Terminal height
        autoPlay: false,    // Don't auto-play on load
        preload: true,      // Preload the recording
        theme: 'dracula',   // Color theme
        fit: 'width',       // Scale to container width
        idleTimeLimit: 2    // Skip idle time > 2 seconds
    }
);
```

### Alternative: Expose Local Services

If you need to expose live running services (not just static demo), use these methods:

#### localhost.run (No Install Required)

```bash
# Expose API
ssh -R 80:localhost:8000 localhost.run

# Expose Grafana
ssh -R 80:localhost:3010 localhost.run
```

#### Cloudflare Tunnel

```bash
# Install cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared

# Expose service
./cloudflared tunnel --url http://localhost:8000
```

#### ngrok

```bash
# Install ngrok
snap install ngrok

# Expose service
ngrok http 8000
```

### Comparison: Static Site vs Live Services

| Aspect | Netlify (Static) | Live Services |
|--------|------------------|---------------|
| **Cost** | Free | Server costs |
| **Setup** | 30 seconds | Docker/AWS required |
| **Uptime** | Always available | Must be running |
| **Interactivity** | Recording only | Full API access |
| **Best for** | Portfolio, sharing | Live demos |
