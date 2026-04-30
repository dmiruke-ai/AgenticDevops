"""
LangGraph Agent Orchestration Graph.

Defines the multi-agent workflow with 6 core nodes:
1. intent_parser - Extract and normalize user intent
2. finops_scorer - Evaluate platform cost/benefit
3. planner - Generate infrastructure artifacts
4. validator - Validate terraform plans
5. approval_gate - Human-in-the-loop approval
6. executor - Execute terraform apply
"""

from typing import Any

from langgraph.graph import StateGraph, END
from observability.agent_tracer import trace_agent_node

# Type alias for agent state
AgentState = dict[str, Any]


@trace_agent_node("intent_parser")
async def intent_parser_node(state: AgentState) -> AgentState:
    """
    STUB: Intent Parser Node

    Will implement:
    - Semantic extraction (PROMPT_CHAIN_01)
    - Confidence transition engine
    - Conflict detection
    - Dialogue policy (PROMPT_CHAIN_02)
    """
    print(f"[STUB] Intent Parser - Session: {state.get('session_id')}")
    return state


@trace_agent_node("finops_scorer")
async def finops_scorer_node(state: AgentState) -> AgentState:
    """
    FinOps Scoring Node - Tree-of-Thought architecture evaluation (PROMPT_CHAIN_05).

    Implements:
    - Tree-of-Thought platform evaluation (EKS, ECS, Lambda, EC2)
    - Cost estimation with multi-dimensional scoring
    - Platform recommendation with flip points
    - Records FinOps metrics for observability
    """
    from agents.finops.scorer import create_finops_scorer
    from intent.schema import IntentSpec
    from observability.agent_tracer import record_finops_evaluation

    session_id = state.get("session_id", "unknown")
    intent_spec_data = state.get("intent_spec", {})

    # Skip if in test mode without LLM
    if state.get("_test_mode", False) and not state.get("_enable_llm", False):
        print(f"[FinOps] Test mode - skipping LLM scoring. Session: {session_id}")
        state["finops_score"] = {
            "primary_recommendation": "ECS Fargate + ALB + RDS",
            "monthly_cost_usd": 150.0,
            "explored_paths": 3,
            "recommendation": "Default ECS Fargate recommendation for balanced cost/performance.",
        }
        return state

    # Create IntentSpec from state
    if isinstance(intent_spec_data, dict):
        try:
            intent_spec = IntentSpec.model_validate(intent_spec_data)
        except Exception:
            intent_spec = IntentSpec(session_id=session_id)
    else:
        intent_spec = intent_spec_data if isinstance(intent_spec_data, IntentSpec) else IntentSpec(session_id=session_id)

    # Extract priority from state or spec
    priority = state.get("priority", "balanced")

    # Create scorer and run evaluation
    print(f"[FinOps] Starting Tree-of-Thought evaluation - Session: {session_id}")
    scorer = create_finops_scorer()

    try:
        result = await scorer.score(intent_spec, priority=priority)

        # Store result in state
        state["finops_score"] = {
            "session_id": result.session_id,
            "primary_recommendation": result.primary_recommendation.architecture_name,
            "monthly_cost_usd": result.primary_recommendation.monthly_cost_usd,
            "cost_score": result.primary_recommendation.cost_score,
            "scalability_score": result.primary_recommendation.scalability_score,
            "reliability_score": result.primary_recommendation.reliability_score,
            "security_score": result.primary_recommendation.security_score,
            "composite_score": result.primary_recommendation.composite_score,
            "explored_paths": len(result.explored_paths),
            "all_paths": [
                {
                    "name": p.architecture_name,
                    "monthly_cost": p.monthly_cost_usd,
                    "composite_score": p.composite_score,
                    "trade_offs": p.trade_offs,
                }
                for p in result.explored_paths
            ],
            "reasoning": {
                "intent_comprehension": result.reasoning.intent_comprehension,
                "constraints": result.reasoning.constraints_identified,
                "architectural_forks": result.reasoning.architectural_forks,
            },
            "recommendation": result.recommendations,
        }

        # Record metrics
        record_finops_evaluation(
            session_id=session_id,
            primary_architecture=result.primary_recommendation.architecture_name,
            monthly_cost=result.primary_recommendation.monthly_cost_usd,
            paths_explored=len(result.explored_paths),
            priority=priority,
        )

        print(f"[FinOps] Recommendation: {result.primary_recommendation.architecture_name} "
              f"(${result.primary_recommendation.monthly_cost_usd:.0f}/mo) - Session: {session_id}")

    except Exception as e:
        print(f"[FinOps] Error during scoring - Session: {session_id}, Error: {e}")
        # Fallback to default recommendation
        state["finops_score"] = {
            "primary_recommendation": "ECS Fargate + ALB + RDS",
            "monthly_cost_usd": 150.0,
            "error": str(e),
            "recommendation": "Default recommendation due to scoring error.",
        }

    return state


