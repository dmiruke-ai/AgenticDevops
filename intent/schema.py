"""
IntentSpec Schema - Core data models for intent representation.

This module defines the complete IntentSpec schema following the intentctl library pattern.
All intent items have confidence bands that govern execution permissions.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ConfidenceBand(str, Enum):
    """
    Confidence levels for intent items.
    Lower confidence items cannot trigger irreversible actions.
    """
    SPECULATIVE = "speculative"  # LLM inferred with no user signal
    INFERRED = "inferred"        # Reasonable inference from context
    CONFIRMED = "confirmed"      # User explicitly affirmed
    STATED = "stated"            # User said it verbatim


class IntentCategory(str, Enum):
    """Three-layer intent taxonomy."""
    TASK = "task"              # What to build (compute, networking, CI/CD)
    META = "meta"              # Why and how (cost optimization, security)
    CONSTRAINT = "constraint"  # Hard requirements (region, compliance, budget)


class SpecItem(BaseModel):
    """
    A single item in the IntentSpec.
    Represents one piece of extracted user intent with confidence tracking.
    """
    id: UUID = Field(default_factory=uuid4)
    key: str = Field(..., description="Intent parameter name (e.g., 'compute_platform', 'region')")
    value: Any = Field(..., description="Intent parameter value")
    confidence: ConfidenceBand = Field(..., description="Confidence level for this item")
    category: IntentCategory = Field(..., description="Intent taxonomy category")
    evidence: str = Field(..., description="Quote or context that supports this extraction")
    turn: int = Field(..., description="Conversation turn when this was extracted/updated")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    depends_on: list[UUID] = Field(default_factory=list, description="IDs of items this depends on")

    model_config = ConfigDict(
        json_encoders={
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }
    )


class OpenQuestion(BaseModel):
    """
    A question the system needs to ask to fill gaps in the IntentSpec.
    """
    id: UUID = Field(default_factory=uuid4)
    question_text: str = Field(..., description="The question to ask the user")
    blocks_action: str = Field(..., description="Which action this question blocks")
    priority: str = Field(..., description="Priority level: high|medium|low")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Conflict(BaseModel):
    """
    Detected conflict between two intent items.
    """
    id: UUID = Field(default_factory=uuid4)
    item_a: UUID = Field(..., description="First conflicting item ID")
    item_b: UUID = Field(..., description="Second conflicting item ID")
    conflict_type: str = Field(..., description="Type of conflict")
    description: str = Field(..., description="Plain language conflict description")
    resolution_options: list[str] = Field(default_factory=list)
    auto_resolvable: bool = Field(default=False)
    auto_resolution: Optional[str] = None


class IntentSpec(BaseModel):
    """
    Canonical intent specification - the single source of truth for user intent.

    This is the load-bearing data structure. All agents read from and write to this.
    Confidence transitions are enforced via IntentTransitionEngine.
    """
    session_id: str = Field(..., description="Session identifier")
    version: int = Field(default=1, description="Increments on every mutation")
    items: dict[UUID, SpecItem] = Field(default_factory=dict, description="Intent items by ID")
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    fixes: list[dict[str, Any]] = Field(default_factory=list, description="Validation error fixes")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        json_encoders={
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }
    )

    def get_item_by_key(self, key: str) -> Optional[SpecItem]:
        """Find first item with matching key."""
        for item in self.items.values():
            if item.key == key:
                return item
        return None

    def get_items_by_category(self, category: IntentCategory) -> list[SpecItem]:
        """Get all items in a specific category."""
        return [item for item in self.items.values() if item.category == category]

    def get_items_by_confidence(self, confidence: ConfidenceBand) -> list[SpecItem]:
        """Get all items at a specific confidence level."""
        return [item for item in self.items.values() if item.confidence == confidence]


class ExtractionResult(BaseModel):
    """
    Output from the Semantic Extractor (PROMPT_CHAIN_01).
    Contains new and updated items to merge into IntentSpec.
    """
    turn: int = Field(..., description="Conversation turn number")
    new_items: list[SpecItem] = Field(default_factory=list)
    updated_items: list[SpecItem] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    conflicts_detected: list[Conflict] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list, description="Assumptions made by LLM")
    reasoning_summary: str = Field(..., description="2-3 sentence summary of extraction")


class TransitionEvent(BaseModel):
    """
    Records a confidence band transition for audit trail.
    """
    item_id: UUID
    from_band: ConfidenceBand
    to_band: ConfidenceBand
    trigger: str  # One of the VALID_TRANSITIONS values
    turn: int
    evidence: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GateDecision(BaseModel):
    """
    Result from checking if an action can proceed based on confidence levels.
    """
    action: str
    passed: bool
    blocking_items: list[UUID] = Field(default_factory=list)
    reason: Optional[str] = None


# Transition rules - the complete state machine
VALID_TRANSITIONS = {
    ("speculative", "inferred"): "context_implies",
    ("speculative", "confirmed"): "explicit_affirmation",
    ("inferred", "confirmed"): "explicit_affirmation",
    ("inferred", "speculative"): "contradicting_signal",
    ("confirmed", "inferred"): "user_revision",
    ("stated", "confirmed"): "always_valid",
}

# Actions that REQUIRE confirmed or stated confidence
IRREVERSIBLE_ACTIONS = {
    "generate_terraform",
    "create_pipeline",
    "terraform_apply",
    "delete_resource",
    "modify_iam",
}
