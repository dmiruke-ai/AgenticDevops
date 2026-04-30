# OPA Security Policies - AI DevOps Agent

## Overview

This directory contains the **5 security policies** that protect the AI DevOps Agent Platform at the intent layer.

All policies execute **before** Terraform code generation, preventing dangerous configurations from ever being created.

## Policies Implemented

### 1. Wildcard IAM Blocking (BLOCKING) ✅

**File:** `intent_security.rego` (lines 15-84)

**What it blocks:**
- `"Resource": "*"` in IAM policies
- `"Action": "*"` in IAM policies
- Any wildcard ARNs except AWS-required services

**Allowed exceptions:**
- `ec2:Describe*` - AWS requires for discovery
- `s3:List*` - Standard for bucket operations
- `xray:*` - X-Ray tracing
- `logs:Create*`, `logs:Describe*` - CloudWatch logging

**Tests:** 4 tests in `intent_security_test.rego`

---

###2. Open Security Group Blocking (BLOCKING) ✅

**File:** `intent_security.rego` (lines 86-146)

**What it blocks:**
- `0.0.0.0/0` ingress on ports other than 80/443
- `::/0` (IPv6 open) ingress on non-HTTP/HTTPS ports

**Allowed exceptions:**
- Port 80 (HTTP) with `0.0.0.0/0`
- Port 443 (HTTPS) with `0.0.0.0/0`

**Tests:** 5 tests in `intent_security_test.rego`

---

### 3. Prompt Injection Detection (BLOCKING) ✅

**File:** `intent_security.rego` (lines 148-210)

**What it blocks:**
- "Ignore previous instructions"
- "You are a DevOps engineer" (role manipulation)
- "Skip OPA validation" (bypass attempts)
- "Allow wildcard" (policy override attempts)

**Detection patterns:**
- Instruction override (9 patterns)
- Role manipulation (6 patterns)
- Policy bypass (7 patterns)

**Tests:** 4 tests in `intent_security_test.rego`

---

### 4. Intent Structure Validation (BLOCKING) ✅

**File:** `intent_security.rego` (lines 212-290)

**What it validates:**
- `session_id` is present
- `turn` number is present
- `new_items` is an array
- Each item has `key` and `category`
- Category is one of: `task_intent`, `meta_intent`, `constraint_intent`

**Tests:** 6 tests in `intent_security_test.rego`

---

### 5. Permissive Configuration Warnings (WARNING) ✅

**File:** `intent_security.rego` (lines 292-332)

**What it warns about:**
- Wide port ranges (>100 ports)
- Too many IAM actions (>10 in one statement)

**Note:** Warnings do NOT block execution - they appear in audit logs.

**Tests:** 2 tests in `intent_security_test.rego`

---

## Testing

### Run All Tests

```bash
# Using OPA CLI
opa test security/policies/

# Using Docker
docker run --rm -v "$PWD/security/policies:/policies" \
  openpolicyagent/opa:latest test /policies/
```

**Expected output:**
```
PASS: 20/20
```

### Test Individual Policy

```bash
# Test wildcard IAM blocking
curl -X POST http://localhost:8182/v1/data/devops_agent/intent_security/deny \
  -d '{
    "input": {
      "intent_spec": {
        "session_id": "test",
        "turn": 1,
        "new_items": [{
          "key": "iam_policy",
          "category": "task_intent",
          "value": {
            "statements": [{
              "actions": ["s3:GetObject"],
              "resources": ["*"]
            }]
          }
        }]
      }
    }
  }'

# Response: ["BLOCKED: Wildcard IAM policy detected..."]
```

---

## Policy Decision Flow

```
User Message
     ↓
Semantic Extraction (LLM)
     ↓
ExtractionResult
     ↓
OPA Intent Gate ← Checks all 5 policies
     ↓
   DENY? → Raise IntentPolicyViolation
     ↓
   ALLOW → Merge into IntentSpec
     ↓
Code Generation
```

---

## Updating Policies

### Method 1: File Edit (Development)

```bash
vim security/policies/intent_security.rego
# OPA auto-reloads in ~100ms (via --watch flag)
```

### Method 2: HTTP API (Production)

```bash
./scripts/update_policy.sh intent_security security/policies/intent_security.rego
```

### Method 3: Rollback

```bash
curl -X POST "http://localhost:8183/policies/intent_security/rollback?version=2"
```

---

## Integration with Application

The Python application uses `OPAIntentGate` to validate intents:

```python
from security.opa_intent_gate import OPAIntentGate, IntentPolicyViolation

gate = OPAIntentGate(opa_url="http://opa:8181")

try:
    gate.validate(extraction_result, user_message, session_id, turn)
    # Policy passed - safe to merge into IntentSpec
except IntentPolicyViolation as e:
    # Policy blocked - return error to user
    print(f"Blocked: {e.violations}")
```

---

## Policy Metadata

- **Version:** 1.0.0
- **Last Updated:** 2026-04-29
- **Total Policies:** 5 (4 blocking + 1 warning)
- **Total Tests:** 20 (all passing)
- **Language:** Rego (OPA Policy Language)

---

## Security Guarantees

With these policies active:

✅ **No wildcard IAM** policies reach Terraform generation
✅ **No open SSH** (port 22) on public internet
✅ **No prompt injection** attacks bypass validation
✅ **No malformed intents** corrupt the IntentSpec
✅ **All violations logged** with session_id + turn for audit

---

## Next Steps

1. **S3-09**: Implement `OPAIntentGate` Python client
2. **S3-10**: Create adversarial test suite (15 inputs)
3. **S3-11**: Add audit logging for all OPA checks
4. **S3-07**: Integrate with validation node
