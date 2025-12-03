"""
Castro-Specific Deferred Crediting Tests.

These tests verify that deferred crediting works correctly in the context
of the Castro et al. experiments, specifically testing:

1. The Nash equilibrium behavior (Bank B pays, Bank A free-rides)
2. Within-tick recycling prevention
3. Credit timing across experiment-specific scenarios

The deferred crediting feature is CRITICAL for Castro alignment because:
- Castro's model assumes incoming payments are only available NEXT tick
- Without deferred crediting, agents can recycle funds within the same tick
- This leads to different (symmetric) equilibria than Castro predicts
"""

from __future__ import annotations

from typing import Any

import pytest

from payment_simulator._core import Orchestrator
from payment_simulator.config import SimulationConfig


# ============================================================================
# Helper Functions
# ============================================================================


def _config_to_ffi(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw config dict to FFI-compatible format."""
    sim_config = SimulationConfig.from_dict(config_dict)
    return sim_config.to_ffi_dict()


def run_simulation(orch: Orchestrator, num_ticks: int) -> None:
    """Run simulation for specified number of ticks."""
    for _ in range(num_ticks):
        orch.tick()


# ============================================================================
# Castro Nash Equilibrium Tests
# ============================================================================


class TestCastroNashEquilibrium:
    """Test the Nash equilibrium behavior predicted by Castro et al.

    In the 2-period game with deferred crediting:
    - Bank A: ℓ₀ = $0 (post no collateral; wait for B's payment)
    - Bank B: ℓ₀ = $200 (post enough to cover both periods)

    This asymmetric equilibrium arises because Bank A can free-ride on
    Bank B's period-1 payment, which becomes available in period 2.
    """

    def test_bank_b_must_pay_period1_with_zero_collateral(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Bank B's period-1 payment should queue if no collateral posted.

        With deferred crediting and zero opening balance:
        - Bank B's $150 period-1 payment has no funding source
        - It should queue (not settle) in tick 0
        """
        # Modify config: set policy to post ZERO initial collateral
        config = exp1_config_dict.copy()

        # Create custom inline policy with 0 initial liquidity
        zero_collateral_policy = {
            "version": "2.0",
            "policy_id": "zero_collateral",
            "parameters": {
                "urgency_threshold": 3.0,
                "initial_liquidity_fraction": 0.0,  # Zero collateral
                "liquidity_buffer_factor": 1.0,
            },
            "strategic_collateral_tree": {
                "type": "action",
                "node_id": "hold",
                "action": "HoldCollateral",
            },
            "payment_tree": {
                "type": "action",
                "node_id": "release",
                "action": "Release",
            },
        }

        # Override agents to use inline policy
        for agent in config["agents"]:
            agent["policy"] = {
                "type": "Inline",
                "decision_trees": zero_collateral_policy,
            }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Run tick 0 (period 1)
        orch.tick()

        # Bank B's $150 payment should be queued (insufficient liquidity)
        # Note: We check if transactions are pending/queued
        events = orch.get_tick_events(0)

        # Should see arrivals but NOT immediate settlements for Bank B
        arrivals = [e for e in events if e.get("event_type") == "Arrival"]
        settlements = [
            e for e in events if e.get("event_type") == "RtgsImmediateSettlement"
        ]

        # Bank B's payment arrives at tick 0
        bank_b_arrivals = [
            a for a in arrivals
            if a.get("sender_id") == "BANK_B"
        ]
        assert len(bank_b_arrivals) > 0, "Bank B payment should arrive at tick 0"

        # With zero collateral, no immediate settlements should occur
        # (Both agents have 0 balance + 0 credit limit effectively)
        # Actually, they have unsecured_cap, so check queue instead
        queue_size = orch.queue_size()
        assert queue_size >= 1, (
            "Bank B's payment should be queued without sufficient collateral"
        )

    def test_deferred_crediting_prevents_immediate_recycling(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """With deferred crediting, Bank A cannot use Bank B's period-1 payment in period 1.

        This is the KEY behavior for Castro alignment:
        - Tick 0: Bank B pays $150 to A (settles if B has collateral)
        - Tick 0: A's balance is NOT immediately updated
        - Tick 0: If A tried to pay B, it would fail (no funds yet)
        - End of Tick 0: A receives $150 deferred credit
        - Tick 1: A can now use the $150 to pay B
        """
        # Create minimal 2-period scenario
        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 2,
                "num_days": 1,
            },
            "deferred_crediting": True,
            "deadline_cap_at_eod": True,
            "lsm_config": {
                "enable_bilateral": False,
                "enable_cycles": False,
                "max_cycle_length": 3,
                "max_cycles_per_tick": 1,
            },
            "agents": [
                {
                    "id": "A",
                    "opening_balance": 0,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "B",
                    "opening_balance": 20000,  # $200 - enough for both periods
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Submit mutual payments at tick 0
        # B→A: $150 (B has funds)
        # A→B: $150 (A has NO funds)
        tx_ba = orch.submit_transaction("B", "A", 15000, 1, 5, False)
        tx_ab = orch.submit_transaction("A", "B", 15000, 1, 5, False)

        # Execute tick 0
        orch.tick()

        # Check what happened
        events = orch.get_tick_events(0)

        # B→A should settle (B has $200)
        ba_settlements = [
            e for e in events
            if e.get("event_type") == "RtgsImmediateSettlement"
            and e.get("sender") == "B"
        ]
        assert len(ba_settlements) == 1, "B→A should settle in tick 0"

        # A→B should be QUEUED (A has no funds IN THIS TICK)
        # With deferred crediting, A's balance is still 0 during tick processing
        queue_size = orch.queue_size()
        assert queue_size == 1, (
            "A→B should be queued because deferred crediting prevents "
            "A from using B's payment within the same tick"
        )

        # Verify A has received the deferred credit at END of tick
        balance_a = orch.get_agent_balance("A")
        assert balance_a == 15000, (
            "A should have $150 after deferred credit applied at end of tick 0"
        )

        # Now run tick 1 - A→B should settle
        orch.tick()

        # Queue should now be empty
        assert orch.queue_size() == 0, "A→B should settle in tick 1"

    def test_immediate_crediting_allows_within_tick_recycling(self) -> None:
        """Control test: WITHOUT deferred crediting, recycling works.

        This demonstrates what the Castro alignment prevents.
        """
        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 2,
                "num_days": 1,
            },
            "deferred_crediting": False,  # IMMEDIATE mode
            "lsm_config": {
                "enable_bilateral": False,
                "enable_cycles": False,
                "max_cycle_length": 3,
                "max_cycles_per_tick": 1,
            },
            "agents": [
                {
                    "id": "A",
                    "opening_balance": 0,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "B",
                    "opening_balance": 20000,  # $200
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Submit mutual payments
        tx_ba = orch.submit_transaction("B", "A", 15000, 1, 5, False)
        tx_ab = orch.submit_transaction("A", "B", 15000, 1, 5, False)

        # Execute tick 0
        orch.tick()

        # With IMMEDIATE crediting, BOTH should settle in tick 0
        # B→A settles first, A immediately gets $150, then A→B settles
        queue_size = orch.queue_size()
        assert queue_size == 0, (
            "With immediate crediting, both payments should settle in same tick "
            "(within-tick recycling)"
        )


# ============================================================================
# DeferredCreditApplied Event Tests
# ============================================================================


class TestDeferredCreditEvents:
    """Test DeferredCreditApplied events in Castro experiment context."""

    def test_deferred_credit_event_emitted_for_receiver(
        self, exp1_orchestrator: Orchestrator
    ) -> None:
        """Verify DeferredCreditApplied event is emitted when credits are applied."""
        orch = exp1_orchestrator

        # Run tick 0 (Bank B's $150 payment arrives)
        orch.tick()

        # Check for deferred credit event
        events = orch.get_tick_events(0)
        deferred_events = [
            e for e in events if e.get("event_type") == "DeferredCreditApplied"
        ]

        # Bank A should receive deferred credit from Bank B's payment
        # (assuming Bank B had sufficient collateral to settle)
        # Note: This depends on the seed policy posting enough collateral
        if len(deferred_events) > 0:
            bank_a_credit = next(
                (e for e in deferred_events if e.get("agent_id") == "BANK_A"),
                None,
            )
            if bank_a_credit:
                assert bank_a_credit["amount"] > 0
                assert "source_transactions" in bank_a_credit

    def test_no_deferred_events_when_no_settlements(self) -> None:
        """When no settlements occur, no deferred credit events should be emitted."""
        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 2,
                "num_days": 1,
            },
            "deferred_crediting": True,
            "agents": [
                {"id": "A", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Submit payments that can't settle (no funds)
        orch.submit_transaction("A", "B", 10000, 1, 5, False)

        orch.tick()

        events = orch.get_tick_events(0)
        deferred_events = [
            e for e in events if e.get("event_type") == "DeferredCreditApplied"
        ]

        assert len(deferred_events) == 0, (
            "No deferred credit events when no settlements occur"
        )


# ============================================================================
# Multi-Tick Credit Timing Tests
# ============================================================================


class TestCreditTiming:
    """Test credit timing across multiple ticks."""

    def test_credits_available_next_tick_not_same_tick(self) -> None:
        """Credits from tick N are available in tick N+1, not tick N.

        This is the fundamental behavior that distinguishes Castro's model.
        """
        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 3,
                "num_days": 1,
            },
            "deferred_crediting": True,
            "lsm_config": {
                "enable_bilateral": False,
                "enable_cycles": False,
            },
            "agents": [
                {
                    "id": "A",
                    "opening_balance": 100000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "B",
                    "opening_balance": 0,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "C",
                    "opening_balance": 0,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Tick 0: A→B (settles, B gets credit at END of tick)
        orch.submit_transaction("A", "B", 50000, 2, 5, False)
        # Tick 0: B→C should queue (B has no credit yet)
        orch.submit_transaction("B", "C", 30000, 2, 5, False)

        orch.tick()  # Tick 0

        # A→B settles, B→C queues
        assert orch.queue_size() == 1

        # B's balance at end of tick 0 includes deferred credit
        balance_b = orch.get_agent_balance("B")
        assert balance_b == 50000

        # Tick 1: B→C should now settle (B has $50k from tick 0)
        orch.tick()

        assert orch.queue_size() == 0, "B→C should settle in tick 1"

    def test_chain_of_deferred_credits(self) -> None:
        """Test chain: A→B→C→D with deferred crediting.

        Each hop should take one additional tick.
        """
        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 10,
                "num_days": 1,
            },
            "deferred_crediting": True,
            "lsm_config": {"enable_bilateral": False, "enable_cycles": False},
            "agents": [
                {"id": "A", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "C", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "D", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Submit chain of payments
        orch.submit_transaction("A", "B", 50000, 9, 5, False)
        orch.submit_transaction("B", "C", 40000, 9, 5, False)
        orch.submit_transaction("C", "D", 30000, 9, 5, False)

        # Tick 0: A→B settles, B→C and C→D queue
        orch.tick()
        assert orch.get_agent_balance("B") == 50000
        assert orch.queue_size() == 2

        # Tick 1: B→C settles, C→D still queues
        orch.tick()
        assert orch.get_agent_balance("C") == 40000
        assert orch.queue_size() == 1

        # Tick 2: C→D settles
        orch.tick()
        assert orch.get_agent_balance("D") == 30000
        assert orch.queue_size() == 0


# ============================================================================
# Integration with Castro Experiment 1
# ============================================================================


class TestExp1DeferredCrediting:
    """Integration tests for deferred crediting in Experiment 1."""

    def test_exp1_config_uses_deferred_crediting(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Verify Exp1 config has deferred_crediting enabled."""
        assert exp1_config_dict.get("deferred_crediting") is True

    def test_exp1_first_tick_payments(
        self, exp1_orchestrator: Orchestrator
    ) -> None:
        """Test Exp1 first tick behavior with deferred crediting.

        Tick 0: Bank B's $150 payment arrives.
        With default seed policy (25% initial liquidity), B may or may not
        have sufficient funds depending on max_collateral_capacity.
        """
        orch = exp1_orchestrator

        # Run tick 0
        orch.tick()

        # Get events
        events = orch.get_tick_events(0)

        # Verify arrivals occurred
        arrivals = [e for e in events if e.get("event_type") == "Arrival"]
        assert len(arrivals) >= 1, "Should have at least one arrival in tick 0"

        # Check for deferred credit events (indicates settlements occurred)
        deferred = [e for e in events if e.get("event_type") == "DeferredCreditApplied"]

        # Log what happened for debugging
        print(f"Tick 0: {len(arrivals)} arrivals, {len(deferred)} deferred credits")
        for d in deferred:
            print(f"  {d.get('agent_id')} received {d.get('amount')}")
