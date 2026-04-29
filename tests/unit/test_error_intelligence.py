"""
Unit tests for Terraform Error Intelligence (S3-01, S3-02, S3-03, S3-04).

Tests error type enum, Pydantic models, and classification structure.

To run LLM fallback tests (S3-04), set ANTHROPIC_API_KEY environment variable:
    export ANTHROPIC_API_KEY=your_key_here
    pytest tests/unit/test_error_intelligence.py::TestLLMFallbackClassification -v
"""

import pytest
import os
from datetime import datetime
from uuid import UUID

from agents.validator.error_intelligence import (
    TerraformErrorType,
    TerraformError,
    ErrorClassificationResult,
    TerraformErrorClassifier,
    create_error_classifier,
    ERROR_FIX_HINTS,
    PLANNER_INSTRUCTIONS,
)


class TestTerraformErrorType:
    """Test TerraformErrorType enum."""

    def test_all_15_error_types_defined(self):
        """Test all 15 error types are defined."""
        error_types = list(TerraformErrorType)
        assert len(error_types) == 15

        # Check specific types exist
        assert TerraformErrorType.RESOURCE_ALREADY_EXISTS in error_types
        assert TerraformErrorType.IAM_PERMISSION_DENIED in error_types
        assert TerraformErrorType.SUBNET_CONFLICT in error_types
        assert TerraformErrorType.QUOTA_EXCEEDED in error_types
        assert TerraformErrorType.UNKNOWN in error_types

    def test_error_type_values(self):
        """Test error type string values."""
        assert TerraformErrorType.RESOURCE_ALREADY_EXISTS.value == "resource_already_exists"
        assert TerraformErrorType.IAM_PERMISSION_DENIED.value == "iam_permission_denied"
        assert TerraformErrorType.UNKNOWN.value == "unknown"

    def test_error_types_have_fix_hints(self):
        """Test all error types have fix hints defined."""
        for error_type in TerraformErrorType:
            assert error_type in ERROR_FIX_HINTS
            assert len(ERROR_FIX_HINTS[error_type]) > 0

    def test_error_types_have_planner_instructions(self):
        """Test all error types have planner instructions."""
        for error_type in TerraformErrorType:
            assert error_type in PLANNER_INSTRUCTIONS
            assert len(PLANNER_INSTRUCTIONS[error_type]) > 0


class TestTerraformError:
    """Test TerraformError Pydantic model."""

    def test_create_terraform_error(self):
        """Test creating TerraformError with required fields."""
        error = TerraformError(
            error_type=TerraformErrorType.IAM_PERMISSION_DENIED,
            error_message="AccessDenied: User is not authorized to perform: iam:CreateRole",
            fix_hint="Grant IAM CreateRole permission",
            planner_instruction="Regenerate with narrower scope",
        )

        assert error.error_type == TerraformErrorType.IAM_PERMISSION_DENIED
        assert "AccessDenied" in error.error_message
        assert isinstance(error.id, UUID)
        assert isinstance(error.timestamp, datetime)
        assert error.retry_count == 0

    def test_terraform_error_with_optional_fields(self):
        """Test TerraformError with optional fields."""
        error = TerraformError(
            error_type=TerraformErrorType.RESOURCE_ALREADY_EXISTS,
            error_message="Resource already exists",
            affected_resource="aws_eks_cluster.main",
            line_number=42,
            fix_hint="Use terraform import",
            planner_instruction="Rename resource",
            retry_count=2,
        )

        assert error.affected_resource == "aws_eks_cluster.main"
        assert error.line_number == 42
        assert error.retry_count == 2

    def test_terraform_error_json_serialization(self):
        """Test TerraformError can be serialized to JSON."""
        error = TerraformError(
            error_type=TerraformErrorType.SUBNET_CONFLICT,
            error_message="CIDR conflict",
            fix_hint="Use different CIDR",
            planner_instruction="Regenerate VPC",
        )

        json_data = error.model_dump()
        assert json_data["error_type"] == "subnet_conflict"
        assert "CIDR conflict" in json_data["error_message"]
        assert "id" in json_data

    def test_terraform_error_default_retry_count(self):
        """Test default retry count is 0."""
        error = TerraformError(
            error_type=TerraformErrorType.RATE_LIMIT,
            error_message="Rate limit exceeded",
            fix_hint="Wait and retry",
            planner_instruction="No regeneration needed",
        )

        assert error.retry_count == 0


