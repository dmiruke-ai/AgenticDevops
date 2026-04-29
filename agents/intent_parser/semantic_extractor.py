"""
Semantic Intent Extractor (PROMPT_CHAIN_01).

Extracts structured intent from user messages using LLM with maximum precision.
Uses instructor library for structured output with automatic schema validation retry.
"""

import instructor
from anthropic import Anthropic
from openai import OpenAI
from pydantic import BaseModel, Field

from config import config
from intent.schema import (
    ConfidenceBand,
    ExtractionResult,
    IntentCategory,
    IntentSpec,
    OpenQuestion,
    SpecItem,
)
from observability.agent_tracer import record_llm_call


# Structured output schema for LLM
class ReasoningSteps(BaseModel):
    """Chain-of-Thought reasoning before JSON output."""

    surface_intent: str = Field(
        ..., description="What did the user literally say? Quote it."
    )
    task_decomposition: list[dict[str, str]] = Field(
        ...,
        description="DevOps actions implied: action, target, confidence, evidence",
    )
    meta_intent: dict[str, str] = Field(
        ..., description="User's underlying goal: motivation, priorities"
    )
    constraints_extraction: list[dict[str, str]] = Field(
        ..., description="Constraints: key, value, confidence, evidence"
    )
    gap_analysis: list[dict[str, str]] = Field(
        ..., description="Missing info: question, blocks_action, priority"
    )
    conflict_check: list[str] = Field(
        ..., description="Conflicts with existing spec"
    )
    assumption_log: list[str] = Field(
        ..., description="Assumptions made that user did NOT say"
    )


class ExtractorResponse(BaseModel):
    """Complete response from semantic extractor."""

    reasoning: ReasoningSteps
    extraction_result: ExtractionResult


