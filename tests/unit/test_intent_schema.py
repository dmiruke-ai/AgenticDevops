"""
Unit tests for IntentSpec schema models.

Tests cover:
- Pydantic model validation
- JSON serialization/deserialization
- Confidence band enum values
- IntentSpec helper methods
- VALID_TRANSITIONS completeness
"""

import json
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from intent.schema import (
    ConfidenceBand,
    Conflict,
    ExtractionResult,
    GateDecision,
    IntentCategory,
    IntentSpec,
    IRREVERSIBLE_ACTIONS,
    OpenQuestion,
    SpecItem,
    TransitionEvent,
    VALID_TRANSITIONS,
)


class TestConfidenceBand:
    """Test ConfidenceBand enum."""

    def test_all_bands_defined(self):
        """Verify all 4 confidence bands are defined."""
        assert ConfidenceBand.SPECULATIVE == "speculative"
        assert ConfidenceBand.INFERRED == "inferred"
        assert ConfidenceBand.CONFIRMED == "confirmed"
        assert ConfidenceBand.STATED == "stated"

    def test_enum_values(self):
        """Verify enum can be instantiated from strings."""
        assert ConfidenceBand("speculative") == ConfidenceBand.SPECULATIVE
        assert ConfidenceBand("confirmed") == ConfidenceBand.CONFIRMED


class TestSpecItem:
    """Test SpecItem model."""

    def test_create_spec_item(self):
        """Test creating a valid SpecItem."""
        item = SpecItem(
            key="compute_platform",
            value="EKS",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence='User said: "I want EKS"',
            turn=1,
        )
        assert item.key == "compute_platform"
        assert item.value == "EKS"
        assert item.confidence == ConfidenceBand.CONFIRMED
        assert isinstance(item.id, UUID)
        assert isinstance(item.created_at, datetime)

    def test_spec_item_json_round_trip(self):
        """Test JSON serialization and deserialization."""
        item = SpecItem(
            key="region",
            value="us-east-1",
            confidence=ConfidenceBand.STATED,
            category=IntentCategory.CONSTRAINT,
            evidence='User specified: "us-east-1"',
            turn=2,
        )

        # Serialize
        json_str = item.model_dump_json()
        data = json.loads(json_str)

        # Deserialize
        restored = SpecItem.model_validate(data)

        assert restored.key == item.key
        assert restored.value == item.value
        assert restored.confidence == item.confidence
        assert restored.category == item.category

    def test_spec_item_with_dependencies(self):
        """Test SpecItem with depends_on field."""
        parent_id = uuid4()
        item = SpecItem(
            key="iam_role",
            value="arn:aws:iam::123456789012:role/EKSRole",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="Generated based on EKS cluster",
            turn=3,
            depends_on=[parent_id],
        )
        assert parent_id in item.depends_on


class TestIntentSpec:
    """Test IntentSpec model."""

    def test_create_empty_intent_spec(self):
        """Test creating an empty IntentSpec."""
        spec = IntentSpec(session_id="test-session-123")
        assert spec.session_id == "test-session-123"
        assert spec.version == 1
        assert len(spec.items) == 0
        assert len(spec.open_questions) == 0
        assert len(spec.conflicts) == 0

    def test_add_items_to_spec(self):
        """Test adding items to IntentSpec."""
        spec = IntentSpec(session_id="test-session-123")

        item1 = SpecItem(
            key="compute_platform",
            value="EKS",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence='User said: "EKS"',
            turn=1,
        )
        item2 = SpecItem(
            key="region",
            value="us-west-2",
            confidence=ConfidenceBand.INFERRED,
            category=IntentCategory.CONSTRAINT,
            evidence="Inferred from context",
            turn=1,
        )

        spec.items[item1.id] = item1
        spec.items[item2.id] = item2

        assert len(spec.items) == 2

    def test_get_item_by_key(self):
        """Test finding items by key."""
        spec = IntentSpec(session_id="test-session-123")

        item = SpecItem(
            key="compute_platform",
            value="Lambda",
            confidence=ConfidenceBand.STATED,
            category=IntentCategory.TASK,
            evidence="User explicitly requested Lambda",
            turn=1,
        )
        spec.items[item.id] = item

        found = spec.get_item_by_key("compute_platform")
        assert found is not None
        assert found.value == "Lambda"

        not_found = spec.get_item_by_key("nonexistent_key")
        assert not_found is None

    def test_get_items_by_category(self):
        """Test filtering items by category."""
        spec = IntentSpec(session_id="test-session-123")

        task_item = SpecItem(
            key="compute_platform",
            value="EKS",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="Task intent",
            turn=1,
        )
        meta_item = SpecItem(
            key="cost_priority",
            value="minimize",
            confidence=ConfidenceBand.INFERRED,
            category=IntentCategory.META,
            evidence="Meta intent",
            turn=1,
        )

        spec.items[task_item.id] = task_item
        spec.items[meta_item.id] = meta_item

        task_items = spec.get_items_by_category(IntentCategory.TASK)
        assert len(task_items) == 1
        assert task_items[0].key == "compute_platform"

    def test_get_items_by_confidence(self):
        """Test filtering items by confidence band."""
        spec = IntentSpec(session_id="test-session-123")

        confirmed_item = SpecItem(
            key="region",
            value="us-east-1",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.CONSTRAINT,
            evidence="Confirmed",
            turn=1,
        )
        speculative_item = SpecItem(
            key="instance_type",
            value="t3.medium",
            confidence=ConfidenceBand.SPECULATIVE,
            category=IntentCategory.TASK,
            evidence="Assumed",
            turn=1,
        )

        spec.items[confirmed_item.id] = confirmed_item
        spec.items[speculative_item.id] = speculative_item

        speculative_items = spec.get_items_by_confidence(ConfidenceBand.SPECULATIVE)
        assert len(speculative_items) == 1
        assert speculative_items[0].key == "instance_type"

    def test_intent_spec_json_round_trip(self):
        """Test complete IntentSpec JSON serialization."""
        spec = IntentSpec(session_id="test-session-123")

        item = SpecItem(
            key="cloud_provider",
            value="AWS",
            confidence=ConfidenceBand.STATED,
            category=IntentCategory.CONSTRAINT,
            evidence="User stated AWS",
            turn=1,
        )
        spec.items[item.id] = item

        # Serialize
        json_str = spec.model_dump_json()
        data = json.loads(json_str)

        # Deserialize
        restored = IntentSpec.model_validate(data)

        assert restored.session_id == spec.session_id
        assert len(restored.items) == 1


