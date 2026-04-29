"""
Intent Confidence Transition Engine (SPEC-02).

Manages confidence state transitions and gate enforcement.
Ensures IntentSpec is a real constraint on execution, not decoration.
"""

from copy import deepcopy
from typing import Optional
from uuid import UUID

from intent.schema import (
    ConfidenceBand,
    GateDecision,
    IntentSpec,
    IRREVERSIBLE_ACTIONS,
    SpecItem,
    TransitionEvent,
    VALID_TRANSITIONS,
)


class IntentTransitionEngine:
    """
    Manages confidence band transitions and execution gates.

    Key responsibilities:
    1. Validate transitions against VALID_TRANSITIONS
    2. Block IRREVERSIBLE_ACTIONS on low-confidence items
    3. Handle revisions with cascading demotion
    """

    def attempt_transition(
        self,
        spec_item: SpecItem,
        to_band: ConfidenceBand,
        trigger: str,
        turn: int,
        evidence: str,
    ) -> tuple[SpecItem, Optional[TransitionEvent]]:
        """
        Attempt a confidence band transition.

        Args:
            spec_item: The item to transition
            to_band: Target confidence band
            trigger: Reason for transition (must match VALID_TRANSITIONS value)
            turn: Current conversation turn
            evidence: Evidence supporting the transition

        Returns:
            Tuple of (updated_item, event). If transition is invalid, returns
            (unchanged_item, None). Never raises - caller decides what to do with None.
        """
        from_band = spec_item.confidence
        transition_key = (from_band.value, to_band.value)

        # Check if transition is valid
        if transition_key not in VALID_TRANSITIONS:
            # Invalid transition - return unchanged
            return spec_item, None

        # Verify trigger matches expected trigger for this transition
        expected_trigger = VALID_TRANSITIONS[transition_key]
        if trigger != expected_trigger:
            # Trigger mismatch - return unchanged
            return spec_item, None

        # Valid transition - create updated item
        updated_item = deepcopy(spec_item)
        updated_item.confidence = to_band
        updated_item.turn = turn
        updated_item.evidence = evidence

        # Create transition event for audit trail
        event = TransitionEvent(
            item_id=spec_item.id,
            from_band=from_band,
            to_band=to_band,
            trigger=trigger,
            turn=turn,
            evidence=evidence,
        )

        return updated_item, event

    def check_gate(
        self,
        action: str,
        intent_spec: IntentSpec,
    ) -> GateDecision:
        """
        Check if an action can proceed based on confidence levels.

        For IRREVERSIBLE_ACTIONS, all items must be at least CONFIRMED.
        For other actions, any confidence level is allowed.

        Args:
            action: The action to check (e.g., "terraform_apply")
            intent_spec: Current IntentSpec

        Returns:
            GateDecision with pass status and blocking items if any
        """
        # Non-irreversible actions always pass
        if action not in IRREVERSIBLE_ACTIONS:
            return GateDecision(
                action=action,
                passed=True,
            )

        # Check all items for confidence level
        blocking_items = []
        for item in intent_spec.items.values():
            if item.confidence in (ConfidenceBand.SPECULATIVE, ConfidenceBand.INFERRED):
                blocking_items.append(item.id)

        if blocking_items:
            # Build reason message
            confidence_levels = {
                intent_spec.items[item_id].confidence.value
                for item_id in blocking_items
            }
            reason = (
                f"Action '{action}' blocked: {len(blocking_items)} items have "
                f"insufficient confidence ({', '.join(confidence_levels)}). "
                f"Items must be 'confirmed' or 'stated' for irreversible actions."
            )

            return GateDecision(
                action=action,
                passed=False,
                blocking_items=blocking_items,
                reason=reason,
            )

        # All items have sufficient confidence
        return GateDecision(
            action=action,
            passed=True,
        )

    def handle_revision(
        self,
        spec: IntentSpec,
        revised_item_id: UUID,
        new_value: str,
        turn: int,
    ) -> tuple[IntentSpec, list[UUID]]:
        """
        Handle user revision of a previously confirmed intent.

        Process:
        1. Update the revised item with new value (re-confirmed)
        2. Find all items that depend on the revised item
        3. Demote dependent items to INFERRED with reason "dependency_revised"
        4. Recursively demote items that depend on demoted items

        Args:
            spec: Current IntentSpec
            revised_item_id: ID of the item being revised
            new_value: New value for the item
            turn: Current conversation turn

        Returns:
            Tuple of (updated_spec, list_of_demoted_ids)
        """
        updated_spec = deepcopy(spec)
        demoted_ids = []

        # Update the revised item
        if revised_item_id not in updated_spec.items:
            return updated_spec, demoted_ids

        revised_item = updated_spec.items[revised_item_id]
        revised_item.value = new_value
        revised_item.turn = turn
        revised_item.evidence = f"User revised value to '{new_value}' at turn {turn}"
        # Keep it confirmed with the new value

        # Find and demote all dependents (recursively)
        def demote_dependents(item_id: UUID, level: int = 1):
            """Recursively demote items that depend on item_id."""
            for item in updated_spec.items.values():
                if item_id in item.depends_on and item.id not in demoted_ids:
                    # Demote this item
                    item.confidence = ConfidenceBand.INFERRED
                    item.turn = turn
                    item.evidence = f"Demoted due to dependency revision (level {level})"
                    demoted_ids.append(item.id)

                    # Recursively demote items that depend on this one
                    demote_dependents(item.id, level + 1)

        # Start cascading demotion
        demote_dependents(revised_item_id)

        # Increment spec version
        updated_spec.version += 1

        return updated_spec, demoted_ids


def find_dependent_items(spec: IntentSpec, parent_id: UUID) -> list[SpecItem]:
    """
    Find all items that directly depend on a parent item.

    Args:
        spec: IntentSpec to search
        parent_id: ID of the parent item

    Returns:
        List of items that have parent_id in their depends_on field
    """
    dependents = []
    for item in spec.items.values():
        if parent_id in item.depends_on:
            dependents.append(item)
    return dependents
