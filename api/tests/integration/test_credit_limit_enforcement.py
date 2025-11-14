"""Test that credit limits are strictly enforced across all settlement mechanisms.

CRITICAL INVARIANT: Agents must NEVER exceed their allowed overdraft limit.
This is a fundamental financial integrity requirement.
"""

import pytest
from payment_simulator._core import Orchestrator


class TestCreditLimitEnforcement:
    """Test that credit limits are enforced in all settlement paths."""

    def test_rtgs_respects_credit_limits(self):
        """RTGS settlement must not allow balance to exceed allowed overdraft."""
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1000000,  # $10,000
                    "credit_limit": 500000,      # $5,000
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1000000,
                    "credit_limit": 500000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Try to send $20,000 (would require $10,000 overdraft, exceeding $5,000 limit)
        tx_id = orch.submit_transaction(
            "BANK_A",     # sender
            "BANK_B",     # receiver
            2000000,      # amount
            50,           # deadline_tick
            5,            # priority
            False,        # is_divisible
        )

        # Process several ticks
        for _ in range(10):
            orch.tick()

        # Transaction should NOT settle immediately - should be queued
        tx_details = orch.get_transaction_details(tx_id)
        assert tx_details["status"] == "pending", "Large tx should be queued without sufficient liquidity"

        # Balance should NOT have gone negative beyond credit limit
        balance = orch.get_agent_balance("BANK_A")
        allowed_overdraft = orch.get_agent_allowed_overdraft_limit("BANK_A")

        assert balance >= -(allowed_overdraft), \
            f"Balance {balance} exceeds allowed overdraft -{allowed_overdraft}"

    def test_lsm_bilateral_respects_credit_limits(self):
        """LSM bilateral settlement must not allow balances to exceed limits."""
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 500000,   # $5,000
                    "credit_limit": 200000,      # $2,000
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 500000,
                    "credit_limit": 200000,
                    "policy": {"type": "Fifo"},
                },
            ],
            "lsm_config": {
                "enable_bilateral": True,
                "enable_cycles": True,
                "max_cycle_length": 4,
                "max_cycles_per_tick": 10,
            },
        }

        orch = Orchestrator.new(config)

        # Create bilateral scenario: A→B $10,000, B→A $9,000
        # Net: A sends $1,000, B receives $1,000
        # But gross flows would violate limits if not offset
        tx1 = orch.submit_transaction(
            "BANK_A",     # sender
            "BANK_B",     # receiver
            1000000,      # amount ($10,000)
            50,           # deadline_tick
            5,            # priority
            False,        # is_divisible
        )

        tx2 = orch.submit_transaction(
            "BANK_B",     # sender
            "BANK_A",     # receiver
            900000,       # amount ($9,000)
            50,           # deadline_tick
            5,            # priority
            False,        # is_divisible
        )

        # Process ticks - LSM should attempt bilateral offset
        for _ in range(20):
            orch.tick()

        # Check that balances never exceeded limits
        balance_a = orch.get_agent_balance("BANK_A")
        balance_b = orch.get_agent_balance("BANK_B")

        allowed_overdraft_a = orch.get_agent_allowed_overdraft_limit("BANK_A")
        allowed_overdraft_b = orch.get_agent_allowed_overdraft_limit("BANK_B")

        assert balance_a >= -(allowed_overdraft_a), \
            f"BANK_A balance {balance_a} exceeds allowed overdraft -{allowed_overdraft_a}"
        assert balance_b >= -(allowed_overdraft_b), \
            f"BANK_B balance {balance_b} exceeds allowed overdraft -{allowed_overdraft_b}"

    def test_lsm_multilateral_respects_credit_limits(self):
        """LSM multilateral settlement must not allow balances to exceed limits."""
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 500000,   # $5,000
                    "credit_limit": 200000,      # $2,000
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 500000,
                    "credit_limit": 200000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_C",
                    "opening_balance": 500000,
                    "credit_limit": 200000,
                    "policy": {"type": "Fifo"},
                },
            ],
            "lsm_config": {
                "enable_bilateral": True,
                "enable_cycles": True,
                "max_cycle_length": 4,
                "max_cycles_per_tick": 10,
            },
        }

        orch = Orchestrator.new(config)

        # Create cycle: A→B→C→A, each $8,000
        # Net flows: all zero
        # But gross flows would violate limits if not offset
        tx1 = orch.submit_transaction(
            "BANK_A",     # sender
            "BANK_B",     # receiver
            800000,       # amount ($8,000)
            50,           # deadline_tick
            5,            # priority
            False,        # is_divisible
        )

        tx2 = orch.submit_transaction(
            "BANK_B",     # sender
            "BANK_C",     # receiver
            800000,       # amount ($8,000)
            50,           # deadline_tick
            5,            # priority
            False,        # is_divisible
        )

        tx3 = orch.submit_transaction(
            "BANK_C",     # sender
            "BANK_A",     # receiver
            800000,       # amount ($8,000)
            50,           # deadline_tick
            5,            # priority
            False,        # is_divisible
        )

        # Process ticks - LSM should attempt multilateral cycle
        for _ in range(20):
            orch.tick()

        # Check that balances never exceeded limits
        for agent_id in ["BANK_A", "BANK_B", "BANK_C"]:
            balance = orch.get_agent_balance(agent_id)
            allowed_overdraft = orch.get_agent_allowed_overdraft_limit(agent_id)

            assert balance >= -(allowed_overdraft), \
                f"{agent_id} balance {balance} exceeds allowed overdraft -{allowed_overdraft}"

    def test_collateral_posting_does_not_allow_violations(self):
        """
        Test that agents with collateral posted still cannot exceed their allowed overdraft.

        This mimics the REGIONAL_TRUST scenario where an agent posts collateral but
        then settles transactions that exceed even the collateral-backed limit.
        """
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1000000,  # $10,000
                    "credit_limit": 500000,      # $5,000
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1000000,
                    "credit_limit": 500000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Track all balances throughout execution
        violations = []

        # Run both Day 1 and Day 2 (ticks 0-199)
        # Scenario events are automatically injected at the right ticks
        for tick in range(200):
            orch.tick()

            # Check all agents after each tick
            for agent_id in ["METRO_CENTRAL", "REGIONAL_TRUST", "MOMENTUM_CAPITAL", "CORRESPONDENT_HUB"]:
                balance = orch.get_agent_balance(agent_id)
                allowed_overdraft = orch.get_agent_allowed_overdraft_limit(agent_id)

                if balance < -(allowed_overdraft):
                    violations.append({
                        "tick": tick,
                        "agent": agent_id,
                        "balance": balance,
                        "allowed_overdraft": allowed_overdraft,
                        "violation": abs(balance) - allowed_overdraft,
                    })

        # Assert no violations occurred
        if violations:
            print("\n=== CREDIT LIMIT VIOLATIONS DETECTED ===")
            for v in violations:
                print(f"Tick {v['tick']}: {v['agent']} - "
                      f"Balance: {v['balance']/100:.2f}, "
                      f"Allowed: -{v['allowed_overdraft']/100:.2f}, "
                      f"Violation: ${v['violation']/100:.2f}")
            print("=" * 50)

        assert len(violations) == 0, \
            f"Found {len(violations)} credit limit violations! First violation: {violations[0]}"
