"""
Verification test for settlement rate fix with split transactions.

This test verifies that the fix correctly handles split transactions by:
1. Using get_system_metrics() from Rust which correctly counts parent transactions
2. Ensuring persisted settlement rate is always ≤ 100%
3. Ensuring displayed settlement rate matches persisted rate
"""

import tempfile
from pathlib import Path
from payment_simulator._core import Orchestrator
from payment_simulator.persistence.connection import DatabaseManager


def test_settlement_rate_fix_with_policy_that_splits():
    """
    Verification: Settlement rate should be ≤ 100% even with split transactions.
    
    This test uses a policy that actively splits transactions and verifies
    that both the displayed and persisted settlement rates are correct.
    """
    
    # Use the liquidity_splitting policy which will split large transactions
    policy_path = Path(__file__).parent.parent.parent.parent / "backend" / "policies" / "liquidity_splitting.json"
    with open(policy_path) as f:
        policy_json = f.read()
    
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 42,  # Fixed seed for determinism
        "agent_configs": [
            {
                "id": "SPLITTER",
                "opening_balance": 300_000,  # Low balance to trigger splitting
                "unsecured_cap": 0,
                "policy": {
                    "type": "FromJson",
                    "json": policy_json
                },
                "arrival_config": {
                    "rate_per_tick": 1.5,
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 150_000,  # Large amounts to trigger splits
                        "std_dev": 30_000
                    },
                    "counterparty_weights": {"RECEIVER": 1.0},
                    "deadline_ticks_ahead": 15
                }
            },
            {
                "id": "RECEIVER",
                "opening_balance": 5_000_000,  # High balance
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"}
            }
        ]
    }
    
    print("\n" + "="*80)
    print("Running simulation with split-capable policy...")
    print("="*80)
    
    orch = Orchestrator.new(config)
    
    # Run simulation
    for tick in range(20):
        orch.tick()
    
    # Get corrected metrics from Rust
    metrics = orch.get_system_metrics()
    
    print(f"\nRust metrics (get_system_metrics):")
    print(f"  Total arrivals:    {metrics['total_arrivals']}")
    print(f"  Total settlements: {metrics['total_settlements']}")
    print(f"  Settlement rate:   {metrics['settlement_rate'] * 100:.1f}%")
    
    # Verify Rust metrics are correct
    assert metrics["settlement_rate"] <= 1.0, \
        f"Rust settlement rate {metrics['settlement_rate'] * 100:.1f}% exceeds 100%"
    
    # Test persistence
    import os
    db_path = os.path.join(tempfile.gettempdir(), f"test_fix_{os.getpid()}.db")

    try:
        db_manager = DatabaseManager(db_path)
        db_manager.initialize_schema()  # Create tables
        db_manager.apply_migrations()   # Apply migrations
        sim_id = "test_fix_verification"

        # Persist using our fixed implementation
        from payment_simulator.cli.commands.run import _persist_simulation_metadata

        _persist_simulation_metadata(
            db_manager=db_manager,
            sim_id=sim_id,
            config=Path("test.yaml"),
            config_dict=config,
            ffi_dict=config,
            agent_ids=["SPLITTER", "RECEIVER"],
            total_arrivals=metrics["total_arrivals"],
            total_settlements=metrics["total_settlements"],
            total_costs=0,
            sim_duration=1.0,
            orch=orch,
            quiet=True
        )
        
        # Query persisted values
        conn = db_manager.get_connection()
        result = conn.execute(
            "SELECT total_arrivals, total_settlements FROM simulations WHERE simulation_id = ?",
            [sim_id]
        ).fetchone()
        
        db_arrivals, db_settlements = result
        db_rate = db_settlements / db_arrivals if db_arrivals > 0 else 0
        
        print(f"\nPersisted values:")
        print(f"  Arrivals:    {db_arrivals}")
        print(f"  Settlements: {db_settlements}")
        print(f"  Rate:        {db_rate * 100:.1f}%")
        
        print(f"\n{'='*80}")
        print(f"VERIFICATION RESULTS")
        print(f"{'='*80}\n")
        
        # Verify persisted values match Rust metrics
        assert db_arrivals == metrics["total_arrivals"], \
            f"Persisted arrivals {db_arrivals} != Rust arrivals {metrics['total_arrivals']}"
        
        assert db_settlements == metrics["total_settlements"], \
            f"Persisted settlements {db_settlements} != Rust settlements {metrics['total_settlements']}"
        
        # Verify settlement rate is ≤ 100%
        assert db_rate <= 1.0, \
            f"Persisted settlement rate {db_rate * 100:.1f}% exceeds 100%"
        
        print(f"✓ PASS: All assertions passed!")
        print(f"  - Rust metrics match persisted values")
        print(f"  - Settlement rate is {db_rate * 100:.1f}% (≤ 100%)")
        print(f"  - Fix is working correctly!")
        
    finally:
        Path(db_path).unlink(missing_ok=True)


if __name__ == "__main__":
    test_settlement_rate_fix_with_policy_that_splits()