class SemanticExtractor:
    """
    Extracts structured intent using Chain-of-Thought LLM prompting.

    Uses claude-sonnet-4 (primary) with gpt-4o fallback.
    All output validated via instructor library.
    """

    SYSTEM_PROMPT = """You are an Intent Extraction Engine for an AI DevOps Agent Platform.
Your job is to extract structured intent from user messages with maximum precision.

You MUST reason step-by-step before producing JSON output.
You MUST follow the exact output schema. No extra keys, no missing required fields.
You MUST assign confidence bands using ONLY: "stated" | "confirmed" | "inferred" | "speculative"

Confidence band rules:
- "stated": User said it explicitly, verbatim (e.g., "I want EKS")
- "confirmed": User affirmed after being asked (e.g., "yes, EKS is right")
- "inferred": Strongly implied by context but not stated (e.g., mentions Kubernetes → likely EKS on AWS)
- "speculative": LLM assumption with no user signal (e.g., assuming us-east-1 because user didn't specify)

NEVER execute or commit to irreversible actions on "inferred" or "speculative" items.

OUTPUT REQUIREMENTS:
1. Reason step-by-step through all 7 reasoning steps
2. Extract new_items with proper confidence bands
3. Identify open_questions that block execution
4. Detect conflicts with existing spec
5. Log all assumptions explicitly
"""

    def __init__(self):
        """Initialize with anthropic client and instructor patching."""
        self.anthropic_client = Anthropic(api_key=config.anthropic_api_key)
        self.openai_client = OpenAI(api_key=config.openai_api_key)

        # Patch clients with instructor for structured output
        self.anthropic_instructor = instructor.from_anthropic(self.anthropic_client)
        self.openai_instructor = instructor.from_openai(self.openai_client)

    async def extract(
        self,
        user_message: str,
        existing_spec: IntentSpec,
        conversation_history: list[str],
        turn: int,
    ) -> ExtractionResult:
        """
        Extract structured intent from user message.

        Args:
            user_message: Current user message
            existing_spec: Existing IntentSpec (may be empty)
            conversation_history: Last 3 turns for context
            turn: Current turn number

        Returns:
            ExtractionResult with new items, questions, and conflicts
        """
        # Build prompt context
        user_prompt = self._build_user_prompt(
            user_message,
            existing_spec,
            conversation_history,
        )

        # Try primary model (claude-sonnet-4)
        try:
            response = await self._extract_with_anthropic(user_prompt, turn)
            return response.extraction_result
        except Exception as e:
            print(f"[SemanticExtractor] Primary model failed: {e}")
            # Fallback to gpt-4o
            response = await self._extract_with_openai(user_prompt, turn)
            return response.extraction_result

    async def _extract_with_anthropic(
        self, user_prompt: str, turn: int
    ) -> ExtractorResponse:
        """Extract using claude-sonnet-4 with instructor."""
        import time

        start = time.perf_counter()

        try:
            response = self.anthropic_instructor.messages.create(
                model=config.primary_model,
                max_tokens=config.max_tokens,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                response_model=ExtractorResponse,
            )

            latency = time.perf_counter() - start

            # Record metrics (approximate token usage)
            record_llm_call(
                node="semantic_extractor",
                model=config.primary_model,
                latency=latency,
                prompt_tokens=len(user_prompt) // 4,  # rough estimate
                completion_tokens=len(str(response)) // 4,
                status="success",
            )

            return response

        except Exception as e:
            record_llm_call(
                node="semantic_extractor",
                model=config.primary_model,
                latency=time.perf_counter() - start,
                prompt_tokens=len(user_prompt) // 4,
                completion_tokens=0,
                status="error",
            )
            raise

    async def _extract_with_openai(
        self, user_prompt: str, turn: int
    ) -> ExtractorResponse:
        """Extract using gpt-4o fallback with instructor."""
        import time

        start = time.perf_counter()

        try:
            response = self.openai_instructor.chat.completions.create(
                model=config.fallback_model,
                max_tokens=config.max_tokens,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_model=ExtractorResponse,
            )

            latency = time.perf_counter() - start

            record_llm_call(
                node="semantic_extractor",
                model=config.fallback_model,
                latency=latency,
                prompt_tokens=len(user_prompt) // 4,
                completion_tokens=len(str(response)) // 4,
                status="success",
            )

            return response

        except Exception as e:
            record_llm_call(
                node="semantic_extractor",
                model=config.fallback_model,
                latency=time.perf_counter() - start,
                prompt_tokens=len(user_prompt) // 4,
                completion_tokens=0,
                status="error",
            )
            raise

    def _build_user_prompt(
        self,
        user_message: str,
        existing_spec: IntentSpec,
        conversation_history: list[str],
    ) -> str:
        """Build the user prompt with context."""
        # Serialize existing spec to JSON
        existing_spec_json = existing_spec.model_dump_json(indent=2)

        # Format conversation history
        history_text = "\n".join(
            [f"Turn {i+1}: {msg}" for i, msg in enumerate(conversation_history[-3:])]
        )

        return f"""USER TURN:
[PREVIOUS_SPEC]: {existing_spec_json}

[CONVERSATION_HISTORY]:
{history_text}

[CURRENT_MESSAGE]: {user_message}

REASONING STEPS (you must output these before JSON):

Step 1 — Surface Intent:
What did the user literally say? Quote it.

Step 2 — Task Intent Decomposition:
What specific DevOps actions does this imply? List each:
- Action: [infra_generation | pipeline_generation | deployment_strategy | debugging | optimization | cost_analysis]
- Target: [EKS | ECS | Lambda | RDS | S3 | multi-tier | unknown]
- Confidence: [stated | confirmed | inferred | speculative]

Step 3 — Meta Intent:
What is the user's underlying goal?
- Motivation: [production_ready | learning | demo | cost_optimization | security_improvement]
- Priority ranking: [cost | speed | scalability | security | reliability] in order

Step 4 — Constraints Extraction:
What constraints did the user specify or imply?
For each constraint: key, value, confidence band, evidence quote

Step 5 — Gap Analysis:
What critical information is missing that would block execution?
For each gap: question text, which downstream agent it blocks, priority (high|medium|low)

Step 6 — Conflict Check:
Does any new information conflict with existing_spec?
List conflicts with affected item IDs.

Step 7 — Assumption Log:
What are you assuming that the user did NOT say?
For each: state it explicitly. These are all "speculative" confidence.

Now provide your complete extraction with reasoning and results."""


def create_extractor() -> SemanticExtractor:
    """Factory function to create semantic extractor instance."""
    return SemanticExtractor()
