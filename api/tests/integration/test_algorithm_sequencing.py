"""
TDD Tests for Algorithm Sequencing (Phase 2)

TARGET2 uses a three-algorithm settlement approach:
1. Algorithm 1: FIFO settlement (oldest first)
2. Algorithm 2: Bilateral offsetting (A↔B netting)
3. Algorithm 3: Multilateral cycle settlement (A→B→C→A)

Test Strategy:
1. Write failing tests first (RED)
2. Implement minimal code to pass (GREEN)
3. Refactor while keeping tests green

This module follows the TDD plan in docs/plans/target2-lsm-tdd-implementation.md
"""

import pytest
from payment_simulator._core import Orchestrator


def make_agent(agent_id: str, balance: int, limits: dict = None, policy: str = "Fifo") -> dict:
    """Helper to create agent config with sensible defaults."""
    agent = {
        "id": agent_id,
        "opening_balance": balance,
        "unsecured_cap": 0,
        "policy": {"type": policy},
    }
    if limits:
        agent["limits"] = limits
    return agent


# ============================================================================
# TDD Step 2.1: Algorithm Sequencing Config
# ============================================================================


class TestAlgorithmSequencingConfig:
    """TDD Step 2.1: Algorithm sequencing configuration."""

    def test_algorithm_sequencing_config_accepted(self):
        """Config with algorithm_sequencing should be accepted."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "algorithm_sequencing": True,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None

    def test_algorithm_sequencing_disabled_by_default(self):
        """Algorithm sequencing should be disabled by default."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)
        # When disabled, no algorithm events should be emitted
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        events = orch.get_tick_events(0)
        alg_events = [e for e in events if e.get("event_type") == "AlgorithmExecution"]
        assert len(alg_events) == 0


# ============================================================================
# TDD Step 2.2: Algorithm Execution Events
# ============================================================================


class TestAlgorithmExecutionEvents:
    """TDD Step 2.2: Algorithm execution events emitted."""

    def test_algorithm_execution_event_emitted(self):
        """AlgorithmExecution event should be emitted for each algorithm run."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "algorithm_sequencing": True,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        events = orch.get_tick_events(0)
        alg_events = [e for e in events if e.get("event_type") == "AlgorithmExecution"]

        assert len(alg_events) >= 1
        event = alg_events[0]

        # Required fields for replay identity
        assert "tick" in event
        assert "algorithm" in event  # 1, 2, or 3
        assert "result" in event  # "Success", "Failure", "NoProgress"
        assert "settlements" in event  # Number of settlements
        assert "settled_value" in event  # Total value settled

    def test_algorithm_1_fifo_event(self):
        """Algorithm 1 (FIFO) execution should be recorded."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "algorithm_sequencing": True,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        # Simple transaction that settles via Algorithm 1 (FIFO)
        tx_id = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        events = orch.get_tick_events(0)
        alg1_events = [e for e in events if e.get("event_type") == "AlgorithmExecution" and e.get("algorithm") == 1]

        assert len(alg1_events) >= 1
        event = alg1_events[0]
        # With ample liquidity, transaction settles immediately via RTGS
        # Algorithm 1 (queue processing) has nothing to do
        # Result will be "Success" if queue items processed, "NoProgress" if queue was empty
        assert event["result"] in ["Success", "NoProgress"]
        # settlements >= 0 (could be 0 if immediate RTGS settled it)
        assert event["settlements"] >= 0

    def test_algorithm_2_bilateral_offset_event(self):
        """Algorithm 2 (bilateral offset) execution should be recorded."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "algorithm_sequencing": True,
            "lsm_config": {"enable_bilateral": True, "enable_cycles": False},
            "agent_configs": [
                make_agent("BANK_A", 100),  # Low liquidity - forces queue
                make_agent("BANK_B", 100),
            ]
        }
        orch = Orchestrator.new(config)

        # Create offsetting payments
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        events = orch.get_tick_events(0)
        alg2_events = [e for e in events if e.get("event_type") == "AlgorithmExecution" and e.get("algorithm") == 2]

        assert len(alg2_events) >= 1
        event = alg2_events[0]
        # settlements counts number of bilateral offset operations (1 offset = 2 tx)
        assert event["settlements"] >= 1
        assert event["result"] == "Success"

    def test_algorithm_3_multilateral_cycle_event(self):
        """Algorithm 3 (multilateral cycle) execution should be recorded."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "algorithm_sequencing": True,
            "lsm_config": {"enable_bilateral": False, "enable_cycles": True},
            "agent_configs": [
                make_agent("BANK_A", 100),  # Low liquidity - forces queue
                make_agent("BANK_B", 100),
                make_agent("BANK_C", 100),
            ]
        }
        orch = Orchestrator.new(config)

        # Create cycle: A→B→C→A
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_C",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.submit_transaction(
            sender="BANK_C",
            receiver="BANK_A",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        events = orch.get_tick_events(0)
        alg3_events = [e for e in events if e.get("event_type") == "AlgorithmExecution" and e.get("algorithm") == 3]

        assert len(alg3_events) >= 1
        event = alg3_events[0]
        # settlements counts number of cycle operations (1 cycle = 3 tx)
        assert event["settlements"] >= 1
        assert event["result"] == "Success"


# ============================================================================
# TDD Step 2.3: Algorithm Sequencing Order
# ============================================================================


class TestAlgorithmSequencingOrder:
    """TDD Step 2.3: Algorithms run in correct sequence."""

    def test_algorithms_run_in_order_1_2_3(self):
        """Algorithms should run in order: 1, 2, 3."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "algorithm_sequencing": True,
            "lsm_config": {"enable_bilateral": True, "enable_cycles": True},
            "agent_configs": [
                make_agent("BANK_A", 100),
                make_agent("BANK_B", 100),
                make_agent("BANK_C", 100),
            ]
        }
        orch = Orchestrator.new(config)

        # Create payments
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        events = orch.get_tick_events(0)
        # Events are emitted in order, so we can check the order of algorithm numbers
        alg_events = [e for e in events if e.get("event_type") == "AlgorithmExecution"]

        # Check algorithms run in sequence
        algorithms = [e.get("algorithm") for e in alg_events]

        # Should have all 3 algorithms
        assert len(algorithms) == 3

        # They should be in order 1, 2, 3
        assert algorithms == [1, 2, 3]


# ============================================================================
# TDD Step 2.4: Algorithm Execution Replay Identity
# ============================================================================


class TestAlgorithmExecutionReplayIdentity:
    """TDD Step 2.4: Algorithm events replay correctly."""

    def test_algorithm_execution_event_has_all_fields(self):
        """AlgorithmExecution event should have all fields for replay."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "algorithm_sequencing": True,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        events = orch.get_tick_events(0)
        alg_events = [e for e in events if e.get("event_type") == "AlgorithmExecution"]

        assert len(alg_events) >= 1
        event = alg_events[0]

        # Full field list for replay identity
        required_fields = [
            "event_type", "tick", "algorithm", "result",
            "settlements", "settled_value"
        ]
        for field in required_fields:
            assert field in event, f"Missing required field: {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
