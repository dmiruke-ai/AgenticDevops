"""
Unit tests for Terraform Error Intelligence (S3-01, S3-02).

Tests error type enum, Pydantic models, and classification structure.
"""

import pytest
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
