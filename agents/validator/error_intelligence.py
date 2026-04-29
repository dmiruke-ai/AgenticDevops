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
import instructor
from anthropic import Anthropic


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


class LLMClassificationOutput(BaseModel):
    """
    Structured output from LLM error classifier (PROMPT_CHAIN_03).

    Used by instructor to validate LLM JSON output.
    """
    error_type: str = Field(..., description="Classified error type")
    affected_resource: Optional[str] = Field(None, description="Resource that failed")
    affected_module: str = Field("unknown", description="Module that generated this resource")
    fix_hint: str = Field(..., description="Human-readable fix suggestion")
    intent_spec_mutation: dict = Field(default_factory=dict, description="IntentSpec mutation for fix")
    planner_instruction: str = Field(..., description="Instructions for smart replanner")
    is_retryable: bool = Field(True, description="Whether error is retryable")
    requires_user_input: bool = Field(False, description="Whether fix requires user clarification")


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
        import re

        # 14 known regex patterns for fast classification (S3-03)
        self.patterns = {
            TerraformErrorType.RESOURCE_ALREADY_EXISTS: re.compile(
                r"(already exists|AlreadyExistsException|ResourceAlreadyExists|duplicate|already been taken)",
                re.IGNORECASE,
            ),
            TerraformErrorType.RESOURCE_NOT_FOUND: re.compile(
                r"(ResourceNotFoundException|NotFound|does not exist|cannot be found|InvalidParameterValue.*not found)",
                re.IGNORECASE,
            ),
            TerraformErrorType.RESOURCE_IN_USE: re.compile(
                r"(ResourceInUseException|in use and cannot|cannot.*delete.*attached|cannot.*delete.*in use)",
                re.IGNORECASE,
            ),
            TerraformErrorType.IAM_PERMISSION_DENIED: re.compile(
                r"(AccessDenied|UnauthorizedOperation|not authorized|Forbidden|InsufficientPermissions|iam:.*denied)",
                re.IGNORECASE,
            ),
            TerraformErrorType.IAM_INVALID_POLICY: re.compile(
                r"(MalformedPolicyDocument|Invalid.*policy|PolicyDocumentInvalid|invalid JSON|syntax error in policy)",
                re.IGNORECASE,
            ),
            TerraformErrorType.SUBNET_CONFLICT: re.compile(
                r"(subnet.*conflict|SubnetConflict|overlapping subnet|subnet.*already exists)",
                re.IGNORECASE,
            ),
            TerraformErrorType.CIDR_OVERLAP: re.compile(
                r"(CIDR.*overlap|InvalidVpcRange|address space.*conflict|CIDR block.*invalid)",
                re.IGNORECASE,
            ),
            TerraformErrorType.SECURITY_GROUP_RULE_CONFLICT: re.compile(
                r"(InvalidPermission\.Duplicate|security group rule.*exists|duplicate.*rule)",
                re.IGNORECASE,
            ),
            TerraformErrorType.QUOTA_EXCEEDED: re.compile(
                r"(LimitExceeded|quota exceeded|exceeded.*limit|too many.*instances|maximum number)",
                re.IGNORECASE,
            ),
            TerraformErrorType.RATE_LIMIT: re.compile(
                r"(Throttling|RequestLimitExceeded|rate.*exceeded|too many requests|429)",
                re.IGNORECASE,
            ),
            TerraformErrorType.INVALID_PARAMETER: re.compile(
                r"(InvalidParameterValue|invalid.*value|ValidationException|unsupported.*type|invalid.*configuration)",
                re.IGNORECASE,
            ),
            TerraformErrorType.MISSING_REQUIRED_PARAMETER: re.compile(
                r"(MissingParameter|missing.*required|required.*missing|argument.*required)",
                re.IGNORECASE,
            ),
            TerraformErrorType.INVALID_REFERENCE: re.compile(
                r"(Reference to undeclared resource|invalid reference|unknown.*attribute|resource.*not found in state)",
                re.IGNORECASE,
            ),
            TerraformErrorType.DEPENDENCY_VIOLATION: re.compile(
                r"(DependencyViolation|circular.*dependency|depends.*not.*created|dependency.*failed)",
                re.IGNORECASE,
            ),
        }

        # Initialize instructor client for LLM fallback (S3-04)
        from config import config
        self.client = instructor.from_anthropic(Anthropic(api_key=config.anthropic_api_key))
        self.classifier_model = config.classifier_model

    def _classify_with_llm(self, stderr_output: str, affected_resource: Optional[str]) -> LLMClassificationOutput:
        """
        LLM fallback classifier for UNKNOWN errors (S3-04 / PROMPT_CHAIN_03).

        Uses claude-haiku-4 with instructor for structured output.

        Args:
            stderr_output: Raw stderr from terraform
            affected_resource: Resource that failed (if known)

        Returns:
            LLMClassificationOutput with structured classification
        """
        # PROMPT_CHAIN_03: Terraform Error Classification
        system_prompt = """You are a Terraform Error Classification Engine.
Your job is to classify a raw Terraform error into a structured error object.

You must classify into ONE of these types:
IAM_PERMISSION_DENIED | IAM_INVALID_POLICY | RESOURCE_ALREADY_EXISTS |
RESOURCE_NOT_FOUND | RESOURCE_IN_USE | QUOTA_EXCEEDED | RATE_LIMIT |
DEPENDENCY_VIOLATION | INVALID_CIDR_BLOCK | SUBNET_CONFLICT | CIDR_OVERLAP |
SECURITY_GROUP_RULE_CONFLICT | MISSING_REQUIRED_PARAMETER | INVALID_PARAMETER |
INVALID_REFERENCE | UNKNOWN

Provide chain-of-thought reasoning, then output structured JSON."""

        user_prompt = f"""[RAW_ERROR_BLOCK]:
{stderr_output}

[AFFECTED_RESOURCE_TYPE]: {affected_resource or "unknown"}

REASONING:
Step 1: What is the root cause of this error? (one sentence)
Step 2: Which error type matches? Why?
Step 3: What is the minimal fix? (what must change in the Terraform to resolve this)
Step 4: Is this retryable without user input? (yes/no and why)
Step 5: Which module generated this resource? (iam | network | compute | pipeline | observability | unknown)

OUTPUT (strict JSON with the fields in LLMClassificationOutput):"""

        try:
            # Use instructor for structured output with auto-retry
            response = self.client.messages.create(
                model=self.classifier_model,
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                system=system_prompt,
                response_model=LLMClassificationOutput,
            )
            return response
        except Exception as e:
            # If LLM fails, return UNKNOWN with error message
            return LLMClassificationOutput(
                error_type="UNKNOWN",
                affected_resource=affected_resource,
                affected_module="unknown",
                fix_hint=f"LLM classification failed: {str(e)}. Manual investigation required.",
                planner_instruction="Review error manually and determine fix strategy.",
                is_retryable=False,
                requires_user_input=True,
            )

    def classify(self, stderr_output: str, affected_resources: List[str]) -> ErrorClassificationResult:
        """
        Classify Terraform error from stderr output.

        Args:
            stderr_output: Raw stderr from terraform plan/apply
            affected_resources: List of resources that failed

        Returns:
            ErrorClassificationResult with typed error and fix guidance
        """
        # Try regex pattern matching first (S3-03)
        error_type = None
        confidence = 0.0

        for err_type, pattern in self.patterns.items():
            if pattern.search(stderr_output):
                error_type = err_type
                confidence = 0.95  # High confidence for regex match
                break

        # Fall back to LLM if no pattern matches (S3-04)
        if error_type is None:
            # Use LLM fallback classifier (PROMPT_CHAIN_03)
            affected_resource = affected_resources[0] if affected_resources else None
            llm_result = self._classify_with_llm(stderr_output, affected_resource)

            # Map LLM error_type string to TerraformErrorType enum
            try:
                # LLM returns uppercase strings like "IAM_PERMISSION_DENIED"
                error_type = TerraformErrorType(llm_result.error_type.lower())
            except ValueError:
                # If LLM returns invalid type, default to UNKNOWN
                error_type = TerraformErrorType.UNKNOWN

            confidence = 0.75  # Medium confidence for LLM classification
            classified_by = "llm"

            # Extract line number if present
            line_number = None
            line_match = __import__('re').search(r'on (\w+\.tf) line (\d+)', stderr_output)
            if line_match:
                line_number = int(line_match.group(2))

            # Build TerraformError from LLM output
            error = TerraformError(
                error_type=error_type,
                error_message=stderr_output[:500],
                affected_resource=llm_result.affected_resource or affected_resource,
                line_number=line_number,
                fix_hint=llm_result.fix_hint,
                planner_instruction=llm_result.planner_instruction,
            )

            # Use LLM-provided retryability
            requires_user_input = llm_result.requires_user_input

            # Build suggested actions from LLM fix_hint
            suggested_actions = [llm_result.fix_hint]

            # Build failed modules from affected_resources
            failed_modules = []
            if affected_resources:
                for resource in affected_resources:
                    failed_modules.append(f"{resource.split('.')[0]}.tf")

        else:
            # Regex match successful
            confidence = 0.95
            classified_by = "regex"

            # Extract line number if present
            line_number = None
            line_match = __import__('re').search(r'on (\w+\.tf) line (\d+)', stderr_output)
            if line_match:
                line_number = int(line_match.group(2))

            # Build TerraformError
            error = TerraformError(
                error_type=error_type,
                error_message=stderr_output[:500],
                affected_resource=affected_resources[0] if affected_resources else None,
                line_number=line_number,
                fix_hint=ERROR_FIX_HINTS[error_type],
                planner_instruction=PLANNER_INSTRUCTIONS[error_type],
            )

            # Build suggested actions based on error type
            suggested_actions = []
            if error_type == TerraformErrorType.RATE_LIMIT:
                suggested_actions = ["Wait 60 seconds", "Retry terraform operation"]
            elif error_type == TerraformErrorType.RESOURCE_ALREADY_EXISTS:
                suggested_actions = ["Use terraform import", "Rename resource with unique suffix"]
            elif error_type == TerraformErrorType.IAM_PERMISSION_DENIED:
                suggested_actions = ["Check IAM permissions", "Grant required permissions", "Reduce scope if over-permissioned"]
            elif error_type == TerraformErrorType.QUOTA_EXCEEDED:
                suggested_actions = ["Request quota increase", "Use different region", "Reduce resource count"]
            else:
                suggested_actions = ["Regenerate failed module", "Check error message for details"]

            # Determine if user input is required
            requires_user_input = error_type in [
                TerraformErrorType.QUOTA_EXCEEDED,
                TerraformErrorType.IAM_PERMISSION_DENIED,
            ]

            # Build failed modules list
            failed_modules = []
            if affected_resources:
                for resource in affected_resources:
                    failed_modules.append(f"{resource.split('.')[0]}.tf")

        return ErrorClassificationResult(
            error=error,
            confidence=confidence,
            failed_modules=failed_modules,
            preserve_modules=[],  # Will be determined by replanner in S3-05
            suggested_actions=suggested_actions,
            requires_user_input=requires_user_input,
            classified_by=classified_by,
        )


def create_error_classifier() -> TerraformErrorClassifier:
    """Factory function for creating TerraformErrorClassifier."""
    return TerraformErrorClassifier()
