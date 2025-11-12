"""
Debug script to investigate settlement rate > 100% bug.

This test runs the problematic scenario and compares the settlement rate
from get_system_metrics() with manual calculations from get_transaction_counts_debug().
"""

import json
import yaml
import pytest
from pathlib import Path
from payment_simulator._core import Orchestrator


def test_settlement_rate_debug():
    """Debug settlement rate calculation with detailed transaction counts."""

    # Load the problematic scenario configuration
    config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "5_agent_lsm_collateral_scenario.yaml"
    if not config_path.exists():
        pytest.skip(f"Config file not found: {config_path}. This test requires example config files.")

    root_dir = Path(__file__).parent.parent.parent.parent

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Convert to orchestrator config format
    orchestrator_config = {
        "ticks_per_day": config["simulation"]["ticks_per_day"],
        "num_days": config["simulation"]["num_days"],
        "rng_seed": config["simulation"]["rng_seed"],
        "agent_configs": [],
    }

    # Convert agent configs
    for agent in config["agents"]:
        agent_config = {
            "id": agent["id"],
            "opening_balance": agent["opening_balance"],
            "credit_limit": agent.get("credit_limit", 0),
        }

        # Handle policy - load JSON if FromJson type
        policy = agent["policy"]
        if policy.get("type") == "FromJson" and "json_path" in policy:
            # Read the policy JSON file (path is relative to project root)
            policy_file = root_dir / policy["json_path"]
            with open(policy_file) as f:
                policy_json = f.read()
            # Pass as json string instead of path
            agent_config["policy"] = {
                "type": "FromJson",
                "json": policy_json,
            }
        else:
            agent_config["policy"] = policy

        # Add arrival config if present
        if "arrival_config" in agent:
            agent_config["arrival_config"] = agent["arrival_config"]

        # Add collateral config if present
        if "collateral_pool_capacity" in agent:
            agent_config["collateral_pool_capacity"] = agent["collateral_pool_capacity"]

        orchestrator_config["agent_configs"].append(agent_config)

    # Create orchestrator
    print("Creating orchestrator...")
    orch = Orchestrator.new(orchestrator_config)

    # Run full simulation
    print(f"Running simulation for {config['simulation']['num_days']} days...")
    total_ticks = config["simulation"]["ticks_per_day"] * config["simulation"]["num_days"]

    for tick in range(total_ticks):
        result = orch.tick()
        if tick % 10 == 0:
            print(f"  Tick {tick}/{total_ticks}: {result['num_settlements']} settlements")

    print("\n" + "="*80)
    print("SETTLEMENT RATE ANALYSIS")
    print("="*80 + "\n")

    # Get official metrics
    metrics = orch.get_system_metrics()
    print("Official metrics (get_system_metrics):")
    print(f"  total_arrivals:    {metrics['total_arrivals']}")
    print(f"  total_settlements: {metrics['total_settlements']}")
    print(f"  settlement_rate:   {metrics['settlement_rate']:.4f} ({metrics['settlement_rate']*100:.1f}%)")

    print("\n" + "-"*80 + "\n")

    # Get debug counts
    debug_counts = orch.get_transaction_counts_debug()
    print("Debug transaction counts (get_transaction_counts_debug):")
    print(f"  total_transactions:  {debug_counts['total_transactions']}")
    print(f"  arrivals:            {debug_counts['arrivals']}")
    print(f"  children:            {debug_counts['children']}")
    print(f"  settled_arrivals:    {debug_counts['settled_arrivals']}")
    print(f"  settled_children:    {debug_counts['settled_children']}")

    # Calculate manual settlement rate
    if debug_counts['arrivals'] > 0:
        manual_rate = debug_counts['settled_arrivals'] / debug_counts['arrivals']
        print(f"\nManual settlement rate: {manual_rate:.4f} ({manual_rate*100:.1f}%)")
        print(f"  Calculation: {debug_counts['settled_arrivals']} / {debug_counts['arrivals']}")

    print("\n" + "-"*80 + "\n")

    # Verify invariants
    print("Invariant checks:")
    expected_total = debug_counts['arrivals'] + debug_counts['children']
    actual_total = debug_counts['total_transactions']

    print(f"  ✓ total == arrivals + children?")
    print(f"    {actual_total} == {debug_counts['arrivals']} + {debug_counts['children']}")
    print(f"    {actual_total} == {expected_total} : {actual_total == expected_total}")

    # Compare official vs manual rates
    print(f"\n  ⚠️  settlement_rate <= 1.0?")
    print(f"    Official: {metrics['settlement_rate']:.4f} : {metrics['settlement_rate'] <= 1.0}")
    if debug_counts['arrivals'] > 0:
        print(f"    Manual:   {manual_rate:.4f} : {manual_rate <= 1.0}")

    # Show discrepancy if exists
    if metrics['total_arrivals'] != debug_counts['arrivals']:
        print(f"\n  ❌ DISCREPANCY in arrivals count:")
        print(f"    Official: {metrics['total_arrivals']}")
        print(f"    Debug:    {debug_counts['arrivals']}")
        print(f"    Diff:     {metrics['total_arrivals'] - debug_counts['arrivals']}")

    if metrics['total_settlements'] != debug_counts['settled_arrivals']:
        print(f"\n  ❌ DISCREPANCY in settlements count:")
        print(f"    Official: {metrics['total_settlements']}")
        print(f"    Debug:    {debug_counts['settled_arrivals']}")
        print(f"    Diff:     {metrics['total_settlements'] - debug_counts['settled_arrivals']}")

    print("\n" + "="*80)

    # Assert basic invariants
    assert actual_total == expected_total, "total_transactions must equal arrivals + children"

    # The bug we're investigating:
    # If this fails, it confirms the bug exists and shows the magnitude
    if metrics['settlement_rate'] > 1.0:
        print(f"\n⚠️  BUG CONFIRMED: Settlement rate is {metrics['settlement_rate']*100:.1f}% (> 100%)")
        print(f"   This is mathematically impossible - cannot settle more than arrived.")

        # Try to identify root cause
        if metrics['total_arrivals'] != debug_counts['arrivals']:
            print(f"\n   LIKELY CAUSE: Arrivals count mismatch")
            print(f"   → The 'calculate_system_metrics' function is counting {metrics['total_arrivals']} arrivals")
            print(f"   → But only {debug_counts['arrivals']} transactions have parent_id = None")
            print(f"   → Check if some transactions are incorrectly missing parent_id")

        if metrics['total_settlements'] != debug_counts['settled_arrivals']:
            print(f"\n   LIKELY CAUSE: Settlements count mismatch")
            print(f"   → The 'is_effectively_settled' logic counts {metrics['total_settlements']} settled")
            print(f"   → But only {debug_counts['settled_arrivals']} arrival transactions are fully settled")
            print(f"   → Check if split children are being double-counted")


if __name__ == "__main__":
    test_settlement_rate_debug()
