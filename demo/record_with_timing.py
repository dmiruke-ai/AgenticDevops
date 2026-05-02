#!/usr/bin/env python3
"""
Record demo with proper timing for asciinema playback.
Creates a .cast file with delays between frames for smooth animation.
"""

import json
import time
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from demo.scenario_1_intent_to_infra import run_scenario_1
from demo.scenario_2_error_handling import run_scenario_2
from demo.scenario_3_finops import run_scenario_3


class AsciinemaRecorder:
    """Records terminal output with timing for asciinema."""

    def __init__(self, output_file: str):
        self.output_file = output_file
        self.start_time = None
        self.frames = []

    def start(self):
        """Start recording."""
        self.start_time = time.time()
        # Write header
        header = {
            "version": 2,
            "width": 100,
            "height": 30,
            "timestamp": int(self.start_time),
            "env": {"SHELL": "/bin/bash", "TERM": "xterm-256color"}
        }
        with open(self.output_file, 'w') as f:
            f.write(json.dumps(header) + '\n')

    def write(self, text: str, delay: float = 0.05):
        """Write text with delay."""
        if self.start_time is None:
            self.start()

        elapsed = time.time() - self.start_time
        frame = [elapsed, "o", text]

        with open(self.output_file, 'a') as f:
            f.write(json.dumps(frame) + '\n')

        # Print to console too
        print(text, end='', flush=True)

        # Add delay for next frame
        if delay > 0:
            time.sleep(delay)

    def write_slow(self, text: str, char_delay: float = 0.01):
        """Write text character by character for typewriter effect."""
        for char in text:
            self.write(char, delay=char_delay)

    def write_fast(self, text: str):
        """Write text with minimal delay (block of text)."""
        self.write(text, delay=0.1)

    def pause(self, seconds: float = 1.0):
        """Add a pause (no output)."""
        time.sleep(seconds)


