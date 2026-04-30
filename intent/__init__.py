"""Intent engine for AI DevOps Agent Platform."""

from intent.schema import (
    IntentSpec,
    SpecItem,
    ConfidenceBand,
    IntentCategory,
    ExtractionResult,
    OpenQuestion,
    Conflict,
    TransitionEvent,
)

from intent.confidence import (
    IntentTransitionEngine,
    VALID_TRANSITIONS,
    IRREVERSIBLE_ACTIONS,
)

from intent.conflict_detector import (
    ConflictDetector,
    ConflictType,
)

from intent.state_store import (
    SessionStateStore,
    create_state_store,
)

from intent.session_manager import (
    SessionManager,
    SessionInfo,
    SessionStatus,
    SessionAccessDenied,
    SessionNotFound,
    SessionExpired,
    create_session_manager,
)

__all__ = [
    # Schema
    "IntentSpec",
    "SpecItem",
    "ConfidenceBand",
    "IntentCategory",
    "ExtractionResult",
    "OpenQuestion",
    "Conflict",
    "TransitionEvent",
    # Confidence
    "IntentTransitionEngine",
    "VALID_TRANSITIONS",
    "IRREVERSIBLE_ACTIONS",
    # Conflict Detection
    "ConflictDetector",
    "ConflictType",
    # State Store
    "SessionStateStore",
    "create_state_store",
    # Session Manager
    "SessionManager",
    "SessionInfo",
    "SessionStatus",
    "SessionAccessDenied",
    "SessionNotFound",
    "SessionExpired",
    "create_session_manager",
]
