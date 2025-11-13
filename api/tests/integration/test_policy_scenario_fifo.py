"""
Level 1: FIFO Policy Tests

Tests for FIFO (First-In-First-Out) policy across various scenarios.
FIFO is the baseline policy with no intelligence - processes in arrival order.

Expected characteristics:
- Good performance with ample liquidity
- Degrades under pressure (no prioritization)
- High deadline violations (no deadline awareness)
- No liquidity management

Test coverage:
1. AmpleLiquidity - Near perfect settlement
2. ModerateActivity - Good settlement with manageable queue
3. HighPressure - Significant degradation, large queue
4. TightDeadlines - High deadline violations
5. FlashDrain - Recovery after spike
6. MultipleAgents - System-wide stability
7. EndOfDayRush - EOD handling without adaptation
8. LiquidityDrain - Progressive depletion
"""

import pytest
from policy_scenario import (
    PolicyScenarioTest,
    OutcomeExpectation,
    Range,
    Exact,
    ScenarioBuilder,
)


class TestFifoPolicyBaseline:
    """Baseline FIFO tests - optimal conditions."""

    def test_fifo_ample_liquidity_near_perfect_settlement(self):
        """
        Policy: FIFO
        Scenario: AmpleLiquidity
        Expected: Settlement rate 0.95-1.0, minimal queue, near-zero violations

        With 10× daily volume liquidity and low arrival rate, FIFO should
        achieve near-perfect settlement with minimal queuing.
        """
        scenario = (
            ScenarioBuilder("AmpleLiquidity")
            .with_description("Low pressure baseline - FIFO should excel")
            .with_duration(100)
            .with_seed(12345)
            .add_agent(
                "BANK_A",
                balance=10_000_000,  # $100k - high liquidity
                arrival_rate=1.0,     # 1 tx/tick - low pressure
                arrival_amount_range=(50_000, 150_000),  # $500-$1,500
                deadline_range=(15, 35),
            )
            .add_agent("BANK_B", balance=20_000_000)  # Receiver
            .build()
        )

        policy = {"type": "Fifo"}

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.95, max=1.0),
            max_queue_depth=Range(min=0, max=5),
            deadline_violations=Range(min=0, max=2),
            overdraft_violations=Exact(0),
            min_balance=Range(min=0),  # Should stay positive
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"FIFO should achieve near-perfect settlement with ample liquidity"

    def test_fifo_moderate_activity_good_settlement(self):
        """
        Policy: FIFO
        Scenario: ModerateActivity
        Expected: Settlement rate 0.85-0.95, queue 3-10, manageable violations

        With balanced liquidity (3-5× daily volume) and moderate arrival rate,
        FIFO should maintain good performance with some queueing.
        """
        scenario = (
            ScenarioBuilder("ModerateActivity")
            .with_description("Balanced scenario - FIFO should perform well")
            .with_duration(100)
            .with_seed(54321)
            .add_agent(
                "BANK_A",
                balance=6_000_000,   # $60k - moderate liquidity
                arrival_rate=2.5,     # 2.5 tx/tick - moderate pressure
                arrival_amount_range=(100_000, 250_000),  # $1k-$2.5k
                deadline_range=(12, 30),
            )
            .add_agent("BANK_B", balance=15_000_000)
            .build()
        )

        policy = {"type": "Fifo"}

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.85, max=0.95),
            max_queue_depth=Range(min=3, max=10),
            deadline_violations=Range(min=0, max=8),
            overdraft_violations=Exact(0),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"FIFO should maintain good settlement rate under moderate activity"


