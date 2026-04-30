"""
Unit tests for Smart Replanner (S3-06 / PROMPT_CHAIN_04).

Tests targeted module regeneration after Terraform validation failures.

To run tests with LLM calls, set ANTHROPIC_API_KEY environment variable:
    export ANTHROPIC_API_KEY=your_key_here
    pytest tests/unit/test_smart_replanner.py -v
"""

import pytest
import os
from datetime import datetime

from agents.planner.smart_replanner import (
    SmartReplanner,
    ReplanningInput,
    ReplanningOutput,
    create_smart_replanner,
)
from agents.validator.error_intelligence import (
    TerraformErrorType,
    TerraformError,
    ErrorClassificationResult,
)


class TestReplanningModels:
    """Test Pydantic models for replanning."""

    def test_replanning_input_creation(self):
        """Test creating ReplanningInput with required fields."""
        input_data = ReplanningInput(
            intent_spec={"compute_platform": {"value": "EKS", "confidence": "confirmed"}},
            passing_modules=["network", "compute"],
            failing_modules=["iam"],
            error_classification=ErrorClassificationResult(
                error=TerraformError(
                    error_type=TerraformErrorType.IAM_PERMISSION_DENIED,
                    error_message="AccessDenied",
                    fix_hint="Grant permission",
                    planner_instruction="Regenerate with managed role",
                ),
                confidence=0.95,
                failed_modules=["iam"],
            ),
            previous_artifacts={
                "main.tf": "# old terraform",
                "iam.tf": "# failed IAM config",
            },
            retry_count=1,
        )

        assert input_data.retry_count == 1
        assert "iam" in input_data.failing_modules
        assert "network" in input_data.passing_modules

    def test_replanning_output_structure(self):
        """Test ReplanningOutput structure."""
        output = ReplanningOutput(
            fixed_modules={
                "iam": "# FIXED: IAM_PERMISSION_DENIED — Use managed role\nresource \"aws_iam_role\" ..."
            },
            unchanged_modules=["network", "compute"],
            fix_summary="Changed IAM module to use AWS-managed role ARN instead of creating custom role",
            reasoning_steps=[
                "Error: User lacks iam:CreateRole permission",
                "Fix: Use existing managed role ARN",
                "Risk: Low - managed roles are pre-validated",
            ],
        )

        assert "iam" in output.fixed_modules
        assert "network" in output.unchanged_modules
        assert len(output.reasoning_steps) == 3
        assert "IAM_PERMISSION_DENIED" in output.fixed_modules["iam"]


class TestSmartReplannerCreation:
    """Test SmartReplanner creation and configuration."""

    def test_create_smart_replanner(self):
        """Test factory function creates SmartReplanner."""
        replanner = create_smart_replanner()
        assert isinstance(replanner, SmartReplanner)

    def test_replanner_has_client(self):
        """Test SmartReplanner has Anthropic client."""
        replanner = SmartReplanner()
        assert hasattr(replanner, 'client')

    def test_replanner_has_model_config(self):
        """Test SmartReplanner has model configuration."""
        replanner = SmartReplanner()
        assert hasattr(replanner, 'model')
        assert "claude" in replanner.model.lower()


class TestReplanningPromptConstruction:
    """Test prompt construction for smart replanning."""

    def test_build_replanning_prompt(self):
        """Test building the Chain-of-Thought replanning prompt."""
        replanner = SmartReplanner()

        input_data = ReplanningInput(
            intent_spec={"platform": "EKS"},
            passing_modules=["network"],
            failing_modules=["iam"],
            error_classification=ErrorClassificationResult(
                error=TerraformError(
                    error_type=TerraformErrorType.IAM_PERMISSION_DENIED,
                    error_message="AccessDenied: iam:CreateRole",
                    fix_hint="Use managed role",
                    planner_instruction="Regenerate with ARN",
                ),
                confidence=0.95,
                failed_modules=["iam"],
                suggested_actions=["Use AWS-managed role ARN"],
            ),
            previous_artifacts={"iam.tf": "resource \"aws_iam_role\" \"bad\" {}"},
            retry_count=1,
        )

        prompt = replanner._build_prompt(input_data)

        # Check key sections
        assert "INTENT_SPEC" in prompt
        assert "PASSING_MODULES" in prompt
        assert "FAILING_MODULES" in prompt
        assert "ERROR_CLASSIFICATION" in prompt
        assert "[RETRY_COUNT]: 1" in prompt or "RETRY_COUNT: 1" in prompt
        assert "Step 1" in prompt  # Chain-of-thought reasoning steps
        assert "Step 2" in prompt
        assert "Step 3" in prompt

    def test_prompt_includes_error_details(self):
        """Test prompt includes detailed error classification."""
        replanner = SmartReplanner()

        error_result = ErrorClassificationResult(
            error=TerraformError(
                error_type=TerraformErrorType.SUBNET_CONFLICT,
                error_message="CIDR conflict: 10.0.1.0/24",
                affected_resource="aws_subnet.private_1",
                fix_hint="Use 10.0.3.0/24 instead",
                planner_instruction="Regenerate with non-overlapping CIDR",
            ),
            confidence=1.0,
            failed_modules=["network"],
            suggested_actions=["Change CIDR to 10.0.3.0/24", "Update route tables"],
        )

        input_data = ReplanningInput(
            intent_spec={},
            passing_modules=["compute"],
            failing_modules=["network"],
            error_classification=error_result,
            previous_artifacts={"network.tf": "# old config"},
            retry_count=1,
        )

        prompt = replanner._build_prompt(input_data)

        assert "SUBNET_CONFLICT" in prompt
        assert "10.0.1.0/24" in prompt or "10.0.3.0/24" in prompt
        assert "aws_subnet.private_1" in prompt

    def test_prompt_preserves_passing_modules(self):
        """Test prompt emphasizes preserving passing modules."""
        replanner = SmartReplanner()

        input_data = ReplanningInput(
            intent_spec={},
            passing_modules=["network", "compute", "pipeline"],
            failing_modules=["iam"],
            error_classification=ErrorClassificationResult(
                error=TerraformError(
                    error_type=TerraformErrorType.IAM_INVALID_POLICY,
                    error_message="Invalid policy",
                    fix_hint="Fix policy",
                    planner_instruction="Regenerate IAM",
                ),
                confidence=0.9,
                failed_modules=["iam"],
            ),
            previous_artifacts={},
            retry_count=2,
        )

        prompt = replanner._build_prompt(input_data)

        assert "network" in prompt
        assert "compute" in prompt
        assert "pipeline" in prompt
        assert "DO NOT" in prompt.upper() or "preserve" in prompt.lower()


