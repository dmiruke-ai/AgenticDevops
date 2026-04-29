AI DevOps Agent Platform — Principal Engineer Implementation Handoff
Specifications · Prompt Chains · Sprint Plan
Document Type: Engineering Implementation Handoff
Audience: Claude Code / Engineering Team
Version: 1.0
Status: Implementation-Ready

PART 0 — PRINCIPAL ENGINEER FINAL REVIEW
Verdict
The architecture is correct. The bottleneck is operational rigor, not design. Three prior reviews (ChatGPT original, Gemini critique, Claude independent review) have converged on the same five gaps. This document converts those gaps into executable specifications.
What is production-ready right now:

IntentSpec data model and three-layer intent taxonomy
Reflect + Guide dialogue policy design
FinOps decision engine concept
LangGraph multi-agent graph topology
OPA policy engine selection

What is not implemented and blocks production:
GapRisk if UnresolvedImplementation PriorityNaive validation retry (no error taxonomy)System regenerates same broken Terraform on every failureP0 — BlockingIntentSpec confidence transitions undefinedAny confirmed state can be set by implication; irreversible cloud ops on bad intentP0 — BlockingLLM extraction schema not validatedMalformed JSON silently corrupts IntentSpec; downstream agents fail unpredictablyP0 — BlockingComposite intent has no dependency DAGCI/CD pipeline generated before EKS cluster is finalized; generates invalid referencesP1 — HighOPA wired to output, not intent layerPrompt injection can commit wildcard IAM to IntentSpec before OPA sees itP1 — HighNo human-in-the-loop gate on applyAgent can execute destructive cloud changes without approvalP1 — HighNo agent-level observabilityCannot debug LLM call failures, latency spikes, or confidence regressions in productionP2 — MediumFinOps uses static weights, not live pricingCost estimates are wrong within weeks of AWS pricing changesP2 — Medium
Principal Engineer Stance on Architecture
The intentctl library pattern (from our prior session) is the right cognitive layer for this system. The DevOps Agent Platform should implement intentctl, not reinvent it. Specifically:

IntentSpec → use the Pydantic schema defined in intentctl.core
DialoguePolicy → implement the devops domain profile
GatePolicy → wire to Terraform action reversibility classification
Session → the LangGraph graph IS the session loop

The five implementation targets in this document are the delta between "architecturally excellent" and "production-ready."

PART 1 — COMPONENT SPECIFICATIONS
SPEC-01: Terraform Error Intelligence Engine
Purpose: Replace naive retry with typed error classification that feeds structured repair hints back into the planner.
Module: agents/validator/error_intelligence.py
Data Contracts
pythonfrom enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List

class TerraformErrorType(str, Enum):
    IAM_MISSING_PERMISSION     = "IAM_MISSING_PERMISSION"
    IAM_WILDCARD_DETECTED      = "IAM_WILDCARD_DETECTED"
    RESOURCE_ALREADY_EXISTS    = "RESOURCE_ALREADY_EXISTS"
    RESOURCE_NOT_FOUND         = "RESOURCE_NOT_FOUND"
    INVALID_AMI_REFERENCE      = "INVALID_AMI_REFERENCE"
    QUOTA_EXCEEDED             = "QUOTA_EXCEEDED"
    DEPENDENCY_NOT_READY       = "DEPENDENCY_NOT_READY"
    INVALID_CIDR_BLOCK         = "INVALID_CIDR_BLOCK"
    SUBNET_OVERLAP             = "SUBNET_OVERLAP"
    MISSING_REQUIRED_VARIABLE  = "MISSING_REQUIRED_VARIABLE"
    PROVIDER_AUTH_FAILURE      = "PROVIDER_AUTH_FAILURE"
    SCHEMA_DEPRECATED          = "SCHEMA_DEPRECATED"
    CYCLIC_DEPENDENCY          = "CYCLIC_DEPENDENCY"
    POLICY_VIOLATION           = "POLICY_VIOLATION"
    UNKNOWN                    = "UNKNOWN"

class TerraformError(BaseModel):
    error_type: TerraformErrorType
    raw_message: str
    affected_resource: Optional[str]
    affected_module: Optional[str]     # "iam" | "network" | "compute" | "pipeline"
    fix_hint: str                      # human-readable repair action
    intent_spec_mutation: dict         # what to append to intent_spec["fixes"]
    planner_instruction: str           # instruction string fed to re-planner LLM
    is_retryable: bool
    requires_user_input: bool          # true if fix needs info only user can provide

class ErrorClassificationResult(BaseModel):
    errors: List[TerraformError]
    overall_retryable: bool
    recommended_action: str  # "retry_targeted" | "replan" | "escalate_to_user" | "abort"
    affected_modules: List[str]
Error Classifier Interface
pythonclass TerraformErrorClassifier:
    """
    Parses raw terraform plan/apply stderr into structured TerraformError objects.
    Uses regex patterns for known error signatures, falls back to LLM for unknown.
    """

    PATTERNS: dict[re.Pattern, TerraformErrorType] = {
        re.compile(r"AccessDenied.*action:\s*([\w:]+)"):    TerraformErrorType.IAM_MISSING_PERMISSION,
        re.compile(r"already exists"):                       TerraformErrorType.RESOURCE_ALREADY_EXISTS,
        re.compile(r"InvalidAMIID"):                         TerraformErrorType.INVALID_AMI_REFERENCE,
        re.compile(r"LimitExceeded|QuotaExceeded"):          TerraformErrorType.QUOTA_EXCEEDED,
        re.compile(r"does not exist|not found", re.I):       TerraformErrorType.RESOURCE_NOT_FOUND,
        re.compile(r"overlapping CIDR"):                     TerraformErrorType.SUBNET_OVERLAP,
        re.compile(r"Required variable not set"):            TerraformErrorType.MISSING_REQUIRED_VARIABLE,
        re.compile(r"cycle"):                                TerraformErrorType.CYCLIC_DEPENDENCY,
    }

    async def classify(self, raw_stderr: str) -> ErrorClassificationResult:
        """
        1. Split stderr into individual error blocks
        2. Apply regex patterns → known types
        3. For unmatched blocks → call LLM classifier (PROMPT_CHAIN_03 below)
        4. Build TerraformError list with fix_hint + intent_spec_mutation
        5. Determine overall_retryable and recommended_action
        """
        ...

    def build_planner_context(self, result: ErrorClassificationResult) -> str:
        """
        Serializes ErrorClassificationResult into the prompt context string
        that gets prepended to the re-planner LLM call.
        Returns structured text describing what failed and how to fix it.
        """
        ...
