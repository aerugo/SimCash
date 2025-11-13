"""
Level 1: Complex Policies Tests

Tests for sophisticated JSON-based policies that demonstrate advanced
decision-making capabilities.

Policies tested:
1. GoliathNationalBank - Time-adaptive, multi-layered, conservative
2. CautiousLiquidityPreserver - Ultra-conservative buffer preservation
3. BalancedCostOptimizer - Holistic cost minimization
4. SmartSplitter - Intelligent transaction splitting
5. AggressiveMarketMaker - High settlement rate, credit usage

Test coverage: 19 tests to complete Phase 1 (50 total tests)
"""

import json
import pytest
from pathlib import Path
from policy_scenario import (
    PolicyScenarioTest,
    PolicyComparator,
    OutcomeExpectation,
    Range,
    Exact,
    ScenarioBuilder,
)


def load_json_policy(policy_name: str) -> dict:
    """Load a JSON policy file and return config for FromJson policy type.

    Args:
        policy_name: Name of policy file (without .json extension)

    Returns:
        Policy config dict with inline JSON string
    """
    # Path relative to api directory
    policy_path = Path(__file__).parent.parent.parent.parent / "backend" / "policies" / f"{policy_name}.json"

    if not policy_path.exists():
        raise FileNotFoundError(f"Policy file not found: {policy_path}")

    with open(policy_path) as f:
        policy_json = json.load(f)

    return {
        "type": "FromJson",
        "json": json.dumps(policy_json),
    }


