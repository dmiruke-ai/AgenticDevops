"""
Unit tests for Validation Loop (S3-07).

Tests the error → classify → replan loop.
"""

import pytest
from datetime import datetime

from agents.validator.validation_loop import (
    ValidationLoop,
    ValidationResult,
    TerraformRunner,
    create_validation_loop,
)
from agents.validator.error_intelligence import (
    TerraformErrorType,
    TerraformError,
    ErrorClassificationResult,
)


class TestValidationResult:
    """Test ValidationResult model."""

    def test_create_passed_result(self):
        """Test creating a passed validation result."""
        result = ValidationResult(
            success=True,
            status="passed",
            terraform_files={"main.tf": "# valid terraform"},
        )

        assert result.success is True
        assert result.status == "passed"
        assert result.total_retries == 0
        assert result.errors_encountered == []
        assert result.requires_user_input is False

    def test_create_fixed_result(self):
        """Test creating a fixed (after retry) result."""
        result = ValidationResult(
            success=True,
            status="fixed",
            terraform_files={"main.tf": "# fixed terraform"},
            total_retries=2,
            fixes_applied=["Changed CIDR block", "Fixed IAM role reference"],
        )

        assert result.success is True
        assert result.status == "fixed"
        assert result.total_retries == 2
        assert len(result.fixes_applied) == 2

    def test_create_failed_result(self):
        """Test creating a failed result."""
        result = ValidationResult(
            success=False,
            status="failed",
            total_retries=3,
            escalation_reason="Max retries (3) exceeded",
        )

        assert result.success is False
        assert result.status == "failed"
        assert result.escalation_reason == "Max retries (3) exceeded"

    def test_create_escalated_result(self):
        """Test creating an escalated result."""
        result = ValidationResult(
            success=False,
            status="escalated",
            total_retries=1,
            escalation_reason="Quota exceeded - requires manual intervention",
            requires_user_input=True,
        )

        assert result.status == "escalated"
        assert result.requires_user_input is True


class TestValidationLoopCreation:
    """Test ValidationLoop creation and configuration."""

    def test_create_loop_default_config(self):
        """Test creating loop with default configuration."""
        loop = ValidationLoop()

        assert loop.max_retries == 3
        assert loop.skip_terraform is False
        assert loop.classifier is not None
        assert loop.replanner is not None

    def test_create_loop_custom_config(self):
        """Test creating loop with custom configuration."""
        loop = ValidationLoop(
            max_retries=5,
            skip_terraform=True,
        )

        assert loop.max_retries == 5
        assert loop.skip_terraform is True

    def test_factory_function(self):
        """Test create_validation_loop factory."""
        loop = create_validation_loop(
            max_retries=2,
            skip_terraform=True,
        )

        assert isinstance(loop, ValidationLoop)
        assert loop.max_retries == 2


class TestResourceExtraction:
    """Test affected resource extraction from error output."""

    def test_extract_simple_resource(self):
        """Test extracting simple resource reference."""
        loop = ValidationLoop()

        error_output = """
        Error: Error creating EKS Cluster (my-cluster): operation error:
        aws_eks_cluster.main: AccessDeniedException
        """

        resources = loop._extract_affected_resources(error_output)

        assert "aws_eks_cluster.main" in resources

    def test_extract_multiple_resources(self):
        """Test extracting multiple resources."""
        loop = ValidationLoop()

        error_output = """
        Error: Error creating VPC
        aws_vpc.main: InvalidVpcRange
        aws_subnet.private: SubnetConflict
        aws_security_group.web: InvalidGroup
        """

        resources = loop._extract_affected_resources(error_output)

        assert "aws_vpc.main" in resources
        assert "aws_subnet.private" in resources
        assert "aws_security_group.web" in resources

    def test_extract_module_prefixed_resource(self):
        """Test extracting module-prefixed resources."""
        loop = ValidationLoop()

        error_output = """
        Error in module.network.aws_vpc.main: CIDR conflict
        """

        resources = loop._extract_affected_resources(error_output)

        assert "module.network.aws_vpc.main" in resources

    def test_extract_from_resource_definition(self):
        """Test extracting from resource definition format."""
        loop = ValidationLoop()

        error_output = """
        Error: resource "aws_iam_role" "eks_cluster" has invalid syntax
        """

        resources = loop._extract_affected_resources(error_output)

        assert "aws_iam_role.eks_cluster" in resources


