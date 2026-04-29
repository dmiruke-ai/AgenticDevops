"""
Unit tests for IntentTransitionEngine (SPEC-02).

Tests all 6 valid confidence transition paths and gate enforcement.
"""

import pytest
from uuid import uuid4

from intent.schema import (
    ConfidenceBand,
    IntentCategory,
    IntentSpec,
    SpecItem,
    VALID_TRANSITIONS,
    IRREVERSIBLE_ACTIONS,
)
from intent.confidence import (
    IntentTransitionEngine,
    GateDecision,
)


class TestIntentTransitionEngine:
    """Test confidence state transitions."""

    def setup_method(self):
        """Create engine instance for each test."""
        self.engine = IntentTransitionEngine()

    def test_transition_speculative_to_inferred(self):
        """Test transition: speculative → inferred (context_implies)."""
        item = SpecItem(
            key="region",
            value="us-east-1",
            confidence=ConfidenceBand.SPECULATIVE,
            category=IntentCategory.CONSTRAINT,
            evidence="Assumed default region",
            turn=1,
        )

        updated_item, event = self.engine.attempt_transition(
            item,
            to_band=ConfidenceBand.INFERRED,
            trigger="context_implies",
            turn=2,
            evidence="User mentioned Virginia datacenter",
        )

        assert updated_item.confidence == ConfidenceBand.INFERRED
        assert event is not None
        assert event.from_band == ConfidenceBand.SPECULATIVE
        assert event.to_band == ConfidenceBand.INFERRED
        assert event.trigger == "context_implies"

    def test_transition_speculative_to_confirmed(self):
        """Test transition: speculative → confirmed (explicit_affirmation)."""
        item = SpecItem(
            key="compute_platform",
            value="EKS",
            confidence=ConfidenceBand.SPECULATIVE,
            category=IntentCategory.TASK,
            evidence="Assumed Kubernetes means EKS",
            turn=1,
        )

        updated_item, event = self.engine.attempt_transition(
            item,
            to_band=ConfidenceBand.CONFIRMED,
            trigger="explicit_affirmation",
            turn=2,
            evidence='User said "yes, EKS is correct"',
        )

        assert updated_item.confidence == ConfidenceBand.CONFIRMED
        assert event is not None
        assert event.trigger == "explicit_affirmation"

    def test_transition_inferred_to_confirmed(self):
        """Test transition: inferred → confirmed (explicit_affirmation)."""
        item = SpecItem(
            key="iac_tool",
            value="Terraform",
            confidence=ConfidenceBand.INFERRED,
            category=IntentCategory.TASK,
            evidence="Inferred from IaC context",
            turn=1,
        )

        updated_item, event = self.engine.attempt_transition(
            item,
            to_band=ConfidenceBand.CONFIRMED,
            trigger="explicit_affirmation",
            turn=2,
            evidence="User confirmed Terraform",
        )

        assert updated_item.confidence == ConfidenceBand.CONFIRMED
        assert event is not None

    def test_transition_inferred_to_speculative(self):
        """Test transition: inferred → speculative (contradicting_signal)."""
        item = SpecItem(
            key="instance_type",
            value="t3.large",
            confidence=ConfidenceBand.INFERRED,
            category=IntentCategory.TASK,
            evidence="Inferred from workload size",
            turn=1,
        )

        updated_item, event = self.engine.attempt_transition(
            item,
            to_band=ConfidenceBand.SPECULATIVE,
            trigger="contradicting_signal",
            turn=2,
            evidence="User mentioned small workload",
        )

        assert updated_item.confidence == ConfidenceBand.SPECULATIVE
        assert event is not None
        assert event.trigger == "contradicting_signal"

    def test_transition_confirmed_to_inferred(self):
        """Test transition: confirmed → inferred (user_revision)."""
        item = SpecItem(
            key="region",
            value="us-west-2",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.CONSTRAINT,
            evidence="User confirmed region",
            turn=1,
        )

        updated_item, event = self.engine.attempt_transition(
            item,
            to_band=ConfidenceBand.INFERRED,
            trigger="user_revision",
            turn=2,
            evidence="User walked back decision",
        )

        assert updated_item.confidence == ConfidenceBand.INFERRED
        assert event is not None
        assert event.trigger == "user_revision"

    def test_transition_stated_to_confirmed(self):
        """Test transition: stated → confirmed (always_valid)."""
        item = SpecItem(
            key="cloud_provider",
            value="AWS",
            confidence=ConfidenceBand.STATED,
            category=IntentCategory.CONSTRAINT,
            evidence='User said "AWS"',
            turn=1,
        )

        updated_item, event = self.engine.attempt_transition(
            item,
            to_band=ConfidenceBand.CONFIRMED,
            trigger="always_valid",
            turn=2,
            evidence="Stated items are always confirmed",
        )

        assert updated_item.confidence == ConfidenceBand.CONFIRMED
        assert event is not None

    def test_invalid_transition_returns_none(self):
        """Test that invalid transitions return None event."""
        item = SpecItem(
            key="test",
            value="value",
            confidence=ConfidenceBand.SPECULATIVE,
            category=IntentCategory.TASK,
            evidence="test",
            turn=1,
        )

        # Try invalid transition: speculative → stated (not in VALID_TRANSITIONS)
        updated_item, event = self.engine.attempt_transition(
            item,
            to_band=ConfidenceBand.STATED,
            trigger="invalid",
            turn=2,
            evidence="Invalid transition",
        )

        assert updated_item.confidence == ConfidenceBand.SPECULATIVE  # unchanged
        assert event is None

    def test_all_valid_transitions_covered(self):
        """Verify all transitions in VALID_TRANSITIONS are tested."""
        # This ensures we don't miss any transitions
        assert len(VALID_TRANSITIONS) == 6
        tested_transitions = {
            ("speculative", "inferred"),
            ("speculative", "confirmed"),
            ("inferred", "confirmed"),
            ("inferred", "speculative"),
            ("confirmed", "inferred"),
            ("stated", "confirmed"),
        }
        assert set(VALID_TRANSITIONS.keys()) == tested_transitions