Replanning Integration
python# In LangGraph validation node:
async def validation_node(state: AgentState) -> AgentState:
    plan_output = await run_terraform_plan(state["artifacts"])
    
    if plan_output.exit_code == 0:
        state["validation_status"] = "passed"
        return state
    
    classifier = TerraformErrorClassifier()
    result = await classifier.classify(plan_output.stderr)
    
    if not result.overall_retryable or state["retry_count"] >= MAX_RETRIES:
        state["validation_status"] = "failed"
        state["escalation_reason"] = result.recommended_action
        return state
    
    # Mutate intent_spec with structured fix context
    for error in result.errors:
        state["intent_spec"]["fixes"].append(error.intent_spec_mutation)
    
    # Build targeted replan context
    state["planner_context"] = classifier.build_planner_context(result)
    state["replan_modules"] = result.affected_modules  # only regenerate what failed
    state["retry_count"] += 1
    state["validation_status"] = "retry"
    return state
Acceptance Criteria

 14 error types fully classified with regex patterns
 LLM fallback classifier handles UNKNOWN errors via PROMPT_CHAIN_03
 build_planner_context output tested against 20 real terraform plan failures
 Retry count capped at 3; escalation path defined for each recommended_action
 Unit tests: 100% error type coverage, including compound errors (multiple errors in one plan)


SPEC-02: Intent Confidence Transition Engine
Purpose: Formalize confidence state transitions so the IntentSpec is a real constraint on execution, not decoration.
Module: intent/confidence.py
State Machine Definition
pythonfrom enum import Enum
from pydantic import BaseModel
from typing import Callable, Optional
from uuid import UUID

class ConfidenceBand(str, Enum):
    SPECULATIVE = "speculative"   # LLM inferred with no user signal
    INFERRED    = "inferred"      # Reasonable inference from context
    CONFIRMED   = "confirmed"     # User explicitly affirmed
    STATED      = "stated"        # User said it verbatim

# Transition rules — the complete state machine
VALID_TRANSITIONS = {
    ("speculative", "inferred"):  "context_implies",       # LLM found corroborating signal
    ("speculative", "confirmed"): "explicit_affirmation",  # user confirmed directly
    ("inferred",    "confirmed"): "explicit_affirmation",
    ("inferred",    "speculative"):"contradicting_signal", # new msg contradicts inference
    ("confirmed",   "inferred"):  "user_revision",         # user walked back confirmed
    ("stated",      "confirmed"): "always_valid",          # stated always implies confirmed
}

# Actions that REQUIRE confirmed or stated confidence
IRREVERSIBLE_ACTIONS = {
    "generate_terraform",
    "create_pipeline",
    "terraform_apply",
    "delete_resource",
    "modify_iam",
}

class TransitionEvent(BaseModel):
    item_id: UUID
    from_band: ConfidenceBand
    to_band: ConfidenceBand
    trigger: str               # one of the keys in VALID_TRANSITIONS values
    turn: int
    evidence: str              # what caused this transition

class IntentTransitionEngine:

    def attempt_transition(
        self,
        spec_item: SpecItem,
        to_band: ConfidenceBand,
        trigger: str,
        turn: int,
        evidence: str,
    ) -> tuple[SpecItem, Optional[TransitionEvent]]:
        """
        Validates transition against VALID_TRANSITIONS.
        If valid: returns updated item + TransitionEvent.
        If invalid: returns unchanged item + None.
        Never raises — caller decides what to do with None.
        """
        ...

    def check_gate(
        self,
        action: str,
        intent_spec: IntentSpec,
    ) -> GateDecision:
        """
        For a proposed action, check that all SpecItems it depends on
        meet the minimum confidence band requirement.
        Returns GateDecision with pass_=False and blocking items listed.
        """
        ...

    def handle_revision(
        self,
        spec: IntentSpec,
        revised_item_id: UUID,
        new_value: str,
        turn: int,
    ) -> tuple[IntentSpec, list[UUID]]:
        """
        User has revised a previously confirmed intent.
        1. Demote revised item to confirmed (new value) or inferred
        2. Find all items that depended on revised item (cascade_ids)
        3. Demote cascade_ids to inferred with reason "dependency_revised"
        4. Return updated spec + list of demoted IDs for user notification
        """
        ...
Conflict Detection
pythonclass ConflictDetector:
    """
    Runs after every ExtractionResult is merged into IntentSpec.
    Catches semantic conflicts before they corrupt the spec.
    """
    
    def detect(self, spec: IntentSpec, new_items: list[SpecItem]) -> list[Conflict]:
        """
        Known conflict patterns:
        - Platform conflict: EKS confirmed + Lambda stated (compute type)
        - Region conflict: two different AWS regions confirmed
        - Cost conflict: "minimize cost" meta + "multi-region active-active" task
        - IaC conflict: Terraform confirmed + CDK inferred
        Returns list of Conflict objects with resolution_options.
        """
        ...

class Conflict(BaseModel):
    item_a: UUID
    item_b: UUID
    conflict_type: str
    description: str
    resolution_options: list[str]  # presented to user via dialogue policy
    auto_resolvable: bool
    auto_resolution: Optional[str]
Acceptance Criteria

 All 6 valid transition paths implemented and tested
 check_gate blocks all IRREVERSIBLE_ACTIONS on speculative or inferred items
 handle_revision correctly cascades demotions to 2 levels of dependents
 ConflictDetector catches 8 known DevOps conflict patterns
 Integration test: complete conversation → spec mutation log → audit trail