@trace_agent_node("planner")
async def planner_node(state: AgentState) -> AgentState:
    """
    STUB: Planner Node

    Will implement:
    - DAG-based artifact generation
    - Terraform template generation
    - IAM policy generation
    - CI/CD pipeline generation
    - Smart replanning (PROMPT_CHAIN_04)
    """
    print(f"[STUB] Planner - Session: {state.get('session_id')}")
    return state


@trace_agent_node("validator")
async def validator_node(state: AgentState) -> AgentState:
    """
    Validator Node - Terraform validation with error intelligence (S3-07).

    Implements:
    - Terraform validate/plan execution
    - Error classification using TerraformErrorClassifier
    - Targeted replanning using SmartReplanner
    - Retry loop (max 3 attempts)
    """
    from agents.validator.validation_loop import create_validation_loop

    session_id = state.get("session_id", "unknown")
    terraform_files = state.get("terraform_files", {})
    intent_spec = state.get("intent_spec", {})

    # Skip validation if no terraform files
    if not terraform_files:
        print(f"[Validator] No terraform files to validate - Session: {session_id}")
        state["validation_status"] = "passed"
        return state

    # Create validation loop
    # Skip actual terraform in test mode
    skip_terraform = state.get("_test_mode", False)
    validator = create_validation_loop(
        max_retries=3,
        skip_terraform=skip_terraform,
    )

    # Run validation loop
    print(f"[Validator] Starting validation - Session: {session_id}")
    result = await validator.validate_and_fix(
        terraform_files=terraform_files,
        intent_spec=intent_spec,
        session_id=session_id,
    )

    # Update state with results
    state["validation_result"] = result.model_dump()
    state["terraform_files"] = result.terraform_files

    if result.success:
        state["validation_status"] = "passed"
        print(f"[Validator] Validation passed - Session: {session_id}, Retries: {result.total_retries}")
    elif result.status == "escalated":
        state["validation_status"] = "escalated"
        state["escalation_reason"] = result.escalation_reason
        print(f"[Validator] Escalated to user - Session: {session_id}, Reason: {result.escalation_reason}")
    else:
        # Check if we should retry
        if result.total_retries < 3:
            state["validation_status"] = "retry"
            print(f"[Validator] Retry needed - Session: {session_id}, Attempt: {result.total_retries}")
        else:
            state["validation_status"] = "failed"
            print(f"[Validator] Validation failed - Session: {session_id}, Reason: {result.escalation_reason}")

    return state


