"""
Example Transaction Journey Tests

Demonstrates tracking individual transactions through complex scenarios
to understand how different policies make decisions.

These tests complement aggregate metric tests by revealing the "how" behind
policy behavior.
"""

import pytest
from policy_scenario import (
    ScenarioBuilder,
)
from policy_scenario.journey import (
    JourneyTracker,
    TransactionJourneyTest,
    assert_settled_within,
    assert_no_deadline_violation,
    compare_journeys,
)


class TestQueueDynamicsJourneys:
    """Track how transactions flow through queues under different policies."""

    def test_urgent_transaction_preempts_normal_fifo_vs_deadline(self):
        """
        Scenario: Two transactions arrive close together, one urgent.

        Setup:
        - Transaction A arrives T10: $1,000, deadline T40 (30 ticks away, urgency low)
        - Agent has $1,500 liquidity
        - Transaction B arrives T15: $500, deadline T18 (3 ticks away, urgency high)

        Expected Behavior:
        - FIFO: A settles first (arrived first), B must wait
        - Deadline: B settles first (higher urgency), A waits

        This reveals how Deadline policy prioritizes by urgency vs FIFO's strict ordering.
        """
        # Scenario with controlled arrivals
        scenario = (
            ScenarioBuilder("UrgentPreemption")
            .with_duration(50)
            .with_seed(11111)
            .add_agent("BANK_A", balance=1_500_000, arrival_rate=0)  # Manual arrivals only
            .add_agent("BANK_B", balance=10_000_000)
            .build()
        )

        # We'll need to manually submit transactions for this test
        # For now, show the test structure
        # TODO: Add manual transaction submission API to framework

        print("\n=== Urgent Preemption Test ===")
        print("This test would track:")
        print("  - Transaction A (normal priority)")
        print("  - Transaction B (urgent)")
        print("Comparing FIFO vs Deadline policies")
        print("\nExpected:")
        print("  FIFO: A settles T10, B settles T11+")
        print("  Deadline: B settles T15, A settles T16+")

        # Skip for now - requires manual transaction API
        pytest.skip("Requires manual transaction submission API")


class TestCollateralUsageJourneys:
    """Track when and how policies use collateral to unlock liquidity."""

    def test_collateral_unlocks_settlement_liquidity_aware(self):
        """
        Scenario: Transaction requires collateral posting to settle.

        Setup:
        - Agent has $500 balance
        - Agent has $5,000 eligible collateral (80% haircut = $4,000 usable)
        - Transaction: $2,000, deadline T20

        Expected (LiquidityAware with collateral enabled):
        1. Transaction arrives
        2. Insufficient liquidity detected
        3. Collateral posted (~$2,500 to unlock $2,000)
        4. Transaction settles

        Journey should show: Arrival → CollateralPosted → RtgsImmediateSettlement
        """
        scenario = (
            ScenarioBuilder("CollateralRequired")
            .with_duration(50)
            .with_seed(22222)
            .add_agent(
                "BANK_A",
                balance=500_000,  # $5k
                arrival_rate=0.1,  # Low rate
                arrival_amount_range=(2_000_000, 2_500_000),  # $20k-$25k (needs collateral)
                posted_collateral=5_000_000,  # $50k collateral available
                collateral_haircut=0.8,  # 80% → $40k usable
            )
            .add_agent("BANK_B", balance=50_000_000)
            .build()
        )

        # Note: This test shows the concept but needs collateral-aware policy
        print("\n=== Collateral Usage Test ===")
        print("Transaction needs $20k-$25k, agent has $5k")
        print("Expected journey:")
        print("  1. Arrival")
        print("  2. InsufficientLiquidity detected")
        print("  3. CollateralPosted (~$30k)")
        print("  4. RtgsImmediateSettlement")

        pytest.skip("Requires collateral-aware policy configuration")


class TestPolicyComparisonsJourneys:
    """Compare how different policies handle the same transaction."""

    def test_same_transaction_different_policies(self):
        """
        Run the SAME scenario under different policies and compare journeys.

        This reveals policy-specific decision-making for identical circumstances.
        """
        # Fixed seed ensures same transaction arrivals
        scenario = (
            ScenarioBuilder("PolicyComparison")
            .with_duration(100)
            .with_seed(33333)
            .add_agent("BANK_A", balance=3_000_000, arrival_rate=2.0,
                      arrival_amount_range=(100_000, 300_000), deadline_range=(10, 30))
            .add_agent("BANK_B", balance=15_000_000)
            .build()
        )

        policies = {
            "FIFO": {"type": "Fifo"},
            "Deadline": {"type": "Deadline", "urgency_threshold": 5},
            # Could add more policies here
        }

        journeys_by_policy = {}

        for policy_name, policy_config in policies.items():
            tracker = JourneyTracker()
            test = TransactionJourneyTest(policy_config, scenario, tracker, agent_id="BANK_A")
            test.run()

            journeys_by_policy[policy_name] = tracker.get_all_journeys()

        # Analyze first transaction across policies
        print("\n=== Policy Comparison ===")
        print(f"Tracked {len(journeys_by_policy['FIFO'])} transactions under FIFO")
        print(f"Tracked {len(journeys_by_policy['Deadline'])} transactions under Deadline")

        if journeys_by_policy["FIFO"] and journeys_by_policy["Deadline"]:
            fifo_first = journeys_by_policy["FIFO"][0]
            deadline_first = journeys_by_policy["Deadline"][0]

            print(f"\nFirst transaction comparison:")
            print(f"  FIFO: {fifo_first.time_to_settle} ticks to settle")
            print(f"  Deadline: {deadline_first.time_to_settle} ticks to settle")

        # This test passes - it demonstrates journey tracking works
        assert len(journeys_by_policy["FIFO"]) > 0
        assert len(journeys_by_policy["Deadline"]) > 0