class TestGateEnforcement:
    """Test check_gate blocks IRREVERSIBLE_ACTIONS on low confidence."""

    def setup_method(self):
        """Create engine instance for each test."""
        self.engine = IntentTransitionEngine()

    def test_gate_passes_with_confirmed_items(self):
        """Gate allows action when all items are confirmed."""
        spec = IntentSpec(session_id="test")

        item = SpecItem(
            key="compute_platform",
            value="EKS",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="User confirmed",
            turn=1,
        )
        spec.items[item.id] = item

        decision = self.engine.check_gate(
            action="generate_terraform",
            intent_spec=spec,
        )

        assert decision.passed is True
        assert len(decision.blocking_items) == 0

    def test_gate_blocks_on_speculative_items(self):
        """Gate blocks irreversible action when items are speculative."""
        spec = IntentSpec(session_id="test")

        item = SpecItem(
            key="region",
            value="us-east-1",
            confidence=ConfidenceBand.SPECULATIVE,
            category=IntentCategory.CONSTRAINT,
            evidence="Assumed",
            turn=1,
        )
        spec.items[item.id] = item

        decision = self.engine.check_gate(
            action="terraform_apply",
            intent_spec=spec,
        )

        assert decision.passed is False
        assert item.id in decision.blocking_items
        assert "speculative" in decision.reason.lower()

    def test_gate_blocks_on_inferred_items(self):
        """Gate blocks irreversible action when items are inferred."""
        spec = IntentSpec(session_id="test")

        item = SpecItem(
            key="iac_tool",
            value="Terraform",
            confidence=ConfidenceBand.INFERRED,
            category=IntentCategory.TASK,
            evidence="Inferred from context",
            turn=1,
        )
        spec.items[item.id] = item

        decision = self.engine.check_gate(
            action="modify_iam",
            intent_spec=spec,
        )

        assert decision.passed is False
        assert item.id in decision.blocking_items

    def test_gate_passes_with_stated_items(self):
        """Gate allows action when items are stated."""
        spec = IntentSpec(session_id="test")

        item = SpecItem(
            key="cloud_provider",
            value="AWS",
            confidence=ConfidenceBand.STATED,
            category=IntentCategory.CONSTRAINT,
            evidence='User said "AWS"',
            turn=1,
        )
        spec.items[item.id] = item

        decision = self.engine.check_gate(
            action="create_pipeline",
            intent_spec=spec,
        )

        assert decision.passed is True

    def test_gate_blocks_all_irreversible_actions(self):
        """Verify all IRREVERSIBLE_ACTIONS are gated."""
        spec = IntentSpec(session_id="test")

        speculative_item = SpecItem(
            key="test",
            value="value",
            confidence=ConfidenceBand.SPECULATIVE,
            category=IntentCategory.TASK,
            evidence="test",
            turn=1,
        )
        spec.items[speculative_item.id] = speculative_item

        for action in IRREVERSIBLE_ACTIONS:
            decision = self.engine.check_gate(action=action, intent_spec=spec)
            assert decision.passed is False, f"Action {action} should be blocked"

    def test_gate_allows_non_irreversible_actions(self):
        """Gate allows non-irreversible actions even with low confidence."""
        spec = IntentSpec(session_id="test")

        speculative_item = SpecItem(
            key="test",
            value="value",
            confidence=ConfidenceBand.SPECULATIVE,
            category=IntentCategory.TASK,
            evidence="test",
            turn=1,
        )
        spec.items[speculative_item.id] = speculative_item

        # These actions are not in IRREVERSIBLE_ACTIONS
        safe_actions = ["read_spec", "ask_question", "show_recommendation"]

        for action in safe_actions:
            decision = self.engine.check_gate(action=action, intent_spec=spec)
            assert decision.passed is True