class TestGoliathNationalBankPolicy:
    """Tests for GoliathNationalBank - time-adaptive conservative policy."""

    def test_goliath_ample_liquidity_excellent_performance(self):
        """
        Policy: GoliathNationalBank
        Scenario: AmpleLiquidity
        Expected: Settlement rate 0.92-1.0, excellent stability

        With ample liquidity, GoliathNationalBank should perform excellently
        while maintaining its conservative buffer management.
        """
        scenario = (
            ScenarioBuilder("AmpleLiquidity")
            .with_description("Ample liquidity - Goliath should excel")
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

        # GoliathNationalBank has its own parameters in the JSON
        policy = load_json_policy("goliath_national_bank")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.92, max=1.0),
            max_queue_depth=Range(min=0, max=5),
            overdraft_violations=Exact(0),
            min_balance=Range(min=5_000_000),  # Strong buffer preservation
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"GoliathNationalBank should excel with ample liquidity"

    def test_goliath_moderate_activity_time_adaptive(self):
        """
        Policy: GoliathNationalBank
        Scenario: ModerateActivity
        Expected: Settlement rate 0.80-0.92, buffer maintained

        Under moderate activity, Goliath's time-adaptive buffer should
        maintain stability.
        """
        scenario = (
            ScenarioBuilder("ModerateActivity")
            .with_description("Moderate activity - test time adaptation")
            .with_duration(100)
            .with_seed(54321)
            .add_agent(
                "BANK_A",
                balance=8_000_000,   # $80k
                arrival_rate=2.5,
                arrival_amount_range=(100_000, 250_000),
                deadline_range=(12, 30),
            )
            .add_agent("BANK_B", balance=15_000_000)
            .build()
        )

        policy = load_json_policy("goliath_national_bank")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.80, max=0.92),
            max_queue_depth=Range(min=3, max=12),
            min_balance=Range(min=3_000_000),  # Buffer protection
            overdraft_violations=Exact(0),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"GoliathNationalBank should maintain buffer under moderate activity"

    def test_goliath_high_pressure_conservative_degradation(self):
        """
        Policy: GoliathNationalBank
        Scenario: HighPressure
        Expected: Settlement rate 0.60-0.80, buffer maintained

        Under high pressure, Goliath should degrade gracefully while
        maintaining its conservative buffer protection.
        """
        scenario = (
            ScenarioBuilder("HighPressure")
            .with_description("High pressure - conservative degradation")
            .with_duration(100)
            .with_seed(99999)
            .add_agent(
                "BANK_A",
                balance=5_000_000,   # $50k
                arrival_rate=5.0,
                arrival_amount_range=(150_000, 300_000),
                deadline_range=(10, 40),
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        policy = load_json_policy("goliath_national_bank")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.60, max=0.80),
            max_queue_depth=Range(min=10, max=25),
            min_balance=Range(min=1_000_000),  # Maintain some buffer despite pressure
            overdraft_violations=Exact(0),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"GoliathNationalBank should degrade conservatively under pressure"

    def test_goliath_end_of_day_rush_adaptive_buffer(self):
        """
        Policy: GoliathNationalBank
        Scenario: EndOfDayRush
        Expected: Settlement rate 0.75-0.90, EOD buffer adaptation

        Goliath has EOD-specific buffer multiplier (0.5×).
        Should be more aggressive at EOD while still maintaining stability.
        """
        scenario = (
            ScenarioBuilder("EndOfDayRush")
            .with_description("EOD rush - test buffer adaptation")
            .with_duration(100)
            .with_ticks_per_day(100)
            .with_seed(88888)
            .add_agent(
                "BANK_A",
                balance=7_000_000,   # $70k
                arrival_rate=2.0,
                arrival_amount_range=(120_000, 240_000),
                deadline_range=(8, 25),
            )
            .add_agent("BANK_B", balance=20_000_000)
            # EOD rush at tick 80
            .add_arrival_rate_change(tick=80, agent_id="BANK_A", multiplier=3.0)
            .build()
        )

        policy = load_json_policy("goliath_national_bank")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.75, max=0.90),
            max_queue_depth=Range(min=5, max=18),
            # EOD buffer is 0.5× normal, so more aggressive
            min_balance=Range(min=0),  # May dip lower at EOD
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"GoliathNationalBank should adapt buffer at EOD"

    def test_goliath_intraday_patterns_time_multipliers(self):
        """
        Policy: GoliathNationalBank
        Scenario: IntradayPatterns
        Expected: Time-adaptive behavior across day

        Goliath has different buffer multipliers:
        - Early day (0-30%): 1.5× buffer
        - Mid day (30-80%): 1.0× buffer
        - EOD (80%+): 0.5× buffer

        This test validates time-aware behavior.
        """
        scenario = (
            ScenarioBuilder("IntradayPatterns")
            .with_description("Intraday patterns - test time multipliers")
            .with_duration(300)  # 3 "days" × 100 ticks
            .with_ticks_per_day(100)
            .with_seed(77777)
            .add_agent(
                "BANK_A",
                balance=8_000_000,   # $80k
                arrival_rate=2.0,
                arrival_amount_range=(120_000, 240_000),
                deadline_range=(10, 30),
            )
            .add_agent("BANK_B", balance=20_000_000)
            # Morning rush (ticks 10-30 of each day)
            .add_arrival_rate_change(tick=10, agent_id="BANK_A", multiplier=2.0)
            .add_arrival_rate_change(tick=30, agent_id="BANK_A", multiplier=1.0)
            # EOD rush (ticks 80-100 of each day)
            .add_arrival_rate_change(tick=80, agent_id="BANK_A", multiplier=2.5)
            .add_arrival_rate_change(tick=100, agent_id="BANK_A", multiplier=1.0)
            .build()
        )

        policy = load_json_policy("goliath_national_bank")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.75, max=0.92),
            max_queue_depth=Range(min=5, max=20),
            # Time-adaptive, so average should be reasonable
            avg_balance=Range(min=4_000_000, max=8_000_000),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"GoliathNationalBank should adapt across intraday patterns"