class TestValidationLoopExecution:
    """Test validation loop execution with skip_terraform=True."""

    @pytest.mark.asyncio
    async def test_validate_passes_immediately(self):
        """Test validation passes when skip_terraform=True."""
        loop = ValidationLoop(skip_terraform=True)

        result = await loop.validate_and_fix(
            terraform_files={"main.tf": "# test terraform"},
            intent_spec={"platform": "EKS"},
        )

        assert result.success is True
        assert result.status == "passed"
        assert result.total_retries == 0
        assert result.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_validate_preserves_files(self):
        """Test validation preserves terraform files."""
        loop = ValidationLoop(skip_terraform=True)

        input_files = {
            "main.tf": "# main terraform",
            "variables.tf": "# variables",
            "outputs.tf": "# outputs",
        }

        result = await loop.validate_and_fix(
            terraform_files=input_files,
            intent_spec={},
        )

        assert result.terraform_files == input_files

    @pytest.mark.asyncio
    async def test_validate_records_timing(self):
        """Test validation records timing information."""
        loop = ValidationLoop(skip_terraform=True)

        result = await loop.validate_and_fix(
            terraform_files={"main.tf": "# test"},
            intent_spec={},
        )

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration_seconds >= 0
        assert result.completed_at >= result.started_at


class TestTerraformRunner:
    """Test TerraformRunner component."""

    def test_runner_creation(self):
        """Test creating TerraformRunner."""
        runner = TerraformRunner()

        assert runner.working_dir is None
        assert runner._temp_dir is None

    @pytest.mark.asyncio
    async def test_runner_setup_creates_files(self):
        """Test runner setup creates terraform files."""
        runner = TerraformRunner()

        try:
            working_dir = await runner.setup({
                "main.tf": "# test main",
                "variables.tf": "# test variables",
            })

            assert working_dir.exists()
            assert (working_dir / "main.tf").exists()
            assert (working_dir / "variables.tf").exists()

            # Check content
            assert (working_dir / "main.tf").read_text() == "# test main"

        finally:
            runner.cleanup()


class TestValidationResultSerialization:
    """Test ValidationResult serialization."""

    def test_result_to_dict(self):
        """Test ValidationResult serializes to dict."""
        result = ValidationResult(
            success=True,
            status="passed",
            terraform_files={"main.tf": "# terraform"},
            total_retries=1,
            fixes_applied=["Fixed CIDR"],
        )

        data = result.model_dump()

        assert data["success"] is True
        assert data["status"] == "passed"
        assert data["total_retries"] == 1
        assert "Fixed CIDR" in data["fixes_applied"]

    def test_result_with_errors_to_dict(self):
        """Test ValidationResult with errors serializes correctly."""
        error = TerraformError(
            error_type=TerraformErrorType.IAM_PERMISSION_DENIED,
            error_message="AccessDenied",
            fix_hint="Grant permission",
            planner_instruction="Use existing role",
        )

        classification = ErrorClassificationResult(
            error=error,
            confidence=0.95,
            failed_modules=["iam"],
        )

        result = ValidationResult(
            success=False,
            status="escalated",
            errors_encountered=[classification],
            escalation_reason="User input required",
            requires_user_input=True,
        )

        data = result.model_dump()

        assert data["success"] is False
        assert len(data["errors_encountered"]) == 1
        assert data["requires_user_input"] is True


class TestValidationLoopIntegration:
    """Integration tests for validation loop (require ANTHROPIC_API_KEY)."""

    @pytest.mark.asyncio
    async def test_validation_with_intent_spec(self):
        """Test validation with full intent spec."""
        loop = ValidationLoop(skip_terraform=True)

        intent_spec = {
            "compute_platform": {"value": "EKS", "confidence": "confirmed"},
            "cloud_provider": {"value": "AWS", "confidence": "confirmed"},
            "region": {"value": "us-west-2", "confidence": "confirmed"},
        }

        terraform_files = {
            "main.tf": """
provider "aws" {
  region = var.region
}

resource "aws_eks_cluster" "main" {
  name     = var.cluster_name
  role_arn = aws_iam_role.eks_cluster.arn
}
            """,
            "variables.tf": """
variable "region" {
  default = "us-west-2"
}

variable "cluster_name" {
  default = "my-cluster"
}
            """,
        }

        result = await loop.validate_and_fix(
            terraform_files=terraform_files,
            intent_spec=intent_spec,
            session_id="test-session",
        )

        # With skip_terraform=True, should pass
        assert result.success is True
        assert result.status == "passed"


class TestValidationLoopEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_terraform_files(self):
        """Test validation with empty terraform files."""
        loop = ValidationLoop(skip_terraform=True)

        result = await loop.validate_and_fix(
            terraform_files={},
            intent_spec={},
        )

        # Should still pass (nothing to validate)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_max_retries_configurable(self):
        """Test max retries is configurable."""
        loop = ValidationLoop(max_retries=5, skip_terraform=True)

        assert loop.max_retries == 5

    @pytest.mark.asyncio
    async def test_session_id_optional(self):
        """Test session_id is optional."""
        loop = ValidationLoop(skip_terraform=True)

        # Should not raise without session_id
        result = await loop.validate_and_fix(
            terraform_files={"main.tf": "# test"},
            intent_spec={},
            session_id=None,
        )

        assert result.success is True
