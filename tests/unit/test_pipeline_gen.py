"""
Unit tests for CI/CD Pipeline Generator (S2-08).

Tests GitHub Actions workflow generation for EKS, ECS, and Lambda.
"""

import pytest
from uuid import uuid4

from agents.generators.pipeline_gen import PipelineGenerator, create_pipeline_generator
from intent.schema import IntentSpec, SpecItem, IntentCategory, ConfidenceBand


class TestPipelineGenerator:
    """Test GitHub Actions pipeline generation."""

    @pytest.mark.asyncio
    async def test_generate_eks_pipeline(self):
        """Test EKS deployment pipeline generation."""
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

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        assert ".github/workflows/deploy.yml" in result
        assert ".github/workflows/pr-validation.yml" in result

        deploy_yaml = result[".github/workflows/deploy.yml"]
        assert "Deploy to EKS" in deploy_yaml
        assert "amazon-ecr-login" in deploy_yaml
        assert "kubectl" in deploy_yaml
        assert "aws eks update-kubeconfig" in deploy_yaml
        assert "docker build" in deploy_yaml

    @pytest.mark.asyncio
    async def test_generate_ecs_pipeline(self):
        """Test ECS deployment pipeline generation."""
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

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        deploy_yaml = result[".github/workflows/deploy.yml"]
        assert "Deploy to ECS" in deploy_yaml
        assert "amazon-ecs-deploy-task-definition" in deploy_yaml
        assert "amazon-ecs-render-task-definition" in deploy_yaml
        assert "aws ecs describe-task-definition" in deploy_yaml

    @pytest.mark.asyncio
    async def test_generate_lambda_pipeline(self):
        """Test Lambda deployment pipeline generation."""
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

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        deploy_yaml = result[".github/workflows/deploy.yml"]
        assert "Deploy to Lambda" in deploy_yaml
        assert "setup-python" in deploy_yaml
        assert "aws lambda update-function-code" in deploy_yaml
        assert "aws lambda publish-version" in deploy_yaml
        assert "zip -r" in deploy_yaml

    @pytest.mark.asyncio
    async def test_pipeline_uses_oidc_authentication(self):
        """Test pipeline uses OIDC (no long-lived credentials)."""
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

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        deploy_yaml = result[".github/workflows/deploy.yml"]
        assert "role-to-assume" in deploy_yaml
        assert "id-token: write" in deploy_yaml
        assert "secrets.AWS_ROLE_ARN" in deploy_yaml

    @pytest.mark.asyncio
    async def test_pipeline_includes_security_scanning(self):
        """Test pipeline includes security vulnerability scanning."""
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

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        deploy_yaml = result[".github/workflows/deploy.yml"]
        assert "trivy" in deploy_yaml.lower()
        assert "Security scan" in deploy_yaml

    @pytest.mark.asyncio
    async def test_pr_workflow_generated(self):
        """Test PR validation workflow is generated."""
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

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        pr_yaml = result[".github/workflows/pr-validation.yml"]
        assert "PR Validation" in pr_yaml
        assert "pull_request" in pr_yaml
        assert "Terraform" in pr_yaml

    @pytest.mark.asyncio
    async def test_pr_workflow_checks_secrets(self):
        """Test PR workflow includes secret scanning."""
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

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        pr_yaml = result[".github/workflows/pr-validation.yml"]
        assert "trufflehog" in pr_yaml.lower()
        assert "Check for secrets" in pr_yaml

    @pytest.mark.asyncio
    async def test_lambda_pipeline_runs_tests(self):
        """Test Lambda pipeline includes test execution."""
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

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        deploy_yaml = result[".github/workflows/deploy.yml"]
        assert "pytest" in deploy_yaml
        assert "Run tests" in deploy_yaml
        assert "bandit" in deploy_yaml  # Security testing

    @pytest.mark.asyncio
    async def test_eks_pipeline_waits_for_rollout(self):
        """Test EKS pipeline waits for deployment rollout."""
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

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        deploy_yaml = result[".github/workflows/deploy.yml"]
        assert "kubectl rollout status" in deploy_yaml

    @pytest.mark.asyncio
    async def test_ecs_pipeline_waits_for_stability(self):
        """Test ECS pipeline waits for service stability."""
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

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        deploy_yaml = result[".github/workflows/deploy.yml"]
        assert "wait-for-service-stability: true" in deploy_yaml

    @pytest.mark.asyncio
    async def test_custom_region_extraction(self):
        """Test custom AWS region in pipeline."""
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
                    evidence="EU region",
                ),
            },
        )

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        deploy_yaml = result[".github/workflows/deploy.yml"]
        assert "eu-west-1" in deploy_yaml

    @pytest.mark.asyncio
    async def test_custom_app_name_extraction(self):
        """Test custom application name in pipeline."""
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
                    value="my-cool-app",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="App name",
                ),
            },
        )

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        deploy_yaml = result[".github/workflows/deploy.yml"]
        assert "my-cool-app" in deploy_yaml

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

        generator = PipelineGenerator()

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

        generator = PipelineGenerator()

        with pytest.raises(ValueError, match="No compute platform specified"):
            await generator.generate(intent_spec)

    @pytest.mark.asyncio
    async def test_factory_function(self):
        """Test create_pipeline_generator factory."""
        generator = create_pipeline_generator()
        assert isinstance(generator, PipelineGenerator)

    @pytest.mark.asyncio
    async def test_yaml_is_valid_github_actions_format(self):
        """Test generated YAML has valid GitHub Actions structure."""
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

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        deploy_yaml = result[".github/workflows/deploy.yml"]

        # Check YAML structure
        assert "name:" in deploy_yaml
        assert "on:" in deploy_yaml
        assert "jobs:" in deploy_yaml
        assert "steps:" in deploy_yaml
        assert "runs-on: ubuntu-latest" in deploy_yaml

    @pytest.mark.asyncio
    async def test_pipeline_uses_latest_action_versions(self):
        """Test pipeline uses modern action versions."""
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

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        deploy_yaml = result[".github/workflows/deploy.yml"]

        # Check for v4 actions (latest stable)
        assert "actions/checkout@v4" in deploy_yaml
        assert "configure-aws-credentials@v4" in deploy_yaml

    @pytest.mark.asyncio
    async def test_lambda_pipeline_publishes_version(self):
        """Test Lambda pipeline publishes immutable versions."""
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

        generator = PipelineGenerator()
        result = await generator.generate(intent_spec)

        deploy_yaml = result[".github/workflows/deploy.yml"]
        assert "publish-version" in deploy_yaml
        assert "Update alias" in deploy_yaml
