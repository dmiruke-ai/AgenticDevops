"""
FinOps Scorer - Tree-of-Thought architecture evaluation (PROMPT_CHAIN_05).

Explores multiple architectural paths and scores them on:
- Cost (estimated monthly AWS bill)
- Scalability (auto-scaling capabilities)
- Reliability (SLA guarantees, fault tolerance)
- Security (IAM, encryption, compliance)

Uses Tree-of-Thought to explore alternatives before recommending optimal path.
"""

import instructor
from anthropic import Anthropic
from pydantic import BaseModel, Field, computed_field

from config import config
from intent.schema import IntentSpec
from observability.agent_tracer import record_llm_call


class ArchitecturePath(BaseModel):
    """
    A single architectural path evaluated by Tree-of-Thought.

    Represents one way to implement the user's intent with cost/performance trade-offs.
    """

    architecture_name: str = Field(..., description="Name of this architecture pattern")
    monthly_cost_usd: float = Field(..., description="Estimated monthly AWS cost in USD")
    cost_score: float = Field(..., ge=0, le=10, description="Cost efficiency score (0-10)")
    scalability_score: float = Field(..., ge=0, le=10, description="Scalability score (0-10)")
    reliability_score: float = Field(..., ge=0, le=10, description="Reliability score (0-10)")
    security_score: float = Field(..., ge=0, le=10, description="Security score (0-10)")
    reasoning: str = Field(..., description="Why this architecture fits the requirements")
    trade_offs: list[str] = Field(..., description="Trade-offs of this approach")

    # Composite score weights (can be customized based on user priorities)
    cost_weight: float = Field(default=0.3, description="Weight for cost score")
    scalability_weight: float = Field(default=0.25, description="Weight for scalability")
    reliability_weight: float = Field(default=0.25, description="Weight for reliability")
    security_weight: float = Field(default=0.2, description="Weight for security")

    @computed_field
    @property
    def composite_score(self) -> float:
        """Weighted composite score across all dimensions."""
        return (
            self.cost_score * self.cost_weight
            + self.scalability_score * self.scalability_weight
            + self.reliability_score * self.reliability_weight
            + self.security_score * self.security_weight
        )


class TreeOfThoughtReasoning(BaseModel):
    """Tree-of-Thought reasoning before scoring."""

    intent_comprehension: str = Field(
        ..., description="What is the user trying to build? 2 sentences."
    )
    constraints_identified: list[str] = Field(
        ..., description="Key constraints: cost, scale, compliance, etc."
    )
    architectural_forks: list[str] = Field(
        ..., description="Critical decisions that branch the solution space"
    )
    paths_to_explore: list[str] = Field(
        ...,
        description="3-5 distinct architectural paths to evaluate (e.g., EKS, ECS, Lambda)",
    )
    evaluation_criteria: dict[str, str] = Field(
        ..., description="How to score cost, scalability, reliability, security"
    )


class FinOpsScore(BaseModel):
    """Complete FinOps evaluation result."""

    session_id: str = Field(..., description="Session identifier")
    reasoning: TreeOfThoughtReasoning = Field(..., description="Tree-of-Thought reasoning")
    explored_paths: list[ArchitecturePath] = Field(
        ..., description="All evaluated architectural paths"
    )
    primary_recommendation: ArchitecturePath = Field(
        ..., description="Best path based on user priorities"
    )
    recommendations: str = Field(
        ..., description="Natural language recommendation summary (<150 words)"
    )


