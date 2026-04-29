"""
Terraform Error Intelligence (SPEC-01 / S3-01, S3-02).

Classifies Terraform errors into typed categories for targeted replanning.
Prevents naive retry - each retry has structured fix context.
"""

from enum import Enum
from typing import Optional, List
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TerraformErrorType(str, Enum):
    """
    15 known Terraform error types for intelligent classification.

    Each type maps to specific fix hints and planner instructions.
    """
    # Resource errors
    RESOURCE_ALREADY_EXISTS = "resource_already_exists"
    RESOURCE_NOT_FOUND = "resource_not_found"
    RESOURCE_IN_USE = "resource_in_use"

    # Permission errors
    IAM_PERMISSION_DENIED = "iam_permission_denied"
    IAM_INVALID_POLICY = "iam_invalid_policy"

    # Networking errors
    SUBNET_CONFLICT = "subnet_conflict"
    CIDR_OVERLAP = "cidr_overlap"
    SECURITY_GROUP_RULE_CONFLICT = "security_group_rule_conflict"

    # Quota/limit errors
    QUOTA_EXCEEDED = "quota_exceeded"
    RATE_LIMIT = "rate_limit"

    # Syntax/validation errors
    INVALID_PARAMETER = "invalid_parameter"
    MISSING_REQUIRED_PARAMETER = "missing_required_parameter"
    INVALID_REFERENCE = "invalid_reference"

    # Dependency errors
    DEPENDENCY_VIOLATION = "dependency_violation"

    # Unknown
    UNKNOWN = "unknown"


class TerraformError(BaseModel):
    """
    Structured representation of a Terraform error.

    Contains error type, raw output, and fix guidance.
    """
    id: UUID = Field(default_factory=uuid4)
    error_type: TerraformErrorType
    error_message: str = Field(..., description="Raw error message from Terraform stderr")
    affected_resource: Optional[str] = Field(None, description="Resource that failed (e.g., aws_eks_cluster.main)")
    line_number: Optional[int] = Field(None, description="Line number in Terraform file")

    fix_hint: str = Field(..., description="Human-readable fix suggestion")
    intent_spec_mutation: Optional[str] = Field(None, description="Suggested IntentSpec change")
    planner_instruction: str = Field(..., description="Instructions for smart replanner")

    retry_count: int = Field(0, description="Number of retries attempted")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorClassificationResult(BaseModel):
    """
    Result of error classification with structured fix context.

    Used by smart replanner to perform targeted module regeneration.
    """
    error: TerraformError
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence (0-1)")

    # Context for replanning
    failed_modules: List[str] = Field(default_factory=list, description="Terraform modules that failed")
    preserve_modules: List[str] = Field(default_factory=list, description="Modules to preserve (don't regenerate)")

    # Fix guidance
    suggested_actions: List[str] = Field(default_factory=list, description="Ordered list of fix actions")
    requires_user_input: bool = Field(False, description="Whether fix requires user clarification")

    # Metadata
    classified_at: datetime = Field(default_factory=datetime.utcnow)
    classified_by: str = Field("regex", description="Classification method (regex/llm)")


# Error type to fix hint mapping (for regex classifier)
ERROR_FIX_HINTS = {
    TerraformErrorType.RESOURCE_ALREADY_EXISTS: (
        "Resource already exists in AWS. Use terraform import or change resource name."
    ),
    TerraformErrorType.RESOURCE_NOT_FOUND: (
        "Referenced resource not found. Check resource names and dependencies."
    ),
    TerraformErrorType.RESOURCE_IN_USE: (
        "Resource is in use and cannot be deleted. Remove dependencies first."
    ),
    TerraformErrorType.IAM_PERMISSION_DENIED: (
        "IAM permissions insufficient. Grant required permissions or reduce scope."
    ),
    TerraformErrorType.IAM_INVALID_POLICY: (
        "IAM policy syntax invalid. Check JSON formatting and AWS policy grammar."
    ),
    TerraformErrorType.SUBNET_CONFLICT: (
        "Subnet CIDR conflicts with existing subnet. Use different CIDR block."
    ),
    TerraformErrorType.CIDR_OVERLAP: (
        "CIDR ranges overlap. Ensure non-overlapping address spaces."
    ),
    TerraformErrorType.SECURITY_GROUP_RULE_CONFLICT: (
        "Security group rule conflicts with existing rule. Check port ranges."
    ),
    TerraformErrorType.QUOTA_EXCEEDED: (
        "AWS service quota exceeded. Request quota increase or use different region."
    ),
    TerraformErrorType.RATE_LIMIT: (
        "API rate limit exceeded. Wait and retry, or reduce parallelism."
    ),
    TerraformErrorType.INVALID_PARAMETER: (
        "Invalid parameter value. Check AWS documentation for valid values."
    ),
    TerraformErrorType.MISSING_REQUIRED_PARAMETER: (
        "Required parameter missing. Add missing parameter to resource."
    ),
    TerraformErrorType.INVALID_REFERENCE: (
        "Invalid resource reference. Check resource names and attribute paths."
    ),
    TerraformErrorType.DEPENDENCY_VIOLATION: (
        "Dependency constraint violated. Ensure resources are created in correct order."
    ),
    TerraformErrorType.UNKNOWN: (
        "Unknown error type. Manual investigation required."
    ),
}


