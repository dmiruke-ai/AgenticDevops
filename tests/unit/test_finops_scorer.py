"""
Unit tests for FinOps Scorer (PROMPT_CHAIN_05).

Tests Tree-of-Thought architecture evaluation and cost/performance scoring.
"""

import pytest
from uuid import uuid4

from agents.finops.scorer import FinOpsScorer, FinOpsScore, ArchitecturePath
from intent.schema import IntentSpec, SpecItem, IntentCategory, ConfidenceBand


class TestFinOpsScorer:
    """Test FinOps scoring with Tree-of-Thought."""

    @pytest.mark.asyncio
    async def test_score_eks_architecture(self):
        """Test scoring EKS-based architecture."""
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
                    evidence="User said: 'I want EKS'",
                )
            },
        )

        scorer = FinOpsScorer()
        result = await scorer.score(intent_spec)

        assert result.session_id == "test-session"
        assert result.primary_recommendation is not None
        assert len(result.explored_paths) >= 1

        # Should have EKS as one of the explored paths
        eks_path = next(
            (p for p in result.explored_paths if "EKS" in p.architecture_name.upper()),
            None,
        )
        assert eks_path is not None
        assert eks_path.monthly_cost_usd > 0
        assert 0 <= eks_path.scalability_score <= 10
        assert 0 <= eks_path.reliability_score <= 10
        assert 0 <= eks_path.security_score <= 10

    @pytest.mark.asyncio
    async def test_score_ecs_architecture(self):
        """Test scoring ECS-based architecture."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="ecs",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="User wants ECS",
                )
            },
        )

        scorer = FinOpsScorer()
        result = await scorer.score(intent_spec)

        # Should have ECS as primary or explored path
        ecs_path = next(
            (p for p in result.explored_paths if "ECS" in p.architecture_name.upper()),
            None,
        )
        assert ecs_path is not None

    @pytest.mark.asyncio
    async def test_score_lambda_architecture(self):
        """Test scoring serverless Lambda architecture."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="lambda",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="User wants serverless",
                )
            },
        )

        scorer = FinOpsScorer()
        result = await scorer.score(intent_spec)

        # Lambda should be in explored paths
        lambda_path = next(
            (p for p in result.explored_paths if "LAMBDA" in p.architecture_name.upper()),
            None,
        )
        assert lambda_path is not None

    @pytest.mark.asyncio
    async def test_explores_multiple_paths(self):
        """Test that Tree-of-Thought explores multiple architectural paths."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="workload",
                    value="web_app",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="User wants web app",
                )
            },
        )

        scorer = FinOpsScorer()
        result = await scorer.score(intent_spec)

        # Should explore at least 2-3 different paths
        assert len(result.explored_paths) >= 2

        # Each path should have unique architecture
        architecture_names = [p.architecture_name for p in result.explored_paths]
        assert len(architecture_names) == len(set(architecture_names)), "Paths should be unique"

    @pytest.mark.asyncio
    async def test_primary_recommendation_is_best_path(self):
        """Test that primary recommendation has best overall score."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="workload",
                    value="api",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="API service",
                )
            },
        )

        scorer = FinOpsScorer()
        result = await scorer.score(intent_spec)

        primary = result.primary_recommendation

        # Primary should be in explored paths
        assert primary in result.explored_paths

        # Primary should have one of the highest composite scores
        all_scores = [p.composite_score for p in result.explored_paths]
        assert primary.composite_score >= max(all_scores) - 0.5  # Within 0.5 of best

    @pytest.mark.asyncio
    async def test_cost_optimization_priority(self):
        """Test that cost-optimized path is recommended for cost priority."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.CONSTRAINT,
                    key="priority",
                    value="cost",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="User prioritizes cost savings",
                ),
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="workload",
                    value="web_app",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="Simple web app",
                ),
            },
        )

        scorer = FinOpsScorer()
        result = await scorer.score(intent_spec)

        # Primary recommendation should emphasize low cost
        primary = result.primary_recommendation
        all_costs = [p.monthly_cost_usd for p in result.explored_paths]

        # Primary should be among the cheaper options
        median_cost = sorted(all_costs)[len(all_costs) // 2]
        assert primary.monthly_cost_usd <= median_cost

    @pytest.mark.asyncio
    async def test_performance_priority(self):
        """Test that high-performance path recommended for performance priority."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.CONSTRAINT,
                    key="priority",
                    value="performance",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="User needs high performance",
                ),
            },
        )

        scorer = FinOpsScorer()
        result = await scorer.score(intent_spec)

        primary = result.primary_recommendation

        # Should prioritize scalability and reliability
        assert primary.scalability_score >= 7.0
        assert primary.reliability_score >= 7.0

    @pytest.mark.asyncio
    async def test_architecture_path_has_reasoning(self):
        """Test that each path includes reasoning and trade-offs."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="workload",
                    value="api",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="API",
                )
            },
        )

        scorer = FinOpsScorer()
        result = await scorer.score(intent_spec)

        for path in result.explored_paths:
            assert len(path.architecture_name) > 0
            assert path.reasoning is not None
            assert len(path.reasoning) > 20  # Should have meaningful reasoning
            assert len(path.trade_offs) > 0  # Should list trade-offs

    @pytest.mark.asyncio
    async def test_composite_score_calculation(self):
        """Test that composite score is calculated correctly."""
        intent_spec = IntentSpec(session_id="test-session")

        scorer = FinOpsScorer()
        result = await scorer.score(intent_spec)

        for path in result.explored_paths:
            # Composite score should be weighted average
            # Default weights: cost_weight=0.3, scalability=0.25, reliability=0.25, security=0.2
            expected = (
                path.cost_score * 0.3
                + path.scalability_score * 0.25
                + path.reliability_score * 0.25
                + path.security_score * 0.2
            )
            assert abs(path.composite_score - expected) < 0.1

    @pytest.mark.asyncio
    async def test_fallback_on_llm_failure(self):
        """Test that scorer provides default recommendations on LLM failure."""
        # This test verifies graceful degradation
        # Will be implemented with mock LLM failure
        intent_spec = IntentSpec(session_id="test-session")

        scorer = FinOpsScorer()
        # Even with empty spec, should return some default analysis
        result = await scorer.score(intent_spec)

        assert result is not None
        assert result.primary_recommendation is not None
        assert len(result.explored_paths) >= 1


class TestArchitecturePath:
    """Test ArchitecturePath model."""

    def test_create_architecture_path(self):
        """Test creating an ArchitecturePath."""
        path = ArchitecturePath(
            architecture_name="EKS + ALB + RDS",
            monthly_cost_usd=250.0,
            cost_score=7.0,
            scalability_score=9.0,
            reliability_score=8.5,
            security_score=8.0,
            reasoning="EKS provides excellent Kubernetes orchestration",
            trade_offs=["Higher cost than ECS", "Requires Kubernetes expertise"],
        )

        assert path.architecture_name == "EKS + ALB + RDS"
        assert path.monthly_cost_usd == 250.0
        assert 0 <= path.composite_score <= 10

    def test_composite_score_defaults(self):
        """Test composite score with default weights."""
        path = ArchitecturePath(
            architecture_name="Test",
            monthly_cost_usd=100.0,
            cost_score=8.0,
            scalability_score=6.0,
            reliability_score=7.0,
            security_score=9.0,
            reasoning="Test reasoning",
            trade_offs=["Trade-off 1"],
        )

        # Default: cost=30%, scalability=25%, reliability=25%, security=20%
        expected = 8.0 * 0.3 + 6.0 * 0.25 + 7.0 * 0.25 + 9.0 * 0.2
        assert abs(path.composite_score - expected) < 0.01