@trace_agent_node("approval_gate")
async def approval_gate_node(state: AgentState) -> AgentState:
    """
    Approval Gate Node - Human-in-the-loop approval (S4-02 / SPEC-05).

    Implements:
    - Blast radius calculation from terraform plan
    - Cost delta computation
    - Human approval request with timeout
    - Returns approved/rejected/timeout decision
    """
    from gates.human_approval import create_approval_gate

    session_id = state.get("session_id", "unknown")
    terraform_plan = state.get("terraform_plan", "")
    intent_spec = state.get("intent_spec", {})

    # Skip if no plan to approve
    if not terraform_plan:
        print(f"[ApprovalGate] No terraform plan - auto-approving. Session: {session_id}")
        state["approved"] = True
        return state

    # Create approval gate
    gate = create_approval_gate()

    # Request approval
    print(f"[ApprovalGate] Requesting approval - Session: {session_id}")
    request = await gate.request_approval(
        session_id=session_id,
        terraform_plan=terraform_plan,
        intent_spec=intent_spec,
    )

    # Store request info in state
    state["approval_request"] = {
        "approval_id": str(request.approval_id),
        "blast_radius": request.blast_radius.model_dump(),
        "cost_delta": request.cost_delta.model_dump(),
        "plan_summary": request.terraform_plan_summary,
    }

    # In test mode, auto-approve
    if state.get("_test_mode", False):
        print(f"[ApprovalGate] Test mode - auto-approving. Session: {session_id}")
        await gate.approve(request.approval_id, decided_by="test-mode")
        state["approved"] = True
        return state

    # Wait for decision (with timeout from config)
    decision = await gate.wait_for_decision(request.approval_id)

    # Update state with decision
    state["approved"] = decision.approved
    state["approval_decision"] = {
        "approved": decision.approved,
        "status": decision.status.value,
        "decided_by": decision.decided_by,
        "reason": decision.reason,
    }

    if decision.approved:
        print(f"[ApprovalGate] APPROVED - Session: {session_id}")
    else:
        print(f"[ApprovalGate] REJECTED/TIMEOUT - Session: {session_id}, Reason: {decision.reason}")

    return state


@trace_agent_node("executor")
async def executor_node(state: AgentState) -> AgentState:
    """
    STUB: Executor Node

    Will implement:
    - Terraform apply execution
    - Real-time output streaming
    - Rollback on failure
    """
    print(f"[STUB] Executor - Session: {state.get('session_id')}")
    return state


def should_continue_to_planner(state: AgentState) -> str:
    """Route based on intent spec confidence and output mode."""
    # STUB: Will check confidence levels and gate decisions
    output_mode = state.get("output_mode", "artifacts")
    if output_mode == "design":
        return "finops_scorer"
    return "planner"


def should_continue_after_validation(state: AgentState) -> str:
    """Route based on validation status."""
    # STUB: Will check validation_status and retry_count
    validation_status = state.get("validation_status", "pending")
    if validation_status == "passed":
        output_mode = state.get("output_mode", "artifacts")
        if output_mode == "deploy":
            return "approval_gate"
        return END
    elif validation_status == "retry":
        return "planner"  # Retry with targeted replanning
    else:
        return END  # Failed - escalate to user


def should_execute(state: AgentState) -> str:
    """Route based on approval decision."""
    # STUB: Will check approval status
    approved = state.get("approved", False)
    return "executor" if approved else END


# Build the graph
def build_graph() -> StateGraph:
    """
    Construct the LangGraph workflow.

    Flow:
    1. intent_parser → parse user intent, build IntentSpec
    2. finops_scorer → evaluate platform options (if needed)
    3. planner → generate artifacts based on IntentSpec
    4. validator → validate terraform plan
       - On error → back to planner for targeted replan
       - On success → approval_gate (if deploy mode) or END
    5. approval_gate → request human approval
    6. executor → execute terraform apply (if approved)
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("intent_parser", intent_parser_node)
    workflow.add_node("finops_scorer", finops_scorer_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("approval_gate", approval_gate_node)
    workflow.add_node("executor", executor_node)

    # Set entry point
    workflow.set_entry_point("intent_parser")

    # Add edges
    workflow.add_conditional_edges(
        "intent_parser",
        should_continue_to_planner,
        {
            "finops_scorer": "finops_scorer",
            "planner": "planner",
        },
    )

    workflow.add_edge("finops_scorer", "planner")
    workflow.add_edge("planner", "validator")

    workflow.add_conditional_edges(
        "validator",
        should_continue_after_validation,
        {
            "approval_gate": "approval_gate",
            "planner": "planner",  # Retry loop
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "approval_gate",
        should_execute,
        {
            "executor": "executor",
            END: END,
        },
    )

    workflow.add_edge("executor", END)

    return workflow.compile()


# Export compiled graph
graph = build_graph()
