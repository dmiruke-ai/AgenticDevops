# AI DevOps Agent - Intent Security Policies (S3-08)
# Package: devops_agent.intent_security
#
# Purpose: Block dangerous configurations at the INTENT layer before code generation.
# This prevents wildcard IAM, open security groups, and prompt injection attacks.
#
# Usage:
#   curl -X POST http://localhost:8182/v1/data/devops_agent/intent_security/allow \
#     -d '{"input": {...}}'

package devops_agent.intent_security

import rego.v1

# =============================================================================
# POLICY 1: Block Wildcard IAM Policies (BLOCKING)
# =============================================================================

# Deny if IAM policy contains wildcard Resource
deny contains msg if {
    some item in input.intent_spec.new_items
    item.category == "task_intent"
    item.key == "iam_policy"

    # Check if any policy statement has wildcard resource
    some statement in item.value.statements
    contains_wildcard_resource(statement.resources)

    msg := sprintf(
        "BLOCKED: Wildcard IAM policy detected. Resource '*' is not allowed. Affected item: %s",
        [item.key]
    )
}

# Deny if IAM policy contains wildcard Action
deny contains msg if {
    some item in input.intent_spec.new_items
    item.category == "task_intent"
    item.key == "iam_policy"

    # Check if any policy statement has wildcard actions
    some statement in item.value.statements
    contains_wildcard_action(statement.actions)

    msg := sprintf(
        "BLOCKED: Wildcard IAM actions detected. Action '*' is not allowed except for AWS-managed services. Affected item: %s",
        [item.key]
    )
}

# Helper: Check if resources list contains wildcard
contains_wildcard_resource(resources) if {
    some resource in resources
    resource == "*"
}

contains_wildcard_resource(resources) if {
    some resource in resources
    contains(resource, ":*/*")  # arn:aws:s3:::*/*
}

# Allowed wildcards (AWS-managed services that require them)
is_allowed_wildcard_action(action) if {
    allowed_wildcards := {
        "ec2:Describe*",
        "s3:List*",
        "xray:*",  # X-Ray tracing
        "logs:Create*",
        "logs:Describe*",
    }
    action in allowed_wildcards
}

# Helper: Check if actions list contains wildcard (with exceptions)
contains_wildcard_action(actions) if {
    some action in actions
    action == "*"
}

contains_wildcard_action(actions) if {
    some action in actions
    contains(action, "*")
    not is_allowed_wildcard_action(action)
}

# =============================================================================
# POLICY 2: Block Open Security Groups (BLOCKING)
# =============================================================================

# Deny if security group allows 0.0.0.0/0 ingress (except port 443/80)
deny contains msg if {
    some item in input.intent_spec.new_items
    item.category == "task_intent"
    item.key == "security_group"

    # Check if any ingress rule has open CIDR
    some rule in item.value.ingress_rules
    contains_open_cidr(rule.cidr_blocks)
    not is_allowed_open_port(rule.port)

    msg := sprintf(
        "BLOCKED: Security group with 0.0.0.0/0 ingress detected on port %d. Only ports 80 and 443 are allowed for public access. Affected item: %s",
        [rule.port, item.key]
    )
}

# Deny if security group allows ::/0 (IPv6 open)
deny contains msg if {
    some item in input.intent_spec.new_items
    item.category == "task_intent"
    item.key == "security_group"

    # Check if any ingress rule has open IPv6 CIDR
    some rule in item.value.ingress_rules
    contains_open_ipv6(rule.cidr_blocks)
    not is_allowed_open_port(rule.port)

    msg := sprintf(
        "BLOCKED: Security group with ::/0 ingress detected on port %d. Only ports 80 and 443 are allowed for public access. Affected item: %s",
        [rule.port, item.key]
    )
}

# Helper: Check if CIDR blocks contain 0.0.0.0/0
contains_open_cidr(cidr_blocks) if {
    some cidr in cidr_blocks
    cidr == "0.0.0.0/0"
}

# Helper: Check if CIDR blocks contain ::/0
contains_open_ipv6(cidr_blocks) if {
    some cidr in cidr_blocks
    cidr == "::/0"
}

# Helper: Allowed open ports (HTTP/HTTPS only)
is_allowed_open_port(port) if {
    port == 80
}

is_allowed_open_port(port) if {
    port == 443
}

# =============================================================================
# POLICY 3: Detect Prompt Injection (BLOCKING)
# =============================================================================

# Deny if user message contains prompt injection patterns
deny contains msg if {
    contains_prompt_injection(input.user_message)

    msg := "BLOCKED: Prompt injection detected in user message. Malicious instructions are not allowed."
}