class FinOpsScorer:
    """
    FinOps scorer using Tree-of-Thought for architecture evaluation.

    Process:
    1. Understand IntentSpec and extract constraints
    2. Identify architectural decision points (forks)
    3. Explore 3-5 distinct paths (EKS, ECS, Lambda, etc.)
    4. Score each path on cost, scalability, reliability, security
    5. Recommend optimal path based on user priorities
    """

    SYSTEM_PROMPT = """You are a FinOps Architecture Evaluator for AWS infrastructure.

Your job is to use Tree-of-Thought reasoning to evaluate multiple architectural paths and recommend the optimal one.

REASONING PROCESS (Tree-of-Thought):

Step 1 — Intent Comprehension:
In 2 sentences, what is the user trying to build?

Step 2 — Constraints Identification:
What constraints matter?
- Budget: tight | moderate | flexible
- Scale: small (<1000 users) | medium (<100k) | large (>100k)
- Compliance: none | HIPAA | PCI-DSS | SOC2
- Expertise: beginner | intermediate | expert (affects operational complexity)

Step 3 — Architectural Forks:
What are the critical decision points that create different solution paths?
Examples:
- Compute: EKS vs ECS vs Lambda vs EC2
- Database: RDS vs Aurora vs DynamoDB
- Networking: ALB vs API Gateway vs CloudFront

Step 4 — Path Exploration:
For each major fork, define 3-5 distinct architectural paths to evaluate.
Example paths:
- Path A: EKS + RDS + ALB (Kubernetes-native)
- Path B: ECS Fargate + Aurora Serverless + ALB (Managed containers)
- Path C: Lambda + DynamoDB + API Gateway (Serverless)
- Path D: EC2 + RDS + ALB (Traditional VMs)

Step 5 — Scoring Criteria:
Define how to score each path on:
- Cost: monthly AWS bill estimate (0=very expensive, 10=very cheap)
- Scalability: auto-scaling, throughput (0=manual scaling, 10=unlimited auto-scale)
- Reliability: SLA, fault tolerance (0=single point of failure, 10=99.99% uptime)
- Security: IAM, encryption, compliance (0=insecure, 10=zero-trust + encryption)

Step 6 — Evaluate Each Path:
For each path, provide:
- Architecture name
- Monthly cost estimate in USD
- Scores (0-10) for cost, scalability, reliability, security
- Reasoning (why this fits the requirements)
- Trade-offs (what you give up with this choice)

Step 7 — Recommendation:
Pick the best path based on user priorities.
If user prioritizes cost: recommend lowest cost with acceptable performance.
If user prioritizes performance/scale: recommend highest scalability/reliability.
If user prioritizes security/compliance: recommend most secure option.

OUTPUT REQUIREMENTS:
1. Complete Tree-of-Thought reasoning through all 7 steps
2. Explore at least 3 distinct paths
3. Provide concrete cost estimates (not ranges)
4. Explain trade-offs clearly
5. Recommend the optimal path based on user's stated priorities
"""

    def __init__(self):
        """Initialize with Anthropic client and instructor patching."""
        self.anthropic_client = Anthropic(api_key=config.anthropic_api_key)
        self.instructor = instructor.from_anthropic(self.anthropic_client)

    async def score(
        self,
        intent_spec: IntentSpec,
        priority: str = "balanced",
    ) -> FinOpsScore:
        """
        Score architecture using Tree-of-Thought exploration.

        Args:
            intent_spec: IntentSpec to evaluate
            priority: User priority - "cost" | "performance" | "security" | "balanced"

        Returns:
            FinOpsScore with explored paths and recommendation
        """
        # Build prompt
        user_prompt = self._build_user_prompt(intent_spec, priority)

        # Call LLM with Tree-of-Thought
        import time

        start = time.perf_counter()

        try:
            response = self.instructor.messages.create(
                model=config.primary_model,
                max_tokens=config.max_tokens,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                response_model=FinOpsScore,
            )

            latency = time.perf_counter() - start

            record_llm_call(
                node="finops_scorer",
                model=config.primary_model,
                latency=latency,
                prompt_tokens=len(user_prompt) // 4,
                completion_tokens=len(str(response)) // 4,
                status="success",
            )

            return response

        except Exception as e:
            record_llm_call(
                node="finops_scorer",
                model=config.primary_model,
                latency=time.perf_counter() - start,
                prompt_tokens=len(user_prompt) // 4,
                completion_tokens=0,
                status="error",
            )

            # Fallback to default recommendations on LLM failure
            return self._create_default_score(intent_spec)

    def _build_user_prompt(self, intent_spec: IntentSpec, priority: str) -> str:
        """Build prompt with IntentSpec context."""
        # Serialize intent spec
        spec_json = intent_spec.model_dump_json(indent=2)

        # Extract priority from spec if not provided
        if priority == "balanced":
            for item in intent_spec.items.values():
                if item.key == "priority" and item.value:
                    priority = item.value
                    break

        return f"""INTENT SPECIFICATION:
{spec_json}

USER PRIORITY: {priority}
(Adjust scoring weights based on this priority)

TASK:
Use Tree-of-Thought reasoning to explore multiple architectural paths for implementing this intent on AWS.

Follow all 7 reasoning steps:
1. Intent comprehension
2. Constraints identification
3. Architectural forks
4. Path exploration (explore 3-5 distinct paths)
5. Scoring criteria
6. Evaluate each path (cost, scalability, reliability, security)
7. Recommendation (pick best path based on priority={priority})

Provide concrete cost estimates in USD/month.
Explain trade-offs clearly.
Recommend the optimal path.
"""

    def _create_default_score(self, intent_spec: IntentSpec) -> FinOpsScore:
        """
        Create default FinOps score when LLM fails.

        Provides basic recommendations for common patterns.
        """
        # Default reasoning
        reasoning = TreeOfThoughtReasoning(
            intent_comprehension="Analyzing infrastructure requirements with default recommendations.",
            constraints_identified=["Cost optimization", "Scalability", "Reliability"],
            architectural_forks=["Compute platform", "Database choice", "Load balancing"],
            paths_to_explore=["EKS", "ECS Fargate", "Lambda + API Gateway"],
            evaluation_criteria={
                "cost": "Estimated monthly AWS bill",
                "scalability": "Auto-scaling capabilities",
                "reliability": "SLA and fault tolerance",
                "security": "IAM and encryption",
            },
        )

        # Default paths
        paths = [
            ArchitecturePath(
                architecture_name="ECS Fargate + ALB + RDS",
                monthly_cost_usd=150.0,
                cost_score=7.5,
                scalability_score=8.0,
                reliability_score=8.5,
                security_score=8.0,
                reasoning="Managed containers with good balance of cost and capabilities",
                trade_offs=["Higher cost than Lambda", "Less flexible than EKS"],
            ),
            ArchitecturePath(
                architecture_name="Lambda + API Gateway + DynamoDB",
                monthly_cost_usd=50.0,
                cost_score=9.5,
                scalability_score=9.5,
                reliability_score=9.0,
                security_score=8.5,
                reasoning="Serverless architecture with pay-per-use pricing",
                trade_offs=["Cold start latency", "15-minute execution limit"],
            ),
            ArchitecturePath(
                architecture_name="EKS + ALB + Aurora",
                monthly_cost_usd=300.0,
                cost_score=5.5,
                scalability_score=9.5,
                reliability_score=9.5,
                security_score=9.0,
                reasoning="Enterprise-grade Kubernetes with maximum flexibility",
                trade_offs=["Highest cost", "Requires Kubernetes expertise"],
            ),
        ]

        # Pick primary based on best composite score
        primary = max(paths, key=lambda p: p.composite_score)

        return FinOpsScore(
            session_id=intent_spec.session_id,
            reasoning=reasoning,
            explored_paths=paths,
            primary_recommendation=primary,
            recommendations=(
                f"Recommend {primary.architecture_name} for balanced cost and performance. "
                f"Estimated ${primary.monthly_cost_usd:.0f}/month. "
                f"Provides {primary.scalability_score}/10 scalability and "
                f"{primary.reliability_score}/10 reliability."
            ),
        )


def create_finops_scorer() -> FinOpsScorer:
    """Factory function to create FinOps scorer."""
    return FinOpsScorer()