class TestHandleRevision:
    """Test handle_revision cascading demotion."""

    def setup_method(self):
        """Create engine instance for each test."""
        self.engine = IntentTransitionEngine()

    def test_revision_demotes_item(self):
        """Test that revising an item demotes its confidence."""
        spec = IntentSpec(session_id="test")

        item = SpecItem(
            key="compute_platform",
            value="EKS",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="User confirmed",
            turn=1,
        )
        spec.items[item.id] = item

        updated_spec, demoted_ids = self.engine.handle_revision(
            spec=spec,
            revised_item_id=item.id,
            new_value="ECS",
            turn=2,
        )

        revised_item = updated_spec.items[item.id]
        assert revised_item.value == "ECS"
        assert revised_item.confidence == ConfidenceBand.CONFIRMED  # Re-confirmed with new value

    def test_revision_cascades_to_dependents(self):
        """Test that revising an item demotes dependent items."""
        spec = IntentSpec(session_id="test")

        # Parent item
        parent = SpecItem(
            key="compute_platform",
            value="EKS",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="User confirmed",
            turn=1,
        )
        spec.items[parent.id] = parent

        # Dependent item
        dependent = SpecItem(
            key="cluster_version",
            value="1.28",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="Confirmed for EKS",
            turn=1,
            depends_on=[parent.id],
        )
        spec.items[dependent.id] = dependent

        updated_spec, demoted_ids = self.engine.handle_revision(
            spec=spec,
            revised_item_id=parent.id,
            new_value="ECS",
            turn=2,
        )

        # Dependent should be demoted
        assert dependent.id in demoted_ids
        dependent_after = updated_spec.items[dependent.id]
        assert dependent_after.confidence == ConfidenceBand.INFERRED

    def test_revision_cascades_two_levels(self):
        """Test cascading demotion to 2 levels of dependents."""
        spec = IntentSpec(session_id="test")

        # Level 0: Parent
        parent = SpecItem(
            key="cloud_provider",
            value="AWS",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.CONSTRAINT,
            evidence="User confirmed",
            turn=1,
        )
        spec.items[parent.id] = parent

        # Level 1: First dependent
        child = SpecItem(
            key="compute_platform",
            value="EKS",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="Confirmed for AWS",
            turn=1,
            depends_on=[parent.id],
        )
        spec.items[child.id] = child

        # Level 2: Second dependent
        grandchild = SpecItem(
            key="node_type",
            value="managed",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="Confirmed for EKS",
            turn=1,
            depends_on=[child.id],
        )
        spec.items[grandchild.id] = grandchild

        updated_spec, demoted_ids = self.engine.handle_revision(
            spec=spec,
            revised_item_id=parent.id,
            new_value="GCP",
            turn=2,
        )

        # Both levels should be demoted
        assert child.id in demoted_ids
        assert grandchild.id in demoted_ids

        child_after = updated_spec.items[child.id]
        grandchild_after = updated_spec.items[grandchild.id]

        assert child_after.confidence == ConfidenceBand.INFERRED
        assert grandchild_after.confidence == ConfidenceBand.INFERRED
