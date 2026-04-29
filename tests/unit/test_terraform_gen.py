"""
Unit tests for Terraform Generator (S2-06).

Tests HCL generation for EKS, ECS, and Lambda platforms.
"""

import pytest
from uuid import uuid4

from agents.generators.terraform_gen import TerraformGenerator, create_terraform_generator
from intent.schema import IntentSpec, SpecItem, IntentCategory, ConfidenceBand


class TestTerraformGenerator:
    """Test Terraform HCL generation."""

    @pytest.mark.asyncio
    async def test_generate_eks_infrastructure(self):
        """Test EKS cluster infrastructure generation."""
        item_id = uuid4()
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                item_id: SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="User wants EKS",
                )
            },
        )

        generator = TerraformGenerator()
        result = await generator.generate(intent_spec)

        assert "main.tf" in result
        assert "variables.tf" in result
        assert "outputs.tf" in result
        assert "provider.tf" in result

        main_tf = result["main.tf"]
        assert "aws_eks_cluster" in main_tf
        assert "aws_eks_node_group" in main_tf
        assert "aws_vpc" in main_tf
        assert "aws_subnet" in main_tf
        assert "aws_nat_gateway" in main_tf

        outputs_tf = result["outputs.tf"]
        assert "cluster_endpoint" in outputs_tf
        assert "cluster_name" in outputs_tf

    @pytest.mark.asyncio
    async def test_generate_ecs_fargate_infrastructure(self):
        """Test ECS Fargate infrastructure generation."""
        item_id = uuid4()
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                item_id: SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="ecs",
                    confidence=ConfidenceBand.CONFIRMED,
                    turn=2,
                    evidence="User confirmed ECS",
                )
            },
        )

        generator = TerraformGenerator()
        result = await generator.generate(intent_spec)

        main_tf = result["main.tf"]
        assert "aws_ecs_cluster" in main_tf
        assert "aws_ecs_task_definition" in main_tf
        assert "aws_ecs_service" in main_tf
        assert "FARGATE" in main_tf
        assert "aws_lb" in main_tf  # Application Load Balancer

        outputs_tf = result["outputs.tf"]
        assert "cluster_name" in outputs_tf
        assert "load_balancer_dns" in outputs_tf

    @pytest.mark.asyncio
    async def test_generate_lambda_infrastructure(self):
        """Test Lambda serverless infrastructure generation."""
        item_id = uuid4()
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                item_id: SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="lambda",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="User wants serverless",
                )
            },
        )

        generator = TerraformGenerator()
        result = await generator.generate(intent_spec)

        main_tf = result["main.tf"]
        assert "aws_lambda_function" in main_tf
        assert "aws_apigatewayv2_api" in main_tf
        assert "aws_iam_role" in main_tf
        assert "lambda_execution" in main_tf

        outputs_tf = result["outputs.tf"]
        assert "function_name" in outputs_tf
        assert "invoke_url" in outputs_tf

    @pytest.mark.asyncio
    async def test_custom_region_extraction(self):
        """Test custom AWS region extraction from IntentSpec."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="Platform",
                ),
                uuid4(): SpecItem(
                    category=IntentCategory.CONSTRAINT,
                    key="region",
                    value="eu-west-1",
                    confidence=ConfidenceBand.CONFIRMED,
                    turn=1,
                    evidence="User wants EU region",
                ),
            },
        )

        generator = TerraformGenerator()
        result = await generator.generate(intent_spec)

        variables_tf = result["variables.tf"]
        assert "eu-west-1" in variables_tf

    @pytest.mark.asyncio
    async def test_custom_app_name_extraction(self):
        """Test custom application name extraction."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="lambda",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="Platform",
                ),
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="app_name",
                    value="my-awesome-app",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="User specified app name",
                ),
            },
        )

        generator = TerraformGenerator()
        result = await generator.generate(intent_spec)

        variables_tf = result["variables.tf"]
        assert "my-awesome-app" in variables_tf

    @pytest.mark.asyncio
    async def test_provider_tf_format(self):
        """Test provider.tf contains correct Terraform syntax."""
        item_id = uuid4()
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                item_id: SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="EKS",
                )
            },
        )

        generator = TerraformGenerator()
        result = await generator.generate(intent_spec)

        provider_tf = result["provider.tf"]
        assert "terraform {" in provider_tf
        assert "required_version" in provider_tf
        assert "hashicorp/aws" in provider_tf
        assert "provider \"aws\"" in provider_tf

    @pytest.mark.asyncio
    async def test_eks_has_iam_roles(self):
        """Test EKS infrastructure includes required IAM roles."""
        item_id = uuid4()
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                item_id: SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="EKS",
                )
            },
        )

        generator = TerraformGenerator()
        result = await generator.generate(intent_spec)

        main_tf = result["main.tf"]
        assert "aws_iam_role" in main_tf
        assert "eks_cluster" in main_tf
        assert "eks_node_group" in main_tf
        assert "AmazonEKSClusterPolicy" in main_tf
        assert "AmazonEKSWorkerNodePolicy" in main_tf

    @pytest.mark.asyncio
    async def test_ecs_has_cloudwatch_logs(self):
        """Test ECS infrastructure includes CloudWatch logging."""
        item_id = uuid4()
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                item_id: SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="ecs_fargate",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="ECS Fargate",
                )
            },
        )

        generator = TerraformGenerator()
        result = await generator.generate(intent_spec)

        main_tf = result["main.tf"]
        assert "aws_cloudwatch_log_group" in main_tf
        assert "awslogs" in main_tf

    @pytest.mark.asyncio
    async def test_lambda_has_api_gateway(self):
        """Test Lambda infrastructure includes API Gateway."""
        item_id = uuid4()
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                item_id: SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="lambda",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="Lambda",
                )
            },
        )

        generator = TerraformGenerator()
        result = await generator.generate(intent_spec)

        main_tf = result["main.tf"]
        assert "aws_apigatewayv2_api" in main_tf
        assert "aws_apigatewayv2_integration" in main_tf
        assert "aws_lambda_permission" in main_tf

    @pytest.mark.asyncio
    async def test_unsupported_platform_raises_error(self):
        """Test that unsupported platform raises ValueError."""
        item_id = uuid4()
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                item_id: SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="azure_aks",  # Unsupported
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="Azure",
                )
            },
        )

        generator = TerraformGenerator()

        with pytest.raises(ValueError, match="Unsupported platform"):
            await generator.generate(intent_spec)

    @pytest.mark.asyncio
    async def test_missing_platform_raises_error(self):
        """Test that missing platform raises ValueError."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.CONSTRAINT,
                    key="region",
                    value="us-east-1",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="Region only",
                )
            },
        )

        generator = TerraformGenerator()

        with pytest.raises(ValueError, match="No compute platform specified"):
            await generator.generate(intent_spec)

    @pytest.mark.asyncio
    async def test_factory_function(self):
        """Test create_terraform_generator factory."""
        generator = create_terraform_generator()
        assert isinstance(generator, TerraformGenerator)

    @pytest.mark.asyncio
    async def test_generated_hcl_is_syntactically_valid(self):
        """Test that generated HCL has valid basic structure."""
        item_id = uuid4()
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                item_id: SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="EKS",
                )
            },
        )

        generator = TerraformGenerator()
        result = await generator.generate(intent_spec)

        main_tf = result["main.tf"]

        # Check basic HCL syntax
        assert main_tf.count("resource ") > 5
        assert main_tf.count("{") == main_tf.count("}")  # Balanced braces
        assert "aws_" in main_tf  # AWS resources
        assert "tags = var.tags" in main_tf  # Variable references

    @pytest.mark.asyncio
    async def test_eks_vpc_has_proper_networking(self):
        """Test EKS VPC includes proper networking components."""
        item_id = uuid4()
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                item_id: SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="EKS",
                )
            },
        )

        generator = TerraformGenerator()
        result = await generator.generate(intent_spec)

        main_tf = result["main.tf"]

        # Check VPC components
        assert "aws_vpc" in main_tf
        assert "aws_subnet" in main_tf  # Both public and private
        assert "aws_internet_gateway" in main_tf
        assert "aws_nat_gateway" in main_tf
        assert "aws_route_table" in main_tf
        assert "10.0.0.0/16" in main_tf  # CIDR block

    @pytest.mark.asyncio
    async def test_ecs_has_load_balancer(self):
        """Test ECS Fargate includes Application Load Balancer."""
        item_id = uuid4()
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                item_id: SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="ecs",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="ECS",
                )
            },
        )

        generator = TerraformGenerator()
        result = await generator.generate(intent_spec)

        main_tf = result["main.tf"]

        assert "aws_lb" in main_tf
        assert "aws_lb_target_group" in main_tf
        assert "aws_lb_listener" in main_tf
        assert "load_balancer_type = \"application\"" in main_tf

    @pytest.mark.asyncio
    async def test_lambda_runtime_version(self):
        """Test Lambda function uses modern Python runtime."""
        item_id = uuid4()
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                item_id: SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="lambda",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="Lambda",
                )
            },
        )

        generator = TerraformGenerator()
        result = await generator.generate(intent_spec)

        main_tf = result["main.tf"]

        assert "runtime" in main_tf
        assert "python3.11" in main_tf  # Modern runtime


class TestTerraformTemplateExtraction:
    """Test IntentSpec parameter extraction."""

    def test_extract_platform(self):
        """Test platform extraction from various keys."""
        generator = TerraformGenerator()

        # Test "platform" key
        spec = IntentSpec(
            session_id="test",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="test",
                )
            },
        )
        assert generator._extract_platform(spec) == "eks"

        # Test "compute_platform" key
        spec2 = IntentSpec(
            session_id="test",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="compute_platform",
                    value="lambda",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="test",
                )
            },
        )
        assert generator._extract_platform(spec2) == "lambda"

    def test_extract_region_default(self):
        """Test region extraction with default fallback."""
        generator = TerraformGenerator()

        spec = IntentSpec(
            session_id="test",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="test",
                )
            },
        )
        assert generator._extract_region(spec) == "us-east-1"  # Default

    def test_extract_app_name_default(self):
        """Test app name extraction with default fallback."""
        generator = TerraformGenerator()

        spec = IntentSpec(
            session_id="test",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="test",
                )
            },
        )
        assert generator._extract_app_name(spec) == "devops-app"  # Default
