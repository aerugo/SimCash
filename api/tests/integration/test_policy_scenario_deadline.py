"""
Level 1: Deadline Policy Tests

Tests for Deadline policy across various scenarios.
Deadline policy prioritizes payments by deadline urgency, releasing
those closest to deadline first to minimize deadline violations.

Expected characteristics:
- Minimizes deadline violations (vs FIFO)
- Strategic prioritization (urgent payments first)
- Good settlement rate with deadline awareness
- May sacrifice liquidity for urgency
- Better performance on tight deadline scenarios

Test coverage:
1. AmpleLiquidity - Excellent settlement with minimal violations
2. TightDeadlines - Minimal violations through prioritization
3. MixedDeadlines - Strategic handling of varied urgency
4. DeadlineWindowChanges - Adapts to regulatory changes
5. HighPressure - Prioritization under pressure
6-10. Parameter variations: urgency threshold sweep (2, 3, 5, 7, 10)
"""

import pytest
from policy_scenario import (
    PolicyScenarioTest,
    PolicyComparator,
    OutcomeExpectation,
    Range,
    Exact,
    ScenarioBuilder,
)


class TestDeadlinePolicyBaseline:
    """Baseline Deadline tests - optimal conditions."""

    def test_deadline_ample_liquidity_excellent_settlement(self):
        """
        Policy: Deadline (urgency=5)
        Scenario: AmpleLiquidity
        Expected: Settlement rate 0.95-1.0, near-zero violations

        With ample liquidity, Deadline should perform as well as FIFO
        while being ready to prioritize if needed.
        """
        scenario = (
            ScenarioBuilder("AmpleLiquidity")
            .with_description("Ample liquidity - Deadline should excel")
            .with_duration(100)
            .with_seed(12345)
            .add_agent(
                "BANK_A",
                balance=10_000_000,  # $100k
                arrival_rate=1.0,
                arrival_amount_range=(50_000, 150_000),
                deadline_range=(15, 35),
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        policy = {
            "type": "Deadline",
            "urgency_threshold": 5,
        }

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.95, max=1.0),
            max_queue_depth=Range(min=0, max=5),
            deadline_violations=Range(min=0, max=2),
            overdraft_violations=Exact(0),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Deadline should achieve excellent settlement with ample liquidity"


class TestDeadlinePolicyDeadlinePressure:
    """Deadline policy under deadline pressure."""

    def test_deadline_tight_deadlines_minimal_violations(self):
        """
        Policy: Deadline (urgency=5)
        Scenario: TightDeadlines
        Expected: Settlement rate 0.70-0.90, violations 30-50% lower than FIFO

        This is where Deadline policy shines. With deadlines 2-8 ticks,
        urgency-based prioritization should significantly reduce violations.
        """
        scenario = (
            ScenarioBuilder("TightDeadlines")
            .with_description("Tight deadlines - Deadline policy advantage")
            .with_duration(80)
            .with_seed(77777)
            .add_agent(
                "BANK_A",
                balance=4_000_000,   # $40k
                arrival_rate=3.0,
                arrival_amount_range=(120_000, 280_000),
                deadline_range=(2, 8),  # Very tight
            )
            .add_agent("BANK_B", balance=18_000_000)
            .build()
        )

        policy = {
            "type": "Deadline",
            "urgency_threshold": 5,
        }

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.70, max=0.90),
            # Expect ~240 arrivals, deadline violations should be low
            deadline_violations=Range(min=0, max=20),  # Much better than FIFO (20-80)
            max_queue_depth=Range(min=5, max=15),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Deadline should minimize violations with tight deadlines"

    def test_deadline_mixed_deadlines_strategic_prioritization(self):
        """
        Policy: Deadline (urgency=5)
        Scenario: MixedDeadlines
        Expected: Settlement rate 0.80-0.95, strategic prioritization

        With wide deadline range (5-30 ticks), policy should strategically
        prioritize urgent ones while processing others when possible.
        """
        scenario = (
            ScenarioBuilder("MixedDeadlines")
            .with_description("Mixed deadlines test strategic prioritization")
            .with_duration(100)
            .with_seed(55555)
            .add_agent(
                "BANK_A",
                balance=5_000_000,   # $50k
                arrival_rate=2.8,
                arrival_amount_range=(120_000, 260_000),
                deadline_range=(5, 30),  # Wide range
            )
            .add_agent("BANK_B", balance=18_000_000)
            .build()
        )

        policy = {
            "type": "Deadline",
            "urgency_threshold": 5,
        }

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.80, max=0.95),
            deadline_violations=Range(min=0, max=10),  # Low violations
            max_queue_depth=Range(min=3, max=12),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Deadline should handle mixed deadlines strategically"

    def test_deadline_deadline_window_changes_adaptation(self):
        """
        Policy: Deadline (urgency=5)
        Scenario: DeadlineWindowChanges
        Expected: Settlement rate 0.65-0.85, adapts to regulatory change

        Regulatory change tightens deadlines mid-simulation.
        Policy should adapt to new deadline environment.
        """
        scenario = (
            ScenarioBuilder("DeadlineWindowChanges")
            .with_description("Regulatory deadline tightening")
            .with_duration(150)
            .with_seed(66666)
            .add_agent(
                "BANK_A",
                balance=5_000_000,   # $50k
                arrival_rate=2.5,
                arrival_amount_range=(130_000, 270_000),
                deadline_range=(20, 40),  # Initially relaxed
            )
            .add_agent("BANK_B", balance=18_000_000)
            # Regulatory change at tick 75: deadlines tighten
            .add_event(
                tick=75,
                event_type="DeadlineWindowChange",
                new_min=10,
                new_max=20
            )
            .build()
        )

        policy = {
            "type": "Deadline",
            "urgency_threshold": 5,
        }

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.65, max=0.85),
            # After tick 75, more payments will be urgent
            deadline_violations=Range(min=5, max=25),
            max_queue_depth=Range(min=5, max=20),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Deadline should adapt to deadline window changes"


