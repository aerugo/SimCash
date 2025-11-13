#!/usr/bin/env python
"""
Extract actual metrics from policy-scenario tests for calibration.

Runs each test and extracts the actual values to assist with calibration.
"""

import subprocess
import re
import sys

# Test files and their test methods
TESTS = {
    "liquidity_aware": [
        "test_liquidity_aware_ample_liquidity_good_settlement",
        "test_liquidity_aware_moderate_activity_buffer_maintained",
        "test_liquidity_aware_high_pressure_buffer_protection",
        "test_liquidity_aware_liquidity_drain_resilience",
        "test_liquidity_aware_flash_drain_buffer_holds",
        "test_liquidity_aware_tight_deadlines_urgency_override",
        "test_liquidity_aware_buffer_1m_less_conservative",
        "test_liquidity_aware_buffer_2m_balanced",
        "test_liquidity_aware_buffer_3m_very_conservative",
        "test_liquidity_aware_urgency_3_strict",
        "test_liquidity_aware_urgency_5_balanced",
        "test_liquidity_aware_urgency_7_relaxed",
    ],
    "deadline": [
        "test_deadline_ample_liquidity_excellent_settlement",
        "test_deadline_tight_deadlines_minimal_violations",
        "test_deadline_mixed_deadlines_strategic_prioritization",
        "test_deadline_deadline_window_changes_adaptation",
        "test_deadline_high_pressure_prioritization",
        "test_deadline_urgency_2_very_strict",
        "test_deadline_urgency_3_strict",
        "test_deadline_urgency_5_balanced",
        "test_deadline_urgency_7_relaxed",
        "test_deadline_urgency_10_very_relaxed",
    ],
}

def extract_metric(output, metric_pattern):
    """Extract a metric value from test output."""
    match = re.search(metric_pattern, output)
    if match:
        return match.group(1)
    return None

def run_test_and_extract(test_file, test_name):
    """Run a single test and extract its metrics."""
    cmd = [
        ".venv/bin/python", "-m", "pytest",
        f"tests/integration/test_policy_scenario_{test_file}.py::{test_name}",
        "-v"
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout + result.stderr

        # Extract metrics
        settlement = extract_metric(output, r"settlement_rate:\s+([\d.]+)")
        queue = extract_metric(output, r"max_queue_depth:\s+(\d+)")
        min_balance = extract_metric(output, r"min_balance:\s+\$?([\d.]+)")
        violations = extract_metric(output, r"deadline_violations:\s+(\d+)")

        return {
            "settlement_rate": settlement,
            "max_queue_depth": queue,
            "min_balance": min_balance,
            "deadline_violations": violations,
            "status": "PASSED" if result.returncode == 0 else "FAILED"
        }
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT"}
    except Exception as e:
        return {"status": f"ERROR: {e}"}

if __name__ == "__main__":
    print("Extracting metrics from policy-scenario tests...")
    print("=" * 70)

    for test_file, test_names in TESTS.items():
        print(f"\n{test_file.upper()} Tests:")
        print("-" * 70)

        for test_name in test_names:
            metrics = run_test_and_extract(test_file, test_name)

            print(f"\n{test_name}:")
            print(f"  Status: {metrics.get('status', 'UNKNOWN')}")

            if metrics.get('settlement_rate'):
                print(f"  Settlement: {float(metrics['settlement_rate'])*100:.1f}%")
            if metrics.get('max_queue_depth'):
                print(f"  Queue: {metrics['max_queue_depth']}")
            if metrics.get('min_balance'):
                print(f"  Min Balance: ${float(metrics['min_balance']):.2f}")
            if metrics.get('deadline_violations'):
                print(f"  Violations: {metrics['deadline_violations']}")

    print("\n" + "=" * 70)
    print("Extraction complete!")
