"""
Dialogue Policy Engine (PROMPT_CHAIN_02).

Implements Reflect + Guide pattern for guiding users toward architectural clarity.
Uses Chain-of-Thought reasoning to craft responses.
"""

import instructor
from anthropic import Anthropic
from pydantic import BaseModel, Field

from config import config
from intent.schema import Conflict, IntentSpec, OpenQuestion
from observability.agent_tracer import record_llm_call


# Structured output schemas
class DialogueReasoning(BaseModel):
    """Chain-of-Thought reasoning for dialogue response."""

    spec_comprehension: str = Field(
        ..., description="2-sentence summary of what user wants to build"
    )
    whats_blocking: str = Field(
        ..., description="Highest-priority question or conflict blocking execution"
    )
    response_strategy: str = Field(
        ..., description="Response type: ask | reflect | confirm | escalate"
    )
    draft_response: str = Field(
        ..., description="Draft response text following Reflect+Guide pattern"
    )


class DialogueResponse(BaseModel):
    """Complete dialogue response."""

    reasoning: DialogueReasoning
    response_text: str = Field(..., description="Final response to user (<120 words)")
    addresses_question_id: str | None = Field(
        None, description="Question ID being addressed"
    )
    resolved_conflict_id: str | None = Field(
        None, description="Conflict ID being resolved"
    )
    ready_to_execute: bool = Field(
        False, description="True if spec is complete and ready for generation"
    )


class DialogueAction(str):
    """Dialogue action types."""

    ASK = "ask"  # Ask clarifying question
    REFLECT = "reflect"  # Summarize understanding, invite correction
    CONFIRM = "confirm"  # Read back complete spec, ask for confirmation
    ESCALATE = "escalate"  # Validation error needs user input


