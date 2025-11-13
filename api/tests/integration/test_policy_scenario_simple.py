"""
Level 1: Simple Policy-Scenario Tests

These tests demonstrate basic predictive testing:
- Single policy
- Simple scenario
- Clear outcome expectations

Each test follows the pattern:
1. Define scenario (using ScenarioBuilder)
2. Define policy
3. Define expected outcomes
4. Run test and verify
"""

import pytest
from policy_scenario import (
    PolicyScenarioTest,
    OutcomeExpectation,
    Range,
    Exact,
    ScenarioBuilder,
)


class TestFifoPolicy:
    """Simple tests for FIFO policy behavior."""

    def test_fifo_with_ample_liquidity_settles_all(self):
        """FIFO with ample liquidity should settle 100% of transactions."""

        # Scenario: Low arrival rate, high liquidity
        scenario = (
            ScenarioBuilder("AmpleLiquidity")
            .with_description("Low pressure, high liquidity scenario")
            .with_duration(50)
            .add_agent(
                "BANK_A",
                balance=10_000_000,  # $100k - plenty of liquidity
                arrival_rate=1.0,     # 1 arrival/tick
                arrival_amount_range=(50_000, 100_000),  # Small payments
                deadline_range=(10, 40),
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        # Policy: Simple FIFO
        policy = {"type": "Fifo"}

        # Expectations: Should settle everything with no violations
        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.95, max=1.0),  # Near perfect
            overdraft_violations=Exact(0),              # No overdrafts
            deadline_violations=Range(min=0, max=2),    # Minimal violations
            min_balance=Range(min=0),                   # Stay positive
        )

        # Run test
        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        # Verify
        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Test failed with {len(result.failures)} failures"

    def test_fifo_with_low_liquidity_builds_queue(self):
        """FIFO with low liquidity should build up queue."""

        # Scenario: High arrival rate, low liquidity
        scenario = (
            ScenarioBuilder("LowLiquidity")
            .with_description("High pressure, low liquidity")
            .with_duration(50)
            .add_agent(
                "BANK_A",
                balance=1_000_000,    # $10k - limited
                arrival_rate=3.0,      # 3 arrivals/tick - high pressure
                arrival_amount_range=(100_000, 200_000),
                deadline_range=(20, 50),
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        policy = {"type": "Fifo"}

        # Expectations: Queue should build up, lower settlement rate
        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.3, max=0.8),   # Degraded
            max_queue_depth=Range(min=10),              # Significant queue
            overdraft_violations=Exact(0),              # Still no overdraft
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Test failed: {result.detailed_report()}"


class TestLiquidityAwarePolicy:
    """Simple tests for LiquidityAware policy behavior."""

    def test_liquidity_aware_maintains_buffer_under_pressure(self):
        """LiquidityAware should maintain buffer despite high arrival rate."""

        # Scenario: High pressure that would drain FIFO
        scenario = (
            ScenarioBuilder("HighPressure")
            .with_description("High arrival rate stress test")
            .with_duration(100)
            .add_agent(
                "BANK_A",
                balance=5_000_000,    # $50k starting
                arrival_rate=4.0,      # High pressure
                arrival_amount_range=(150_000, 300_000),
                deadline_range=(10, 40),
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        # Policy: LiquidityAware with buffer target
        policy = {
            "type": "LiquidityAware",
            "target_buffer": 2_000_000,  # $20k buffer
            "urgency_threshold": 5,
        }

        # Expectations: Should protect buffer at cost of queue buildup
        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.60, max=1.0),   # May hold some payments
            min_balance=Range(min=0),                    # Stay positive
            overdraft_violations=Exact(0),               # No overdrafts
            max_queue_depth=Range(min=0, max=50),        # Queue may build
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Test failed: {result.detailed_report()}"

    def test_liquidity_aware_releases_urgent_payments(self):
        """LiquidityAware should release urgent payments even if buffer violated."""

        # Scenario: Urgent payments with low liquidity
        scenario = (
            ScenarioBuilder("UrgentPayments")
            .with_description("Short deadlines, low liquidity")
            .with_duration(50)
            .add_agent(
                "BANK_A",
                balance=1_500_000,    # $15k - tight
                arrival_rate=2.0,
                arrival_amount_range=(200_000, 400_000),
                deadline_range=(2, 8),  # Very urgent!
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        policy = {
            "type": "LiquidityAware",
            "target_buffer": 1_000_000,  # $10k buffer
            "urgency_threshold": 5,       # Release if deadline ≤ 5
        }

        # Expectations: Should settle urgent ones, fewer violations
        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.50, max=1.0),
            deadline_violations=Range(min=0, max=10),  # Some acceptable
            # Note: min_balance might dip below buffer due to urgency
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Test failed: {result.detailed_report()}"


class TestDeadlinePolicy:
    """Simple tests for Deadline-aware policy."""

    def test_deadline_policy_minimizes_violations(self):
        """DeadlinePolicy should minimize deadline violations."""

        # Scenario: Mixed deadlines with moderate liquidity
        scenario = (
            ScenarioBuilder("MixedDeadlines")
            .with_description("Wide range of deadlines")
            .with_duration(80)
            .add_agent(
                "BANK_A",
                balance=3_000_000,    # $30k
                arrival_rate=2.5,
                arrival_amount_range=(100_000, 250_000),
                deadline_range=(2, 30),  # Wide range
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        policy = {
            "type": "Deadline",
            "urgency_threshold": 5,
        }

        # Expectations: Fewer violations than FIFO would have
        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.60, max=1.0),
            deadline_violations=Range(min=0, max=8),  # Should be low
            overdraft_violations=Exact(0),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Test failed: {result.detailed_report()}"


class TestScenarioBuilder:
    """Test the ScenarioBuilder API itself."""

    def test_scenario_builder_creates_valid_config(self):
        """ScenarioBuilder should produce valid orchestrator config."""

        scenario = (
            ScenarioBuilder("TestScenario")
            .with_description("Test scenario")
            .with_duration(100)
            .with_ticks_per_day(50)
            .with_seed(12345)
            .add_agent("BANK_A", balance=1_000_000, arrival_rate=2.0)
            .add_agent("BANK_B", balance=2_000_000)
            .build()
        )

        # Verify scenario properties
        assert scenario.name == "TestScenario"
        assert scenario.description == "Test scenario"
        assert scenario.duration_ticks == 100
        assert scenario.ticks_per_day == 50
        assert scenario.seed == 12345
        assert len(scenario.agents) == 2

        # Convert to orchestrator config
        policy_configs = {
            "BANK_A": {"type": "Fifo"},
            "BANK_B": {"type": "Fifo"},
        }
        orch_config = scenario.to_orchestrator_config(policy_configs)

        # Verify config structure
        assert orch_config["ticks_per_day"] == 50
        assert orch_config["num_days"] == 2  # ceil(100/50)
        assert orch_config["rng_seed"] == 12345
        assert len(orch_config["agent_configs"]) == 2

        # Verify BANK_A has arrival config
        bank_a_config = next(
            c for c in orch_config["agent_configs"] if c["id"] == "BANK_A"
        )
        assert "arrival_config" in bank_a_config
        assert bank_a_config["arrival_config"]["rate_per_tick"] == 2.0

    def test_scenario_with_events(self):
        """ScenarioBuilder should support scenario events."""

        scenario = (
            ScenarioBuilder("CrisisScenario")
            .with_duration(200)
            .add_agent("BANK_A", balance=5_000_000, arrival_rate=2.0)
            .add_agent("BANK_B", balance=3_000_000)
            .add_collateral_adjustment(
                tick=50,
                agent_id="BANK_A",
                haircut_change=-0.2
            )
            .add_arrival_rate_change(
                tick=100,
                multiplier=2.0  # Global spike
            )
            .add_large_payment(
                tick=150,
                sender="BANK_A",
                receiver="BANK_B",
                amount=2_000_000
            )
            .build()
        )

        # Verify events
        assert len(scenario.events) == 3

        # Verify event types
        event_types = [e.event_type for e in scenario.events]
        assert "CollateralAdjustment" in event_types
        assert "GlobalArrivalRateChange" in event_types
        assert "CustomTransactionArrival" in event_types


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
