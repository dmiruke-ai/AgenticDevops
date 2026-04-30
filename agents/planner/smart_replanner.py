"""
Smart Replanner for targeted Terraform module regeneration (S3-06 / PROMPT_CHAIN_04).

Implements Chain-of-Thought replanning after validation failures.
Only regenerates failing modules, preserves passing modules.
"""

import json
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

from agents.validator.error_intelligence import ErrorClassificationResult

# config, instructor and anthropic are imported lazily in SmartReplanner.__init__
# to allow using models without those dependencies


class ReplanningInput(BaseModel):
    """
    Input for smart replanning operation.

    Contains error classification, module status, and previous artifacts.
    """
    intent_spec: Dict[str, Any] = Field(
        ...,
        description="Current IntentSpec (canonical representation of user intent)"
    )
    passing_modules: List[str] = Field(
        ...,
        description="List of modules that passed validation (preserve these)"
    )
    failing_modules: List[str] = Field(
        ...,
        description="List of modules that failed validation (regenerate these)"
    )
    error_classification: ErrorClassificationResult = Field(
        ...,
        description="Structured error classification from TerraformErrorClassifier"
    )
    previous_artifacts: Dict[str, str] = Field(
        default_factory=dict,
        description="Previous Terraform artifacts that failed (filename -> content)"
    )
    retry_count: int = Field(
        ...,
        ge=1,
        le=3,
        description="Current retry attempt (1-3)"
    )


class ReplanningOutput(BaseModel):
    """
    Output from smart replanning operation.

    Contains fixed modules and reasoning for the changes.
    """
    fixed_modules: Dict[str, str] = Field(
        ...,
        description="Corrected Terraform for failing modules (module_name -> HCL)"
    )
    unchanged_modules: List[str] = Field(
        ...,
        description="List of modules preserved (not regenerated)"
    )
    fix_summary: str = Field(
        ...,
        min_length=20,
        description="Plain language description of what changed and why"
    )
    reasoning_steps: List[str] = Field(
        default_factory=list,
        description="Chain-of-thought reasoning steps from LLM"
    )


class SmartReplanner:
    """
    Smart Replanner for targeted Terraform module regeneration.

    Uses PROMPT_CHAIN_04 (Chain-of-Thought) to fix only failing modules
    while preserving passing modules.

    Ensures fixed modules do NOT reproduce the original error.
    """

    def __init__(self):
        """Initialize SmartReplanner with Anthropic client."""
        self.model = "claude-sonnet-4-20250514"  # Default model
        self.client = None
        # Lazy import to allow tests to run without dependencies
        try:
            from config import AgentConfig
            config = AgentConfig()
            self.model = config.primary_model

            import instructor
            from anthropic import Anthropic
            self.client = instructor.from_anthropic(Anthropic())
        except ImportError:
            pass

    def replan(self, input_data: ReplanningInput) -> ReplanningOutput:
        """
        Perform smart replanning to fix failing modules.

        Args:
            input_data: Replanning input with error classification and modules

        Returns:
            Replanning output with fixed modules and reasoning

        Raises:
            ValueError: If no failing modules specified
            RuntimeError: If instructor client not available
        """
        if not input_data.failing_modules:
            raise ValueError("No failing modules specified for replanning")

        if self.client is None:
            raise RuntimeError("SmartReplanner requires instructor and anthropic packages")

        prompt = self._build_prompt(input_data)

        # Call LLM with structured output validation
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0.2,  # Lower temperature for more deterministic fixes
            response_model=ReplanningOutput,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        return response

    def _build_prompt(self, input_data: ReplanningInput) -> str:
        """
        Build PROMPT_CHAIN_04 (Chain-of-Thought replanning prompt).

        Args:
            input_data: Replanning input data

        Returns:
            Fully constructed prompt with context and instructions
        """
        error = input_data.error_classification.error
        classification = input_data.error_classification

        # Build error classification summary
        error_summary = {
            "error_type": error.error_type.name,
            "error_message": error.error_message,
            "affected_resource": error.affected_resource,
            "fix_hint": error.fix_hint,
            "planner_instruction": error.planner_instruction,
            "suggested_actions": classification.suggested_actions,
            "requires_user_input": classification.requires_user_input,
        }

        prompt = f"""You are the Infrastructure Replanning Engine for an AI DevOps Agent Platform.

A previous Terraform generation failed validation. Your job is to fix ONLY the failing modules.
Do NOT regenerate modules that passed validation — preserve them exactly.

CRITICAL RULES:
1. ONLY modify modules in the FAILING_MODULES list
2. Do NOT touch any modules in the PASSING_MODULES list
3. Each fixed module MUST include a comment: "# FIXED: [error_type] — [fix_summary]"
4. The fix must NOT reproduce the original error
5. Use the fix_hint and planner_instruction from ERROR_CLASSIFICATION

CONTEXT:

[INTENT_SPEC]:
{json.dumps(input_data.intent_spec, indent=2)}

[PASSING_MODULES] (preserve these exactly):
{', '.join(input_data.passing_modules) if input_data.passing_modules else 'None - all modules failed'}

[FAILING_MODULES] (regenerate these):
{', '.join(input_data.failing_modules)}

[ERROR_CLASSIFICATION]:
{json.dumps(error_summary, indent=2)}

[PREVIOUS_ARTIFACTS] (that failed validation):
{json.dumps(input_data.previous_artifacts, indent=2) if input_data.previous_artifacts else 'No previous artifacts provided'}

[RETRY_COUNT]: {input_data.retry_count} of 3

CHAIN-OF-THOUGHT REASONING:

Step 1 — Error Root Cause Summary:
For each error in ERROR_CLASSIFICATION, state in one sentence what the Terraform did wrong.

Step 2 — Targeted Fix Plan:
For each failing module, describe the specific change needed.
Reference the fix_hint and planner_instruction from error classification.
DO NOT change anything in passing modules.

Step 3 — Dependency Check:
Will fixing the failing module require changes to any passing module's outputs?
If yes: list which passing modules must also be touched, and why.
If no: explicitly state "No changes to passing modules required."

Step 4 — Risk Assessment:
What is the risk of this fix introducing a new error?
Rate as: Low | Medium | High
If medium or high: describe the secondary risk.

Step 5 — Generate Fixed Artifacts:
Produce the corrected Terraform for ONLY the failing modules.
Each file must include a comment at the top: "# FIXED: [error_type] — [fix_summary]"

OUTPUT REQUIREMENTS:
- fixed_modules: Dict mapping module name to corrected Terraform HCL
- unchanged_modules: List of module names preserved (from PASSING_MODULES)
- fix_summary: Plain language description (minimum 20 characters)
- reasoning_steps: Your Step 1-5 reasoning as a list of strings

Remember: The goal is targeted repair, not full regeneration.
"""

        return prompt


def create_smart_replanner() -> SmartReplanner:
    """Factory function for creating SmartReplanner."""
    return SmartReplanner()
