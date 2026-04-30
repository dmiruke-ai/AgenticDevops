# Dynamic OPA Policy Management

This document describes the **3 mechanisms** for updating Rego policies dynamically in the AI DevOps Agent Platform.

## Overview

The platform supports dynamic policy updates without application restart:

- ✅ **File-based updates** - OPA auto-reloads via `--watch` flag
- ✅ **HTTP API updates** - REST API for programmatic updates
- ✅ **Version control** - Automatic versioning with rollback
- ✅ **Validation** - Syntax checking before activation
- ✅ **Audit trail** - Track all policy changes

## Architecture

```
┌─────────────────┐
│  Policy Admin   │ (Port 8183)
│    Service      │
└────────┬────────┘
         │ HTTP API
         ▼
┌─────────────────┐      ┌──────────────┐
│   OPA Server    │◄─────┤  --watch     │
│  (Port 8182)    │      │  Auto-reload │
└─────────────────┘      └──────────────┘
         ▲
         │ Volume Mount
         │
┌─────────────────┐      ┌──────────────┐
│ /policies       │      │ /versions    │
│ (Active)        │      │ (History)    │
└─────────────────┘      └──────────────┘
```

## Method 1: File-Based Updates (Simplest)

OPA automatically reloads policies when files change (via `--watch` flag).

### Usage

```bash
# Edit policy directly
vim security/policies/intent_security.rego

# OPA detects change and reloads in ~100ms
# Check OPA logs
docker-compose logs -f opa
```

**Pros:**
- ✅ Instant reload (~100ms)
- ✅ No API calls needed
- ✅ Works with any text editor
- ✅ Git-friendly

**Cons:**
- ❌ No validation before reload
- ❌ No automatic versioning
- ❌ Requires file system access

**Best for:** Local development, quick iterations

---

## Method 2: HTTP API Updates (Recommended)

Use the Policy Admin Service REST API for programmatic updates.

### Start Services

```bash
docker-compose up -d opa policy-admin
```

### API Endpoints

#### Update Policy

```bash
curl -X PUT http://localhost:8183/policies/intent_security \
  -H "Content-Type: text/plain" \
  --data-binary @security/policies/intent_security.rego
```

**Or use the helper script:**

```bash
./scripts/update_policy.sh intent_security security/policies/intent_security.rego
```

#### Validate Before Update

```bash
curl -X POST http://localhost:8183/policies/validate \
  -H "Content-Type: text/plain" \
  --data-binary @new_policy.rego
```

Response:
```json
{
  "valid": true,
  "error": null,
  "timestamp": "2026-04-29T12:00:00Z"
}
```

#### List All Policies

```bash
curl http://localhost:8183/policies
```

#### Get Policy Content

```bash
curl http://localhost:8183/policies/intent_security
```

#### List Policy Versions

```bash
curl http://localhost:8183/policies/intent_security/versions
```

Response:
```json
{
  "policy_name": "intent_security",
  "total_versions": 5,
  "versions": [
    {
      "version": 1,
      "content_hash": "abc123...",
      "timestamp": "2026-04-29T10:00:00Z",
      "file_size": 2048
    },
    ...
  ]
}
```

#### Rollback to Previous Version

```bash
curl -X POST "http://localhost:8183/policies/intent_security/rollback?version=3"
```

#### Delete Policy

```bash
curl -X DELETE http://localhost:8183/policies/intent_security
```

**Note:** This is a soft delete - version history is preserved.

**Pros:**
- ✅ Validation before activation
- ✅ Automatic versioning
- ✅ Rollback capability
- ✅ Programmatic access
- ✅ Audit trail
- ✅ No file system access needed

**Cons:**
- ❌ Requires running policy-admin service
- ❌ More complex setup

**Best for:** Production, CI/CD pipelines, automated updates

---

## Method 3: OPA Bundle API (Enterprise)

Use OPA's native bundle server for centralized policy distribution.

### Configuration

```yaml
# OPA config with bundle server
services:
  opa:
    command:
      - "run"
      - "--server"
      - "--set=bundles.authz.service=bundle_server"
      - "--set=bundles.authz.resource=bundles/policies.tar.gz"
```

### Create Bundle

```bash
# Package policies into bundle
cd security/policies
tar -czf ../../bundles/policies.tar.gz *.rego

# OPA polls bundle server and auto-updates
```

**Pros:**
- ✅ Enterprise-grade distribution
- ✅ Multiple OPA instances sync automatically
- ✅ Centralized policy management
- ✅ Signing and verification support

