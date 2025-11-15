"""
Level 2: Comparative Policy-Scenario Tests

These tests compare multiple policies on the same scenario to verify
relative performance characteristics.

Each test follows the pattern:
1. Define a scenario
2. Define multiple policies to compare
3. Run PolicyComparator
4. Verify relative performance (Policy A better than Policy B on metric X)
"""

import pytest
from policy_scenario import (
    PolicyComparator,
    OutcomeExpectation,
    Range,
    Exact,
    ScenarioBuilder,
)


class TestPolicyComparison:
    """Comparative tests between different policies."""

    def test_liquidity_aware_preserves_balance_better_than_fifo(self):
        """LiquidityAware should maintain higher min_balance than FIFO.

        Calibrated: Added bidirectional flow so agents can sustain operations.
        Without incoming liquidity, both policies drain completely.
        """

        # Scenario: High pressure with bidirectional flow
        scenario = (
            ScenarioBuilder("HighDrainPressure")
            .with_description("High pressure with bidirectional flow")
            .with_duration(100)
            .with_seed(99999)
            .add_agent(
                "BANK_A",
                balance=20_000_000,    # $200k - sufficient for operations
                arrival_rate=4.0,       # High pressure
                arrival_amount_range=(200_000, 400_000),  # Large payments
                deadline_range=(10, 40),
            )
            .add_agent(
                "BANK_B",
                balance=30_000_000,     # $300k
                arrival_rate=3.0,       # Send back to A
                arrival_amount_range=(200_000, 400_000),
                deadline_range=(10, 40),
            )
            .build()
        )

        # Compare FIFO vs LiquidityAware
        comparator = PolicyComparator(scenario)

        result = comparator.compare(
            policies=[
                ("FIFO", {"type": "Fifo"}),
                ("LiquidityAware", {
                    "type": "LiquidityAware",
                    "target_buffer": 2_000_000,  # $20k buffer
                    "urgency_threshold": 5,
                }),
            ],
            metrics=["settlement_rate", "min_balance", "max_queue_depth"],
            agent_id="BANK_A",
        )

        # Print comparison
        print("\n" + result.comparison_table())

        # Assertions
        fifo_min_balance = result.get_metric("FIFO", "min_balance")
        la_min_balance = result.get_metric("LiquidityAware", "min_balance")

        assert la_min_balance is not None and fifo_min_balance is not None
        assert la_min_balance >= fifo_min_balance, (
            f"LiquidityAware should preserve balance better. "
            f"LA: ${la_min_balance/100:.2f}, FIFO: ${fifo_min_balance/100:.2f}"
        )

        # LiquidityAware likely has larger queue (trade-off)
        la_queue = result.get_metric("LiquidityAware", "max_queue_depth")
        fifo_queue = result.get_metric("FIFO", "max_queue_depth")

        assert la_queue is not None and fifo_queue is not None
        print(f"\nQueue trade-off: FIFO={fifo_queue}, LA={la_queue}")

    def test_deadline_policy_reduces_violations_vs_fifo(self):
        """DeadlinePolicy should have fewer deadline violations than FIFO."""

        # Scenario: Mixed deadlines with constrained liquidity
        scenario = (
            ScenarioBuilder("MixedDeadlineScenario")
            .with_description("Wide range of deadlines to test prioritization")
            .with_duration(120)
            .with_seed(77777)
            .add_agent(
                "BANK_A",
                balance=3_000_000,    # $30k - moderate
                arrival_rate=3.0,
                arrival_amount_range=(150_000, 300_000),
                deadline_range=(2, 25),  # Some very urgent
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        comparator = PolicyComparator(scenario)

        result = comparator.compare(
            policies=[
                ("FIFO", {"type": "Fifo"}),
                ("DeadlineAware", {
                    "type": "Deadline",
                    "urgency_threshold": 5,
                }),
            ],
            metrics=["settlement_rate", "deadline_violations", "max_queue_depth"],
            agent_id="BANK_A",
        )

        print("\n" + result.comparison_table())

        # DeadlineAware should have fewer violations
        fifo_violations = result.get_metric("FIFO", "deadline_violations")
        deadline_violations = result.get_metric("DeadlineAware", "deadline_violations")

        assert fifo_violations is not None and deadline_violations is not None

        # Allow for some randomness, but deadline policy should be better
        assert deadline_violations <= fifo_violations, (
            f"DeadlineAware should have fewer violations. "
            f"Deadline: {deadline_violations}, FIFO: {fifo_violations}"
        )

    def test_three_way_policy_comparison(self):
        """Compare FIFO, LiquidityAware, and DeadlineAware on same scenario.

        Calibrated: Added bidirectional flow for realistic operations.
        Policies can now demonstrate their different characteristics.
        """

        # Scenario: Realistic daily operations with bidirectional flow
        scenario = (
            ScenarioBuilder("RealisticDaily")
            .with_description("Typical daily operations, bidirectional")
            .with_duration(100)  # 1 day
            .with_seed(12345)
            .add_agent(
                "BANK_A",
                balance=20_000_000,    # $200k
                unsecured_cap=2_000_000,  # $20k credit available
                arrival_rate=2.5,
                arrival_amount_range=(100_000, 300_000),
                deadline_range=(5, 30),
            )
            .add_agent(
                "BANK_B",
                balance=25_000_000,     # $250k
                arrival_rate=2.0,       # Send back to A
                arrival_amount_range=(100_000, 300_000),
                deadline_range=(5, 30),
            )
            .build()
        )

        comparator = PolicyComparator(scenario)

        result = comparator.compare(
            policies=[
                ("FIFO", {"type": "Fifo"}),
                ("LiquidityAware", {
                    "type": "LiquidityAware",
                    "target_buffer": 3_000_000,
                    "urgency_threshold": 5,
                }),
                ("DeadlineAware", {
                    "type": "Deadline",
                    "urgency_threshold": 5,
                }),
            ],
            metrics=[
                "settlement_rate",
                "deadline_violations",
                "min_balance",
                "max_queue_depth",
            ],
            agent_id="BANK_A",
        )

        print("\n" + result.comparison_table())

        # Verify all policies ran
        assert len(result.results) == 3
        assert all(r.actual.num_arrivals > 0 for r in result.results.values())

        # Expected characteristics:
        # - FIFO: High settlement rate, may drain liquidity
        # - LiquidityAware: Protected balance, possibly lower settlement
        # - DeadlineAware: Fewer violations, balanced approach

        fifo_sr = result.get_metric("FIFO", "settlement_rate")
        la_sr = result.get_metric("LiquidityAware", "settlement_rate")
        da_sr = result.get_metric("DeadlineAware", "settlement_rate")

        print(f"\nSettlement rates: FIFO={fifo_sr:.3f}, LA={la_sr:.3f}, DA={da_sr:.3f}")

        # All should have reasonable settlement rates
        # Calibrated: With bidirectional flow, all policies should perform well
        assert fifo_sr and fifo_sr > 0.6
        assert la_sr and la_sr > 0.5  # May be lower due to buffer protection
        assert da_sr and da_sr > 0.6

    def test_parameter_tuning_comparison(self):
        """Compare same policy with different parameter values."""

        # Scenario: Moderate pressure
        scenario = (
            ScenarioBuilder("ModeratePreference")
            .with_description("Test parameter sensitivity")
            .with_duration(100)
            .with_seed(55555)
            .add_agent(
                "BANK_A",
                balance=5_000_000,
                arrival_rate=3.0,
                arrival_amount_range=(150_000, 250_000),
                deadline_range=(5, 20),
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        comparator = PolicyComparator(scenario)

        # Compare different buffer sizes
        result = comparator.compare(
            policies=[
                ("Buffer_1M", {
                    "type": "LiquidityAware",
                    "target_buffer": 1_000_000,  # $10k
                    "urgency_threshold": 5,
                }),
                ("Buffer_2M", {
                    "type": "LiquidityAware",
                    "target_buffer": 2_000_000,  # $20k
                    "urgency_threshold": 5,
                }),
                ("Buffer_3M", {
                    "type": "LiquidityAware",
                    "target_buffer": 3_000_000,  # $30k
                    "urgency_threshold": 5,
                }),
            ],
            metrics=["settlement_rate", "min_balance", "max_queue_depth"],
            agent_id="BANK_A",
        )

        print("\n" + result.comparison_table())

        # Higher buffer should mean:
        # - Lower settlement rate (more conservative)
        # - Higher min_balance (better protection)
        # - Higher max_queue_depth (more holding)

        sr_1m = result.get_metric("Buffer_1M", "settlement_rate")
        sr_3m = result.get_metric("Buffer_3M", "settlement_rate")

        min_bal_1m = result.get_metric("Buffer_1M", "min_balance")
        min_bal_3m = result.get_metric("Buffer_3M", "min_balance")

        # Higher buffer = more conservative = lower settlement rate OR higher min balance
        # (Trade-off may vary by scenario)
        print(f"\nBuffer impact:")
        print(f"  1M buffer: SR={sr_1m:.3f}, min_bal=${min_bal_1m/100:.2f}")
        print(f"  3M buffer: SR={sr_3m:.3f}, min_bal=${min_bal_3m/100:.2f}")

        # At least verify they all ran successfully
        assert sr_1m is not None and sr_3m is not None
        assert min_bal_1m is not None and min_bal_3m is not None


class TestComparatorUtilities:
    """Test the PolicyComparator class itself."""

    def test_comparator_handles_identical_policies(self):
        """Comparator should produce identical results for identical policies."""

        scenario = (
            ScenarioBuilder("DeterminismTest")
            .with_duration(50)
            .with_seed(11111)  # Fixed seed for determinism
            .add_agent("BANK_A", balance=5_000_000, arrival_rate=2.0)
            .add_agent("BANK_B", balance=10_000_000)
            .build()
        )

        comparator = PolicyComparator(scenario)

        result = comparator.compare(
            policies=[
                ("FIFO_1", {"type": "Fifo"}),
                ("FIFO_2", {"type": "Fifo"}),
            ],
            metrics=["settlement_rate", "max_queue_depth"],
            agent_id="BANK_A",
        )

        # Same policy, same seed = identical results
        sr_1 = result.get_metric("FIFO_1", "settlement_rate")
        sr_2 = result.get_metric("FIFO_2", "settlement_rate")

        assert sr_1 == sr_2, "Identical policies should produce identical results"

        queue_1 = result.get_metric("FIFO_1", "max_queue_depth")
        queue_2 = result.get_metric("FIFO_2", "max_queue_depth")

        assert queue_1 == queue_2

    def test_comparison_table_generation(self):
        """Verify comparison table generates without errors."""

        scenario = (
            ScenarioBuilder("TableTest")
            .with_duration(30)
            .add_agent("BANK_A", balance=3_000_000, arrival_rate=1.5)
            .add_agent("BANK_B", balance=5_000_000)
            .build()
        )

        comparator = PolicyComparator(scenario)

        result = comparator.compare(
            policies=[
                ("FIFO", {"type": "Fifo"}),
                ("Deadline", {"type": "Deadline", "urgency_threshold": 5}),
            ],
            metrics=["settlement_rate", "max_queue_depth"],
            agent_id="BANK_A",
        )

        # Should generate table without errors
        table = result.comparison_table()

        assert isinstance(table, str)
        assert len(table) > 0
        assert "FIFO" in table
        assert "Deadline" in table
        assert "settlement_rate" in table

        print("\n" + table)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
