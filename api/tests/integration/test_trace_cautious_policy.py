"""
Transaction-Trace Tests for CautiousLiquidityPreserver Policy

These tests trace individual transactions through the CautiousLiquidityPreserver
policy decision tree, verifying correct behavior at each decision point.

Each test exercises a specific branch of the policy tree with known
transaction characteristics and agent state.
"""

import json
import pytest
from pathlib import Path
from policy_scenario import (
    PolicyScenarioTest,
    OutcomeExpectation,
    Range,
    Exact,
    ScenarioBuilder,
)
from payment_simulator._core import Orchestrator


def load_json_policy(policy_name: str) -> dict:
    """Load a JSON policy file from backend/policies/ directory."""
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


class TestCautiousEODBranches:
    """Test EOD rush branch of Cautious policy tree."""

    def test_cautious_eod_past_deadline_forces_release(self):
        """
        Policy: CautiousLiquidityPreserver
        Branch: EOD Rush → Past Deadline → Force Release

        Transaction: Deadline tick 5, arrives tick 1
        Scenario: EOD rush at tick 5 (deadline already passed)
        Agent: Insufficient liquidity ($500 balance, $1000 transaction)

        Expected: MUST release despite insufficient liquidity to avoid double penalty
        """
        scenario = (
            ScenarioBuilder("EOD_PastDeadline")
            .with_description("EOD rush with overdue transaction")
            .with_duration(10)
            .with_ticks_per_day(10)
            .with_seed(12345)
            .add_agent(
                "BANK_A",
                balance=500_000,  # $5k - insufficient
                arrival_rate=0.0,  # No automatic arrivals
            )
            .add_agent("BANK_B", balance=10_000_000)
            # Inject specific transaction
            .add_large_payment(
                tick=1,
                sender="BANK_A",
                receiver="BANK_B",
                amount=1_000_000,  # $10k - requires $5k more
                deadline_offset=4,  # Deadline at tick 5
            )
            # Trigger EOD rush at deadline tick
            .add_arrival_rate_change(tick=5, agent_id="BANK_A", multiplier=0.0)
            .build()
        )

        policy = load_json_policy("cautious_liquidity_preserver")

        # Create orchestrator and run manually to observe behavior
        orch_config = scenario.to_orchestrator_config({"BANK_A": policy, "BANK_B": {"type": "Fifo"}})
        orch = Orchestrator.new(orch_config)

        # Run until deadline
        for _ in range(5):
            orch.tick()

        # At tick 5 (deadline), transaction should be past deadline
        # Cautious policy should FORCE RELEASE despite insufficient liquidity
        final_tick = orch.current_tick()
        assert final_tick >= 5

        # Check transaction was settled (forced release)
        metrics = orch.get_metrics("BANK_A")

        # Transaction should have settled eventually (force release path)
        # Even if it goes into overdraft
        assert metrics["settlement_rate"] > 0, "Past deadline tx should force release"

    def test_cautious_eod_with_liquidity_releases(self):
        """
        Policy: CautiousLiquidityPreserver
        Branch: EOD Rush → Has Liquidity → Release

        Transaction: Deadline tick 9, amount $1000
        Scenario: EOD rush at tick 8
        Agent: Sufficient liquidity ($2000 balance)

        Expected: Release immediately when EOD rush detected
        """
        scenario = (
            ScenarioBuilder("EOD_HasLiquidity")
            .with_description("EOD rush with sufficient liquidity")
            .with_duration(15)
            .with_ticks_per_day(15)
            .with_seed(54321)
            .add_agent(
                "BANK_A",
                balance=2_000_000,  # $20k - ample
                arrival_rate=0.0,
            )
            .add_agent("BANK_B", balance=10_000_000)
            # Inject transaction before EOD
            .add_large_payment(
                tick=5,
                sender="BANK_A",
                receiver="BANK_B",
                amount=1_000_000,  # $10k
                deadline_offset=4,  # Deadline at tick 9
            )
            # EOD rush at tick 8 (before deadline)
            .add_arrival_rate_change(tick=8, agent_id="BANK_A", multiplier=0.0)
            .build()
        )

        policy = load_json_policy("cautious_liquidity_preserver")

        orch_config = scenario.to_orchestrator_config({"BANK_A": policy, "BANK_B": {"type": "Fifo"}})
        orch = Orchestrator.new(orch_config)

        # Run until after EOD rush
        for _ in range(10):
            orch.tick()

        metrics = orch.get_metrics("BANK_A")

        # Should have high settlement rate (released during EOD)
        assert metrics["settlement_rate"] >= 0.9, "EOD + liquidity should release"
        assert metrics["max_queue_depth"] <= 5, "Should not queue when can afford"

    def test_cautious_eod_no_liquidity_holds(self):
        """
        Policy: CautiousLiquidityPreserver
        Branch: EOD Rush → No Liquidity → Hold

        Transaction: Amount $2000, deadline tick 9
        Scenario: EOD rush at tick 8
        Agent: Insufficient liquidity ($500 balance)

        Expected: Hold even during EOD rush if cannot afford
        """
        scenario = (
            ScenarioBuilder("EOD_NoLiquidity")
            .with_description("EOD rush without sufficient liquidity")
            .with_duration(15)
            .with_ticks_per_day(15)
            .with_seed(99999)
            .add_agent(
                "BANK_A",
                balance=500_000,  # $5k - insufficient
                arrival_rate=0.0,
            )
            .add_agent("BANK_B", balance=10_000_000)
            # Inject transaction
            .add_large_payment(
                tick=5,
                sender="BANK_A",
                receiver="BANK_B",
                amount=2_000_000,  # $20k - way over budget
                deadline_offset=4,  # Deadline tick 9
            )
            # EOD rush at tick 8
            .add_arrival_rate_change(tick=8, agent_id="BANK_A", multiplier=0.0)
            .build()
        )

        policy = load_json_policy("cautious_liquidity_preserver")

        orch_config = scenario.to_orchestrator_config({"BANK_A": policy, "BANK_B": {"type": "Fifo"}})
        orch = Orchestrator.new(orch_config)

        # Run simulation
        for _ in range(10):
            orch.tick()

        metrics = orch.get_metrics("BANK_A")

        # Should have low settlement (held due to no liquidity)
        assert metrics["settlement_rate"] < 0.5, "EOD without liquidity should hold"
        assert metrics["max_queue_depth"] >= 1, "Transaction should be queued"