class TestReplanningExecution:
    """Test smart replanning execution (requires API key)."""

    def setup_method(self):
        """Check for API key before running LLM tests."""
        self.has_api_key = bool(os.environ.get('ANTHROPIC_API_KEY'))
        if not self.has_api_key:
            pytest.skip("ANTHROPIC_API_KEY not set - skipping LLM tests")

    def test_replan_iam_permission_error(self):
        """Test replanning for IAM permission denied error."""
        replanner = SmartReplanner()

        input_data = ReplanningInput(
            intent_spec={
                "compute_platform": {"value": "EKS", "confidence": "confirmed"},
                "cloud_provider": {"value": "AWS", "confidence": "confirmed"},
            },
            passing_modules=["network", "compute"],
            failing_modules=["iam"],
            error_classification=ErrorClassificationResult(
                error=TerraformError(
                    error_type=TerraformErrorType.IAM_PERMISSION_DENIED,
                    error_message=(
                        "Error: creating IAM Role (eks-cluster-role): AccessDenied: "
                        "User is not authorized to perform: iam:CreateRole"
                    ),
                    affected_resource="aws_iam_role.eks_cluster",
                    fix_hint="Use AWS-managed IAM role ARN instead of creating custom role",
                    planner_instruction=(
                        "Regenerate IAM module to reference existing role ARN "
                        "(arn:aws:iam::aws:policy/AmazonEKSClusterPolicy) instead of creating new role"
                    ),
                ),
                confidence=0.98,
                failed_modules=["iam"],
                suggested_actions=[
                    "Reference AWS-managed role: arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
                    "Use data source to lookup existing role",
                ],
            ),
            previous_artifacts={
                "iam.tf": """
resource "aws_iam_role" "eks_cluster" {
  name = "eks-cluster-role"
  assume_role_policy = jsonencode({...})
}
                """
            },
            retry_count=1,
        )

        output = replanner.replan(input_data)

        # Validate output structure
        assert isinstance(output, ReplanningOutput)
        assert "iam" in output.fixed_modules
        assert "network" in output.unchanged_modules
        assert "compute" in output.unchanged_modules

        # Validate fix quality
        assert "FIXED:" in output.fixed_modules["iam"]
        assert len(output.fix_summary) > 20
        assert len(output.reasoning_steps) >= 3

        # Validate the fix addresses the error
        fixed_iam = output.fixed_modules["iam"]
        # Should NOT create role if permission denied
        assert "aws_iam_role" not in fixed_iam or "data \"aws_iam_role\"" in fixed_iam

    def test_replan_subnet_conflict_error(self):
        """Test replanning for subnet CIDR overlap."""
        replanner = SmartReplanner()

        input_data = ReplanningInput(
            intent_spec={"cloud_provider": {"value": "AWS", "confidence": "confirmed"}},
            passing_modules=["compute", "iam"],
            failing_modules=["network"],
            error_classification=ErrorClassificationResult(
                error=TerraformError(
                    error_type=TerraformErrorType.SUBNET_CONFLICT,
                    error_message=(
                        "Error: creating EC2 Subnet: InvalidSubnet.Conflict: "
                        "The CIDR '10.0.1.0/24' conflicts with another subnet"
                    ),
                    affected_resource="aws_subnet.private_1",
                    line_number=45,
                    fix_hint="Use non-overlapping CIDR block (e.g., 10.0.3.0/24)",
                    planner_instruction="Regenerate network module with CIDR blocks: [10.0.3.0/24, 10.0.4.0/24]",
                ),
                confidence=1.0,
                failed_modules=["network"],
                suggested_actions=["Change CIDR to 10.0.3.0/24", "Update subnet CIDR allocation"],
            ),
            previous_artifacts={
                "network.tf": """
resource "aws_subnet" "private_1" {
  cidr_block = "10.0.1.0/24"
  vpc_id     = aws_vpc.main.id
}
                """
            },
            retry_count=1,
        )

        output = replanner.replan(input_data)

        # Validate output
        assert "network" in output.fixed_modules
        assert "compute" in output.unchanged_modules
        assert "iam" in output.unchanged_modules

        # Validate the fix changes CIDR
        fixed_network = output.fixed_modules["network"]
        assert "10.0.3.0/24" in fixed_network or "10.0.4.0/24" in fixed_network
        # Should NOT have the conflicting CIDR
        if "10.0.1.0/24" in fixed_network:
            # If present, should be in comment about what was fixed
            assert "#" in fixed_network or "FIXED" in fixed_network

    def test_replan_does_not_reproduce_error(self):
        """
        Acceptance criteria: Fixed module differs from and does not reproduce original error.

        This is the key test for S3-06.
        """
        replanner = SmartReplanner()

        # Use a clear error case
        input_data = ReplanningInput(
            intent_spec={"platform": "EKS"},
            passing_modules=["network"],
            failing_modules=["iam"],
            error_classification=ErrorClassificationResult(
                error=TerraformError(
                    error_type=TerraformErrorType.IAM_PERMISSION_DENIED,
                    error_message="AccessDenied: iam:CreateRole",
                    fix_hint="Use existing role instead of creating",
                    planner_instruction="Reference data source for existing role",
                ),
                confidence=0.95,
                failed_modules=["iam"],
            ),
            previous_artifacts={
                "iam.tf": 'resource "aws_iam_role" "new_role" { name = "my-role" }'
            },
            retry_count=1,
        )

        output = replanner.replan(input_data)

        # Fixed module must differ from previous
        assert output.fixed_modules["iam"] != input_data.previous_artifacts["iam.tf"]

        # Fixed module should include FIXED comment
        assert "FIXED:" in output.fixed_modules["iam"]

        # Should not attempt to create role if permission denied
        fixed_code = output.fixed_modules["iam"]
        # Either uses data source or doesn't create role
        assert (
            "data " in fixed_code.lower()
            or 'resource "aws_iam_role"' not in fixed_code
        )