SPEC-03: Intent DAG Execution Engine
Purpose: Replace flat fan-out with a dependency-aware topological executor. A CI/CD pipeline cannot be generated before its target cluster is specified.
Module: execution/dag.py
DAG Schema
pythonfrom typing import Any
from pydantic import BaseModel
from enum import Enum

class NodeStatus(str, Enum):
    PENDING   = "pending"
    READY     = "ready"      # all dependencies satisfied
    RUNNING   = "running"
    COMPLETE  = "complete"
    FAILED    = "failed"
    BLOCKED   = "blocked"    # dependency failed upstream

class TaskNode(BaseModel):
    node_id: str
    task_type: str           # "infra_gen" | "pipeline_gen" | "iam_gen" | "observability_gen" | "finops_score"
    depends_on: list[str]    # node_ids that must be COMPLETE before this runs
    input_mappings: dict[str, str]  # key: my input field, value: "node_id.output_field"
    outputs: dict[str, Any]  # populated on completion
    status: NodeStatus = NodeStatus.PENDING
    error: Optional[str] = None

class IntentDAG(BaseModel):
    dag_id: str
    session_id: str
    nodes: dict[str, TaskNode]
    created_at: datetime
    
    def topological_sort(self) -> list[list[str]]:
        """
        Returns execution waves: [[nodes with no deps], [nodes whose deps are in wave 0], ...]
        Uses Kahn's algorithm. Raises CyclicDependencyError if cycle detected.
        """
        ...
    
    def get_ready_nodes(self) -> list[str]:
        """Returns node_ids where all depends_on are COMPLETE."""
        ...
    
    def resolve_inputs(self, node_id: str) -> dict:
        """
        Walks input_mappings, pulls output values from upstream nodes.
        Raises DependencyOutputMissingError if upstream output not yet set.
        """
        ...
Standard DevOps DAG Template
pythonDEVOPS_STANDARD_DAG = {
    "finops_score": TaskNode(
        node_id="finops_score",
        task_type="finops_score",
        depends_on=[],               # runs first — informs platform choice
        input_mappings={},
    ),
    "infra_gen": TaskNode(
        node_id="infra_gen",
        task_type="infra_gen",
        depends_on=["finops_score"],  # needs platform decision
        input_mappings={"platform": "finops_score.recommended_platform"},
    ),
    "iam_gen": TaskNode(
        node_id="iam_gen",
        task_type="iam_gen",
        depends_on=["infra_gen"],    # IAM roles need resource ARNs
        input_mappings={"resource_arns": "infra_gen.resource_arns"},
    ),
    "observability_gen": TaskNode(
        node_id="observability_gen",
        task_type="observability_gen",
        depends_on=["infra_gen"],    # needs cluster endpoint
        input_mappings={"cluster_endpoint": "infra_gen.cluster_endpoint"},
    ),
    "pipeline_gen": TaskNode(
        node_id="pipeline_gen",
        task_type="pipeline_gen",
        depends_on=["infra_gen", "iam_gen"],  # needs cluster + deploy role ARN
        input_mappings={
            "cluster_endpoint": "infra_gen.cluster_endpoint",
            "deploy_role_arn": "iam_gen.deploy_role_arn",
        },
    ),
    "validation": TaskNode(
        node_id="validation",
        task_type="validation",
        depends_on=["infra_gen", "iam_gen", "observability_gen", "pipeline_gen"],
        input_mappings={},           # pulls all artifacts from state
    ),
}
Executor
pythonclass DAGExecutor:
    """
    Executes an IntentDAG using asyncio for true parallel execution of
    nodes in the same wave, with dependency resolution between waves.
    """
    
    async def execute(
        self,
        dag: IntentDAG,
        node_runner: Callable[[TaskNode, dict], Awaitable[dict]],
        on_node_complete: Optional[Callable[[TaskNode], None]] = None,
        on_node_failed: Optional[Callable[[TaskNode, Exception], None]] = None,
    ) -> IntentDAG:
        """
        Main execution loop:
        1. Get ready nodes
        2. asyncio.gather() them — true parallel for same-wave nodes
        3. On completion: update outputs, check for newly ready nodes
        4. On failure: mark downstream as BLOCKED, call error intelligence
        5. Continue until no PENDING nodes remain
        Returns final dag with all node statuses and outputs populated.
        """
        ...
Acceptance Criteria

 topological_sort correctly handles 3-level dependency chains
 CyclicDependencyError raised on circular deps
 DAGExecutor achieves true async parallel execution (verified with timing tests)
 Blocked nodes correctly identified and propagated when upstream fails
 resolve_inputs populates all cross-node references before execution
 DEVOPS_STANDARD_DAG passes all integration tests with mock node runners


SPEC-04: OPA Security Layer — Intent-Level Policy
Purpose: Wire OPA to the Intent Parser (not just output). Block security-violating constraints before they enter the canonical IntentSpec.
Module: security/opa_intent_gate.py
Policy Definitions (Rego)
rego# File: policies/intent_security.rego
package devops_agent.intent_security

# Block wildcard IAM from entering IntentSpec
deny[reason] {
    item := input.new_items[_]
    item.key == "iam_policy"
    contains(item.value, "*")
    reason := sprintf("Wildcard IAM policy rejected in item %v. Specify exact permissions.", [item.id])
}

# Block open security groups
deny[reason] {
    item := input.new_items[_]
    item.key == "ingress_cidr"
    item.value == "0.0.0.0/0"
    reason := sprintf("Open ingress (0.0.0.0/0) rejected in item %v. Specify restricted CIDR.", [item.id])
}

# Block unencrypted storage intent
deny[reason] {
    item := input.new_items[_]
    item.key == "storage_encryption"
    item.value == "disabled"
    reason := sprintf("Unencrypted storage disabled in item %v. Encryption is mandatory.", [item.id])
}