class TestCautiousUrgencyBranches:
    """Test urgency-based decision branches."""

    def test_cautious_urgent_can_afford_releases(self):
        """
        Policy: CautiousLiquidityPreserver
        Branch: Very Urgent (<3 ticks) → Can Afford → Release

        Transaction: Deadline in 2 ticks, amount $1000
        Agent: Balance $2000

        Expected: Release immediately due to urgency + affordability
        """
        scenario = (
            ScenarioBuilder("Urgent_CanAfford")
            .with_description("Urgent transaction with sufficient liquidity")
            .with_duration(10)
            .with_seed(11111)
            .add_agent(
                "BANK_A",
                balance=2_000_000,  # $20k
                arrival_rate=0.0,
            )
            .add_agent("BANK_B", balance=10_000_000)
            # Inject urgent transaction
            .add_large_payment(
                tick=1,
                sender="BANK_A",
                receiver="BANK_B",
                amount=1_000_000,  # $10k
                deadline_offset=2,  # Very urgent (2 ticks)
            )
            .build()
        )

        policy = load_json_policy("cautious_liquidity_preserver")

        orch_config = scenario.to_orchestrator_config({"BANK_A": policy, "BANK_B": {"type": "Fifo"}})
        orch = Orchestrator.new(orch_config)

        # Run for a few ticks
        for _ in range(5):
            orch.tick()

        metrics = orch.get_metrics("BANK_A")

        # Should release quickly
        assert metrics["settlement_rate"] >= 0.9, "Urgent + affordable should release"

    def test_cautious_urgent_penalty_cheaper_holds(self):
        """
        Policy: CautiousLiquidityPreserver
        Branch: Very Urgent → Can't Afford → Penalty Cheaper → Hold

        Transaction: Deadline 2 ticks, amount $5000
        Agent: Balance $1000, High overdraft cost
        Config: Deadline penalty < overdraft cost × ticks

        Expected: Hold and accept deadline penalty (cheaper than credit)
        """
        scenario = (
            ScenarioBuilder("Urgent_PenaltyCheaper")
            .with_description("Urgent but penalty cheaper than credit")
            .with_duration(10)
            .with_seed(22222)
            .add_agent(
                "BANK_A",
                balance=1_000_000,  # $10k
                arrival_rate=0.0,
                # Would need to configure costs to make penalty cheaper
                # This may require adding cost configuration to ScenarioBuilder
            )
            .add_agent("BANK_B", balance=10_000_000)
            .add_large_payment(
                tick=1,
                sender="BANK_A",
                receiver="BANK_B",
                amount=5_000_000,  # $50k - insufficient
                deadline_offset=2,  # Urgent
            )
            .build()
        )

        policy = load_json_policy("cautious_liquidity_preserver")

        orch_config = scenario.to_orchestrator_config({"BANK_A": policy, "BANK_B": {"type": "Fifo"}})
        orch = Orchestrator.new(orch_config)

        # Run simulation
        for _ in range(5):
            orch.tick()

        metrics = orch.get_metrics("BANK_A")

        # Should hold (low settlement)
        assert metrics["settlement_rate"] < 0.5, "Should hold when penalty cheaper"
        assert metrics["deadline_violations"] >= 1, "Should incur deadline violation"