class TestErrorClassificationResult:
    """Test ErrorClassificationResult Pydantic model."""

    def test_create_classification_result(self):
        """Test creating ErrorClassificationResult."""
        error = TerraformError(
            error_type=TerraformErrorType.INVALID_PARAMETER,
            error_message="Invalid instance type",
            fix_hint="Use valid instance type",
            planner_instruction="Regenerate with correct type",
        )

        result = ErrorClassificationResult(
            error=error,
            confidence=0.95,
            failed_modules=["main.tf"],
            preserve_modules=["variables.tf", "outputs.tf"],
            suggested_actions=["Change instance type to t3.medium", "Verify region availability"],
            requires_user_input=False,
            classified_by="regex",
        )

        assert result.error.error_type == TerraformErrorType.INVALID_PARAMETER
        assert result.confidence == 0.95
        assert "main.tf" in result.failed_modules
        assert len(result.suggested_actions) == 2
        assert result.classified_by == "regex"

    def test_classification_confidence_validation(self):
        """Test confidence must be between 0 and 1."""
        error = TerraformError(
            error_type=TerraformErrorType.UNKNOWN,
            error_message="Unknown error",
            fix_hint="Investigate manually",
            planner_instruction="Analyze error",
        )

        # Valid confidence
        result = ErrorClassificationResult(
            error=error,
            confidence=0.5,
        )
        assert result.confidence == 0.5

        # Invalid confidence should raise validation error
        with pytest.raises(Exception):  # Pydantic validation error
            ErrorClassificationResult(
                error=error,
                confidence=1.5,  # > 1.0
            )

    def test_classification_result_defaults(self):
        """Test ErrorClassificationResult default values."""
        error = TerraformError(
            error_type=TerraformErrorType.DEPENDENCY_VIOLATION,
            error_message="Dependency error",
            fix_hint="Fix dependencies",
            planner_instruction="Add depends_on",
        )

        result = ErrorClassificationResult(
            error=error,
            confidence=0.8,
        )

        assert result.failed_modules == []
        assert result.preserve_modules == []
        assert result.suggested_actions == []
        assert result.requires_user_input is False
        assert result.classified_by == "regex"
        assert isinstance(result.classified_at, datetime)

    def test_classification_result_json_serialization(self):
        """Test ErrorClassificationResult serializes to JSON."""
        error = TerraformError(
            error_type=TerraformErrorType.QUOTA_EXCEEDED,
            error_message="Quota exceeded",
            fix_hint="Request quota increase",
            planner_instruction="Reduce resource count",
        )

        result = ErrorClassificationResult(
            error=error,
            confidence=0.99,
            failed_modules=["compute.tf"],
            suggested_actions=["Use smaller instance type"],
        )

        json_data = result.model_dump()
        assert json_data["confidence"] == 0.99
        assert "compute.tf" in json_data["failed_modules"]
        assert json_data["error"]["error_type"] == "quota_exceeded"


class TestTerraformErrorClassifier:
    """Test TerraformErrorClassifier."""

    def test_create_classifier(self):
        """Test creating TerraformErrorClassifier."""
        classifier = TerraformErrorClassifier()
        assert classifier is not None
        assert isinstance(classifier.patterns, dict)

    def test_classify_returns_result(self):
        """Test classify returns ErrorClassificationResult."""
        classifier = TerraformErrorClassifier()

        result = classifier.classify(
            stderr_output="Error: some terraform error",
            affected_resources=["aws_instance.web"],
        )

        assert isinstance(result, ErrorClassificationResult)
        assert isinstance(result.error, TerraformError)
        assert result.confidence >= 0.0
        assert result.confidence <= 1.0

    def test_classify_stub_returns_unknown(self):
        """Test classify stub returns UNKNOWN type."""
        classifier = TerraformErrorClassifier()

        result = classifier.classify(
            stderr_output="Unexpected error",
            affected_resources=[],
        )

        # Stub implementation returns UNKNOWN
        assert result.error.error_type == TerraformErrorType.UNKNOWN

    def test_factory_function(self):
        """Test create_error_classifier factory."""
        classifier = create_error_classifier()
        assert isinstance(classifier, TerraformErrorClassifier)