# Block public S3 buckets
deny[reason] {
    item := input.new_items[_]
    item.key == "s3_acl"
    item.value == "public-read"
    reason := sprintf("Public S3 ACL rejected in item %v.", [item.id])
}

# Require MFA for production environment intents
warn[reason] {
    item := input.new_items[_]
    item.key == "environment"
    item.value == "production"
    not any_item_has_key(input.full_spec.items, "mfa_required")
    reason := "Production environment specified without MFA requirement. Consider adding MFA policy."
}

any_item_has_key(items, key) {
    items[_].key == key
}
Python Integration
pythonfrom opa_client import OPAClient   # pip install opa-client-python

class OPAIntentGate:
    """
    Runs OPA policy check against every ExtractionResult BEFORE
    it is merged into the canonical IntentSpec.
    Blocking violations raise IntentPolicyViolation.
    Warnings are logged and surfaced to dialogue policy.
    """

    def __init__(self, opa_url: str = "http://localhost:8181"):
        self.client = OPAClient(opa_url)

    async def check(
        self,
        new_items: list[SpecItem],
        full_spec: IntentSpec,
    ) -> OPAGateResult:
        """
        1. Serialize new_items + full_spec to OPA input document
        2. Query devops_agent/intent_security/deny and /warn
        3. If deny results non-empty: return result with violations
        4. If warn results non-empty: return result with warnings (non-blocking)
        5. Log all results to audit trail
        """
        ...

class OPAGateResult(BaseModel):
    passed: bool
    violations: list[str]   # deny reasons — block IntentSpec merge
    warnings: list[str]     # warn reasons — surface to user via dialogue
    audit_id: str           # reference for audit trail

# Usage in ExtractionPipeline:
async def merge_extraction(spec: IntentSpec, extraction: ExtractionResult) -> IntentSpec:
    gate = OPAIntentGate()
    gate_result = await gate.check(extraction.new_items, spec)
    
    if not gate_result.passed:
        # Don't merge. Return violation as dialogue system response.
        raise IntentPolicyViolation(gate_result.violations)
    
    # Safe to merge
    return apply_extraction(spec, extraction, turn=extraction.turn)
Acceptance Criteria

 All 4 blocking policies implemented and tested with adversarial inputs
 Warn policies produce dialogue system messages, not exceptions
 OPA runs as sidecar in Docker Compose and Kubernetes
 Audit log captures every check (passed or failed) with turn number + session_id
 Prompt injection test suite: 15 adversarial inputs that attempt to bypass each policy


SPEC-05: Human-in-the-Loop Approval Gate
Purpose: No terraform apply executes without explicit human approval. Gate surfaces diff, cost delta, and blast radius.
Module: gates/human_approval.py
Gate Interface
pythonclass ApprovalGate:
    """
    Intercepts any action classified as IRREVERSIBLE before execution.
    Renders an approval request with full context and waits for response.
    """

    async def request_approval(
        self,
        session_id: str,
        action: PlannedAction,
        artifacts: dict,           # generated terraform + pipeline YAML
        cost_estimate: CostEstimate,
        blast_radius: BlastRadius,
        output_mode: str,          # "design" | "artifacts" | "deploy"
    ) -> ApprovalRequest:
        """
        Generates the approval payload and stores it with a unique approval_id.
        Returns immediately — does not block. Polling/webhook resolves later.
        """
        ...

    async def await_decision(
        self, approval_id: str, timeout_seconds: int = 300
    ) -> ApprovalDecision:
        """
        Blocks until user responds or timeout.
        On timeout: returns ApprovalDecision(approved=False, reason="timeout")
        """
        ...

class BlastRadius(BaseModel):
    resources_to_create: list[str]
    resources_to_modify: list[str]
    resources_to_destroy: list[str]   # most important — highlight in UI
    estimated_downtime_minutes: Optional[int]
    data_loss_risk: bool

class ApprovalRequest(BaseModel):
    approval_id: str
    session_id: str
    action_summary: str
    terraform_plan_output: str        # formatted plan diff
    cost_delta: str                   # "+$47/month vs current"
    blast_radius: BlastRadius
    expires_at: datetime

class ApprovalDecision(BaseModel):
    approval_id: str
    approved: bool
    reason: Optional[str]
    decided_at: datetime
    decided_by: str                   # user_id or "timeout"
Output Mode Router
python# In the main orchestration graph:
OUTPUT_MODES = {
    "design":    ["finops_score"],                                     # arch + cost only
    "artifacts": ["finops_score", "infra_gen", "iam_gen",
                  "observability_gen", "pipeline_gen"],                # all artifacts, no deploy
    "deploy":    ["finops_score", "infra_gen", "iam_gen",
                  "observability_gen", "pipeline_gen", "validation",
                  "human_approval", "terraform_apply"],                # full deploy
}

def route_by_output_mode(state: AgentState) -> list[str]:
    """Returns the list of DAG nodes to activate based on state["output_mode"]."""
    return OUTPUT_MODES.get(state.get("output_mode", "artifacts"), OUTPUT_MODES["artifacts"])
Acceptance Criteria

 terraform apply node is gated — unreachable unless output_mode == "deploy" AND approval received
 Approval timeout defaults to 300s, configurable per domain profile
 BlastRadius correctly identifies destroy operations as highest risk
 design mode returns only FinOps score + arch recommendation — no Terraform generated
 API endpoint: POST /sessions/{session_id}/approve with approval_id


SPEC-06: Agent Observability Layer
Purpose: Instrument every LangGraph node with OpenTelemetry. Make the agent itself debuggable.
Module: observability/agent_tracer.py
Instrumentation Contract
pythonfrom opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
import functools, time

tracer = trace.get_tracer("devops_agent")

