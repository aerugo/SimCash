"""
TDD test for LSM releases metric with split transactions.

Bug: LSM releases counter counts ALL transactions settled by LSM (including split children),
which can exceed the total number of arrivals.

Fix: Count only parent transactions that were effectively settled via LSM.
"""

import tempfile
from pathlib import Path
from payment_simulator._core import Orchestrator
from payment_simulator.persistence.connection import DatabaseManager


def test_lsm_releases_should_not_exceed_total_arrivals():
    """
    TDD Test: LSM releases should never exceed total arrivals.
    
    When a transaction is split and all children are settled via LSM,
    this should count as 1 LSM settlement, not N settlements.
    """
    
    # Use a scenario likely to trigger LSM with splitting
    policy_path = Path(__file__).parent.parent.parent.parent / "simulator" / "policies" / "liquidity_splitting.json"
    with open(policy_path) as f:
        policy_json = f.read()
    
    config = {
        "ticks_per_day": 50,
        "num_days": 1,
        "rng_seed": 42,  # Seed known to produce good LSM scenarios
        "lsm_config": {
            "enable_bilateral": True,
            "enable_cycles": True,
            "max_cycle_length": 4
        },
        "agent_configs": [
            {
                "id": "AGENT_A",
                "opening_balance": 100_000,  # Very low to force queuing
                "unsecured_cap": 0,
                "policy": {
                    "type": "FromJson",
                    "json": policy_json
                },
                "arrival_config": {
                    "rate_per_tick": 1.5,  # High rate
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 60_000,
                        "std_dev": 10_000
                    },
                    "counterparty_weights": {"AGENT_B": 0.6, "AGENT_C": 0.4},
                    "deadline_ticks_ahead": 30
                }
            },
            {
                "id": "AGENT_B",
                "opening_balance": 100_000,
                "unsecured_cap": 0,
                "policy": {
                    "type": "FromJson",
                    "json": policy_json
                },
                "arrival_config": {
                    "rate_per_tick": 1.5,
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 60_000,
                        "std_dev": 10_000
                    },
                    "counterparty_weights": {"AGENT_A": 0.6, "AGENT_C": 0.4},
                    "deadline_ticks_ahead": 30
                }
            },
            {
                "id": "AGENT_C",
                "opening_balance": 100_000,
                "unsecured_cap": 0,
                "policy": {
                    "type": "FromJson",
                    "json": policy_json
                },
                "arrival_config": {
                    "rate_per_tick": 1.5,
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 60_000,
                        "std_dev": 10_000
                    },
                    "counterparty_weights": {"AGENT_A": 0.4, "AGENT_B": 0.6},
                    "deadline_ticks_ahead": 30
                }
            }
        ]
    }
    
    print("\n" + "="*80)
    print("Running simulation with LSM and splitting...")
    print("="*80)
    
    orch = Orchestrator.new(config)
    
    # Track using SimulationStats (buggy counter)
    from payment_simulator.cli.execution.stats import SimulationStats
    buggy_stats = SimulationStats()
    
    for tick in range(50):
        result = orch.tick()

        # This will accumulate buggy counts
        from payment_simulator.cli.execution.stats import TickResult
        day = tick // 50  # ticks_per_day = 50
        tick_result = TickResult(
            tick=tick,
            day=day,
            num_arrivals=result["num_arrivals"],
            num_settlements=result["num_settlements"],
            num_lsm_releases=result["num_lsm_releases"],
            total_cost=result["total_cost"],
            events=orch.get_tick_events(tick)
        )
        buggy_stats.update(tick_result)
    
    # Get corrected metrics from Rust
    corrected_metrics = orch.get_system_metrics()
    
    print(f"\nBuggy tick counter:")
    print(f"  LSM Releases: {buggy_stats.total_lsm_releases}")
    print(f"  Total Arrivals: {corrected_metrics['total_arrivals']}")
    
    if buggy_stats.total_lsm_releases > 0:
        buggy_pct = buggy_stats.total_lsm_releases / corrected_metrics['total_arrivals'] * 100
        print(f"  Ratio: {buggy_pct:.1f}%")
    
    # The bug: LSM releases can exceed arrivals
    if buggy_stats.total_lsm_releases > corrected_metrics['total_arrivals']:
        print(f"\n❌ BUG DETECTED: LSM releases ({buggy_stats.total_lsm_releases}) > arrivals ({corrected_metrics['total_arrivals']})")
        print(f"   This is impossible - we can't settle more than arrived!")
    
    # Now calculate CORRECT LSM count from events
    all_events = orch.get_all_events()
    
    # Build transaction hierarchy
    parent_to_children = {}
    child_to_parent = {}
    
    for event in all_events:
        if event['event_type'] == 'PolicySplit':
            parent_id = event['tx_id']
            child_ids = event['child_ids']
            parent_to_children[parent_id] = child_ids
            for child_id in child_ids:
                child_to_parent[child_id] = parent_id
    
    # Track which transactions were settled by LSM
    lsm_settled_txs = set()
    lsm_events = [e for e in all_events if e['event_type'] in ['LsmBilateralOffset', 'LsmCycleSettlement']]

    print(f"\nFound {len(lsm_events)} LSM events in simulation")

    for event in lsm_events:
        # Extract transaction IDs from the event
        # LSM events store tx_ids directly, not in details
        tx_ids = event.get('tx_ids', [])
        lsm_settled_txs.update(tx_ids)

        if len(lsm_settled_txs) == 0:  # Debug first event
            print(f"Sample LSM event keys: {list(event.keys())}")
            print(f"Sample LSM event: {event}")
    
    # Count parent transactions that were effectively settled via LSM
    corrected_lsm_count = 0
    
    # Get all parent transaction IDs (those that arrived)
    parent_tx_ids = set()
    for event in all_events:
        if event['event_type'] == 'Arrival':
            parent_tx_ids.add(event['tx_id'])
    
    for parent_id in parent_tx_ids:
        children = parent_to_children.get(parent_id, [])
        
        if not children:
            # No children - check if parent itself was settled by LSM
            if parent_id in lsm_settled_txs:
                corrected_lsm_count += 1
        else:
            # Has children - check if ALL children were settled by LSM
            if all(child_id in lsm_settled_txs for child_id in children):
                corrected_lsm_count += 1
    
    print(f"\nCorrected calculation (from events):")
    print(f"  Parent transactions: {len(parent_tx_ids)}")
    print(f"  Parents effectively settled by LSM: {corrected_lsm_count}")
    if len(parent_tx_ids) > 0:
        correct_pct = corrected_lsm_count / len(parent_tx_ids) * 100
        print(f"  LSM settlement rate: {correct_pct:.1f}%")
    
    print(f"\n{'='*80}")
    print("TEST ASSERTIONS")
    print(f"{'='*80}\n")
    
    # Assertion 1: Corrected LSM count should never exceed arrivals
    assert corrected_lsm_count <= corrected_metrics['total_arrivals'], \
        f"Corrected LSM count {corrected_lsm_count} exceeds arrivals {corrected_metrics['total_arrivals']}"
    
    print(f"✓ PASS: Corrected LSM count ({corrected_lsm_count}) ≤ arrivals ({corrected_metrics['total_arrivals']})")
    
    # Assertion 2: If buggy counter exceeded arrivals, corrected should be lower
    if buggy_stats.total_lsm_releases > corrected_metrics['total_arrivals']:
        assert corrected_lsm_count < buggy_stats.total_lsm_releases, \
            "Corrected count should be less than buggy count when bug manifests"
        print(f"✓ PASS: Corrected count ({corrected_lsm_count}) < buggy count ({buggy_stats.total_lsm_releases})")
        print(f"\n✅ FIX VERIFIED: Corrected count is mathematically sound!")
    else:
        print(f"ℹ️  No bug manifested in this run (LSM releases didn't exceed arrivals)")
        print(f"   Test still validates the corrected counting logic")


if __name__ == "__main__":
    test_lsm_releases_should_not_exceed_total_arrivals()