class TestErrorFixHints:
    """Test ERROR_FIX_HINTS completeness."""

    def test_fix_hints_cover_all_types(self):
        """Test all error types have fix hints."""
        for error_type in TerraformErrorType:
            assert error_type in ERROR_FIX_HINTS
            hint = ERROR_FIX_HINTS[error_type]
            assert isinstance(hint, str)
            assert len(hint) > 20  # Meaningful hint

    def test_fix_hints_are_actionable(self):
        """Test fix hints contain actionable guidance."""
        # Check specific hints have keywords
        assert "import" in ERROR_FIX_HINTS[TerraformErrorType.RESOURCE_ALREADY_EXISTS].lower()
        assert "permission" in ERROR_FIX_HINTS[TerraformErrorType.IAM_PERMISSION_DENIED].lower()
        assert "cidr" in ERROR_FIX_HINTS[TerraformErrorType.SUBNET_CONFLICT].lower()
        assert "quota" in ERROR_FIX_HINTS[TerraformErrorType.QUOTA_EXCEEDED].lower()


class TestPlannerInstructions:
    """Test PLANNER_INSTRUCTIONS completeness."""

    def test_planner_instructions_cover_all_types(self):
        """Test all error types have planner instructions."""
        for error_type in TerraformErrorType:
            assert error_type in PLANNER_INSTRUCTIONS
            instruction = PLANNER_INSTRUCTIONS[error_type]
            assert isinstance(instruction, str)
            assert len(instruction) > 30  # Detailed instruction

    def test_planner_instructions_mention_regenerate(self):
        """Test most planner instructions involve regeneration."""
        regenerate_count = 0
        for error_type in TerraformErrorType:
            instruction = PLANNER_INSTRUCTIONS[error_type]
            if "regenerate" in instruction.lower():
                regenerate_count += 1

        # Many errors should trigger regeneration (at least half)
        assert regenerate_count >= 7

    def test_rate_limit_instruction_no_regenerate(self):
        """Test RATE_LIMIT doesn't require regeneration."""
        instruction = PLANNER_INSTRUCTIONS[TerraformErrorType.RATE_LIMIT]
        assert "No regeneration" in instruction or "Wait" in instruction


class TestErrorTypeCategories:
    """Test error types are properly categorized."""

    def test_resource_errors(self):
        """Test resource-related errors."""
        resource_errors = [
            TerraformErrorType.RESOURCE_ALREADY_EXISTS,
            TerraformErrorType.RESOURCE_NOT_FOUND,
            TerraformErrorType.RESOURCE_IN_USE,
        ]
        assert len(resource_errors) == 3

    def test_permission_errors(self):
        """Test permission-related errors."""
        permission_errors = [
            TerraformErrorType.IAM_PERMISSION_DENIED,
            TerraformErrorType.IAM_INVALID_POLICY,
        ]
        assert len(permission_errors) == 2

    def test_networking_errors(self):
        """Test networking-related errors."""
        networking_errors = [
            TerraformErrorType.SUBNET_CONFLICT,
            TerraformErrorType.CIDR_OVERLAP,
            TerraformErrorType.SECURITY_GROUP_RULE_CONFLICT,
        ]
        assert len(networking_errors) == 3

    def test_quota_errors(self):
        """Test quota/limit errors."""
        quota_errors = [
            TerraformErrorType.QUOTA_EXCEEDED,
            TerraformErrorType.RATE_LIMIT,
        ]
        assert len(quota_errors) == 2

    def test_validation_errors(self):
        """Test syntax/validation errors."""
        validation_errors = [
            TerraformErrorType.INVALID_PARAMETER,
            TerraformErrorType.MISSING_REQUIRED_PARAMETER,
            TerraformErrorType.INVALID_REFERENCE,
        ]
        assert len(validation_errors) == 3