class TestDeadlinePolicyLiquidityPressure:
    """Deadline policy under liquidity pressure."""

    def test_deadline_high_pressure_prioritization(self):
        """
        Policy: Deadline (urgency=5)
        Scenario: HighPressure
        Expected: Settlement rate 0.55-0.75, prioritization under pressure

        Under high pressure, Deadline should still prioritize urgent payments
        even with constrained liquidity.
        """
        scenario = (
            ScenarioBuilder("HighPressure")
            .with_description("High pressure with deadline prioritization")
            .with_duration(100)
            .with_seed(99999)
            .add_agent(
                "BANK_A",
                balance=5_000_000,   # $50k - limited
                arrival_rate=5.0,
                arrival_amount_range=(150_000, 300_000),
                deadline_range=(10, 40),  # Mixed urgency
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        policy = {
            "type": "Deadline",
            "urgency_threshold": 5,
        }

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.55, max=0.75),
            deadline_violations=Range(min=10, max=35),  # Better than FIFO despite pressure
            max_queue_depth=Range(min=15, max=40),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Deadline should prioritize even under high pressure"


class TestDeadlinePolicyParameterVariations:
    """Test Deadline with different urgency thresholds."""

    def test_deadline_urgency_2_very_strict(self):
        """
        Policy: Deadline (urgency=2)
        Scenario: MixedDeadlines
        Expected: Only very urgent (≤2 ticks) get priority

        Very strict urgency means fewer payments prioritized.
        May have more violations than balanced threshold.
        """
        scenario = (
            ScenarioBuilder("MixedDeadlines")
            .with_description("Test urgency=2 - very strict")
            .with_duration(100)
            .with_seed(30001)
            .add_agent(
                "BANK_A",
                balance=5_000_000,
                arrival_rate=2.8,
                arrival_amount_range=(120_000, 260_000),
                deadline_range=(5, 30),
            )
            .add_agent("BANK_B", balance=18_000_000)
            .build()
        )

        policy = {
            "type": "Deadline",
            "urgency_threshold": 2,  # Very strict
        }

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.70, max=0.90),
            deadline_violations=Range(min=5, max=20),
            max_queue_depth=Range(min=5, max=15),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Urgency=2 should be very strict"

    def test_deadline_urgency_3_strict(self):
        """
        Policy: Deadline (urgency=3)
        Scenario: MixedDeadlines
        Expected: Strict prioritization (≤3 ticks)
        """
        scenario = (
            ScenarioBuilder("MixedDeadlines")
            .with_description("Test urgency=3 - strict")
            .with_duration(100)
            .with_seed(30001)  # Same seed for comparison
            .add_agent(
                "BANK_A",
                balance=5_000_000,
                arrival_rate=2.8,
                arrival_amount_range=(120_000, 260_000),
                deadline_range=(5, 30),
            )
            .add_agent("BANK_B", balance=18_000_000)
            .build()
        )

        policy = {
            "type": "Deadline",
            "urgency_threshold": 3,
        }

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.75, max=0.92),
            deadline_violations=Range(min=3, max=15),
            max_queue_depth=Range(min=4, max=13),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Urgency=3 should be strict"

    def test_deadline_urgency_5_balanced(self):
        """
        Policy: Deadline (urgency=5)
        Scenario: MixedDeadlines
        Expected: Balanced prioritization (≤5 ticks)

        This is our baseline urgency threshold.
        """
        scenario = (
            ScenarioBuilder("MixedDeadlines")
            .with_description("Test urgency=5 - balanced")
            .with_duration(100)
            .with_seed(30001)  # Same seed for comparison
            .add_agent(
                "BANK_A",
                balance=5_000_000,
                arrival_rate=2.8,
                arrival_amount_range=(120_000, 260_000),
                deadline_range=(5, 30),
            )
            .add_agent("BANK_B", balance=18_000_000)
            .build()
        )

        policy = {
            "type": "Deadline",
            "urgency_threshold": 5,  # Balanced (baseline)
        }

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.80, max=0.95),
            deadline_violations=Range(min=0, max=10),
            max_queue_depth=Range(min=3, max=12),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Urgency=5 should be balanced"

    def test_deadline_urgency_7_relaxed(self):
        """
        Policy: Deadline (urgency=7)
        Scenario: MixedDeadlines
        Expected: Relaxed prioritization (≤7 ticks)

        More payments considered urgent = more aggressive prioritization.
        """
        scenario = (
            ScenarioBuilder("MixedDeadlines")
            .with_description("Test urgency=7 - relaxed")
            .with_duration(100)
            .with_seed(30001)  # Same seed for comparison
            .add_agent(
                "BANK_A",
                balance=5_000_000,
                arrival_rate=2.8,
                arrival_amount_range=(120_000, 260_000),
                deadline_range=(5, 30),
            )
            .add_agent("BANK_B", balance=18_000_000)
            .build()
        )

        policy = {
            "type": "Deadline",
            "urgency_threshold": 7,
        }

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.82, max=0.97),
            deadline_violations=Range(min=0, max=8),  # Fewer violations
            max_queue_depth=Range(min=2, max=10),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Urgency=7 should be relaxed"

    def test_deadline_urgency_10_very_relaxed(self):
        """
        Policy: Deadline (urgency=10)
        Scenario: MixedDeadlines
        Expected: Very relaxed prioritization (≤10 ticks)

        Almost all payments in this scenario will be considered urgent.
        Should have minimal violations.
        """
        scenario = (
            ScenarioBuilder("MixedDeadlines")
            .with_description("Test urgency=10 - very relaxed")
            .with_duration(100)
            .with_seed(30001)  # Same seed for comparison
            .add_agent(
                "BANK_A",
                balance=5_000_000,
                arrival_rate=2.8,
                arrival_amount_range=(120_000, 260_000),
                deadline_range=(5, 30),
            )
            .add_agent("BANK_B", balance=18_000_000)
            .build()
        )

        policy = {
            "type": "Deadline",
            "urgency_threshold": 10,
        }

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.85, max=1.0),
            deadline_violations=Range(min=0, max=5),  # Minimal violations
            max_queue_depth=Range(min=1, max=8),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"Urgency=10 should be very relaxed"


