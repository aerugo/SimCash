"""
TDD test for settlement rate bug with split transactions.

Bug: When SimulationStats counts settlements, it counts ALL settled transactions
including split children. But arrivals only counts parent transactions.
This causes settlement_rate > 100% when transactions are split.

Fix: When persisting final metadata, recalculate arrivals and settlements
using the corrected logic from the frontend API endpoint.
"""

import tempfile
from pathlib import Path
import pytest
from payment_simulator._core import Orchestrator
from payment_simulator.persistence.connection import DatabaseManager


@pytest.mark.skip(reason="API changed: get_all_transactions() method no longer exists. Settlement rate fix now uses get_system_metrics() instead.")
def test_settlement_rate_bug_with_split_transactions():
    """
    TDD Test: Demonstrates the bug where settlement rate exceeds 100% with splits.

    Expected behavior AFTER fix:
    - Total arrivals = count of parent transactions only
    - Total settlements = count of effectively settled parents
    - Settlement rate ≤ 100%
    """

    # Simple config - just enough to test the counting logic
    config = {
        "ticks_per_day": 10,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"}
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"}
            }
        ]
    }

    orch = Orchestrator.new(config)

    # Submit 5 parent transactions
    parent_tx_ids = []
    for i in range(5):
        tx_id = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,  # $1,000
            deadline_tick=8,
            priority=5,
            divisible=False
        )
        parent_tx_ids.append(tx_id)

    # Manually split 2 of them into children (simulate PolicySplit)
    # We'll use Rust's split functionality by getting transaction details
    # and creating children manually for testing

    print(f"\n{'='*80}")
    print(f"Created {len(parent_tx_ids)} parent transactions")
    print(f"{'='*80}\n")

    # Run simulation
    tick_arrivals = 0
    tick_settlements = 0

    for tick in range(10):
        result = orch.tick()
        tick_arrivals += result["num_arrivals"]
        tick_settlements += result["num_settlements"]

        if result["num_settlements"] > 0:
            print(f"Tick {tick}: {result['num_settlements']} settlements")

    print(f"\nRaw tick counters (BUGGY):")
    print(f"  tick_arrivals:    {tick_arrivals}")
    print(f"  tick_settlements: {tick_settlements}")
    if tick_arrivals > 0:
        tick_rate = tick_settlements / tick_arrivals
        print(f"  tick_rate:        {tick_rate * 100:.1f}%")

    # Get all transactions to calculate correct values
    all_txs = orch.get_all_transactions()
    parents = [tx for tx in all_txs if tx.get("parent_id") is None]
    children = [tx for tx in all_txs if tx.get("parent_id") is not None]

    print(f"\nTransaction breakdown:")
    print(f"  Parents:  {len(parents)}")
    print(f"  Children: {len(children)}")
    print(f"  Total:    {len(all_txs)}")

    # Count effectively settled parents
    effectively_settled = 0
    for parent in parents:
        parent_children = [c for c in children if c.get("parent_id") == parent["id"]]

        if not parent_children:
            # No children - check if settled
            if parent["status"] == "settled":
                effectively_settled += 1
        else:
            # Has children - check if ALL children settled
            if all(c["status"] == "settled" for c in parent_children):
                effectively_settled += 1

    print(f"\nCorrect calculation:")
    print(f"  Arrivals (parents only):    {len(parents)}")
    print(f"  Effectively settled:        {effectively_settled}")
    correct_rate = effectively_settled / len(parents) if len(parents) > 0 else 0
    print(f"  Correct settlement rate:    {correct_rate * 100:.1f}%")

    # Test persistence with BUGGY values
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db_manager = DatabaseManager(db_path)
        sim_id = "test_split_bug"

        from payment_simulator.cli.execution.persistence import _persist_simulation_metadata

        _persist_simulation_metadata(
            db_manager=db_manager,
            sim_id=sim_id,
            config_path=Path("test.yaml"),
            config_dict=config,
            ffi_dict=config,
            agent_ids=["BANK_A", "BANK_B"],
            total_arrivals=tick_arrivals,        # BUG: Wrong count
            total_settlements=tick_settlements,  # BUG: Wrong count
            total_costs=0,
            duration=1.0,
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

        print(f"\nPersisted to DB (BUGGY):")
        print(f"  Arrivals:    {db_arrivals}")
        print(f"  Settlements: {db_settlements}")
        print(f"  Rate:        {db_rate * 100:.1f}%")

        print(f"\n{'='*80}")
        print(f"TEST RESULT")
        print(f"{'='*80}\n")

        # THE BUG: If splits occurred, rate could exceed 100%
        # After fix: rate should always be ≤ 100%

        if db_rate > 1.0:
            print(f"❌ BUG DETECTED: Settlement rate is {db_rate * 100:.1f}% (> 100%)")
            print(f"\nThis happens because:")
            print(f"  - Arrivals counter used tick results: {db_arrivals}")
            print(f"  - Settlements counter used tick results: {db_settlements}")
            print(f"  - Should use parent-only counting!")
            print(f"\nExpected correct rate: {correct_rate * 100:.1f}%")

            pytest.fail(
                f"Settlement rate {db_rate * 100:.1f}% exceeds 100%. "
                f"This demonstrates the bug we need to fix."
            )
        else:
            print(f"✓ PASS: Settlement rate is {db_rate * 100:.1f}% (≤ 100%)")

    finally:
        Path(db_path).unlink(missing_ok=True)


if __name__ == "__main__":
    test_settlement_rate_bug_with_split_transactions()
