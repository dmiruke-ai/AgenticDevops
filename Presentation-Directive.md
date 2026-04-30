# Agentic DevOps Platform — End User Presentation Directive

## 🧠 Objective

Build and present an **AI DevOps Agent Platform** that:

* Converts natural language intent into infrastructure + CI/CD
* Demonstrates production-grade reasoning and system design
* Is **instantly understandable, demoable on demand, NOT always running**

---

## ⚖️ Core Principle

> The system must be **always visible, not always running, and instantly demoable**

---

## 🧱 1. Architecture Boundaries (MANDATORY)

### ✅ Core Components

* Intent Parser (IntentSpec engine)
* Reasoning Engine (planner)
* Infra Generator (Terraform / CDK)
* CI/CD Generator
* Validation + Replanning Loop
* FinOps + Security modules

### ❌ Strict Prohibitions

* No naive retry loops
* No unvalidated LLM outputs
* No hidden logic inside prompts
* No coupling between infra generation and runtime execution

---

## 🔁 2. Core System Rules

### IntentSpec Requirements

* Must be **structured, versioned, persistent**
* Must include:

  * Surface / Task / Meta intent
  * Confidence levels (stated, inferred, confirmed)
  * Assumptions and open questions

### REQUIRED Additions

* Confidence transition rules
* Conflict resolution protocol
* Schema validation (JSON strict)

---

### Validation Loop (CRITICAL)

Must implement:

```
Error → Classification → Structured Fix → Targeted Regeneration
```

NOT:

```
retry_same_output()
```

---

### DAG Execution Model (MANDATORY)

* Tasks must be dependency-aware
* Example:

```
infra_gen → pipeline_gen → deployment_strategy
```

---

## 🔐 3. Security Requirements

Must include:

* Prompt injection protection
* Policy validation before execution
* IAM constraints enforcement

---

## 📊 4. Observability Requirements (NON-NEGOTIABLE)

Must expose:

* IntentSpec mutations
* LLM calls
* retry / failure loops
* cost estimation decisions

---

## 🎬 5. Portfolio Presentation Strategy

### Layer 1 — ALWAYS VISIBLE (MANDATORY)

* GitHub repo
* README with architecture
* screenshots (infra, logs, outputs)
* demo video (2–3 min)

---

### Layer 2 — ON-DEMAND DEMO

* Live demo (local/cloud)
* scripted flow:

  * user intent → generated infra → validation → output

---

### Layer 3 — ALWAYS-ON SYSTEM

❌ NOT REQUIRED
❌ AVOID (cost + reliability risk)

---

## ⚙️ 6. Demo Requirements

### Must Support

```
make demo-up
```

---

### Required Scenarios

#### Scenario 1 — Intent → Infra

* user input → Terraform + pipeline

#### Scenario 2 — Failure Handling

* inject Terraform error → system fixes

#### Scenario 3 — Optimization

* cost-aware decision change

---

## 📁 7. Repository Structure

```
agentic-devops/
├── README.md
├── demo/
├── architecture/
├── intent-parser/
├── reasoning-engine/
├── infra-generator/
├── validation-loop/
├── policy/
├── observability/
└── infra/
```

---

## 📘 8. README Requirements

Top section MUST include:

* what this is (2 lines)
* architecture diagram
* key features

Then:

* how it works
* demo steps
* screenshots
* video link

---

## 🎯 9. Success Criteria

System is valid ONLY if:

* understandable in < 60 seconds
* demoable in < 5 minutes
* produces:

  * structured outputs
  * explainable decisions
  * observable behavior

---

## 🔚 Final Directive

Build a system that:

* behaves like production
* enforces correctness
* demonstrates reasoning and repair
* but is optimized for **clarity and demo, not uptime**