class TestDeadlinePolicyComparisons:
    """Comparative tests to validate Deadline characteristics."""

    def test_deadline_vs_fifo_violation_reduction(self):
        """
        Comparison: Deadline vs FIFO
        Scenario: TightDeadlines
        Metric: deadline_violations
        Expected: Deadline should have significantly fewer violations

        This validates Deadline's core value proposition.
        """
        scenario = (
            ScenarioBuilder("TightDeadlines")
            .with_description("Compare deadline violation rates")
            .with_duration(80)
            .with_seed(77777)
            .add_agent(
                "BANK_A",
                balance=4_000_000,
                arrival_rate=3.0,
                arrival_amount_range=(120_000, 280_000),
                deadline_range=(2, 8),
            )
            .add_agent("BANK_B", balance=18_000_000)
            .build()
        )

        comparator = PolicyComparator(scenario)

        result = comparator.compare(
            policies=[
                ("FIFO", {"type": "Fifo"}),
                ("Deadline", {"type": "Deadline", "urgency_threshold": 5}),
            ],
            metrics=["settlement_rate", "deadline_violations", "max_queue_depth"],
            agent_id="BANK_A",
        )

        print("\n" + result.comparison_table())

        fifo_violations = result.get_metric("FIFO", "deadline_violations")
        deadline_violations = result.get_metric("Deadline", "deadline_violations")

        assert fifo_violations is not None and deadline_violations is not None

        # Deadline should have fewer violations
        reduction = fifo_violations - deadline_violations
        reduction_pct = (reduction / max(fifo_violations, 1)) * 100

        print(f"\nViolation reduction: {reduction} ({reduction_pct:.1f}% improvement)")

        assert deadline_violations <= fifo_violations, (
            f"Deadline should have fewer violations. "
            f"Deadline: {deadline_violations}, FIFO: {fifo_violations}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
