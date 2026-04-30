#!/usr/bin/env python3
"""
AI DevOps Agent Platform - Full Demo Runner

Runs all three demo scenarios in sequence with visual output.

Usage:
    python demo/run_demo.py           # Full demo with services
    python demo/run_demo.py --mock    # Mock mode (no external services)
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from demo.scenario_1_intent_to_infra import run_scenario_1
from demo.scenario_2_error_handling import run_scenario_2
from demo.scenario_3_finops import run_scenario_3


def print_banner():
    """Print demo banner."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║     █████╗ ██╗    ██████╗ ███████╗██╗   ██╗ ██████╗ ██████╗ ███████╗        ║
║    ██╔══██╗██║    ██╔══██╗██╔════╝██║   ██║██╔═══██╗██╔══██╗██╔════╝        ║
║    ███████║██║    ██║  ██║█████╗  ██║   ██║██║   ██║██████╔╝███████╗        ║
║    ██╔══██║██║    ██║  ██║██╔══╝  ╚██╗ ██╔╝██║   ██║██╔═══╝ ╚════██║        ║
║    ██║  ██║██║    ██████╔╝███████╗ ╚████╔╝ ╚██████╔╝██║     ███████║        ║
║    ╚═╝  ╚═╝╚═╝    ╚═════╝ ╚══════╝  ╚═══╝   ╚═════╝ ╚═╝     ╚══════╝        ║
║                                                                              ║
║              AI-Powered Infrastructure from Natural Language                 ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)


def print_section(title: str, description: str):
    """Print section header."""
    print(f"""
{'═' * 78}
  {title}
{'─' * 78}
  {description}
{'═' * 78}
""")


async def main(mock_mode: bool = False):
    """Run all demo scenarios."""
    print_banner()

    print(f"\n  Mode: {'🔸 MOCK (no external services)' if mock_mode else '🔹 LIVE (with services)'}\n")

    # Scenario 1: Intent → Infrastructure
    print_section(
        "SCENARIO 1: Intent → Infrastructure",
        "Converting natural language to production-ready Terraform + CI/CD"
    )
    await run_scenario_1(mock_mode=mock_mode)

    input("\n  Press Enter to continue to Scenario 2...")

    # Scenario 2: Error Handling
    print_section(
        "SCENARIO 2: Error Handling & Smart Replanning",
        "Demonstrating intelligent error classification and targeted fixes"
    )
    await run_scenario_2(mock_mode=mock_mode)

    input("\n  Press Enter to continue to Scenario 3...")

    # Scenario 3: FinOps
    print_section(
        "SCENARIO 3: FinOps Cost Optimization",
        "Tree-of-Thought architecture evaluation with cost analysis"
    )
    await run_scenario_3(mock_mode=mock_mode)

    # Summary
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           DEMO COMPLETE                                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ✅ Scenario 1: Intent → Infrastructure                                     ║
║     • Natural language parsed to structured IntentSpec                       ║
║     • Terraform + CI/CD generated with validation                            ║
║                                                                              ║
║  ✅ Scenario 2: Error Handling                                               ║
║     • Terraform errors classified (15 error types)                           ║
║     • Smart replanning with targeted fixes                                   ║
║                                                                              ║
║  ✅ Scenario 3: FinOps Optimization                                          ║
║     • Tree-of-Thought architecture evaluation                                ║
║     • Cost-aware recommendations with flip points                            ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Key Capabilities Demonstrated:                                              ║
║  • Confidence-aware intent parsing                                           ║
║  • OPA security policy enforcement                                           ║
║  • Multi-tenant session isolation                                            ║
║  • Human-in-the-loop approval gates                                          ║
║  • Full observability (OpenTelemetry + Prometheus)                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI DevOps Agent Demo")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    args = parser.parse_args()

    asyncio.run(main(mock_mode=args.mock))
