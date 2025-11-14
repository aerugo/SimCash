"""
TDD Tests for Issue #3: Budget Operation Display

Problem:
- SetReleaseBudget actions execute and persist to database
- Budget values are correct in events
- BUT: Verbose output doesn't show budget operations

Expected:
- Budget operations should be visible in verbose output
- Should show agent ID, max_value, and optional counterparty focus

TDD Approach:
1. RED: Test fails - no budget display in verbose output
2. GREEN: Add log_budget_operations() to display
3. REFACTOR: Clean up and verify
"""

import pytest
import json
from io import StringIO
import sys
from payment_simulator._core import Orchestrator
from payment_simulator.cli.execution.display import display_tick_verbose_output
from payment_simulator.cli.execution.state_provider import OrchestratorStateProvider


class TestBudgetOperationDisplay:
    """Test that SetReleaseBudget operations are displayed in verbose output."""

    def test_budget_operations_appear_in_verbose_output(self, tmp_path):
        """Test that SetReleaseBudget operations are displayed in verbose tick output.

        TDD RED: This test will FAIL because:
        - Budget operations execute but aren't displayed
        - Need to add log_budget_operations() function
        """

        # Create policy with SetReleaseBudget action
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "cost_params": {
                "liquidity_cost_bps_per_day": 10,
                "delay_cost_per_tick": 0.1,
                "deadline_penalty": 100.0,
                "overdue_delay_multiplier": 5.0,
                "split_friction_bps": 5,
            },
            "agent_configs": [
                {
                    "id": "TEST_BANK",
                    "opening_balance": 100000,
                    "credit_limit": 50000,
                    "policy_id": "test_budget",
                }
            ],
        }

        # Policy that sets budget at tick 0
        policy_def = {
            "version": "1.0",
            "policy_id": "test_budget",
            "description": "Test policy that sets release budget",
            "parameters": {},
            "bank_tree": {
                "type": "action",
                "node_id": "SetBudget",
                "action": "SetReleaseBudget",
                "parameters": {
                    "max_value_to_release": {"value": 50000.0}
                }
            },
            "payment_tree": {
                "type": "action",
                "node_id": "HoldAll",
                "action": "Hold"
            }
        }

        # Pass policy as JSON string
        config["agent_configs"][0]["policy"] = {
            "type": "FromJson",
            "json": json.dumps(policy_def)
        }

        orch = Orchestrator.new(config)

        # Run first tick - should set budget
        orch.tick()

        # Get events from tick 0
        events = orch.get_tick_events(0)
        print(f"\nTotal events: {len(events)}")

        # Print all events to see what's actually generated
        for event in events:
            print(f"  All events: {event}")

        # Filter for budget events (event_type is 'BankBudgetSet')
        budget_events = [
            e for e in events
            if e.get('event_type') in ['BankBudgetSet', 'BudgetSet', 'SetReleaseBudget']
        ]
        print(f"Budget events: {len(budget_events)}")
        for event in budget_events:
            print(f"  Budget event: {event}")

        # Verify budget event exists
        assert len(budget_events) > 0, "SetReleaseBudget should generate events"

        # Now test verbose display
        # Capture stderr (console writes to stderr, not stdout)
        captured_output = StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured_output

        try:
            # Create state provider
            provider = OrchestratorStateProvider(orch)

            # Display tick verbose output
            display_tick_verbose_output(
                provider=provider,
                events=events,
                tick_num=0,
                agent_ids=["TEST_BANK"],
                prev_balances={},
                num_arrivals=0,
                num_settlements=0,
                num_lsm_releases=0,
                total_cost=0
            )

        finally:
            sys.stderr = old_stderr

        output = captured_output.getvalue()
        print(f"\nVerbose output:\n{output}")

        # TDD GREEN: These assertions should now PASS
        assert "Budget" in output or "budget" in output, \
            "Verbose output should display budget operations"

        # Check for specific budget details (displayed as $500.00)
        assert "500" in output, \
            "Should show budget max_value (50000 cents = $500.00)"

        assert "TEST_BANK" in output, \
            "Should show agent ID that set budget"

    def test_budget_display_shows_all_fields(self, tmp_path):
        """Test that budget display shows all relevant fields.

        TDD RED: Will fail because display function doesn't exist yet.
        """

        # Create policy with full budget parameters
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "cost_params": {
                "liquidity_cost_bps_per_day": 10,
                "delay_cost_per_tick": 0.1,
                "deadline_penalty": 100.0,
                "overdue_delay_multiplier": 5.0,
                "split_friction_bps": 5,
            },
            "agent_configs": [
                {
                    "id": "TEST_BANK",
                    "opening_balance": 100000,
                    "credit_limit": 50000,
                    "policy_id": "test_budget_full",
                },
                {
                    "id": "COUNTERPARTY",
                    "opening_balance": 100000,
                    "credit_limit": 0,
                    "policy_id": "test_budget_full",
                }
            ],
        }

        # Policy with focus_counterparties
        policy_def = {
            "version": "1.0",
            "policy_id": "test_budget_full",
            "description": "Test policy with full budget parameters",
            "parameters": {},
            "bank_tree": {
                "type": "action",
                "node_id": "SetBudget",
                "action": "SetReleaseBudget",
                "parameters": {
                    "max_value_to_release": {"value": 75000.0},
                    "focus_counterparties": {"value": ["COUNTERPARTY"]},
                    "max_per_counterparty": {"value": 25000.0}
                }
            },
            "payment_tree": {
                "type": "action",
                "node_id": "HoldAll",
                "action": "Hold"
            }
        }

        config["agent_configs"][0]["policy"] = {
            "type": "FromJson",
            "json": json.dumps(policy_def)
        }
        config["agent_configs"][1]["policy"] = {
            "type": "FromJson",
            "json": json.dumps(policy_def)
        }

        orch = Orchestrator.new(config)
        orch.tick()

        events = orch.get_tick_events(0)
        budget_events = [
            e for e in events
            if e.get('event_type') in ['BankBudgetSet', 'BudgetSet', 'SetReleaseBudget']
        ]

        assert len(budget_events) > 0

        # Capture verbose output (console writes to stderr)
        captured_output = StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured_output

        try:
            provider = OrchestratorStateProvider(orch)
            display_tick_verbose_output(
                provider=provider,
                events=events,
                tick_num=0,
                agent_ids=["TEST_BANK", "COUNTERPARTY"],
                prev_balances={},
                num_arrivals=0,
                num_settlements=0,
                num_lsm_releases=0,
                total_cost=0
            )
        finally:
            sys.stderr = old_stderr

        output = captured_output.getvalue()
        print(f"\nVerbose output:\n{output}")

        # TDD GREEN: These assertions should now PASS
        assert "750" in output, \
            "Should show max_value (75000 cents = $750.00)"

        assert "COUNTERPARTY" in output, \
            "Should show focus_counterparties"

        assert "250" in output, \
            "Should show max_per_counterparty (25000 cents = $250.00)"


if __name__ == "__main__":
    print("=" * 80)
    print("TEST 1: Budget operations appear in verbose output")
    print("=" * 80)
    try:
        test = TestBudgetOperationDisplay()
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            test.test_budget_operations_appear_in_verbose_output(Path(tmpdir))
        print("\n✓ TEST 1 PASSED")
    except AssertionError as e:
        print(f"\n✗ TEST 1 FAILED (RED - expected): {e}")
    except Exception as e:
        print(f"\n✗ TEST 1 ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("TEST 2: Budget display shows all fields")
    print("=" * 80)
    try:
        test = TestBudgetOperationDisplay()
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            test.test_budget_display_shows_all_fields(Path(tmpdir))
        print("\n✓ TEST 2 PASSED")
    except AssertionError as e:
        print(f"\n✗ TEST 2 FAILED (RED - expected): {e}")
    except Exception as e:
        print(f"\n✗ TEST 2 ERROR: {e}")
        import traceback
        traceback.print_exc()