# Planner instructions for each error type
PLANNER_INSTRUCTIONS = {
    TerraformErrorType.RESOURCE_ALREADY_EXISTS: (
        "Regenerate the resource with a unique name suffix. "
        "Update all references to use the new name."
    ),
    TerraformErrorType.RESOURCE_NOT_FOUND: (
        "Verify the resource exists in the dependencies. "
        "If it's an external resource, add data source to lookup."
    ),
    TerraformErrorType.RESOURCE_IN_USE: (
        "Remove the resource deletion from the plan. "
        "Add explicit dependencies to ensure proper ordering."
    ),
    TerraformErrorType.IAM_PERMISSION_DENIED: (
        "Regenerate IAM policy with narrower scope. "
        "Remove actions that require elevated permissions."
    ),
    TerraformErrorType.IAM_INVALID_POLICY: (
        "Regenerate IAM policy with correct JSON structure. "
        "Validate against AWS IAM policy grammar."
    ),
    TerraformErrorType.SUBNET_CONFLICT: (
        "Regenerate VPC with different CIDR block. "
        "Use cidrsubnet() function with unique offsets."
    ),
    TerraformErrorType.CIDR_OVERLAP: (
        "Adjust CIDR calculations to eliminate overlap. "
        "Increase address space or use non-contiguous ranges."
    ),
    TerraformErrorType.SECURITY_GROUP_RULE_CONFLICT: (
        "Regenerate security group with non-overlapping port ranges. "
        "Consolidate duplicate rules."
    ),
    TerraformErrorType.QUOTA_EXCEEDED: (
        "Reduce resource count or change instance type. "
        "Consider different region with available capacity."
    ),
    TerraformErrorType.RATE_LIMIT: (
        "No regeneration needed. Wait 60 seconds and retry. "
        "Reduce parallel resource creation."
    ),
    TerraformErrorType.INVALID_PARAMETER: (
        "Regenerate resource with corrected parameter value. "
        "Check AWS documentation for valid values."
    ),
    TerraformErrorType.MISSING_REQUIRED_PARAMETER: (
        "Regenerate resource with required parameter added. "
        "Use sensible default if not in IntentSpec."
    ),
    TerraformErrorType.INVALID_REFERENCE: (
        "Fix resource reference syntax. "
        "Use correct attribute path (e.g., aws_vpc.main.id)."
    ),
    TerraformErrorType.DEPENDENCY_VIOLATION: (
        "Add explicit depends_on to resource. "
        "Ensure dependency chain is correct."
    ),
    TerraformErrorType.UNKNOWN: (
        "Analyze error message and regenerate affected module. "
        "May require user clarification."
    ),
}


class TerraformErrorClassifier:
    """
    Classifies Terraform errors using regex patterns and LLM fallback.

    Classification flow:
    1. Try regex pattern matching (14 known patterns)
    2. If no match, use LLM fallback classifier
    3. Return ErrorClassificationResult with fix context
    """

    def __init__(self):
        # Will be populated in S3-03 with regex patterns
        self.patterns = {}

    def classify(self, stderr_output: str, affected_resources: List[str]) -> ErrorClassificationResult:
        """
        Classify Terraform error from stderr output.

        Args:
            stderr_output: Raw stderr from terraform plan/apply
            affected_resources: List of resources that failed

        Returns:
            ErrorClassificationResult with typed error and fix guidance
        """
        # Regex classification in S3-03
        # LLM fallback in S3-04

        # For now, return UNKNOWN (will be implemented in S3-03)
        error = TerraformError(
            error_type=TerraformErrorType.UNKNOWN,
            error_message=stderr_output[:500],  # Truncate for storage
            affected_resource=affected_resources[0] if affected_resources else None,
            fix_hint=ERROR_FIX_HINTS[TerraformErrorType.UNKNOWN],
            planner_instruction=PLANNER_INSTRUCTIONS[TerraformErrorType.UNKNOWN],
        )

        return ErrorClassificationResult(
            error=error,
            confidence=0.0,
            failed_modules=[],
            preserve_modules=[],
            suggested_actions=["Analyze error manually"],
            requires_user_input=True,
            classified_by="stub",
        )


def create_error_classifier() -> TerraformErrorClassifier:
    """Factory function for creating TerraformErrorClassifier."""
    return TerraformErrorClassifier()