class TestReplanningEdgeCases:
    """Test edge cases and error handling."""

    def test_high_retry_count_acknowledged(self):
        """Test replanning acknowledges high retry count."""
        replanner = SmartReplanner()

        input_data = ReplanningInput(
            intent_spec={},
            passing_modules=[],
            failing_modules=["compute"],
            error_classification=ErrorClassificationResult(
                error=TerraformError(
                    error_type=TerraformErrorType.QUOTA_EXCEEDED,
                    error_message="LimitExceeded: Maximum clusters reached",
                    fix_hint="Request quota increase",
                    planner_instruction="Cannot auto-fix",
                ),
                confidence=1.0,
                failed_modules=["compute"],
                requires_user_input=True,
            ),
            previous_artifacts={},
            retry_count=3,  # Final retry
        )

        prompt = replanner._build_prompt(input_data)

        assert "RETRY_COUNT: 3" in prompt or "3 of 3" in prompt

    def test_multiple_failing_modules(self):
        """Test replanning with multiple failing modules."""
        replanner = SmartReplanner()

        input_data = ReplanningInput(
            intent_spec={},
            passing_modules=["pipeline"],
            failing_modules=["network", "iam"],
            error_classification=ErrorClassificationResult(
                error=TerraformError(
                    error_type=TerraformErrorType.DEPENDENCY_VIOLATION,
                    error_message="IAM role depends on non-existent VPC",
                    fix_hint="Create VPC first or fix dependency order",
                    planner_instruction="Regenerate with correct dependencies",
                ),
                confidence=0.85,
                failed_modules=["network", "iam"],
            ),
            previous_artifacts={},
            retry_count=1,
        )

        prompt = replanner._build_prompt(input_data)

        assert "network" in prompt
        assert "iam" in prompt

    def test_no_passing_modules(self):
        """Test replanning when all modules failed."""
        replanner = SmartReplanner()

        input_data = ReplanningInput(
            intent_spec={},
            passing_modules=[],  # Everything failed
            failing_modules=["network", "compute", "iam"],
            error_classification=ErrorClassificationResult(
                error=TerraformError(
                    error_type=TerraformErrorType.INVALID_PARAMETER,
                    error_message="Invalid provider configuration",
                    fix_hint="Fix provider settings",
                    planner_instruction="Regenerate all modules",
                ),
                confidence=0.7,
                failed_modules=["network", "compute", "iam"],
            ),
            previous_artifacts={},
            retry_count=1,
        )

        prompt = replanner._build_prompt(input_data)

        # Should still generate valid prompt
        assert len(prompt) > 100
        assert "FAILING_MODULES" in prompt
