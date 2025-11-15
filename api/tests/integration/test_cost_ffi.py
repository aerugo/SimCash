"""
Integration tests for cost-related FFI methods.

These tests verify that cost data crosses the Rust↔Python boundary correctly
and that all 5 cost types are properly exposed.
"""
import pytest
from payment_simulator._core import Orchestrator


def create_orchestrator_with_costs():
    """
    Create an orchestrator and run it to accumulate costs.

    Configuration designed to generate all 5 cost types:
    - Liquidity cost: Some agents go into overdraft
    - Collateral cost: Agents with collateral_pledged > 0
    - Delay cost: Transactions stuck in Queue 1
    - Split friction cost: Divisible transactions that get split
    - Deadline penalty: Transactions that miss deadlines
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 50000,  # Small balance → likely overdraft
                "unsecured_cap": 100000,
                "collateral_pledged": 20000,  # Will accrue collateral cost
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 5.0,  # High rate → pressure
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 25000,
                        "std_dev": 5000,
                    },
                    "counterparty_weights": {"BANK_C": 1.0},
                    "deadline_range": [5, 50],
                    "priority": 5,
                    "divisible": True,  # Enable splitting
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 50000,
                "unsecured_cap": 100000,
                "collateral_pledged": 15000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 3.0,
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 20000,
                        "std_dev": 5000,
                    },
                    "counterparty_weights": {"BANK_C": 1.0},
                    "deadline_range": [5, 40],
                    "priority": 5,
                    "divisible": True,
                },
            },
            {
                "id": "BANK_C",
                "opening_balance": 500000,  # Large balance → likely receiver
                "unsecured_cap": 0,
                "collateral_pledged": 0,
                "policy": {"type": "Fifo"},
                # No arrival_config - just receives
            },
        ],
        "costs": {
            "overdraft_bps_per_day": 100,  # 1% per day
            "collateral_opportunity_bps_per_day": 20,  # 0.2% per day
            "queue1_delay_per_tick": 10,  # $0.10 per tick per transaction
            "split_fee": 500,  # $5.00 per split
            "deadline_base_penalty": 10000,  # $100.00 base
            "deadline_penalty_per_tick": 1000,  # $10.00 per tick overdue
        },
    }

    orch = Orchestrator.new(config)

    # Run 50 ticks to accumulate costs
    for _ in range(50):
        orch.tick()

    return orch


def create_orchestrator_with_activity():
    """Create orchestrator with basic activity for system metrics."""
    config = {
        "rng_seed": 54321,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "unsecured_cap": 0,
                "collateral_pledged": 0,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 10000,
                        "max": 50000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": True,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 0,
                "collateral_pledged": 0,
                "policy": {"type": "Fifo"},
                # No arrivals
            },
        ],
        "costs": {
            "overdraft_bps_per_day": 100,
            "collateral_opportunity_bps_per_day": 20,
            "queue1_delay_per_tick": 10,
            "split_fee": 500,
            "deadline_base_penalty": 10000,
            "deadline_penalty_per_tick": 1000,
        },
    }

    orch = Orchestrator.new(config)

    # Run 20 ticks
    for _ in range(20):
        orch.tick()

    return orch


class TestAgentCostFFI:
    """Tests for get_agent_accumulated_costs FFI method."""

    def test_get_agent_accumulated_costs_returns_all_cost_types(self):
        """FFI returns all 5 cost types for an agent."""
        # GIVEN: Simulation with costs accumulated
        orch = create_orchestrator_with_costs()

        # WHEN: Query agent costs
        costs = orch.get_agent_accumulated_costs("BANK_A")

        # THEN: All cost types present
        assert "liquidity_cost" in costs, "Missing liquidity_cost"
        assert "collateral_cost" in costs, "Missing collateral_cost"
        assert "delay_cost" in costs, "Missing delay_cost"
        assert "split_friction_cost" in costs, "Missing split_friction_cost"
        assert "deadline_penalty" in costs, "Missing deadline_penalty"
        assert "total_cost" in costs, "Missing total_cost"

    def test_get_agent_accumulated_costs_returns_integers(self):
        """All cost values are integers (i64 in Rust, int in Python)."""
        # GIVEN: Simulation with costs
        orch = create_orchestrator_with_costs()

        # WHEN: Query agent costs
        costs = orch.get_agent_accumulated_costs("BANK_A")

        # THEN: All values are integers (no floats for money!)
        for key, value in costs.items():
            assert isinstance(value, int), f"{key} should be int, got {type(value)}"

    def test_get_agent_accumulated_costs_non_negative(self):
        """All costs are non-negative."""
        # GIVEN: Simulation with costs
        orch = create_orchestrator_with_costs()

        # WHEN: Query agent costs
        costs = orch.get_agent_accumulated_costs("BANK_A")

        # THEN: All costs >= 0 (costs never negative)
        for key, value in costs.items():
            assert value >= 0, f"{key} should be >= 0, got {value}"

    def test_get_agent_accumulated_costs_total_is_sum(self):
        """total_cost equals sum of individual cost components."""
        # GIVEN: Simulation with costs
        orch = create_orchestrator_with_costs()

        # WHEN: Query agent costs
        costs = orch.get_agent_accumulated_costs("BANK_A")

        # THEN: Total matches sum
        expected_total = (
            costs["liquidity_cost"]
            + costs["collateral_cost"]
            + costs["delay_cost"]
            + costs["split_friction_cost"]
            + costs["deadline_penalty"]
        )
        assert costs["total_cost"] == expected_total

    def test_get_agent_accumulated_costs_for_all_agents(self):
        """Can query costs for every agent in simulation."""
        # GIVEN: Simulation with 3 agents
        orch = create_orchestrator_with_costs()

        # WHEN: Query each agent
        agent_ids = ["BANK_A", "BANK_B", "BANK_C"]

        # THEN: All queries succeed
        for agent_id in agent_ids:
            costs = orch.get_agent_accumulated_costs(agent_id)
            assert isinstance(costs, dict)
            assert "total_cost" in costs

    def test_get_agent_accumulated_costs_nonexistent_agent_raises_error(self):
        """Querying non-existent agent raises KeyError."""
        # GIVEN: Simulation
        orch = create_orchestrator_with_costs()

        # WHEN/THEN: Query non-existent agent raises
        with pytest.raises(KeyError, match="Agent not found"):
            orch.get_agent_accumulated_costs("NONEXISTENT")

    def test_cost_accumulation_over_ticks(self):
        """Costs increase monotonically over ticks (at least for some agents)."""
        # GIVEN: Orchestrator with small balance (will go into overdraft)
        config = {
            "rng_seed": 99999,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10000,  # Very small
                    "unsecured_cap": 500000,
                    "collateral_pledged": 100000,  # Large collateral
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 10.0,  # High rate
                        "amount_distribution": {
                            "type": "Uniform",
                            "min": 50000,
                            "max": 100000,
                        },
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [10, 50],
                        "priority": 5,
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1000000,
                    "unsecured_cap": 0,
                    "collateral_pledged": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
            "costs": {
                "overdraft_bps_per_day": 100,
                "collateral_opportunity_bps_per_day": 50,  # High collateral cost
                "queue1_delay_per_tick": 100,
                "split_fee": 500,
                "deadline_base_penalty": 10000,
                "deadline_penalty_per_tick": 1000,
            },
        }

        orch = Orchestrator.new(config)

        # Run 5 ticks
        for _ in range(5):
            orch.tick()

        initial_costs = orch.get_agent_accumulated_costs("BANK_A")
        initial_total = initial_costs["total_cost"]

        # WHEN: Run 20 more ticks
        for _ in range(20):
            orch.tick()

        # THEN: Costs increased (overdraft and/or collateral cost accruing)
        final_costs = orch.get_agent_accumulated_costs("BANK_A")
        final_total = final_costs["total_cost"]

        assert final_total > initial_total, "Costs should increase over ticks"
        # At least one cost type increased
        assert (
            final_costs["liquidity_cost"] > initial_costs["liquidity_cost"]
            or final_costs["collateral_cost"] > initial_costs["collateral_cost"]
            or final_costs["delay_cost"] > initial_costs["delay_cost"]
        )


class TestSystemMetricsFFI:
    """Tests for get_system_metrics FFI method."""

    def test_get_system_metrics_returns_expected_fields(self):
        """FFI returns comprehensive system-wide metrics."""
        # GIVEN: Simulation with activity
        orch = create_orchestrator_with_activity()

        # WHEN: Query system metrics
        metrics = orch.get_system_metrics()

        # THEN: Contains expected KPIs
        assert "total_arrivals" in metrics
        assert "total_settlements" in metrics
        assert "settlement_rate" in metrics
        assert "avg_delay_ticks" in metrics
        assert "max_delay_ticks" in metrics
        assert "queue1_total_size" in metrics
        assert "queue2_total_size" in metrics
        assert "peak_overdraft" in metrics
        assert "agents_in_overdraft" in metrics

    def test_get_system_metrics_settlement_rate_valid_range(self):
        """Settlement rate is between 0.0 and 1.0."""
        # GIVEN: Simulation with activity
        orch = create_orchestrator_with_activity()

        # WHEN: Query metrics
        metrics = orch.get_system_metrics()

        # THEN: Settlement rate in valid range
        assert 0.0 <= metrics["settlement_rate"] <= 1.0

    def test_get_system_metrics_counts_non_negative(self):
        """All count fields are non-negative."""
        # GIVEN: Simulation
        orch = create_orchestrator_with_activity()

        # WHEN: Query metrics
        metrics = orch.get_system_metrics()

        # THEN: Counts are non-negative
        assert metrics["total_arrivals"] >= 0
        assert metrics["total_settlements"] >= 0
        assert metrics["max_delay_ticks"] >= 0
        assert metrics["queue1_total_size"] >= 0
        assert metrics["queue2_total_size"] >= 0
        assert metrics["peak_overdraft"] >= 0
        assert metrics["agents_in_overdraft"] >= 0

    def test_get_system_metrics_settlements_le_arrivals(self):
        """Settlements cannot exceed arrivals."""
        # GIVEN: Simulation
        orch = create_orchestrator_with_activity()

        # WHEN: Query metrics
        metrics = orch.get_system_metrics()

        # THEN: Settlements <= arrivals (logical invariant)
        assert metrics["total_settlements"] <= metrics["total_arrivals"]

    def test_get_system_metrics_settlement_rate_calculation(self):
        """Settlement rate equals settlements / arrivals."""
        # GIVEN: Simulation with activity
        orch = create_orchestrator_with_activity()

        # WHEN: Query metrics
        metrics = orch.get_system_metrics()

        # THEN: Settlement rate matches calculation
        if metrics["total_arrivals"] > 0:
            expected_rate = metrics["total_settlements"] / metrics["total_arrivals"]
            assert abs(metrics["settlement_rate"] - expected_rate) < 1e-6
        else:
            assert metrics["settlement_rate"] == 0.0

    def test_get_system_metrics_types(self):
        """Metrics have correct types."""
        # GIVEN: Simulation
        orch = create_orchestrator_with_activity()

        # WHEN: Query metrics
        metrics = orch.get_system_metrics()

        # THEN: Types are correct
        assert isinstance(metrics["total_arrivals"], int)
        assert isinstance(metrics["total_settlements"], int)
        assert isinstance(metrics["settlement_rate"], float)
        assert isinstance(metrics["avg_delay_ticks"], float)
        assert isinstance(metrics["max_delay_ticks"], int)
        assert isinstance(metrics["queue1_total_size"], int)
        assert isinstance(metrics["queue2_total_size"], int)
        assert isinstance(metrics["peak_overdraft"], int)
        assert isinstance(metrics["agents_in_overdraft"], int)

    def test_get_system_metrics_zero_state(self):
        """Metrics work correctly in initial state (no activity)."""
        # GIVEN: Fresh orchestrator (no ticks)
        config = {
            "rng_seed": 11111,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100000,
                    "unsecured_cap": 0,
                    "collateral_pledged": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
            "costs": {
                "overdraft_bps_per_day": 100,
                "collateral_opportunity_bps_per_day": 20,
                "queue1_delay_per_tick": 10,
                "split_fee": 500,
                "deadline_base_penalty": 10000,
                "deadline_penalty_per_tick": 1000,
            },
        }

        orch = Orchestrator.new(config)

        # WHEN: Query metrics immediately (no ticks)
        metrics = orch.get_system_metrics()

        # THEN: All metrics are zero or sensible defaults
        assert metrics["total_arrivals"] == 0
        assert metrics["total_settlements"] == 0
        assert metrics["settlement_rate"] == 0.0
        assert metrics["avg_delay_ticks"] == 0.0
        assert metrics["max_delay_ticks"] == 0
        assert metrics["queue1_total_size"] == 0
        assert metrics["queue2_total_size"] == 0
        assert metrics["peak_overdraft"] == 0
        assert metrics["agents_in_overdraft"] == 0


class TestFFIDeterminism:
    """Test that FFI cost and metrics queries are deterministic."""

    def test_cost_queries_deterministic_across_runs(self):
        """Same seed produces identical cost data."""
        # GIVEN: Two orchestrators with same seed
        seed = 77777

        config = {
            "rng_seed": seed,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 50000,
                    "unsecured_cap": 100000,
                    "collateral_pledged": 20000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 3.0,
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 30000,
                            "std_dev": 5000,
                        },
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [10, 50],
                        "priority": 5,
                        "divisible": True,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100000,
                    "unsecured_cap": 0,
                    "collateral_pledged": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
            "costs": {
                "overdraft_bps_per_day": 100,
                "collateral_opportunity_bps_per_day": 20,
                "queue1_delay_per_tick": 10,
                "split_fee": 500,
                "deadline_base_penalty": 10000,
                "deadline_penalty_per_tick": 1000,
            },
        }

        orch1 = Orchestrator.new(config)
        orch2 = Orchestrator.new(config)

        # WHEN: Run same number of ticks
        for _ in range(30):
            orch1.tick()
            orch2.tick()

        costs1 = orch1.get_agent_accumulated_costs("BANK_A")
        costs2 = orch2.get_agent_accumulated_costs("BANK_A")

        # THEN: Costs are identical
        assert costs1 == costs2, "Same seed must produce identical costs"

    def test_metrics_queries_deterministic_across_runs(self):
        """Same seed produces identical system metrics."""
        # GIVEN: Two orchestrators with same seed
        seed = 88888

        config = {
            "rng_seed": seed,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100000,
                    "unsecured_cap": 0,
                    "collateral_pledged": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 2.0,
                        "amount_distribution": {
                            "type": "Uniform",
                            "min": 10000,
                            "max": 50000,
                        },
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [10, 50],
                        "priority": 5,
                        "divisible": True,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100000,
                    "unsecured_cap": 0,
                    "collateral_pledged": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
            "costs": {
                "overdraft_bps_per_day": 100,
                "collateral_opportunity_bps_per_day": 20,
                "queue1_delay_per_tick": 10,
                "split_fee": 500,
                "deadline_base_penalty": 10000,
                "deadline_penalty_per_tick": 1000,
            },
        }

        orch1 = Orchestrator.new(config)
        orch2 = Orchestrator.new(config)

        # WHEN: Run same number of ticks
        for _ in range(25):
            orch1.tick()
            orch2.tick()

        metrics1 = orch1.get_system_metrics()
        metrics2 = orch2.get_system_metrics()

        # THEN: Metrics are identical
        assert metrics1 == metrics2, "Same seed must produce identical metrics"