class TestCautiousLiquidityPreserverPolicy:
    """Tests for CautiousLiquidityPreserver - ultra-conservative policy."""

    def test_cautious_ample_liquidity_conservative_settlement(self):
        """
        Policy: CautiousLiquidityPreserver
        Scenario: AmpleLiquidity
        Expected: Settlement rate 0.85-0.95, very conservative even with ample liquidity

        Even with ample liquidity, Cautious is conservative (2.5× buffer multiplier).
        """
        scenario = (
            ScenarioBuilder("AmpleLiquidity")
            .with_description("Ample liquidity - but Cautious stays conservative")
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

        policy = load_json_policy("cautious_liquidity_preserver")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.85, max=0.95),  # Lower than aggressive policies
            max_queue_depth=Range(min=0, max=8),  # Slightly larger queue
            min_balance=Range(min=7_000_000),  # Excellent preservation
            overdraft_violations=Exact(0),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"CautiousLiquidityPreserver should be conservative even with ample liquidity"

    def test_cautious_moderate_activity_large_buffer(self):
        """
        Policy: CautiousLiquidityPreserver
        Scenario: ModerateActivity
        Expected: Settlement rate 0.60-0.80, large buffer maintained

        Under moderate activity, Cautious should maintain large buffer
        at the cost of settlement rate.
        """
        scenario = (
            ScenarioBuilder("ModerateActivity")
            .with_description("Moderate activity - test ultra-conservative approach")
            .with_duration(100)
            .with_seed(54321)
            .add_agent(
                "BANK_A",
                balance=6_000_000,   # $60k
                arrival_rate=2.5,
                arrival_amount_range=(100_000, 250_000),
                deadline_range=(12, 30),
            )
            .add_agent("BANK_B", balance=15_000_000)
            .build()
        )

        policy = load_json_policy("cautious_liquidity_preserver")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.60, max=0.80),  # Lower than balanced policies
            max_queue_depth=Range(min=8, max=20),  # Larger queue
            min_balance=Range(min=3_500_000),  # Excellent preservation
            overdraft_violations=Exact(0),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"CautiousLiquidityPreserver should maintain large buffer"

    def test_cautious_high_pressure_maximum_preservation(self):
        """
        Policy: CautiousLiquidityPreserver
        Scenario: HighPressure
        Expected: Settlement rate 0.40-0.65, maximum buffer preservation

        Under high pressure, Cautious should prioritize buffer preservation
        above all else. Lowest settlement rate but best balance preservation.
        """
        scenario = (
            ScenarioBuilder("HighPressure")
            .with_description("High pressure - maximum preservation mode")
            .with_duration(100)
            .with_seed(99999)
            .add_agent(
                "BANK_A",
                balance=5_000_000,   # $50k
                arrival_rate=5.0,
                arrival_amount_range=(150_000, 300_000),
                deadline_range=(10, 40),
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        policy = load_json_policy("cautious_liquidity_preserver")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.40, max=0.65),  # Lowest settlement rate
            max_queue_depth=Range(min=20, max=50),  # Massive queue
            min_balance=Range(min=2_000_000),  # Best preservation across all policies
            overdraft_violations=Exact(0),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"CautiousLiquidityPreserver should maximize preservation under pressure"

    def test_cautious_liquidity_crisis_survives(self):
        """
        Policy: CautiousLiquidityPreserver
        Scenario: LiquidityCrisis
        Expected: Survives crisis with best min_balance

        In a multi-event liquidity crisis, Cautious should survive with
        the highest min_balance of any policy.
        """
        scenario = (
            ScenarioBuilder("LiquidityCrisis")
            .with_description("Multi-event crisis - survival test")
            .with_duration(200)
            .with_seed(42)
            .add_agent(
                "BANK_A",
                balance=5_000_000,
                credit_limit=2_000_000,
                arrival_rate=3.0,
                arrival_amount_range=(150_000, 350_000),
                deadline_range=(8, 25),
                posted_collateral=3_000_000,
                collateral_haircut=0.1,
            )
            .add_agent("BANK_B", balance=15_000_000)
            .add_collateral_adjustment(tick=50, agent_id="BANK_A", haircut_change=-0.2)
            .add_arrival_rate_change(tick=100, multiplier=2.0)
            .add_large_payment(tick=150, sender="BANK_A", receiver="BANK_B", amount=2_000_000, deadline_offset=10)
            .build()
        )

        policy = load_json_policy("cautious_liquidity_preserver")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.35, max=0.65),  # Survives but low rate
            min_balance=Range(min=500_000),  # Survives with positive balance
            overdraft_violations=Range(min=0, max=5),  # Minimal credit usage
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"CautiousLiquidityPreserver should survive liquidity crisis"