**Cons:**
- ❌ Requires bundle server setup
- ❌ More complex architecture
- ❌ Overkill for single-instance deployments

**Best for:** Multi-instance deployments, enterprise environments

---

## Quick Start Guide

### 1. Start Stack

```bash
docker-compose up -d
```

### 2. Create Initial Policy

```bash
# Create policy file
cat > security/policies/intent_security.rego <<'EOF'
package devops_agent.intent_security

# Block wildcard IAM
deny["Wildcard IAM denied"] {
    input.iam_policy.Resource == "*"
}
EOF
```

### 3. Update Policy via API

```bash
./scripts/update_policy.sh intent_security security/policies/intent_security.rego
```

Output:
```
==========================================
OPA Policy Update
==========================================
Policy Name:    intent_security
Policy File:    security/policies/intent_security.rego
Validate:       true
Save Version:   true

[1/3] Validating policy...
✅ Policy validation passed

[2/3] Updating policy...
✅ Policy updated successfully
   Version: 1

[3/3] Verifying policy is active in OPA...
✅ Policy is active in OPA
```

### 4. Test Policy

```bash
# Test with wildcard (should deny)
curl -X POST http://localhost:8182/v1/data/devops_agent/intent_security/deny \
  -d '{"input": {"iam_policy": {"Resource": "*"}}}'

# Response: ["Wildcard IAM denied"]
```

### 5. Update Policy Again

```bash
# Edit policy
vim security/policies/intent_security.rego

# Update with validation
./scripts/update_policy.sh intent_security security/policies/intent_security.rego
# Version: 2
```

### 6. Rollback if Needed

```bash
curl -X POST "http://localhost:8183/policies/intent_security/rollback?version=1"
```

---

## Policy Development Workflow

### Local Development

1. **Edit** policy file directly
2. OPA auto-reloads via `--watch`
3. **Test** immediately
4. **Commit** to Git when satisfied

### Production Deployment

1. **Validate** locally: `opa test security/policies/`
2. **Update via API**: `./scripts/update_policy.sh ...`
3. **Verify** activation: Check OPA health endpoint
4. **Monitor** audit logs
5. **Rollback** if issues detected

### CI/CD Integration

```yaml
# .github/workflows/deploy-policies.yml
name: Deploy OPA Policies

on:
  push:
    paths:
      - 'security/policies/*.rego'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Validate Policies
        run: |
          docker run --rm -v $PWD:/workspace \
            openpolicyagent/opa:latest \
            test /workspace/security/policies/

      - name: Deploy to Production
        run: |
          ./scripts/update_policy.sh intent_security \
            security/policies/intent_security.rego
        env:
          POLICY_ADMIN_URL: https://api.example.com:8183
```

---

## Monitoring and Debugging

### View Policy Versions

```bash
curl http://localhost:8183/policies/intent_security/versions | jq
```

### Check OPA Logs

```bash
docker-compose logs -f opa
```

### Test Policy Decision

```bash
# Query OPA directly
curl -X POST http://localhost:8182/v1/data/devops_agent/intent_security/allow \
  -d @test_input.json
```

### Health Check

```bash
# Policy Admin Service
curl http://localhost:8183/health

# OPA Server
curl http://localhost:8182/health
```

---

## Security Considerations

1. **Validation is mandatory** in production (use `validate=true`)
2. **Version all changes** (use `save_version=true`)
3. **Audit all updates** - Check `/versions` directory
4. **Test before deploy** - Use staging environment
5. **Limit API access** - Add authentication in production

---

## Troubleshooting

### Policy not reloading

```bash
# Check OPA has --watch flag
docker-compose exec opa ps aux | grep watch

# Force reload via API
curl -X PUT http://localhost:8182/v1/policies/intent_security \
  --data-binary @security/policies/intent_security.rego
```

### Validation fails

```bash
# Check syntax locally
opa check security/policies/intent_security.rego

# Get detailed error
curl -X POST http://localhost:8183/policies/validate \
  -H "Content-Type: text/plain" \
  --data-binary @security/policies/intent_security.rego | jq
```

### Rollback needed

```bash
# List versions
curl http://localhost:8183/policies/intent_security/versions

# Rollback to specific version
curl -X POST "http://localhost:8183/policies/intent_security/rollback?version=3"
```

---

## Next Steps

- Implement S3-08: Write the 4 security policies
- Implement S3-09: Python OPAIntentGate client
- Implement S3-10: Adversarial test suite
- Set up CI/CD for automatic policy deployment