class TestFifoPolicyPressure:
    """FIFO under liquidity and deadline pressure."""

    def test_fifo_high_pressure_significant_degradation(self):
        """
        Policy: FIFO
        Scenario: HighPressure
        Expected: Settlement rate 0.40-0.70, large queue 15-40, many violations

        With limited liquidity (1.5-2× daily volume) and high arrival rate,
        FIFO should show significant degradation with large queue buildup.
        """
        scenario = (
            ScenarioBuilder("HighPressure")
            .with_description("High arrival rate stress test")
            .with_duration(100)
            .with_seed(99999)
            .add_agent(
                "BANK_A",
                balance=5_000_000,   # $50k - limited
                arrival_rate=5.0,     # 5 tx/tick - high pressure
                arrival_amount_range=(150_000, 300_000),  # $1.5k-$3k - large
                deadline_range=(10, 40),
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        policy = {"type": "Fifo"}

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.40, max=0.70),
            max_queue_depth=Range(min=15, max=40),
            deadline_violations=Range(min=5, max=25),  # Significant violations
            overdraft_violations=Exact(0),  # No credit, so no overdraft
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"FIFO should degrade under high pressure but remain stable"

    def test_fifo_tight_deadlines_high_violation_rate(self):
        """
        Policy: FIFO
        Scenario: TightDeadlines
        Expected: Settlement rate 0.50-0.80, violations 15-35% of arrivals

        With tight deadlines (2-8 ticks) and no deadline awareness,
        FIFO should have high deadline violation rates.
        """
        scenario = (
            ScenarioBuilder("TightDeadlines")
            .with_description("Short deadlines expose FIFO's lack of prioritization")
            .with_duration(80)
            .with_seed(77777)
            .add_agent(
                "BANK_A",
                balance=4_000_000,   # $40k - constrained
                arrival_rate=3.0,     # 3 tx/tick
                arrival_amount_range=(120_000, 280_000),
                deadline_range=(2, 8),  # Very tight!
            )
            .add_agent("BANK_B", balance=18_000_000)
            .build()
        )

        policy = {"type": "Fifo"}

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.50, max=0.80),
            # Expect ~240 arrivals (80 ticks × 3 rate)
            # High violations due to no prioritization
            deadline_violations=Range(min=20, max=80),
            max_queue_depth=Range(min=8, max=20),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"FIFO should show high deadline violations without prioritization"

    def test_fifo_liquidity_drain_progressive_depletion(self):
        """
        Policy: FIFO
        Scenario: LiquidityDrain
        Expected: Settlement rate 0.45-0.70, progressive queue growth

        Sustained high arrivals with no incoming payments should cause
        progressive liquidity depletion and queue growth.
        """
        scenario = (
            ScenarioBuilder("LiquidityDrain")
            .with_description("Sustained outflow - tests FIFO resilience")
            .with_duration(150)
            .with_seed(33333)
            .add_agent(
                "BANK_A",
                balance=8_000_000,   # $80k starting
                arrival_rate=4.0,     # High sustained rate
                arrival_amount_range=(180_000, 320_000),
                deadline_range=(15, 35),
            )
            .add_agent("BANK_B", balance=30_000_000)  # Only receives
            .build()
        )

        policy = {"type": "Fifo"}

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.45, max=0.70),
            max_queue_depth=Range(min=25, max=60),  # Progressive buildup
            min_balance=Range(min=0),  # Should stay non-negative
            # Balance should deplete significantly
            avg_balance=Range(min=0, max=4_000_000),  # <50% of starting
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"FIFO should handle sustained drain without crash"


class TestFifoPolicyScenarioEvents:
    """FIFO with scenario events."""

    def test_fifo_flash_drain_spike_and_recovery(self):
        """
        Policy: FIFO
        Scenario: FlashDrain
        Expected: Handle spike, recover afterward

        Sudden spike in arrivals followed by return to normal.
        FIFO should handle spike with queue buildup then recover.
        """
        scenario = (
            ScenarioBuilder("FlashDrain")
            .with_description("Sudden spike tests shock resilience")
            .with_duration(100)
            .with_seed(11111)
            .add_agent(
                "BANK_A",
                balance=6_000_000,   # $60k
                arrival_rate=1.5,     # Normal rate initially
                arrival_amount_range=(100_000, 200_000),
                deadline_range=(10, 30),
            )
            .add_agent("BANK_B", balance=20_000_000)
            # Spike: 3× multiplier at tick 30
            .add_arrival_rate_change(tick=30, agent_id="BANK_A", multiplier=3.0)
            # Large payment shock at tick 40
            .add_large_payment(
                tick=40,
                sender="BANK_A",
                receiver="BANK_B",
                amount=2_000_000,
                deadline_offset=15
            )
            # Recovery: back to normal at tick 60
            .add_arrival_rate_change(tick=60, agent_id="BANK_A", multiplier=1.0)
            .build()
        )

        policy = {"type": "Fifo"}

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.60, max=0.85),
            max_queue_depth=Range(min=12, max=35),
            # Should handle events without crashing
            overdraft_violations=Exact(0),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"FIFO should handle flash drain and recover"

    def test_fifo_end_of_day_rush_no_adaptation(self):
        """
        Policy: FIFO
        Scenario: EndOfDayRush
        Expected: No special EOD handling, standard degradation

        FIFO has no time awareness, so should treat EOD rush like
        any other high-pressure period.
        """
        scenario = (
            ScenarioBuilder("EndOfDayRush")
            .with_description("EOD rush - FIFO has no time adaptation")
            .with_duration(100)
            .with_ticks_per_day(100)  # Entire scenario is 1 "day"
            .with_seed(88888)
            .add_agent(
                "BANK_A",
                balance=7_000_000,   # $70k
                arrival_rate=2.0,     # Normal rate
                arrival_amount_range=(120_000, 240_000),
                deadline_range=(8, 25),
            )
            .add_agent("BANK_B", balance=20_000_000)
            # EOD rush: 3× spike at tick 80 (80% of day)
            .add_arrival_rate_change(tick=80, agent_id="BANK_A", multiplier=3.0)
            .build()
        )

        policy = {"type": "Fifo"}

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.65, max=0.88),
            max_queue_depth=Range(min=10, max=28),
            # EOD penalties may occur
            deadline_violations=Range(min=5, max=20),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"FIFO should handle EOD rush without special behavior"