class TestOpenQuestion:
    """Test OpenQuestion model."""

    def test_create_open_question(self):
        """Test creating an OpenQuestion."""
        question = OpenQuestion(
            question_text="Which AWS region should we use?",
            blocks_action="generate_terraform",
            priority="high",
        )
        assert question.question_text == "Which AWS region should we use?"
        assert question.blocks_action == "generate_terraform"
        assert question.priority == "high"
        assert isinstance(question.id, UUID)


class TestConflict:
    """Test Conflict model."""

    def test_create_conflict(self):
        """Test creating a Conflict."""
        item_a_id = uuid4()
        item_b_id = uuid4()

        conflict = Conflict(
            item_a=item_a_id,
            item_b=item_b_id,
            conflict_type="platform_conflict",
            description="EKS and Lambda are mutually exclusive",
            resolution_options=["Keep EKS", "Keep Lambda"],
            auto_resolvable=False,
        )

        assert conflict.item_a == item_a_id
        assert conflict.item_b == item_b_id
        assert conflict.conflict_type == "platform_conflict"
        assert len(conflict.resolution_options) == 2


class TestExtractionResult:
    """Test ExtractionResult model."""

    def test_create_extraction_result(self):
        """Test creating an ExtractionResult."""
        item = SpecItem(
            key="platform",
            value="ECS",
            confidence=ConfidenceBand.INFERRED,
            category=IntentCategory.TASK,
            evidence="Inferred from container mention",
            turn=2,
        )

        result = ExtractionResult(
            turn=2,
            new_items=[item],
            reasoning_summary="User mentioned containers, inferred ECS",
        )

        assert result.turn == 2
        assert len(result.new_items) == 1
        assert result.new_items[0].key == "platform"


class TestTransitionEvent:
    """Test TransitionEvent model."""

    def test_create_transition_event(self):
        """Test creating a TransitionEvent."""
        item_id = uuid4()
        event = TransitionEvent(
            item_id=item_id,
            from_band=ConfidenceBand.SPECULATIVE,
            to_band=ConfidenceBand.CONFIRMED,
            trigger="explicit_affirmation",
            turn=3,
            evidence="User confirmed the assumption",
        )

        assert event.item_id == item_id
        assert event.from_band == ConfidenceBand.SPECULATIVE
        assert event.to_band == ConfidenceBand.CONFIRMED
        assert event.trigger == "explicit_affirmation"


class TestGateDecision:
    """Test GateDecision model."""

    def test_gate_decision_passed(self):
        """Test a passing gate decision."""
        decision = GateDecision(
            action="generate_terraform",
            passed=True,
        )
        assert decision.passed is True
        assert len(decision.blocking_items) == 0

    def test_gate_decision_blocked(self):
        """Test a blocked gate decision."""
        blocking_id = uuid4()
        decision = GateDecision(
            action="terraform_apply",
            passed=False,
            blocking_items=[blocking_id],
            reason="Region has speculative confidence",
        )
        assert decision.passed is False
        assert blocking_id in decision.blocking_items


class TestValidTransitions:
    """Test VALID_TRANSITIONS constant."""

    def test_all_transitions_defined(self):
        """Verify all expected transitions are defined."""
        expected_transitions = [
            ("speculative", "inferred"),
            ("speculative", "confirmed"),
            ("inferred", "confirmed"),
            ("inferred", "speculative"),
            ("confirmed", "inferred"),
            ("stated", "confirmed"),
        ]

        for transition in expected_transitions:
            assert transition in VALID_TRANSITIONS

    def test_transition_triggers(self):
        """Verify transition triggers are meaningful."""
        assert VALID_TRANSITIONS[("speculative", "confirmed")] == "explicit_affirmation"
        assert VALID_TRANSITIONS[("inferred", "speculative")] == "contradicting_signal"
        assert VALID_TRANSITIONS[("confirmed", "inferred")] == "user_revision"


class TestIrreversibleActions:
    """Test IRREVERSIBLE_ACTIONS constant."""

    def test_all_actions_defined(self):
        """Verify critical actions are marked as irreversible."""
        expected_actions = {
            "generate_terraform",
            "create_pipeline",
            "terraform_apply",
            "delete_resource",
            "modify_iam",
        }

        assert IRREVERSIBLE_ACTIONS == expected_actions

    def test_terraform_apply_is_irreversible(self):
        """Verify terraform_apply requires high confidence."""
        assert "terraform_apply" in IRREVERSIBLE_ACTIONS