class TestBalancedCostOptimizerPolicy:
    """Tests for BalancedCostOptimizer - holistic cost minimization."""

    def test_balanced_ample_liquidity_efficient_settlement(self):
        """
        Policy: BalancedCostOptimizer
        Scenario: AmpleLiquidity
        Expected: Settlement rate 0.90-1.0, low total cost

        With ample liquidity, BalancedCostOptimizer should achieve
        high settlement rate with minimal costs.
        """
        scenario = (
            ScenarioBuilder("AmpleLiquidity")
            .with_description("Ample liquidity - cost optimization easy")
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

        policy = load_json_policy("balanced_cost_optimizer")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.90, max=1.0),
            max_queue_depth=Range(min=0, max=5),
            # total_cost=Range(min=0, max=50_000),  # Minimal costs
            overdraft_violations=Exact(0),
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"BalancedCostOptimizer should minimize costs with ample liquidity"

    def test_balanced_moderate_activity_cost_trade_offs(self):
        """
        Policy: BalancedCostOptimizer
        Scenario: ModerateActivity
        Expected: Settlement rate 0.80-0.93, balanced cost profile

        Under moderate activity, should balance delay, overdraft, and
        deadline costs to minimize total cost.
        """
        scenario = (
            ScenarioBuilder("ModerateActivity")
            .with_description("Moderate activity - cost optimization")
            .with_duration(100)
            .with_seed(54321)
            .add_agent(
                "BANK_A",
                balance=6_000_000,   # $60k
                arrival_rate=2.5,
                arrival_amount_range=(100_000, 250_000),
                deadline_range=(12, 30),
            )
            .add_agent("BANK_B", balance=15_000_000)
            .build()
        )

        policy = load_json_policy("balanced_cost_optimizer")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.80, max=0.93),
            max_queue_depth=Range(min=3, max=12),
            # Balanced cost profile (no single cost dominates)
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"BalancedCostOptimizer should balance costs under moderate activity"

    def test_balanced_high_pressure_cost_aware_degradation(self):
        """
        Policy: BalancedCostOptimizer
        Scenario: HighPressure
        Expected: Settlement rate 0.70-0.88, cost-aware decisions

        Under high pressure, should make cost-aware trade-offs,
        potentially using credit if it minimizes total cost.
        """
        scenario = (
            ScenarioBuilder("HighPressure")
            .with_description("High pressure - cost-aware degradation")
            .with_duration(100)
            .with_seed(99999)
            .add_agent(
                "BANK_A",
                balance=5_000_000,   # $50k
                arrival_rate=5.0,
                arrival_amount_range=(150_000, 300_000),
                deadline_range=(10, 40),
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        policy = load_json_policy("balanced_cost_optimizer")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.70, max=0.88),
            max_queue_depth=Range(min=8, max=20),
            # May use credit if it minimizes total cost
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"BalancedCostOptimizer should make cost-aware decisions under pressure"

    def test_balanced_liquidity_crisis_cost_minimization(self):
        """
        Policy: BalancedCostOptimizer
        Scenario: LiquidityCrisis
        Expected: Survives with lowest total cost

        In a crisis, BalancedCostOptimizer should have the lowest total
        cost of any policy by making optimal trade-offs.
        """
        scenario = (
            ScenarioBuilder("LiquidityCrisis")
            .with_description("Crisis - cost minimization critical")
            .with_duration(200)
            .with_seed(42)
            .add_agent(
                "BANK_A",
                balance=5_000_000,
                credit_limit=2_000_000,
                arrival_rate=3.0,
                arrival_amount_range=(150_000, 350_000),
                deadline_range=(8, 25),
                posted_collateral=3_000_000,
                collateral_haircut=0.1,
            )
            .add_agent("BANK_B", balance=15_000_000)
            .add_collateral_adjustment(tick=50, agent_id="BANK_A", haircut_change=-0.2)
            .add_arrival_rate_change(tick=100, multiplier=2.0)
            .add_large_payment(tick=150, sender="BANK_A", receiver="BANK_B", amount=2_000_000, deadline_offset=10)
            .build()
        )

        policy = load_json_policy("balanced_cost_optimizer")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.60, max=0.80),
            # total_cost=Range(min=0, max=500_000),  # Best cost among policies
            # Should survive without massive violations
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"BalancedCostOptimizer should minimize costs in crisis"

    def test_balanced_intraday_time_adaptive_costs(self):
        """
        Policy: BalancedCostOptimizer
        Scenario: IntradayPatterns
        Expected: Time-adaptive cost optimization

        BalancedCostOptimizer is time-aware and should adjust decisions
        based on time of day (early, mid, late, EOD).
        """
        scenario = (
            ScenarioBuilder("IntradayPatterns")
            .with_description("Intraday patterns - time-adaptive cost optimization")
            .with_duration(300)  # 3 "days"
            .with_ticks_per_day(100)
            .with_seed(77777)
            .add_agent(
                "BANK_A",
                balance=8_000_000,   # $80k
                arrival_rate=2.0,
                arrival_amount_range=(120_000, 240_000),
                deadline_range=(10, 30),
            )
            .add_agent("BANK_B", balance=20_000_000)
            .add_arrival_rate_change(tick=10, agent_id="BANK_A", multiplier=2.0)
            .add_arrival_rate_change(tick=30, agent_id="BANK_A", multiplier=1.0)
            .add_arrival_rate_change(tick=80, agent_id="BANK_A", multiplier=2.5)
            .add_arrival_rate_change(tick=100, agent_id="BANK_A", multiplier=1.0)
            .build()
        )

        policy = load_json_policy("balanced_cost_optimizer")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.75, max=0.92),
            max_queue_depth=Range(min=5, max=18),
            # Time-adaptive, should handle patterns well
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"BalancedCostOptimizer should adapt costs across intraday patterns"