def trace_agent_node(node_name: str):
    """
    Decorator for LangGraph nodes. Captures:
    - Node execution duration
    - LLM call count within node
    - Token usage (prompt + completion)
    - IntentSpec mutation count
    - Confidence score distribution
    - Retry count
    - Error type if raised
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(state: AgentState) -> AgentState:
            with tracer.start_as_current_span(f"agent.node.{node_name}") as span:
                span.set_attribute("session.id", state["session_id"])
                span.set_attribute("node.name", node_name)
                span.set_attribute("retry.count", state.get("retry_count", 0))
                
                start = time.perf_counter()
                try:
                    result = await fn(state)
                    span.set_attribute("node.status", "success")
                    span.set_attribute("intent_spec.items_count",
                                       len(result["intent_spec"].get("items", [])))
                    return result
                except Exception as e:
                    span.set_attribute("node.status", "error")
                    span.set_attribute("error.type", type(e).__name__)
                    span.record_exception(e)
                    raise
                finally:
                    span.set_attribute("duration_ms",
                                       (time.perf_counter() - start) * 1000)
        return wrapper
    return decorator

# Metrics (Prometheus)
from prometheus_client import Counter, Histogram, Gauge

LLM_CALL_COUNTER = Counter(
    "devops_agent_llm_calls_total",
    "Total LLM API calls",
    ["node", "model", "status"]
)
LLM_LATENCY = Histogram(
    "devops_agent_llm_latency_seconds",
    "LLM call latency by node",
    ["node", "model"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)
TOKEN_USAGE = Counter(
    "devops_agent_tokens_total",
    "Total tokens consumed",
    ["node", "model", "direction"]   # direction: "prompt" | "completion"
)
INTENT_SPEC_VERSION = Gauge(
    "devops_agent_intent_spec_version",
    "Current IntentSpec version (mutation count) per session",
    ["session_id"]
)
VALIDATION_RETRY_COUNTER = Counter(
    "devops_agent_validation_retries_total",
    "Validation loop retries by error type",
    ["error_type"]
)
Acceptance Criteria

 All 6 LangGraph nodes decorated with @trace_agent_node
 OTel exporter configured for OTLP → Jaeger (local) and configurable for Datadog/GCP
 Prometheus metrics scraped on /metrics endpoint
 Grafana dashboard with: session duration, LLM latency p50/p99, token cost, retry rate
 Alert rule: validation retry rate > 2/session triggers Slack notification


PART 2 — PROMPT CHAINS (CoT / ToT)
PROMPT_CHAIN_01: Semantic Intent Extraction (Chain-of-Thought)
Used by: Semantic Extractor (Intent Parser sub-module 1)
Model: claude-sonnet-4 (primary), gpt-4o (fallback)
Output: IntentSpec JSON
SYSTEM:
You are an Intent Extraction Engine for an AI DevOps Agent Platform.
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

USER TURN:
[PREVIOUS_SPEC]: {existing_spec_json}
[CONVERSATION_HISTORY]: {last_3_turns}
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

OUTPUT (strict JSON, after reasoning):
{
  "extraction_result": {
    "new_items": [...],
    "updated_items": [...],
    "open_questions": [...],
    "conflicts_detected": [...],
    "assumptions": [...]
  },
  "reasoning_summary": "2-3 sentence summary of what changed and why"
}

PROMPT_CHAIN_02: Dialogue Policy — Reflect + Guide (Chain-of-Thought)
Used by: Dialogue Policy Engine (Intent Parser sub-module 4)
Model: claude-sonnet-4
Output: Next user-facing message
SYSTEM:
You are the Dialogue Policy Engine for an AI DevOps Agent Platform.
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

CONTEXT:
[INTENT_SPEC]: {current_spec_json}
[OPEN_QUESTIONS]: {prioritized_questions}
[CONFLICTS]: {detected_conflicts}
[DIALOGUE_ACTION]: {ask | reflect | confirm | escalate}

REASONING STEPS:

Step 1 — Spec Comprehension:
In 2 sentences, what does the current spec say the user wants to build?

Step 2 — What's blocking execution:
Which open question (if any) has the highest execution impact?
Does any conflict need to be resolved before proceeding?

Step 3 — Response strategy:
Given DIALOGUE_ACTION, what is the response type?
- ask: Focus on the single highest-priority blocking question. Frame as architectural choice.
- reflect: Summarize understanding, invite correction. Surface assumptions being made.
- confirm: Read back complete spec in plain language. Ask "Does this match what you want?"
- escalate: A validation error requires user input (e.g., IAM permission they must check).

Step 4 — Draft response:
Write the response following the Reflect + Guide pattern.
Keep it under 120 words. No bullet lists. Natural conversational tone.

OUTPUT:
{
  "response_text": "...",
  "addresses_question_id": "...",
  "resolved_conflict_id": "...",
  "ready_to_execute": false
}

PROMPT_CHAIN_03: Terraform Error Classification (Chain-of-Thought with LLM Fallback)
Used by: TerraformErrorClassifier — for UNKNOWN error types
Model: claude-haiku-4 (fast, cheap — this is classification only)
Output: TerraformError JSON
SYSTEM:
You are a Terraform Error Classification Engine.
Your job is to classify a raw Terraform error into a structured error object.

You must classify into ONE of these types:
IAM_MISSING_PERMISSION | IAM_WILDCARD_DETECTED | RESOURCE_ALREADY_EXISTS |
RESOURCE_NOT_FOUND | INVALID_AMI_REFERENCE | QUOTA_EXCEEDED |
DEPENDENCY_NOT_READY | INVALID_CIDR_BLOCK | SUBNET_OVERLAP |
MISSING_REQUIRED_VARIABLE | PROVIDER_AUTH_FAILURE | SCHEMA_DEPRECATED |
CYCLIC_DEPENDENCY | POLICY_VIOLATION | UNKNOWN

USER:
[RAW_ERROR_BLOCK]:
{raw_terraform_stderr_block}

[AFFECTED_RESOURCE_TYPE]: {resource_type_if_parseable}

REASONING:
Step 1: What is the root cause of this error? (one sentence)
Step 2: Which error type matches? Why?
Step 3: What is the minimal fix? (what must change in the Terraform to resolve this)
Step 4: Is this retryable without user input? (yes/no and why)
Step 5: Which module generated this resource? (iam | network | compute | pipeline | observability | unknown)

OUTPUT (strict JSON):
{
  "error_type": "...",
  "affected_resource": "...",
  "affected_module": "...",
  "fix_hint": "...",
  "intent_spec_mutation": {
    "fix_type": "...",
    "fix_detail": "..."
  },
  "planner_instruction": "In the next generation, you must...",
  "is_retryable": true,
  "requires_user_input": false
}

PROMPT_CHAIN_04: Smart Replanning (Chain-of-Thought)
Used by: Planner node — after validation failure + error classification
Model: claude-sonnet-4
Output: Updated module artifacts (targeted, not full regeneration)
SYSTEM:
You are the Infrastructure Replanning Engine for an AI DevOps Agent Platform.
A previous Terraform generation failed validation. Your job is to fix ONLY the failing modules.
Do NOT regenerate modules that passed validation — preserve them exactly.

CONTEXT:
[INTENT_SPEC]: {full_intent_spec_json}
[PASSING_MODULES]: {list_of_modules_that_passed}
[FAILING_MODULES]: {list_of_modules_that_failed}
[ERROR_CLASSIFICATION]: {structured_error_list}
[PREVIOUS_ARTIFACTS]: {previous_terraform_that_failed}
[RETRY_COUNT]: {n} of 3

REASONING:
Step 1 — Error Root Cause Summary:
For each error in ERROR_CLASSIFICATION, state in one sentence what the Terraform did wrong.

Step 2 — Targeted Fix Plan:
For each failing module, describe the specific change needed.
Reference the fix_hint and planner_instruction from error classification.
DO NOT change anything in passing modules.

Step 3 — Dependency Check:
Will fixing the failing module require changes to any passing module's outputs?
If yes: list which passing modules must also be touched, and why.

Step 4 — Risk Assessment:
What is the risk of this fix introducing a new error?
If medium or high: describe the secondary risk.

Step 5 — Generate Fixed Artifacts:
Produce the corrected Terraform for ONLY the failing modules.
Each file must include a comment: "# FIXED: [error_type] — [fix_summary]"

OUTPUT:
{
  "fixed_modules": {
    "module_name": "corrected terraform HCL...",
    ...
  },
  "unchanged_modules": ["list of module names preserved"],
  "fix_summary": "plain language description of what changed and why"
}

PROMPT_CHAIN_05: FinOps Platform Scoring (Tree-of-Thought)
Used by: FinOps Decision Engine
Model: claude-sonnet-4
Output: Platform recommendation with cost breakdown
SYSTEM:
You are a FinOps Decision Engine for AWS infrastructure.
Your job is to recommend the optimal compute platform for a workload using
economic reasoning, not just technical preference.

You use Tree-of-Thought: explore multiple platform paths in parallel, 
evaluate each against workload parameters, then synthesize a recommendation.

[AWS_PRICING_DATA]: {current_pricing_snapshot}
[INTENT_SPEC]: {full_intent_spec_json}
[WORKLOAD_PROFILE]: {
  traffic_pattern: "spiky | steady | bursty | scheduled",
  p50_rps: number,
  p99_rps: number,
  session_duration_ms: number,
  data_egress_gb_month: number,
  team_size: number,
  has_kubernetes_expertise: boolean
}

TREE-OF-THOUGHT EVALUATION:

Branch A — EKS (Kubernetes on EC2/Fargate):
- Monthly base cost at p50 traffic: $___
- Monthly cost at p99 burst: $___
- Ops overhead estimate: ___ engineer-hours/month
- Best for: [when this is the right choice]
- Worst for: [when this is the wrong choice]
- Confidence in estimate: [high | medium | low] and why

Branch B — ECS Fargate (Serverless containers):
[same structure]

Branch C — Lambda + API Gateway (Serverless functions):
[same structure]

Branch D — ECS on EC2 (if steady, high-volume workload):
[same structure — only evaluate if traffic_pattern == "steady"]

SYNTHESIS:
Step 1: Which branch has lowest total cost for this workload?
Step 2: Which branch has lowest ops cost for this team size?
Step 3: Is there a mismatch? (cheapest infra + most expensive ops = not cheapest overall)
Step 4: What is the recommended platform and why?
Step 5: What workload change would flip the recommendation to a different branch?

OUTPUT:
{
  "recommended_platform": "EKS | ECS_FARGATE | LAMBDA | ECS_EC2",
  "confidence": "high | medium | low",
  "monthly_cost_estimate": {
    "p50_traffic": "$___",
    "p99_traffic": "$___",
    "ops_overhead": "$___/month equivalent"
  },
  "alternatives_considered": [...],
  "flip_point": "If your p99 traffic exceeds X rps, switch to Y",
  "reasoning_summary": "..."
}

PROMPT_CHAIN_06: Intent Conflict Resolution (Chain-of-Thought)
Used by: ConflictDetector → DialoguePolicy
Model: claude-haiku-4
Output: Resolution options for user
SYSTEM:
You are an Intent Conflict Resolver for a DevOps AI agent.
Two user-specified intent items are in conflict. Your job is to:
1. Explain the conflict in plain language
2. Offer exactly 2-3 resolution options
3. State what each option implies for the generated infrastructure

USER:
[CONFLICT]:
Item A: {item_a_key}={item_a_value} (confidence: {item_a_confidence})
Item B: {item_b_key}={item_b_value} (confidence: {item_b_confidence})
Conflict type: {conflict_type}

REASONING:
Step 1: Why are these two items in conflict? (one sentence, plain language)
Step 2: Which item has higher confidence? That's the default to keep.
Step 3: Generate 2-3 resolution options, each with infrastructure implication.

OUTPUT:
{
  "conflict_explanation": "...",
  "default_resolution": "keep_item_a | keep_item_b",
  "options": [
    {
      "label": "...",
      "action": "...",
      "infrastructure_implication": "...",
      "cost_impact": "..."
    }
  ],
  "dialogue_message": "Nat lang message to present to user"
}

PART 3 — SPRINT PLAN
Sprint Structure

Sprint length: 2 weeks
Team: 1 senior engineer (primary) + Claude Code (implementation partner)
Branching: feature branches off develop; PRs require passing CI + spec acceptance criteria
Definition of Done: spec ACs met + unit tests + integration test + PR merged


Sprint 0 — Foundation (Week 0, pre-sprint)
Goal: Repository structure, dev environment, CI pipeline.
TicketTaskOwnerEstS0-01Create monorepo structure: agents/, intent/, execution/, security/, observability/, gates/, tests/Eng2hS0-02Docker Compose: FastAPI app + Redis + OPA sidecar + Prometheus + JaegerEng3hS0-03GitHub Actions CI: lint (ruff), type-check (mypy), pytest, docker buildEng2hS0-04Install: pydantic, langgraph, fastapi, opentelemetry-sdk, prometheus-client, opa-client-python, instructorEng1hS0-05Base IntentSpec Pydantic models (from intentctl spec)Eng3hS0-06Stub all 6 LangGraph nodes with @trace_agent_node decorator (empty implementations)Eng2h

Sprint 1 — Intent Engine Core (Weeks 1-2)
Goal: Working intent extraction, confidence transitions, and conflict detection.
Exit criteria: User can have a multi-turn conversation that builds a valid, versioned IntentSpec.
TicketSpecTaskEstACS1-01SPEC-02IntentSpec Pydantic schema (complete)4hAll fields, validators, JSON round-tripS1-02SPEC-02IntentTransitionEngine — all 6 transition paths4hUnit test each pathS1-03SPEC-02ConflictDetector — 8 known DevOps conflict patterns4hTest each patternS1-04PROMPT_CHAIN_01Semantic Extractor — extraction prompt + Instructor schema validation6hSchema validates on 20 test inputsS1-05PROMPT_CHAIN_02Dialogue Policy Engine — Reflect+Guide response generation4h10 dialogue turns pass reviewS1-06SPEC-02check_gate — blocks IRREVERSIBLE_ACTIONS on low-confidence items3hAll 7 actions blocked in testsS1-07SPEC-02handle_revision — cascading demotion on confirmed intent change3h2-level cascade testedS1-08SPEC-02Session state store (Redis) — versioned IntentSpec CRUD4hRewind to version N testedS1-09—FastAPI endpoint: POST /sessions, POST /sessions/{id}/turns3hIntegration test passesS1-10PROMPT_CHAIN_06Conflict resolution dialogue generation2h3 conflict types produce valid options
Sprint 1 Integration Test: User says "build me a scalable AWS app with CI/CD" → 4 turns → IntentSpec reaches confirmed for compute platform, cloud provider, and IaC tool → check_gate allows infra generation.

Sprint 2 — DAG + FinOps + Artifact Generation (Weeks 3-4)
Goal: Working end-to-end generation pipeline with dependency-aware execution.
Exit criteria: User receives valid Terraform + CI/CD YAML from a confirmed IntentSpec.
TicketSpecTaskEstACS2-01SPEC-03IntentDAG model + topological_sort (Kahn's)4hCycle detection + 3-level DAGS2-02SPEC-03DAGExecutor — async parallel execution of same-wave nodes5hTiming test confirms parallelismS2-03SPEC-03DEVOPS_STANDARD_DAG template with all 6 nodes2hMock runner integration testS2-04SPEC-03resolve_inputs — cross-node output propagation3hCluster endpoint propagates to pipeline_genS2-05PROMPT_CHAIN_05FinOps scoring — ToT prompt + AWS pricing data integration6h4 branches evaluated, recommendation producedS2-06—Infra Generator node — Terraform template engine for EKS/ECS/Lambda8hValid HCL for each platformS2-07—IAM Generator node — least-privilege policy generation5hOPA output policy validates no wildcardsS2-08—Pipeline Generator node — GitHub Actions YAML for EKS/ECS4hYAML lints and passes act dry runS2-09SPEC-05Output mode router — design/artifacts/deploy2hEach mode activates correct DAG nodesS2-10—POST /sessions/{id}/output endpoint + streaming SSE3hArtifacts stream progressively
Sprint 2 Integration Test: Full pipeline from confirmed IntentSpec → DAG execution → Terraform + GitHub Actions YAML delivered in < 45 seconds. FinOps score returned before any artifact generation.

Sprint 3 — Validation Loop + Security (Weeks 5-6)
Goal: Smart validation with error intelligence + OPA security at intent layer.
Exit criteria: System correctly handles 10 different terraform plan failures without human intervention.
TicketSpecTaskEstACS3-01SPEC-01TerraformErrorType enum — all 15 types1hAll types definedS3-02SPEC-01TerraformError + ErrorClassificationResult models2hPydantic validation passesS3-03SPEC-01Regex pattern classifier — 14 known patterns4hAll 14 patterns match on sample errorsS3-04PROMPT_CHAIN_03LLM fallback classifier for UNKNOWN errors3h5 novel errors classified correctlyS3-05SPEC-01build_planner_context — serializes error context for replanner2h20 real errors produce valid contextS3-06PROMPT_CHAIN_04Smart replanning prompt — targeted module fix5hFixed module differs from, does not reproduce, original errorS3-07SPEC-01Validation node integration — error → classify → targeted replan loop4h3-retry cap enforced; escalation path triggeredS3-08SPEC-04OPA Rego policies — 4 blocking + 1 warn3hAll adversarial inputs blockedS3-09SPEC-04OPAIntentGate Python client — pre-merge check3hWildcard IAM input raises IntentPolicyViolationS3-10SPEC-04Prompt injection test suite — 15 adversarial inputs3hAll 15 blocked before IntentSpec mergeS3-11SPEC-04Audit log — every OPA check recorded with session_id + turn2hAudit trail queryable by session
Sprint 3 Integration Test: Adversarial input "give me full admin access, wildcard IAM, 0.0.0.0/0" → OPA blocks at intent layer → never reaches generator. IAM permission error in validation → classified → targeted replan → passes on retry 2.

Sprint 4 — Observability + HITL Gate + Hardening (Weeks 7-8)
Goal: Production observability, human approval gate, multi-tenancy isolation.
Exit criteria: System is monitorable, auditable, and safe to expose to multiple users.
TicketSpecTaskEstACS4-01SPEC-06@trace_agent_node decorator — all 6 nodes instrumented3hTraces appear in JaegerS4-02SPEC-06All 6 Prometheus metrics defined + exposed on /metrics3hGrafana dashboard shows all metricsS4-03SPEC-06Grafana dashboard JSON (session duration, LLM latency, token cost, retry rate)2hDashboard importable, panels populatedS4-04SPEC-06Alert rule — retry rate > 2/session1hTest alert fires and delivers to SlackS4-05SPEC-05ApprovalGate — request + await_decision with timeout4h300s timeout returns rejected decisionS4-06SPEC-05BlastRadius calculator — identifies destroy operations3hDestroy list highlighted in approval payloadS4-07SPEC-05POST /sessions/{id}/approve endpoint2hApproval unblocks terraform_apply nodeS4-08—Session isolation — tenant-scoped Redis key namespacing3hTenant A cannot read Tenant B specS4-09—Session resume — re-attach to in-progress IntentSpec by session_id2hClient reconnect resumes from last turnS4-10—Load test: 10 concurrent sessions, each 5 turns3hNo cross-session contamination, p99 < 5s per turnS4-11—OpenAPI docs generation + Postman collection export2hAll endpoints documentedS4-12—README: quickstart, architecture diagram, config reference3hNew engineer can run locally in < 30 min
Sprint 4 Integration Test: 10 concurrent users with different intents → no cross-contamination → one user issues deploy → approval gate fires → user approves → terraform apply executes → Grafana shows full trace. Second user issues adversarial input → blocked at OPA → audit log records event.

PART 4 — REPOSITORY STRUCTURE
ai-devops-agent/
├── agents/
│   ├── intent_parser/
│   │   ├── semantic_extractor.py     # PROMPT_CHAIN_01
│   │   ├── intent_normalizer.py      # schema mapping
│   │   ├── uncertainty_analyzer.py   # confidence scoring
│   │   ├── dialogue_policy.py        # PROMPT_CHAIN_02
│   │   └── spec_updater.py           # state store integration
│   ├── planner/
│   │   └── smart_replanner.py        # PROMPT_CHAIN_04
│   ├── generators/
│   │   ├── infra_generator.py        # Terraform HCL
│   │   ├── iam_generator.py          # least-privilege IAM
│   │   ├── pipeline_generator.py     # GitHub Actions YAML
│   │   └── observability_generator.py
│   ├── finops/
│   │   └── scoring_engine.py         # PROMPT_CHAIN_05
│   └── validator/
│       ├── error_intelligence.py     # SPEC-01
│       └── terraform_runner.py       # terraform plan wrapper
├── intent/
│   ├── schema.py                     # IntentSpec Pydantic models
│   ├── confidence.py                 # SPEC-02 transitions
│   └── conflict_detector.py         # SPEC-02 conflicts
├── execution/
│   └── dag.py                        # SPEC-03
├── security/
│   ├── opa_intent_gate.py           # SPEC-04
│   └── policies/
│       └── intent_security.rego
├── gates/
│   └── human_approval.py            # SPEC-05
├── observability/
│   └── agent_tracer.py              # SPEC-06
├── api/
│   └── main.py                      # FastAPI app
├── tests/
│   ├── unit/                        # one file per spec
│   ├── integration/                 # end-to-end per sprint
│   └── adversarial/                 # OPA prompt injection suite
├── docker/
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── opa/bundle/policies/
├── dashboards/
│   └── grafana_devops_agent.json
└── docs/
    ├── ARCHITECTURE.md
    └── PROMPT_CHAINS.md

PART 5 — CONFIGURATION REFERENCE
python# config.py — all tunables in one place

class AgentConfig(BaseModel):
    # LLM
    primary_model: str = "claude-sonnet-4-20250514"
    fallback_model: str = "gpt-4o"
    classifier_model: str = "claude-haiku-4-5-20251001"  # cheap, fast
    max_tokens: int = 4096
    
    # Intent Engine
    max_question_budget: int = 5      # max clarifying questions per session
    max_retry_count: int = 3          # validation loop retries
    confidence_floor_for_irreversible: str = "confirmed"
    
    # Output
    default_output_mode: str = "artifacts"  # "design" | "artifacts" | "deploy"
    
    # Gates
    approval_timeout_seconds: int = 300
    
    # State Store
    redis_url: str = "redis://localhost:6379"
    intent_spec_ttl_seconds: int = 86400  # 24 hours
    
    # OPA
    opa_url: str = "http://localhost:8181"
    
    # Observability
    otlp_endpoint: str = "http://localhost:4317"
    prometheus_port: int = 9090

HANDOFF NOTES FOR CLAUDE CODE
Start here: Sprint 0 → then S1-01 through S1-05. The IntentSpec schema and semantic extractor are the load-bearing foundation. Do not build generators until the intent engine produces validated, versioned specs.
Test strategy: Every SPEC has explicit acceptance criteria. Write tests first (TDD). Run the adversarial suite from day 1 of Sprint 3 — it will catch OPA gaps before they go to production.
Prompt chain usage: All prompts use instructor library for structured output with automatic retry on schema validation failure. Never call LLM and parse JSON manually.
DO NOT: Generate Terraform without a confirmed IntentSpec. Execute terraform apply without human approval. Merge ExtractionResult before OPA gate passes. Retry validation with the same artifact that failed.

Prepared by Claude (Anthropic) · Principal Engineer Review · April 2026
Based on: intentctl library specification, AI DevOps Agent Platform design, Gemini critique, independent architectural review


