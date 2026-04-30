#!/usr/bin/env python3
"""
Scenario 3: FinOps Cost Optimization

Demonstrates:
- Tree-of-Thought architecture evaluation
- Multi-dimensional scoring (cost, scalability, reliability, security)
- Cost-aware recommendations
- Flip point analysis

Usage:
    python demo/scenario_3_finops.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_step(step: int, title: str):
    """Print step header."""
    print(f"\n  ┌─ Step {step}: {title}")
    print(f"  │")


def print_output(content: str, indent: int = 4):
    """Print indented output."""
    for line in content.split('\n'):
        print(f"  │{' ' * indent}{line}")


def print_step_end():
    """Print step footer."""
    print(f"  └{'─' * 70}")


async def run_scenario_3(mock_mode: bool = False):
    """Run Scenario 3: FinOps Cost Optimization."""

    # =========================================================================
    # Step 1: User Intent with Cost Priority
    # =========================================================================
    print_step(1, "User Intent (Cost-Sensitive)")

    user_message = "I need to deploy a REST API service. Budget is tight - " \
                   "keep costs under $100/month if possible."

    print_output(f'"{user_message}"')
    print_output("")
    print_output("Extracted Priority: COST")
    print_output("Budget Constraint: $100/month")

    print_step_end()

    # =========================================================================
    # Step 2: Tree-of-Thought Reasoning
    # =========================================================================
    print_step(2, "Tree-of-Thought Reasoning (7 Steps)")

    print_output("Step 1 — Intent Comprehension:")
    print_output("  User wants a REST API with strict cost constraints.")
    print_output("  Budget suggests small-to-medium scale workload.")
    print_output("")
    print_output("Step 2 — Constraints Identification:")
    print_output("  • Budget: TIGHT ($100/month)")
    print_output("  • Scale: Small-Medium (implied)")
    print_output("  • Compliance: None specified")
    print_output("  • Expertise: Unknown (assume intermediate)")
    print_output("")
    print_output("Step 3 — Architectural Forks:")
    print_output("  Fork 1: Compute → Lambda vs ECS vs EKS vs EC2")
    print_output("  Fork 2: Database → DynamoDB vs RDS vs Aurora")
    print_output("  Fork 3: API Layer → API Gateway vs ALB")
    print_output("")
    print_output("Step 4 — Paths to Explore:")
    print_output("  Path A: Lambda + API Gateway + DynamoDB")
    print_output("  Path B: ECS Fargate + ALB + RDS")
    print_output("  Path C: EKS + ALB + Aurora")
    print_output("  Path D: EC2 + ALB + RDS")

    print_step_end()

    # =========================================================================
    # Step 3: Architecture Evaluation
    # =========================================================================
    print_step(3, "Multi-Dimensional Scoring")

    print_output("Scoring Dimensions:")
    print_output("  • Cost (30%): Monthly AWS bill efficiency")
    print_output("  • Scalability (25%): Auto-scaling capabilities")
    print_output("  • Reliability (25%): SLA and fault tolerance")
    print_output("  • Security (20%): IAM, encryption")
    print_output("")
    print_output("┌─────────────────────────────┬────────┬──────┬───────┬─────────┬──────────┬───────────┐")
    print_output("│ Architecture                │ $/mo   │ Cost │ Scale │ Reliab. │ Security │ Composite │")
    print_output("├─────────────────────────────┼────────┼──────┼───────┼─────────┼──────────┼───────────┤")
    print_output("│ Lambda + API GW + DynamoDB  │ $25    │ 9.5  │ 9.0   │ 9.0     │ 8.5      │ 9.05 ★    │")
    print_output("│ ECS Fargate + ALB + RDS     │ $150   │ 7.0  │ 8.0   │ 8.5     │ 8.0      │ 7.80      │")
    print_output("│ EKS + ALB + Aurora          │ $350   │ 5.0  │ 9.5   │ 9.5     │ 9.0      │ 7.95      │")
    print_output("│ EC2 + ALB + RDS             │ $120   │ 7.5  │ 7.0   │ 7.5     │ 7.5      │ 7.40      │")
    print_output("└─────────────────────────────┴────────┴──────┴───────┴─────────┴──────────┴───────────┘")
    print_output("")
    print_output("★ = Recommended (highest composite score within budget)")

    print_step_end()

    # =========================================================================
    # Step 4: Cost Breakdown
    # =========================================================================
    print_step(4, "Cost Breakdown (Recommended Architecture)")

    print_output("Lambda + API Gateway + DynamoDB")
    print_output("─" * 50)
    print_output("")
    print_output("  AWS Lambda:")
    print_output("    Requests:     1M/month × $0.20/1M = $0.20")
    print_output("    Compute:      100ms × 1M × $0.0000166667 = $1.67")
    print_output("    Subtotal:     $1.87")
    print_output("")
    print_output("  API Gateway:")
    print_output("    Requests:     1M/month × $3.50/1M = $3.50")
    print_output("    Subtotal:     $3.50")
    print_output("")
    print_output("  DynamoDB:")
    print_output("    On-demand:    1M reads × $0.25/1M = $0.25")
    print_output("                  500K writes × $1.25/1M = $0.63")
    print_output("    Storage:      1GB × $0.25 = $0.25")
    print_output("    Subtotal:     $1.13")
    print_output("")
    print_output("  CloudWatch:")
    print_output("    Logs:         ~$5.00")
    print_output("")
    print_output("  ─────────────────────────────────────────")
    print_output("  TOTAL:          $11.50/month (88% under budget)")
    print_output("")
    print_output("  ✓ Well within $100/month budget")
    print_output("  ✓ Scales to zero when not in use")
    print_output("  ✓ No server management required")

    print_step_end()

    # =========================================================================
    # Step 5: Flip Points
    # =========================================================================
    print_step(5, "Flip Point Analysis")

    print_output("When should you switch architectures?")
    print_output("")
    print_output("Lambda → ECS Fargate:")
    print_output("  Flip Point: ~3 million requests/month")
    print_output("  Reason: Lambda per-request pricing exceeds Fargate fixed cost")
    print_output("")
    print_output("ECS Fargate → EKS:")
    print_output("  Flip Point: ~10 services or 50+ pods")
    print_output("  Reason: EKS control plane cost ($73/mo) amortized")
    print_output("")
    print_output("Current Load vs Flip Points:")
    print_output("  Your load:    1M requests/month")
    print_output("  Flip point:   3M requests/month")
    print_output("  Headroom:     200% growth before switch needed")
    print_output("")
    print_output("  📈 Recommendation: Stay with Lambda until 3M requests")

    print_step_end()

    # =========================================================================
    # Step 6: Trade-offs
    # =========================================================================
    print_step(6, "Trade-offs Acknowledged")

    print_output("Lambda + API Gateway + DynamoDB")
    print_output("")
    print_output("Advantages:")
    print_output("  ✓ Lowest cost (pay-per-use)")
    print_output("  ✓ Auto-scales to millions of requests")
    print_output("  ✓ No server management")
    print_output("  ✓ Built-in high availability")
    print_output("")
    print_output("Trade-offs:")
    print_output("  ⚠ Cold start latency (100-500ms first request)")
    print_output("  ⚠ 15-minute max execution time")
    print_output("  ⚠ Limited to 10GB memory per function")
    print_output("  ⚠ Vendor lock-in (AWS-specific)")
    print_output("")
    print_output("Mitigations:")
    print_output("  → Use provisioned concurrency for latency-sensitive endpoints")
    print_output("  → Break long operations into Step Functions")
    print_output("  → Design for portability with adapters")

    print_step_end()

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n  ╔═══════════════════════════════════════════════════════════════╗")
    print("  ║  SCENARIO 3 COMPLETE                                          ║")
    print("  ╠═══════════════════════════════════════════════════════════════╣")
    print("  ║  User Priority:    COST ($100/month budget)                   ║")
    print("  ║  Paths Evaluated:  4 (Lambda, ECS, EKS, EC2)                  ║")
    print("  ║  Recommendation:   Lambda + API Gateway + DynamoDB            ║")
    print("  ║  Estimated Cost:   $11.50/month (88% under budget)            ║")
    print("  ║                                                               ║")
    print("  ║  Tree-of-Thought Process:                                     ║")
    print("  ║  1. Intent comprehension                                      ║")
    print("  ║  2. Constraints identification                                ║")
    print("  ║  3. Architectural forks                                       ║")
    print("  ║  4. Path exploration (4 options)                              ║")
    print("  ║  5. Multi-dimensional scoring                                 ║")
    print("  ║  6. Trade-off analysis                                        ║")
    print("  ║  7. Cost-aware recommendation                                 ║")
    print("  ╚═══════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    asyncio.run(run_scenario_3())