def print_banner(recorder):
    """Print demo banner with animation."""
    banner = """
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
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    for line in banner.split('\n'):
        recorder.write(line + '\n', delay=0.05)
    recorder.pause(0.5)


def main():
    """Run demo with timing."""
    output_file = Path(__file__).parent / "recordings" / "demo-quick.cast"
    recorder = AsciinemaRecorder(str(output_file))

    recorder.start()

    # Banner
    print_banner(recorder)

    recorder.write_fast("\n  Mode: MOCK (no external services)\n\n")
    recorder.pause(0.5)

    # Scenario 1
    recorder.write_fast("\n" + "="*78 + "\n")
    recorder.write_fast("  SCENARIO 1: Intent → Infrastructure\n")
    recorder.write_fast("-"*78 + "\n")
    recorder.write_fast("  Converting natural language to production-ready Terraform + CI/CD\n")
    recorder.write_fast("="*78 + "\n\n")
    recorder.pause(1)

    recorder.write_fast("\n  ┌─ Step 1: User Intent (Natural Language)\n")
    recorder.write_fast("  │\n")
    recorder.pause(0.3)
    recorder.write_slow('  │    "Deploy a scalable web application on AWS with EKS, auto-scaling,\n', 0.02)
    recorder.write_slow('  │     and a CI/CD pipeline using GitHub Actions"\n', 0.02)
    recorder.write_fast("  └" + "─"*70 + "\n\n")
    recorder.pause(1)

    recorder.write_fast("  ┌─ Step 2: Intent Parsing → IntentSpec\n")
    recorder.write_fast("  │\n")
    recorder.write_fast("  │    IntentSpec created:\n")
    recorder.pause(0.3)
    recorder.write_fast("  │      Session: demo-88959b1d\n")
    recorder.write_fast("  │      Version: 1\n")
    recorder.write_fast("  │      Items: 6\n")
    recorder.write_fast("  │    \n")
    recorder.write_fast("  │    Extracted Items:\n")
    recorder.pause(0.2)
    recorder.write_fast("  │      ● cloud_provider: AWS [stated]\n")
    recorder.pause(0.1)
    recorder.write_fast("  │      ● compute_platform: EKS [stated]\n")
    recorder.pause(0.1)
    recorder.write_fast("  │      ● scaling: auto-scaling [stated]\n")
    recorder.pause(0.1)
    recorder.write_fast("  │      ● ci_cd_platform: GitHub Actions [stated]\n")
    recorder.pause(0.1)
    recorder.write_fast("  │      ○ region: us-east-1 [inferred]\n")
    recorder.pause(0.1)
    recorder.write_fast("  │      ○ node_count: 3 [inferred]\n")
    recorder.write_fast("  └" + "─"*70 + "\n\n")
    recorder.pause(1)

    recorder.write_fast("  ┌─ Step 3: OPA Security Policy Check\n")
    recorder.write_fast("  │\n")
    recorder.write_fast("  │    Checking policies:\n")
    recorder.pause(0.2)
    recorder.write_fast("  │      ✓ No wildcard IAM detected\n")
    recorder.pause(0.15)
    recorder.write_fast("  │      ✓ No open security groups (0.0.0.0/0 on sensitive ports)\n")
    recorder.pause(0.15)
    recorder.write_fast("  │      ✓ No prompt injection patterns\n")
    recorder.pause(0.15)
    recorder.write_fast("  │      ✓ Intent structure valid\n")
    recorder.pause(0.3)
    recorder.write_fast("  │    \n")
    recorder.write_fast("  │    Result: ALLOWED\n")
    recorder.write_fast("  └" + "─"*70 + "\n\n")
    recorder.pause(1)

    recorder.write_fast("  ┌─ Step 4: Terraform Generation\n")
    recorder.write_fast("  │\n")
    recorder.write_fast("  │    Generated: main.tf\n")
    recorder.write_fast("  │    " + "─"*50 + "\n")
    recorder.pause(0.2)
    recorder.write_fast("  │    terraform {\n")
    recorder.write_fast('  │      required_version = ">= 1.0"\n')
    recorder.write_fast("  │      required_providers {\n")
    recorder.write_fast("  │        aws = {\n")
    recorder.write_fast('  │          source  = "hashicorp/aws"\n')
    recorder.write_fast('  │          version = "~> 5.0"\n')
    recorder.write_fast("  │        }\n")
    recorder.write_fast("  │      }\n")
    recorder.write_fast("  │    }\n")
    recorder.pause(0.3)
    recorder.write_fast("  │    \n")
    recorder.write_fast('  │    module "eks" {\n')
    recorder.write_fast('  │      source          = "terraform-aws-modules/eks/aws"\n')
    recorder.write_fast('  │      cluster_name    = "demo-cluster"\n')
    recorder.write_fast('  │      cluster_version = "1.28"\n')
    recorder.write_fast("  │      ... (truncated)\n")
    recorder.write_fast("  └" + "─"*70 + "\n\n")
    recorder.pause(1.5)

    # Completion box
    recorder.write_fast("  ╔" + "═"*63 + "╗\n")
    recorder.write_fast("  ║  SCENARIO 1 COMPLETE" + " "*42 + "║\n")
    recorder.write_fast("  ╠" + "═"*63 + "╣\n")
    recorder.write_fast("  ║  Input:  Natural language intent" + " "*30 + "║\n")
    recorder.write_fast("  ║  Output: Validated Terraform + CI/CD pipeline" + " "*17 + "║\n")
    recorder.write_fast("  ╚" + "═"*63 + "╝\n\n")
    recorder.pause(2)

    recorder.write_fast("\n" + "─"*78 + "\n")
    recorder.write_fast("\n✅ Demo complete! Scenario 1 recorded with timing.\n\n")

    print(f"\n\n✅ Recording saved to: {output_file}")
    print(f"   Size: {output_file.stat().st_size} bytes")
    print(f"\n▶️  Preview: asciinema play {output_file}")


if __name__ == "__main__":
    main()