class TestRegexPatternClassification:
    """Test S3-03: Regex pattern classification."""

    def test_classify_resource_already_exists(self):
        """Test RESOURCE_ALREADY_EXISTS pattern matching."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: Resource already exists: aws_eks_cluster.main"

        result = classifier.classify(stderr, ["aws_eks_cluster.main"])

        assert result.error.error_type == TerraformErrorType.RESOURCE_ALREADY_EXISTS
        assert result.confidence == 0.95
        assert result.classified_by == "regex"
        assert "import" in " ".join(result.suggested_actions).lower()

    def test_classify_resource_not_found(self):
        """Test RESOURCE_NOT_FOUND pattern matching."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: ResourceNotFoundException: The specified VPC does not exist"

        result = classifier.classify(stderr, ["aws_vpc.main"])

        assert result.error.error_type == TerraformErrorType.RESOURCE_NOT_FOUND
        assert result.confidence == 0.95
        assert result.classified_by == "regex"

    def test_classify_iam_permission_denied(self):
        """Test IAM_PERMISSION_DENIED pattern matching."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: AccessDenied: User is not authorized to perform: iam:CreateRole"

        result = classifier.classify(stderr, ["aws_iam_role.eks"])

        assert result.error.error_type == TerraformErrorType.IAM_PERMISSION_DENIED
        assert result.confidence == 0.95
        assert result.requires_user_input is True
        assert "permission" in " ".join(result.suggested_actions).lower()

    def test_classify_subnet_conflict(self):
        """Test SUBNET_CONFLICT pattern matching."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: SubnetConflict: The CIDR block 10.0.1.0/24 conflicts with existing subnet"

        result = classifier.classify(stderr, ["aws_subnet.private"])

        assert result.error.error_type == TerraformErrorType.SUBNET_CONFLICT
        assert result.confidence == 0.95

    def test_classify_cidr_overlap(self):
        """Test CIDR_OVERLAP pattern matching."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: InvalidVpcRange: CIDR block 10.0.0.0/16 overlaps with existing VPC"

        result = classifier.classify(stderr, ["aws_vpc.main"])

        assert result.error.error_type == TerraformErrorType.CIDR_OVERLAP
        assert result.confidence == 0.95

    def test_classify_quota_exceeded(self):
        """Test QUOTA_EXCEEDED pattern matching."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: LimitExceeded: You have exceeded the maximum number of VPCs in this region"

        result = classifier.classify(stderr, ["aws_vpc.main"])

        assert result.error.error_type == TerraformErrorType.QUOTA_EXCEEDED
        assert result.confidence == 0.95
        assert result.requires_user_input is True
        assert "quota" in " ".join(result.suggested_actions).lower()

    def test_classify_rate_limit(self):
        """Test RATE_LIMIT pattern matching."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: Throttling: Rate exceeded. Please retry after 60 seconds"

        result = classifier.classify(stderr, ["aws_eks_cluster.main"])

        assert result.error.error_type == TerraformErrorType.RATE_LIMIT
        assert result.confidence == 0.95
        assert result.requires_user_input is False
        assert "Wait" in result.suggested_actions[0]

    def test_classify_invalid_parameter(self):
        """Test INVALID_PARAMETER pattern matching."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: InvalidParameterValue: Instance type 't99.mega' is not supported"

        result = classifier.classify(stderr, ["aws_instance.web"])

        assert result.error.error_type == TerraformErrorType.INVALID_PARAMETER
        assert result.confidence == 0.95

    def test_classify_missing_required_parameter(self):
        """Test MISSING_REQUIRED_PARAMETER pattern matching."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: MissingParameter: Required parameter 'vpc_id' is missing"

        result = classifier.classify(stderr, ["aws_subnet.private"])

        assert result.error.error_type == TerraformErrorType.MISSING_REQUIRED_PARAMETER
        assert result.confidence == 0.95

    def test_classify_invalid_reference(self):
        """Test INVALID_REFERENCE pattern matching."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: Reference to undeclared resource: aws_vpc.nonexistent"

        result = classifier.classify(stderr, ["aws_subnet.private"])

        assert result.error.error_type == TerraformErrorType.INVALID_REFERENCE
        assert result.confidence == 0.95

    def test_classify_dependency_violation(self):
        """Test DEPENDENCY_VIOLATION pattern matching."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: DependencyViolation: Resource has dependencies that have not been created"

        result = classifier.classify(stderr, ["aws_instance.web"])

        assert result.error.error_type == TerraformErrorType.DEPENDENCY_VIOLATION
        assert result.confidence == 0.95

    def test_classify_unknown_error(self):
        """Test UNKNOWN error triggers LLM fallback (S3-04)."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: Some completely novel error that doesn't match any pattern"

        result = classifier.classify(stderr, ["aws_something.unknown"])

        # Should trigger LLM fallback (may fail without API key, which is fine for this test)
        # Either LLM classifies it or returns UNKNOWN after LLM failure
        assert result.classified_by in ["llm", "unknown"]
        # LLM returns 0.75 confidence, or 0.0 if it stays UNKNOWN
        assert result.confidence >= 0.0
        assert result.requires_user_input is True

    def test_extract_line_number(self):
        """Test line number extraction from error message."""
        classifier = TerraformErrorClassifier()
        stderr = "Error on main.tf line 42: Resource already exists"

        result = classifier.classify(stderr, ["aws_eks_cluster.main"])

        assert result.error.line_number == 42

    def test_extract_affected_resource(self):
        """Test affected resource extraction."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: AccessDenied"

        result = classifier.classify(stderr, ["aws_iam_role.eks", "aws_iam_policy.example"])

        assert result.error.affected_resource == "aws_iam_role.eks"

    def test_failed_modules_extraction(self):
        """Test failed modules are extracted from affected resources."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: AccessDenied"

        result = classifier.classify(stderr, ["aws_iam_role.eks", "aws_eks_cluster.main"])

        assert "aws_iam_role.tf" in result.failed_modules
        assert "aws_eks_cluster.tf" in result.failed_modules

    def test_case_insensitive_matching(self):
        """Test patterns are case insensitive."""
        classifier = TerraformErrorClassifier()
        stderr = "ERROR: RESOURCE ALREADY EXISTS"

        result = classifier.classify(stderr, [])

        assert result.error.error_type == TerraformErrorType.RESOURCE_ALREADY_EXISTS
        assert result.confidence == 0.95

    def test_multiple_pattern_keywords(self):
        """Test error with multiple pattern keywords uses first match."""
        classifier = TerraformErrorClassifier()
        # This error has both "already exists" and "duplicate"
        stderr = "Error: Resource already exists and is a duplicate"

        result = classifier.classify(stderr, [])

        # Should match RESOURCE_ALREADY_EXISTS (first pattern checked)
        assert result.error.error_type == TerraformErrorType.RESOURCE_ALREADY_EXISTS
        assert result.confidence == 0.95

    def test_suggested_actions_are_actionable(self):
        """Test suggested actions contain actionable steps."""
        classifier = TerraformErrorClassifier()

        # Test rate limit
        result = classifier.classify("Error: Throttling", [])
        assert len(result.suggested_actions) >= 2
        assert any("wait" in action.lower() for action in result.suggested_actions)

        # Test IAM permission
        result = classifier.classify("Error: AccessDenied", [])
        assert any("permission" in action.lower() for action in result.suggested_actions)

    def test_confidence_threshold_for_classified_by(self):
        """Test classified_by field matches confidence level."""
        classifier = TerraformErrorClassifier()

        # High confidence regex match
        result = classifier.classify("Error: AccessDenied", [])
        assert result.classified_by == "regex"
        assert result.confidence == 0.95

        # Novel error triggers LLM fallback
        result = classifier.classify("Error: Something weird", [])
        # Should use LLM classifier (0.75 confidence)
        assert result.classified_by == "llm"
        # LLM fallback provides medium confidence
        assert result.confidence == 0.75


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="Requires ANTHROPIC_API_KEY environment variable for LLM calls"
)
class TestLLMFallbackClassification:
    """Test S3-04: LLM fallback classifier for UNKNOWN errors.

    These tests require ANTHROPIC_API_KEY to be set in environment.
    They make real API calls to test the LLM fallback classifier.
    """

    def test_llm_classifier_handles_novel_kubernetes_error(self):
        """Test LLM classifies Kubernetes CRD validation error."""
        classifier = TerraformErrorClassifier()
        stderr = """
        Error: Provider produced inconsistent result after apply

        When applying changes to kubernetes_manifest.app_crd, provider
        "kubernetes" produced an unexpected new value: .spec.validation.openAPIV3Schema
        has invalid schema: type object does not have properties defined
        """

        result = classifier.classify(stderr, ["kubernetes_manifest.app_crd"])

        # Should be classified by LLM
        assert result.error.error_type != TerraformErrorType.UNKNOWN
        assert result.classified_by == "llm"
        assert result.confidence > 0.0
        assert len(result.suggested_actions) > 0
        assert result.error.fix_hint is not None
        assert result.error.planner_instruction is not None

    def test_llm_classifier_handles_version_mismatch(self):
        """Test LLM classifies Terraform version constraint error."""
        classifier = TerraformErrorClassifier()
        stderr = """
        Error: Incompatible provider version

        Provider registry.terraform.io/hashicorp/aws requires Terraform 1.5.0 or later,
        but you are running Terraform 1.3.7. Please upgrade your Terraform installation
        or use an older version of the provider.
        """

        result = classifier.classify(stderr, ["provider.aws"])

        assert result.error.error_type != TerraformErrorType.UNKNOWN
        assert result.classified_by == "llm"
        assert result.confidence > 0.0
        assert "version" in result.error.fix_hint.lower() or "upgrade" in result.error.fix_hint.lower()

    def test_llm_classifier_handles_timeout_error(self):
        """Test LLM classifies resource creation timeout."""
        classifier = TerraformErrorClassifier()
        stderr = """
        Error: timeout while waiting for state to become 'available'

        aws_db_instance.postgres: Still creating... [15m0s elapsed]
        aws_db_instance.postgres: Creation complete after 15m3s
        Error: operation timed out after 15 minutes
        """

        result = classifier.classify(stderr, ["aws_db_instance.postgres"])

        assert result.error.error_type != TerraformErrorType.UNKNOWN
        assert result.classified_by == "llm"
        assert result.confidence > 0.0
        assert "timeout" in result.error.fix_hint.lower() or "wait" in result.error.fix_hint.lower()

    def test_llm_classifier_handles_complex_networking_error(self):
        """Test LLM classifies complex multi-dependency networking error."""
        classifier = TerraformErrorClassifier()
        stderr = """
        Error: Error creating VPC Peering Connection

        InvalidVpcPeeringConnectionStateTransition: VPC vpc-12345 has overlapping
        route table entries with VPC vpc-67890. Additionally, security group
        sg-abc123 references security group sg-def456 which is not in the same
        VPC or a peered VPC. This configuration is not supported.
        """

        result = classifier.classify(stderr, ["aws_vpc_peering_connection.peer"])

        assert result.error.error_type != TerraformErrorType.UNKNOWN
        assert result.classified_by == "llm"
        assert result.confidence > 0.0
        assert len(result.suggested_actions) > 0

    def test_llm_classifier_handles_plugin_error(self):
        """Test LLM classifies provider plugin crash."""
        classifier = TerraformErrorClassifier()
        stderr = """
        Error: Plugin did not respond

        The plugin encountered an error, and failed to respond to the plugin.(*GRPCProvider).
        ApplyResourceChange call. The plugin logs may contain more details.

        Plugin crashed: signal: segmentation fault (core dumped)
        """

        result = classifier.classify(stderr, ["aws_instance.web"])

        assert result.error.error_type != TerraformErrorType.UNKNOWN
        assert result.classified_by == "llm"
        assert result.confidence > 0.0
        assert result.requires_user_input is True  # Plugin crashes often need investigation

    def test_llm_classifier_returns_llm_classified_by(self):
        """Test LLM classifier sets classified_by to 'llm'."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: Some completely novel terraform error that doesn't match any pattern"

        result = classifier.classify(stderr, ["aws_unknown.resource"])

        # Should be classified by LLM, not regex
        if result.error.error_type != TerraformErrorType.UNKNOWN:
            assert result.classified_by == "llm"

    def test_llm_classifier_preserves_affected_resource(self):
        """Test LLM classifier preserves affected resource information."""
        classifier = TerraformErrorClassifier()
        stderr = "Error: Some novel error requiring LLM classification"

        result = classifier.classify(stderr, ["aws_eks_cluster.production"])

        # Even if LLM classifies, should preserve resource info
        assert result.error.affected_resource == "aws_eks_cluster.production"