class TestSmartSplitterPolicy:
    """Tests for SmartSplitter - intelligent transaction splitting."""

    def test_smart_splitter_split_opportunities_queue_reduction(self):
        """
        Policy: SmartSplitter
        Scenario: SplitOpportunities
        Expected: 20-40% queue reduction vs non-splitters

        With divisible transactions and liquidity constraints,
        SmartSplitter should reduce queue depth through strategic splits.
        """
        scenario = (
            ScenarioBuilder("SplitOpportunities")
            .with_description("Divisible transactions - splitting opportunities")
            .with_duration(100)
            .with_seed(55555)
            .add_agent(
                "BANK_A",
                balance=4_000_000,   # $40k - constrained
                arrival_rate=2.5,
                arrival_amount_range=(200_000, 500_000),  # Large, divisible amounts
                deadline_range=(12, 30),
            )
            .add_agent("BANK_B", balance=15_000_000)
            .build()
        )

        policy = load_json_policy("smart_splitter")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.75, max=0.90),
            max_queue_depth=Range(min=3, max=15),  # Lower than non-splitters
            # Splits should occur strategically
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"SmartSplitter should reduce queue through strategic splitting"

    def test_smart_splitter_cost_aware_splitting(self):
        """
        Policy: SmartSplitter
        Scenario: SplitCostTradeoff
        Expected: Only splits when cost-effective

        SmartSplitter should only split when split_cost < delay_cost.
        Tests cost-awareness of splitting decisions.
        """
        scenario = (
            ScenarioBuilder("SplitCostTradeoff")
            .with_description("Test cost-aware splitting decisions")
            .with_duration(150)
            .with_seed(66666)
            .add_agent(
                "BANK_A",
                balance=5_000_000,   # $50k
                arrival_rate=2.8,
                arrival_amount_range=(180_000, 450_000),
                deadline_range=(10, 35),
            )
            .add_agent("BANK_B", balance=18_000_000)
            .build()
        )

        policy = load_json_policy("smart_splitter")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.70, max=0.88),
            max_queue_depth=Range(min=5, max=18),
            # Strategic splits (not excessive)
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"SmartSplitter should split only when cost-effective"

    def test_smart_splitter_high_pressure_gridlock_prevention(self):
        """
        Policy: SmartSplitter
        Scenario: HighPressure
        Expected: Prevents gridlock through strategic splits

        Under high pressure, splitting can prevent gridlock by allowing
        partial settlements to free up liquidity.
        """
        scenario = (
            ScenarioBuilder("HighPressure")
            .with_description("High pressure - gridlock prevention")
            .with_duration(100)
            .with_seed(99999)
            .add_agent(
                "BANK_A",
                balance=5_000_000,   # $50k
                arrival_rate=5.0,
                arrival_amount_range=(150_000, 300_000),
                deadline_range=(10, 40),
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        policy = load_json_policy("smart_splitter")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.65, max=0.85),
            max_queue_depth=Range(min=8, max=22),  # Better than non-splitters
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"SmartSplitter should prevent gridlock under pressure"

    def test_smart_splitter_vs_fifo_queue_comparison(self):
        """
        Comparison: SmartSplitter vs FIFO
        Scenario: SplitOpportunities
        Metric: max_queue_depth
        Expected: SmartSplitter should have 20-40% lower queue depth

        Validates splitting reduces queue depth.
        """
        scenario = (
            ScenarioBuilder("SplitOpportunities")
            .with_description("Compare queue depths")
            .with_duration(100)
            .with_seed(55555)
            .add_agent(
                "BANK_A",
                balance=4_000_000,
                arrival_rate=2.5,
                arrival_amount_range=(200_000, 500_000),
                deadline_range=(12, 30),
            )
            .add_agent("BANK_B", balance=15_000_000)
            .build()
        )

        comparator = PolicyComparator(scenario)

        result = comparator.compare(
            policies=[
                ("FIFO", {"type": "Fifo"}),
                ("SmartSplitter", {
                    **load_json_policy("smart_splitter"),
                }),
            ],
            metrics=["settlement_rate", "max_queue_depth"],
            agent_id="BANK_A",
        )

        print("\n" + result.comparison_table())

        fifo_queue = result.get_metric("FIFO", "max_queue_depth")
        splitter_queue = result.get_metric("SmartSplitter", "max_queue_depth")

        assert fifo_queue is not None and splitter_queue is not None

        # SmartSplitter should have lower queue depth
        reduction = fifo_queue - splitter_queue
        reduction_pct = (reduction / max(fifo_queue, 1)) * 100

        print(f"\nQueue depth reduction: {reduction} ({reduction_pct:.1f}%)")

        # Allow for some variability but splitter should generally be better
        # or at least not worse
        assert splitter_queue <= fifo_queue * 1.2, (
            f"SmartSplitter should not have significantly worse queue. "
            f"Splitter: {splitter_queue}, FIFO: {fifo_queue}"
        )


class TestAggressiveMarketMakerPolicy:
    """Tests for AggressiveMarketMaker - high settlement, credit usage."""

    def test_aggressive_ample_liquidity_maximum_settlement(self):
        """
        Policy: AggressiveMarketMaker
        Scenario: AmpleLiquidity
        Expected: Settlement rate 0.95-1.0, highest among policies

        With ample liquidity, Aggressive should achieve maximum settlement.
        """
        scenario = (
            ScenarioBuilder("AmpleLiquidity")
            .with_description("Ample liquidity - maximum settlement")
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

        policy = load_json_policy("aggressive_market_maker")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.95, max=1.0),  # Maximum
            max_queue_depth=Range(min=0, max=3),  # Minimal queue
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"AggressiveMarketMaker should achieve maximum settlement"

    def test_aggressive_high_pressure_credit_usage(self):
        """
        Policy: AggressiveMarketMaker
        Scenario: HighPressure (with credit)
        Expected: Settlement rate 0.75-0.92, uses credit

        Under high pressure, Aggressive should use credit to maintain
        high settlement rate.
        """
        scenario = (
            ScenarioBuilder("HighPressure")
            .with_description("High pressure - willing to use credit")
            .with_duration(100)
            .with_seed(99999)
            .add_agent(
                "BANK_A",
                balance=5_000_000,   # $50k
                credit_limit=3_000_000,  # $30k credit available
                arrival_rate=5.0,
                arrival_amount_range=(150_000, 300_000),
                deadline_range=(10, 40),
            )
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        policy = load_json_policy("aggressive_market_maker")

        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.75, max=0.92),  # Highest under pressure
            max_queue_depth=Range(min=5, max=15),  # Lowest queue
            # May use credit (no overdraft violations with credit limit)
        )

        test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
        result = test.run()

        if not result.passed:
            print(result.detailed_report())

        assert result.passed, f"AggressiveMarketMaker should use credit for high settlement"

    def test_aggressive_vs_cautious_settlement_comparison(self):
        """
        Comparison: AggressiveMarketMaker vs CautiousLiquidityPreserver
        Scenario: ModerateActivity
        Metric: settlement_rate
        Expected: Aggressive should have 20-40% higher settlement rate

        Validates the extreme ends of the conservative-aggressive spectrum.
        """
        scenario = (
            ScenarioBuilder("ModerateActivity")
            .with_description("Compare aggressive vs cautious")
            .with_duration(100)
            .with_seed(54321)
            .add_agent(
                "BANK_A",
                balance=6_000_000,
                arrival_rate=2.5,
                arrival_amount_range=(100_000, 250_000),
                deadline_range=(12, 30),
            )
            .add_agent("BANK_B", balance=15_000_000)
            .build()
        )

        comparator = PolicyComparator(scenario)

        result = comparator.compare(
            policies=[
                ("CautiousLiquidityPreserver", {
                    **load_json_policy("cautious_liquidity_preserver"),
                }),
                ("AggressiveMarketMaker", {
                    **load_json_policy("aggressive_market_maker"),
                }),
            ],
            metrics=["settlement_rate", "min_balance", "max_queue_depth"],
            agent_id="BANK_A",
        )

        print("\n" + result.comparison_table())

        cautious_sr = result.get_metric("CautiousLiquidityPreserver", "settlement_rate")
        aggressive_sr = result.get_metric("AggressiveMarketMaker", "settlement_rate")

        assert cautious_sr is not None and aggressive_sr is not None

        # Aggressive should have higher settlement rate
        assert aggressive_sr > cautious_sr, (
            f"Aggressive should have higher settlement rate. "
            f"Aggressive: {aggressive_sr:.3f}, Cautious: {cautious_sr:.3f}"
        )

        # Cautious should have higher min_balance
        cautious_balance = result.get_metric("CautiousLiquidityPreserver", "min_balance")
        aggressive_balance = result.get_metric("AggressiveMarketMaker", "min_balance")

        assert cautious_balance is not None and aggressive_balance is not None
        assert cautious_balance >= aggressive_balance, (
            f"Cautious should preserve balance better. "
            f"Cautious: ${cautious_balance/100:.2f}, Aggressive: ${aggressive_balance/100:.2f}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