# Deny if intent spec was manipulated via injection
deny contains msg if {
    some item in input.intent_spec.new_items
    item.source == "llm_extraction"

    # Check if extracted value contains injection patterns
    contains_prompt_injection(sprintf("%v", [item.value]))

    msg := sprintf(
        "BLOCKED: Prompt injection detected in extracted intent. Affected item: %s",
        [item.key]
    )
}

# Helper: Detect common prompt injection patterns
contains_prompt_injection(text) if {
    lower_text := lower(text)

    # Pattern 1: Instruction override
    injection_patterns := {
        "ignore previous",
        "ignore all previous",
        "disregard previous",
        "forget previous",
        "new instructions",
        "system prompt",
        "you are now",
        "act as if",
        "pretend you are",
    }

    some pattern in injection_patterns
    contains(lower_text, pattern)
}

contains_prompt_injection(text) if {
    lower_text := lower(text)

    # Pattern 2: Role manipulation
    role_patterns := {
        "you are a devops engineer",
        "you are an infrastructure expert",
        "as a security engineer",
        "ignore security policies",
        "bypass validation",
        "skip checks",
    }

    some pattern in role_patterns
    contains(lower_text, pattern)
}

contains_prompt_injection(text) if {
    lower_text := lower(text)

    # Pattern 3: Policy override attempts
    override_patterns := {
        "allow wildcard",
        "enable wildcard",
        "permit 0.0.0.0",
        "allow all traffic",
        "disable security",
        "skip opa",
        "bypass opa",
    }

    some pattern in override_patterns
    contains(lower_text, pattern)
}

# =============================================================================
# POLICY 4: Validate Intent Structure (BLOCKING)
# =============================================================================

# Deny if intent spec is missing required fields
deny contains msg if {
    not input.intent_spec.session_id

    msg := "BLOCKED: Invalid intent structure. Missing required field: session_id"
}

deny contains msg if {
    not input.intent_spec.turn

    msg := "BLOCKED: Invalid intent structure. Missing required field: turn"
}

# Deny if new_items is not an array
deny contains msg if {
    not is_array(input.intent_spec.new_items)

    msg := "BLOCKED: Invalid intent structure. Field 'new_items' must be an array"
}

# Deny if spec item is missing required fields
deny contains msg if {
    some item in input.intent_spec.new_items
    not item.key

    msg := "BLOCKED: Invalid spec item. Missing required field: key"
}

deny contains msg if {
    some item in input.intent_spec.new_items
    not item.category

    msg := sprintf(
        "BLOCKED: Invalid spec item. Missing required field: category for key '%s'",
        [item.key]
    )
}

deny contains msg if {
    some item in input.intent_spec.new_items
    not valid_category(item.category)

    msg := sprintf(
        "BLOCKED: Invalid category '%s' for key '%s'. Must be one of: task_intent, meta_intent, constraint_intent",
        [item.category, item.key]
    )
}

# Helper: Valid categories
valid_category(category) if {
    category == "task_intent"
}

valid_category(category) if {
    category == "meta_intent"
}

valid_category(category) if {
    category == "constraint_intent"
}

# =============================================================================
# POLICY 5: Warn on Overly Permissive Configurations (WARNING)
# =============================================================================

# Warn if security group allows wide port ranges
warn contains msg if {
    some item in input.intent_spec.new_items
    item.category == "task_intent"
    item.key == "security_group"

    some rule in item.value.ingress_rules
    wide_port_range(rule.from_port, rule.to_port)

    msg := sprintf(
        "WARNING: Security group allows wide port range (%d-%d). Consider narrowing to specific ports. Affected item: %s",
        [rule.from_port, rule.to_port, item.key]
    )
}

# Warn if IAM policy has too many actions
warn contains msg if {
    some item in input.intent_spec.new_items
    item.category == "task_intent"
    item.key == "iam_policy"

    some statement in item.value.statements
    count(statement.actions) > 10

    msg := sprintf(
        "WARNING: IAM policy has %d actions in a single statement. Consider splitting into multiple policies. Affected item: %s",
        [count(statement.actions), item.key]
    )
}

# Helper: Check if port range is too wide (>100 ports)
wide_port_range(from_port, to_port) if {
    to_port - from_port > 100
}

# =============================================================================
# MAIN DECISION: Allow or Deny
# =============================================================================

# Default: deny if any deny rule triggers
default allow := false

# Allow if no deny rules triggered
allow if {
    count(deny) == 0
}

# Collect all warnings (non-blocking)
warnings := warn

# Metadata for policy version tracking
policy_metadata := {
    "version": "1.0.0",
    "last_updated": "2026-04-29",
    "policies": [
        "wildcard_iam_blocking",
        "open_security_group_blocking",
        "prompt_injection_detection",
        "intent_structure_validation",
        "permissive_config_warnings",
    ],
}
