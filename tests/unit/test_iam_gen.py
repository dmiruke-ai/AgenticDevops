"""
Unit tests for IAM Policy Generator (S2-07).

Tests least-privilege IAM policy generation with no wildcard resources.
"""

import pytest
from uuid import uuid4

from agents.generators.iam_gen import IAMPolicyGenerator, create_iam_generator
from intent.schema import IntentSpec, SpecItem, IntentCategory, ConfidenceBand


class TestIAMPolicyGenerator:
    """Test IAM policy generation."""

    @pytest.mark.asyncio
    async def test_generate_eks_policies(self):
        """Test EKS IAM policy generation."""
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

        generator = IAMPolicyGenerator()
        result = await generator.generate(intent_spec)

        assert "eks_cluster_role_policy" in result
        assert "eks_node_group_policy" in result
        assert "metadata" in result
        assert result["metadata"]["platform"] == "eks"
        assert result["metadata"]["has_wildcards"] is False

        # Check cluster policy structure
        cluster_policy = result["eks_cluster_role_policy"]
        assert cluster_policy["Version"] == "2012-10-17"
        assert "Statement" in cluster_policy
        assert len(cluster_policy["Statement"]) > 0

    @pytest.mark.asyncio
    async def test_generate_ecs_policies(self):
        """Test ECS IAM policy generation."""
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

        generator = IAMPolicyGenerator()
        result = await generator.generate(intent_spec)

        assert "ecs_task_execution_policy" in result
        assert "ecs_task_policy" in result
        assert "metadata" in result
        assert result["metadata"]["platform"] == "ecs"

        # Check execution policy
        exec_policy = result["ecs_task_execution_policy"]
        assert "Statement" in exec_policy
        assert any("ECR" in stmt.get("Sid", "") for stmt in exec_policy["Statement"])

    @pytest.mark.asyncio
    async def test_generate_lambda_policies(self):
        """Test Lambda IAM policy generation."""
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

        generator = IAMPolicyGenerator()
        result = await generator.generate(intent_spec)

        assert "lambda_execution_policy" in result
        assert "lambda_function_policy" in result
        assert "metadata" in result
        assert result["metadata"]["platform"] == "lambda"

        # Check function policy
        func_policy = result["lambda_function_policy"]
        assert "Statement" in func_policy
        assert len(func_policy["Statement"]) >= 3  # S3, DynamoDB, SQS

    @pytest.mark.asyncio
    async def test_policies_have_no_dangerous_wildcards(self):
        """Test that generated policies don't have wildcard resource ARNs."""
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

        generator = IAMPolicyGenerator()
        result = await generator.generate(intent_spec)

        # Validate no wildcards
        assert generator.validate_no_wildcards(result) is True

    @pytest.mark.asyncio
    async def test_eks_policy_scoped_to_specific_cluster(self):
        """Test EKS policies are scoped to specific cluster ARN."""
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
                ),
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="app_name",
                    value="my-app",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="App name",
                ),
            },
        )

        generator = IAMPolicyGenerator()
        result = await generator.generate(intent_spec)

        cluster_policy = result["eks_cluster_role_policy"]
        # Check that cluster ARN contains the app name
        cluster_statement = cluster_policy["Statement"][0]
        assert "my-app-cluster" in cluster_statement["Resource"]

    @pytest.mark.asyncio
    async def test_ecs_policy_has_cloudwatch_logs(self):
        """Test ECS policies include CloudWatch Logs access."""
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

        generator = IAMPolicyGenerator()
        result = await generator.generate(intent_spec)

        exec_policy = result["ecs_task_execution_policy"]
        log_statement = next(
            (s for s in exec_policy["Statement"] if "CloudWatchLogs" in s.get("Sid", "")),
            None,
        )
        assert log_statement is not None
        assert "logs:PutLogEvents" in log_statement["Action"]

    @pytest.mark.asyncio
    async def test_lambda_policy_has_xray_tracing(self):
        """Test Lambda policies include X-Ray tracing."""
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

        generator = IAMPolicyGenerator()
        result = await generator.generate(intent_spec)

        exec_policy = result["lambda_execution_policy"]
        xray_statement = next(
            (s for s in exec_policy["Statement"] if "XRay" in s.get("Sid", "")),
            None,
        )
        assert xray_statement is not None
        assert "xray:PutTraceSegments" in xray_statement["Action"]

    @pytest.mark.asyncio
    async def test_custom_resource_arns(self):
        """Test policy generation with custom resource ARNs."""
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

        resource_arns = {
            "account_id": "123456789012",
            "function_name": "custom-function",
        }

        generator = IAMPolicyGenerator()
        result = await generator.generate(intent_spec, resource_arns=resource_arns)

        exec_policy = result["lambda_execution_policy"]
        log_statement = next(
            (s for s in exec_policy["Statement"] if "CloudWatchLogs" in s.get("Sid", "")),
            None,
        )
        assert "123456789012" in log_statement["Resource"]
        assert "custom-function" in log_statement["Resource"]

    @pytest.mark.asyncio
    async def test_unsupported_platform_raises_error(self):
        """Test unsupported platform raises ValueError."""
        item_id = uuid4()
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                item_id: SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="azure",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="Azure",
                )
            },
        )

        generator = IAMPolicyGenerator()

        with pytest.raises(ValueError, match="Unsupported platform"):
            await generator.generate(intent_spec)

    @pytest.mark.asyncio
    async def test_missing_platform_raises_error(self):
        """Test missing platform raises ValueError."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.CONSTRAINT,
                    key="region",
                    value="us-east-1",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="Region",
                )
            },
        )

        generator = IAMPolicyGenerator()

        with pytest.raises(ValueError, match="No compute platform specified"):
            await generator.generate(intent_spec)

    @pytest.mark.asyncio
    async def test_factory_function(self):
        """Test create_iam_generator factory."""
        generator = create_iam_generator()
        assert isinstance(generator, IAMPolicyGenerator)

    @pytest.mark.asyncio
    async def test_ecs_task_policy_has_s3_access(self):
        """Test ECS task policy includes S3 access."""
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

        generator = IAMPolicyGenerator()
        result = await generator.generate(intent_spec)

        task_policy = result["ecs_task_policy"]
        s3_statement = next(
            (s for s in task_policy["Statement"] if "S3" in s.get("Sid", "")),
            None,
        )
        assert s3_statement is not None
        assert "s3:GetObject" in s3_statement["Action"]
        assert "s3:PutObject" in s3_statement["Action"]

    @pytest.mark.asyncio
    async def test_lambda_policy_has_sqs_access(self):
        """Test Lambda function policy includes SQS access."""
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

        generator = IAMPolicyGenerator()
        result = await generator.generate(intent_spec)

        func_policy = result["lambda_function_policy"]
        sqs_statement = next(
            (s for s in func_policy["Statement"] if "SQS" in s.get("Sid", "")),
            None,
        )
        assert sqs_statement is not None
        assert "sqs:SendMessage" in sqs_statement["Action"]

    @pytest.mark.asyncio
    async def test_policy_version_is_standard(self):
        """Test all policies use standard AWS policy version."""
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

        generator = IAMPolicyGenerator()
        result = await generator.generate(intent_spec)

        for policy_name, policy_doc in result.items():
            if policy_name == "metadata":
                continue
            assert policy_doc["Version"] == "2012-10-17"

    @pytest.mark.asyncio
    async def test_all_statements_have_sid(self):
        """Test all policy statements have Sid for identification."""
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

        generator = IAMPolicyGenerator()
        result = await generator.generate(intent_spec)

        for policy_name, policy_doc in result.items():
            if policy_name == "metadata":
                continue

            for statement in policy_doc["Statement"]:
                assert "Sid" in statement
                assert len(statement["Sid"]) > 0

    @pytest.mark.asyncio
    async def test_metadata_includes_generation_timestamp(self):
        """Test metadata includes generation timestamp."""
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

        generator = IAMPolicyGenerator()
        result = await generator.generate(intent_spec)

        metadata = result["metadata"]
        assert "generated_at" in metadata
        assert "T" in metadata["generated_at"]  # ISO format timestamp

    @pytest.mark.asyncio
    async def test_ecs_policy_has_secrets_manager_access(self):
        """Test ECS execution policy includes Secrets Manager access."""
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

        generator = IAMPolicyGenerator()
        result = await generator.generate(intent_spec)

        exec_policy = result["ecs_task_execution_policy"]
        secrets_statement = next(
            (s for s in exec_policy["Statement"] if "SecretsManager" in s.get("Sid", "")),
            None,
        )
        assert secrets_statement is not None
        assert "secretsmanager:GetSecretValue" in secrets_statement["Action"]


class TestWildcardValidation:
    """Test wildcard resource validation."""

    def test_validate_no_wildcards_passes_for_safe_policies(self):
        """Test validation passes for policies without dangerous wildcards."""
        generator = IAMPolicyGenerator()

        safe_policy = {
            "test_policy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "S3Access",
                        "Effect": "Allow",
                        "Action": ["s3:GetObject"],
                        "Resource": "arn:aws:s3:::my-bucket/*",
                    }
                ],
            },
            "metadata": {"has_wildcards": False},
        }

        assert generator.validate_no_wildcards(safe_policy) is True

    def test_validate_no_wildcards_allows_ec2_describe(self):
        """Test validation allows EC2 describe actions with wildcard (AWS requirement)."""
        generator = IAMPolicyGenerator()

        ec2_policy = {
            "test_policy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "EC2Describe",
                        "Effect": "Allow",
                        "Action": ["ec2:DescribeSubnets", "ec2:DescribeVpcs"],
                        "Resource": "*",
                    }
                ],
            },
        }

        assert generator.validate_no_wildcards(ec2_policy) is True

    def test_validate_no_wildcards_allows_xray(self):
        """Test validation allows X-Ray with wildcard (AWS requirement)."""
        generator = IAMPolicyGenerator()

        xray_policy = {
            "test_policy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "XRay",
                        "Effect": "Allow",
                        "Action": ["xray:PutTraceSegments"],
                        "Resource": "*",
                    }
                ],
            },
        }

        assert generator.validate_no_wildcards(xray_policy) is True

    def test_validate_no_wildcards_fails_for_dangerous_wildcards(self):
        """Test validation fails for dangerous wildcard resources."""
        generator = IAMPolicyGenerator()

        dangerous_policy = {
            "test_policy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AdminAccess",
                        "Effect": "Allow",
                        "Action": ["s3:*"],
                        "Resource": "*",  # Dangerous - grants access to all S3 buckets
                    }
                ],
            },
        }

        assert generator.validate_no_wildcards(dangerous_policy) is False
