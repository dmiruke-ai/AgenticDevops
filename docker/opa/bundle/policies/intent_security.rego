# File: policies/intent_security.rego
# OPA Policy Bundle for Intent-Level Security
#
# These policies run BEFORE ExtractionResult merges into IntentSpec.
# They prevent security-violating constraints from entering the canonical spec.

package devops_agent.intent_security

# Block wildcard IAM from entering IntentSpec
deny[reason] {
    item := input.new_items[_]
    item.key == "iam_policy"
    contains(item.value, "*")
    reason := sprintf("Wildcard IAM policy rejected in item %v. Specify exact permissions.", [item.id])
}

# Block open security groups
deny[reason] {
    item := input.new_items[_]
    item.key == "ingress_cidr"
    item.value == "0.0.0.0/0"
    reason := sprintf("Open ingress (0.0.0.0/0) rejected in item %v. Specify restricted CIDR.", [item.id])
}

# Block unencrypted storage intent
deny[reason] {
    item := input.new_items[_]
    item.key == "storage_encryption"
    item.value == "disabled"
    reason := sprintf("Unencrypted storage disabled in item %v. Encryption is mandatory.", [item.id])
}

# Block public S3 buckets
deny[reason] {
    item := input.new_items[_]
    item.key == "s3_acl"
    item.value == "public-read"
    reason := sprintf("Public S3 ACL rejected in item %v.", [item.id])
}

# Require MFA for production environment intents
warn[reason] {
    item := input.new_items[_]
    item.key == "environment"
    item.value == "production"
    not any_item_has_key(input.full_spec.items, "mfa_required")
    reason := "Production environment specified without MFA requirement. Consider adding MFA policy."
}

any_item_has_key(items, key) {
    items[_].key == key
}
