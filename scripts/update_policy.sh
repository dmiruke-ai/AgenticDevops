#!/bin/bash
# Script to update OPA policies dynamically
#
# Usage:
#   ./scripts/update_policy.sh intent_security security/policies/intent_security.rego
#   ./scripts/update_policy.sh intent_security security/policies/intent_security.rego --no-validate
#   ./scripts/update_policy.sh intent_security security/policies/intent_security.rego --no-version

set -e

POLICY_NAME="${1}"
POLICY_FILE="${2}"
POLICY_ADMIN_URL="${POLICY_ADMIN_URL:-http://localhost:8183}"

# Validate arguments
if [ -z "$POLICY_NAME" ] || [ -z "$POLICY_FILE" ]; then
    echo "Usage: $0 <policy_name> <policy_file> [--no-validate] [--no-version]"
    echo ""
    echo "Examples:"
    echo "  $0 intent_security security/policies/intent_security.rego"
    echo "  $0 intent_security new_policy.rego --no-validate"
    exit 1
fi

if [ ! -f "$POLICY_FILE" ]; then
    echo "Error: Policy file not found: $POLICY_FILE"
    exit 1
fi

# Parse flags
VALIDATE="true"
SAVE_VERSION="true"

for arg in "$@"; do
    case $arg in
        --no-validate)
            VALIDATE="false"
            ;;
        --no-version)
            SAVE_VERSION="false"
            ;;
    esac
done

echo "=========================================="
echo "OPA Policy Update"
echo "=========================================="
echo "Policy Name:    $POLICY_NAME"
echo "Policy File:    $POLICY_FILE"
echo "Validate:       $VALIDATE"
echo "Save Version:   $SAVE_VERSION"
echo "Admin URL:      $POLICY_ADMIN_URL"
echo ""

# Step 1: Validate policy (optional)
if [ "$VALIDATE" = "true" ]; then
    echo "[1/3] Validating policy..."

    VALIDATION_RESULT=$(curl -s -X POST "$POLICY_ADMIN_URL/policies/validate" \
        -H "Content-Type: text/plain" \
        --data-binary "@$POLICY_FILE")

    VALID=$(echo "$VALIDATION_RESULT" | jq -r '.valid')

    if [ "$VALID" != "true" ]; then
        echo "❌ Policy validation FAILED:"
        echo "$VALIDATION_RESULT" | jq -r '.error'
        exit 1
    fi

    echo "✅ Policy validation passed"
else
    echo "[1/3] Skipping validation (--no-validate)"
fi

# Step 2: Update policy
echo ""
echo "[2/3] Updating policy..."

UPDATE_RESULT=$(curl -s -X PUT "$POLICY_ADMIN_URL/policies/$POLICY_NAME?validate=$VALIDATE&save_version=$SAVE_VERSION" \
    -H "Content-Type: text/plain" \
    --data-binary "@$POLICY_FILE")

UPDATE_STATUS=$(echo "$UPDATE_RESULT" | jq -r '.reload_status')
VERSION=$(echo "$UPDATE_RESULT" | jq -r '.version')

if [ "$UPDATE_STATUS" = "success" ]; then
    echo "✅ Policy updated successfully"
    if [ "$VERSION" != "null" ]; then
        echo "   Version: $VERSION"
    fi
else
    echo "⚠️  Policy written, OPA will auto-reload"
fi

# Step 3: Verify policy is active
echo ""
echo "[3/3] Verifying policy is active in OPA..."

sleep 1  # Give OPA time to reload

OPA_URL="${OPA_URL:-http://localhost:8182}"
POLICY_CHECK=$(curl -s "$OPA_URL/v1/policies/$POLICY_NAME" || echo "{}")

if echo "$POLICY_CHECK" | jq -e '.result' >/dev/null 2>&1; then
    echo "✅ Policy is active in OPA"
else
    echo "⚠️  Could not verify policy in OPA (may still be loading)"
fi

echo ""
echo "=========================================="
echo "Policy update complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  • View versions:  curl $POLICY_ADMIN_URL/policies/$POLICY_NAME/versions"
echo "  • Test policy:    curl -X POST $OPA_URL/v1/data/devops_agent/intent_security/allow -d '{...}'"
echo "  • Rollback:       curl -X POST $POLICY_ADMIN_URL/policies/$POLICY_NAME/rollback?version=1"