class DialoguePolicyEngine:
    """
    Guides users toward architectural clarity with Reflect + Guide pattern.

    Rules:
    1. Ask AT MOST ONE question per turn
    2. Never ask yes/no questions — offer 2-3 concrete options with trade-offs
    3. Confirm spec before execution
    4. Name conflicts explicitly and ask user to choose
    5. Lead with understanding — correct before asking
    """

    SYSTEM_PROMPT = """You are the Dialogue Policy Engine for an AI DevOps Agent Platform.
Your role is to guide users toward architectural clarity — NOT interrogate them.

RULES:
1. Ask AT MOST ONE question per turn
2. Never ask yes/no questions — always offer 2-3 concrete options with trade-offs
3. If the user is ready to execute, confirm the spec in natural language before proceeding
4. If there are conflicts, name them explicitly and ask user to choose
5. Lead with what you understood — correct before asking

The Reflect + Guide pattern:
"Here's what I understood: [spec summary].
 There's one key decision that shapes everything: [architectural fork].
 Path A: [option] — best for [use case], costs ~[$].
 Path B: [option] — best for [use case], costs ~[$].
 Which direction fits your goal?"

Keep responses under 120 words. No bullet lists. Natural conversational tone.
"""

    def __init__(self):
        """Initialize with anthropic client and instructor patching."""
        self.anthropic_client = Anthropic(api_key=config.anthropic_api_key)
        self.instructor = instructor.from_anthropic(self.anthropic_client)

    async def generate_response(
        self,
        intent_spec: IntentSpec,
        open_questions: list[OpenQuestion],
        conflicts: list[Conflict],
        action: DialogueAction,
    ) -> DialogueResponse:
        """
        Generate user-facing dialogue response.

        Args:
            intent_spec: Current IntentSpec
            open_questions: Prioritized open questions
            conflicts: Detected conflicts
            action: Dialogue action (ask | reflect | confirm | escalate)

        Returns:
            DialogueResponse with reasoning and response text
        """
        # Build context
        user_prompt = self._build_user_prompt(
            intent_spec,
            open_questions,
            conflicts,
            action,
        )

        # Generate response with LLM
        import time

        start = time.perf_counter()

        try:
            response = self.instructor.messages.create(
                model=config.primary_model,
                max_tokens=config.max_tokens,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                response_model=DialogueResponse,
            )

            latency = time.perf_counter() - start

            record_llm_call(
                node="dialogue_policy",
                model=config.primary_model,
                latency=latency,
                prompt_tokens=len(user_prompt) // 4,
                completion_tokens=len(str(response)) // 4,
                status="success",
            )

            return response

        except Exception as e:
            record_llm_call(
                node="dialogue_policy",
                model=config.primary_model,
                latency=time.perf_counter() - start,
                prompt_tokens=len(user_prompt) // 4,
                completion_tokens=0,
                status="error",
            )
            raise

    def _build_user_prompt(
        self,
        intent_spec: IntentSpec,
        open_questions: list[OpenQuestion],
        conflicts: list[Conflict],
        action: DialogueAction,
    ) -> str:
        """Build prompt with full context."""
        # Serialize intent spec
        spec_json = intent_spec.model_dump_json(indent=2)

        # Format open questions
        questions_text = "\n".join(
            [
                f"- {q.question_text} (blocks: {q.blocks_action}, priority: {q.priority})"
                for q in open_questions[:3]  # Top 3 questions
            ]
        )
        if not questions_text:
            questions_text = "None"

        # Format conflicts
        conflicts_text = "\n".join(
            [
                f"- {c.conflict_type}: {c.description}"
                for c in conflicts[:2]  # Top 2 conflicts
            ]
        )
        if not conflicts_text:
            conflicts_text = "None"

        return f"""CONTEXT:
[INTENT_SPEC]: {spec_json}

[OPEN_QUESTIONS]: {questions_text}

[CONFLICTS]: {conflicts_text}

[DIALOGUE_ACTION]: {action}

REASONING STEPS:

Step 1 — Spec Comprehension:
In 2 sentences, what does the current spec say the user wants to build?

Step 2 — What's blocking execution:
Which open question (if any) has the highest execution impact?
Does any conflict need to be resolved before proceeding?

Step 3 — Response strategy:
Given DIALOGUE_ACTION={action}, what is the response type?
- ask: Focus on the single highest-priority blocking question. Frame as architectural choice.
- reflect: Summarize understanding, invite correction. Surface assumptions being made.
- confirm: Read back complete spec in plain language. Ask "Does this match what you want?"
- escalate: A validation error requires user input (e.g., IAM permission they must check).

Step 4 — Draft response:
Write the response following the Reflect + Guide pattern.
Keep it under 120 words. No bullet lists. Natural conversational tone.

Now provide your complete reasoning and response."""

    async def confirm_specification(self, intent_spec: IntentSpec) -> str:
        """
        Generate a natural language confirmation of the complete spec.

        Args:
            intent_spec: Complete IntentSpec ready for execution

        Returns:
            Natural language summary for user confirmation
        """
        response = await self.generate_response(
            intent_spec=intent_spec,
            open_questions=[],
            conflicts=[],
            action=DialogueAction.CONFIRM,
        )
        return response.response_text

    async def ask_clarifying_question(
        self,
        intent_spec: IntentSpec,
        question: OpenQuestion,
    ) -> str:
        """
        Ask a specific clarifying question using Reflect + Guide.

        Args:
            intent_spec: Current IntentSpec
            question: The question to ask

        Returns:
            Natural language question with options and trade-offs
        """
        response = await self.generate_response(
            intent_spec=intent_spec,
            open_questions=[question],
            conflicts=[],
            action=DialogueAction.ASK,
        )
        return response.response_text

    async def present_conflict_resolution(
        self,
        intent_spec: IntentSpec,
        conflict: Conflict,
    ) -> str:
        """
        Present a conflict and ask user to resolve it.

        Args:
            intent_spec: Current IntentSpec
            conflict: Conflict to resolve

        Returns:
            Natural language conflict description with options
        """
        response = await self.generate_response(
            intent_spec=intent_spec,
            open_questions=[],
            conflicts=[conflict],
            action=DialogueAction.ASK,
        )
        return response.response_text


def create_dialogue_policy() -> DialoguePolicyEngine:
    """Factory function to create dialogue policy engine."""
    return DialoguePolicyEngine()