class TestCautiousBufferBranches:
    """Test buffer-based decision branches."""

    def test_cautious_strong_buffer_releases(self):
        """
        Policy: CautiousLiquidityPreserver
        Branch: Strong Buffer (2.5× amount) → Release

        Transaction: Amount $1000
        Agent: Balance $3000 (3× transaction = strong buffer)

        Expected: Release due to strong buffer protection
        """
        scenario = (
            ScenarioBuilder("StrongBuffer")
            .with_description("Transaction with 3× buffer")
            .with_duration(10)
            .with_seed(33333)
            .add_agent(
                "BANK_A",
                balance=3_000_000,  # $30k
                arrival_rate=0.0,
            )
            .add_agent("BANK_B", balance=10_000_000)
            .add_large_payment(
                tick=1,
                sender="BANK_A",
                receiver="BANK_B",
                amount=1_000_000,  # $10k (3× buffer = $30k)
                deadline_offset=10,
            )
            .build()
        )

        policy = load_json_policy("cautious_liquidity_preserver")

        orch_config = scenario.to_orchestrator_config({"BANK_A": policy, "BANK_B": {"type": "Fifo"}})
        orch = Orchestrator.new(orch_config)

        # Run simulation
        for _ in range(5):
            orch.tick()

        metrics = orch.get_metrics("BANK_A")

        # Should release with strong buffer
        assert metrics["settlement_rate"] >= 0.9, "Strong buffer should allow release"

    def test_cautious_early_day_no_buffer_holds(self):
        """
        Policy: CautiousLiquidityPreserver
        Branch: Early/Mid Day → No Buffer → Hold (Preserving Buffer)

        Transaction: Amount $2000
        Agent: Balance $2500 (1.25× = weak buffer)
        Time: Early day (20% progress)

        Expected: Hold to preserve buffer (below 2.5× threshold)
        """
        scenario = (
            ScenarioBuilder("EarlyDay_WeakBuffer")
            .with_description("Early day with insufficient buffer")
            .with_duration(100)
            .with_ticks_per_day(100)
            .with_seed(44444)
            .add_agent(
                "BANK_A",
                balance=2_500_000,  # $25k
                arrival_rate=0.0,
            )
            .add_agent("BANK_B", balance=10_000_000)
            # Transaction at tick 20 (20% of day = early)
            .add_large_payment(
                tick=20,
                sender="BANK_A",
                receiver="BANK_B",
                amount=2_000_000,  # $20k (only 1.25× buffer)
                deadline_offset=30,
            )
            .build()
        )

        policy = load_json_policy("cautious_liquidity_preserver")

        orch_config = scenario.to_orchestrator_config({"BANK_A": policy, "BANK_B": {"type": "Fifo"}})
        orch = Orchestrator.new(orch_config)

        # Run past transaction arrival
        for _ in range(30):
            orch.tick()

        metrics = orch.get_metrics("BANK_A")

        # Should hold due to weak buffer early in day
        assert metrics["settlement_rate"] < 0.5, "Weak buffer early day should hold"
        assert metrics["max_queue_depth"] >= 1, "Transaction should be queued"


class TestCautiousLateDayBranches:
    """Test late-day specific decision branches."""

    def test_cautious_late_day_minimal_liquidity_releases(self):
        """
        Policy: CautiousLiquidityPreserver
        Branch: Late Day (>80%) → Minimal Liquidity → Release

        Transaction: Amount $1000
        Agent: Balance $1100 (just enough)
        Time: 85% through day

        Expected: Release with minimal liquidity in late day
        """
        scenario = (
            ScenarioBuilder("LateDay_MinimalLiquidity")
            .with_description("Late day with just enough liquidity")
            .with_duration(100)
            .with_ticks_per_day(100)
            .with_seed(55555)
            .add_agent(
                "BANK_A",
                balance=1_100_000,  # $11k
                arrival_rate=0.0,
            )
            .add_agent("BANK_B", balance=10_000_000)
            # Transaction at tick 85 (late day)
            .add_large_payment(
                tick=85,
                sender="BANK_A",
                receiver="BANK_B",
                amount=1_000_000,  # $10k (barely enough)
                deadline_offset=10,
            )
            .build()
        )

        policy = load_json_policy("cautious_liquidity_preserver")

        orch_config = scenario.to_orchestrator_config({"BANK_A": policy, "BANK_B": {"type": "Fifo"}})
        orch = Orchestrator.new(orch_config)

        # Run simulation
        for _ in range(95):
            orch.tick()

        metrics = orch.get_metrics("BANK_A")

        # Should release in late day
        assert metrics["settlement_rate"] >= 0.8, "Late day with minimal liquidity should release"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