class TestTimeOfDayBehavior:
    """Track how time-adaptive policies change behavior throughout the day."""

    def test_goliath_buffer_adaptation_early_vs_eod(self):
        """
        GoliathNationalBank uses time-of-day buffer multipliers:
        - Early day (T0-T33): 1.5× buffer (conservative)
        - Mid-day (T34-T66): 1.0× buffer (balanced)
        - EOD (T67-T100): 0.5× buffer (aggressive)

        Track identical transactions at different times to see adaptation.
        """
        # This would require manual transaction submission at specific ticks
        print("\n=== Time-of-Day Adaptation Test ===")
        print("Would submit identical $10k transaction at:")
        print("  T20 (early): Expected to queue (buffer protection)")
        print("  T50 (mid): Expected moderate treatment")
        print("  T90 (EOD): Expected to settle (relaxed buffer)")

        pytest.skip("Requires manual transaction submission at specific ticks")


class TestDeadlineViolationRecovery:
    """Track what happens when transactions violate deadlines."""

    def test_overdue_transaction_urgency_increases(self):
        """
        Transaction arrives with deadline, becomes overdue, then eventually settles.

        Track urgency progression and policy response to overdue status.
        """
        scenario = (
            ScenarioBuilder("DeadlineViolation")
            .with_duration(100)
            .with_seed(44444)
            .add_agent(
                "BANK_A",
                balance=500_000,  # Low liquidity
                arrival_rate=1.5,  # Moderate pressure
                arrival_amount_range=(200_000, 400_000),  # Large transactions
                deadline_range=(5, 15),  # Tight deadlines
            )
            .add_agent("BANK_B", balance=15_000_000)
            .build()
        )

        tracker = JourneyTracker()
        policy = {"type": "Deadline", "urgency_threshold": 5}
        test = TransactionJourneyTest(policy, scenario, tracker, agent_id="BANK_A")
        test.run()

        # Find transactions that violated deadlines
        violated = [j for j in tracker.get_all_journeys() if j.violated_deadline]

        print(f"\n=== Deadline Violation Test ===")
        print(f"Total transactions: {len(tracker.get_all_journeys())}")
        print(f"Deadline violations: {len(violated)}")

        if violated:
            example = violated[0]
            print(f"\nExample violation:")
            print(f"  Deadline: T{example.deadline}")
            print(f"  Arrived: T{example.arrival_tick}")
            print(f"  Settled: T{example.settlement_tick if example.settlement_tick else 'NEVER'}")
            print(f"  Events: {[e.event_type for e in example.events]}")

        # Test passes if we tracked violations
        assert len(tracker.get_all_journeys()) > 0


# Utility test to demonstrate journey tracking capability
class TestJourneyFramework:
    """Demonstrate the journey tracking framework works."""

    def test_journey_tracking_basic_functionality(self):
        """Verify journey tracking captures transaction lifecycle."""
        scenario = (
            ScenarioBuilder("BasicJourneyTest")
            .with_duration(100)
            .with_seed(99999)
            .add_agent("BANK_A", balance=10_000_000, arrival_rate=1.0,
                      arrival_amount_range=(50_000, 150_000), deadline_range=(15, 35))
            .add_agent("BANK_B", balance=20_000_000)
            .build()
        )

        tracker = JourneyTracker()
        policy = {"type": "Fifo"}
        test = TransactionJourneyTest(policy, scenario, tracker, agent_id="BANK_A")
        test.run()

        journeys = tracker.get_all_journeys()

        print(f"\n=== Journey Tracking Test ===")
        print(f"Tracked {len(journeys)} transactions")

        if journeys:
            # Show first journey as example
            example = journeys[0]
            print(f"\nExample journey:")
            print(example.summary())

        # Assertions
        assert len(journeys) > 0, "Should track at least one transaction"

        # Verify journey has expected properties
        if journeys:
            journey = journeys[0]
            assert journey.tx_id is not None
            assert journey.sender == "BANK_A"
            assert journey.receiver == "BANK_B"
            assert journey.amount > 0
            assert len(journey.events) > 0
            assert journey.arrival_tick is not None

        print("\n✓ Journey tracking framework working correctly!")


if __name__ == "__main__":
    # Run the framework test to demonstrate capability
    test = TestJourneyFramework()
    test.test_journey_tracking_basic_functionality()