class TestFifoPolicyMultiAgent:
    """FIFO in multi-agent scenarios."""

    def test_fifo_multiple_agents_system_stability(self):
        """
        Policy: FIFO
        Scenario: MultipleAgentsNormal
        Expected: Fair resource allocation, system-wide stability

        With 3 agents all using FIFO, system should remain stable
        with balanced resource usage.
        """
        scenario = (
            ScenarioBuilder("MultipleAgentsNormal")
            .with_description("3 agents with balanced activity")
            .with_duration(100)
            .with_seed(55555)
            .add_agent(
                "BANK_A",
                balance=8_000_000,
                arrival_rate=2.0,
                arrival_amount_range=(100_000, 250_000),
                deadline_range=(12, 30),
                counterparty_weights={"BANK_B": 0.6, "BANK_C": 0.4}
            )
            .add_agent(
                "BANK_B",
                balance=6_000_000,
                arrival_rate=1.8,
                arrival_amount_range=(90_000, 220_000),
                deadline_range=(12, 30),
                counterparty_weights={"BANK_A": 0.5, "BANK_C": 0.5}
            )
            .add_agent(
                "BANK_C",
                balance=10_000_000,
                arrival_rate=1.5,
                arrival_amount_range=(120_000, 280_000),
                deadline_range=(12, 30),
                counterparty_weights={"BANK_A": 0.5, "BANK_B": 0.5}
            )
            .build()
        )

        policy = {"type": "Fifo"}

        # Test BANK_A (representative)
        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.75, max=0.95),
            max_queue_depth=Range(min=3, max=15),
            overdraft_violations=Exact(0),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"FIFO should maintain stability in multi-agent system"

    def test_fifo_determinism_identical_seeds(self):
        """
        Policy: FIFO
        Scenario: Same scenario, same seed
        Expected: Identical results

        Critical test: Same seed must produce identical results.
        This validates determinism requirement.
        """
        scenario = (
            ScenarioBuilder("DeterminismTest")
            .with_description("Determinism validation")
            .with_duration(50)
            .with_seed(12345)  # Fixed seed
            .add_agent(
                "BANK_A",
                balance=5_000_000,
                arrival_rate=2.5,
                arrival_amount_range=(100_000, 200_000),
                deadline_range=(10, 25),
            )
            .add_agent("BANK_B", balance=10_000_000)
            .build()
        )

        policy = {"type": "Fifo"}

        # Run twice
        test1 = PolicyScenarioTest(policy, scenario, OutcomeExpectation(), agent_id="BANK_A")
        result1 = test1.run()

        test2 = PolicyScenarioTest(policy, scenario, OutcomeExpectation(), agent_id="BANK_A")
        result2 = test2.run()

        # Results must be identical
        assert result1.actual.settlement_rate == result2.actual.settlement_rate
        assert result1.actual.max_queue_depth == result2.actual.max_queue_depth
        assert result1.actual.num_settlements == result2.actual.num_settlements
        assert result1.actual.deadline_violations == result2.actual.deadline_violations

        print(f"✓ Determinism verified: Both runs produced identical results")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
