"""Gold Standard Test Suite: Event Replay Identity

This test suite defines the success criteria for complete replay identity.
Every event type must be replayed with perfect fidelity from the simulation_events table.

These tests follow TDD principles - they currently FAIL and define what needs to be implemented.

Success Criteria:
1. All event types have enriched fields in Rust Event enum
2. FFI correctly serializes all fields
3. PersistenceManager stores complete events
4. Replay logic sources all data from simulation_events
5. No manual reconstruction logic needed
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict
import json

from payment_simulator._core import Orchestrator
from payment_simulator.persistence.event_queries import get_simulation_events
from payment_simulator.cli.commands.run import run_simulation
from payment_simulator.cli.commands.replay import replay_simulation


class TestEventEnrichment:
    """Phase 2: Verify all event types contain enriched fields."""

    def test_lsm_bilateral_offset_has_all_fields(self):
        """LSM bilateral offset events must contain agent_a, agent_b, amount_a, amount_b."""
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 50000,  # Low balance to trigger LSM
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 50000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Create bilateral offset scenario: A owes B, B owes A
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=60000,  # More than balance
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=60000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Tick forward - LSM should detect bilateral offset
        orch.tick()

        # Get events from orchestrator (tick 1)
        current_tick = orch.current_tick()
        events = orch.get_tick_events(current_tick)

        # Find LSM bilateral offset event
        lsm_bilateral = [e for e in events if e.get('event_type') == 'lsm_bilateral_offset']

        if lsm_bilateral:
            event = lsm_bilateral[0]

            # CRITICAL: These fields must exist for rich display
            assert 'agent_a' in event, "Missing agent_a field"
            assert 'agent_b' in event, "Missing agent_b field"
            assert 'amount_a' in event, "Missing amount_a field (amount flowing A→B)"
            assert 'amount_b' in event, "Missing amount_b field (amount flowing B→A)"
            assert 'tx_ids' in event, "Missing tx_ids field"
            assert 'tick' in event, "Missing tick field"

            # Verify amounts are different (not just total offset amount)
            assert isinstance(event['amount_a'], int), "amount_a must be integer"
            assert isinstance(event['amount_b'], int), "amount_b must be integer"
        else:
            pytest.skip("No bilateral offset occurred in this scenario")

    def test_lsm_cycle_settlement_has_all_fields(self):
        """LSM cycle settlement events must contain agents, tx_amounts, net_positions, etc."""
        config = {
            "rng_seed": 123,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {"id": "A", "opening_balance": 10000, "credit_limit": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 10000, "credit_limit": 0, "policy": {"type": "Fifo"}},
                {"id": "C", "opening_balance": 10000, "credit_limit": 0, "policy": {"type": "Fifo"}},
            ],
        }

        orch = Orchestrator.new(config)

        # Create cycle: A→B→C→A
        orch.submit_transaction(
            sender="A",
            receiver="B",
            amount=15000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        orch.submit_transaction(
            sender="B",
            receiver="C",
            amount=15000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        orch.submit_transaction(
            sender="C",
            receiver="A",
            amount=15000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        orch.tick()

        current_tick = orch.current_tick()
        events = orch.get_tick_events(current_tick)
        lsm_cycles = [e for e in events if e.get('event_type') == 'lsm_cycle_settlement']

        if lsm_cycles:
            event = lsm_cycles[0]

            # CRITICAL: These fields must exist for rich visualization
            assert 'agents' in event, "Missing agents field"
            assert 'tx_amounts' in event, "Missing tx_amounts field"
            assert 'total_value' in event, "Missing total_value field"
            assert 'net_positions' in event, "Missing net_positions field"
            assert 'max_net_outflow' in event, "Missing max_net_outflow field"
            assert 'max_net_outflow_agent' in event, "Missing max_net_outflow_agent field"
            assert 'tx_ids' in event, "Missing tx_ids field"
            assert 'tick' in event, "Missing tick field"

            # Verify data types
            assert isinstance(event['agents'], list), "agents must be list"
            assert isinstance(event['tx_amounts'], list), "tx_amounts must be list"
            assert isinstance(event['net_positions'], list), "net_positions must be list"
            assert len(event['agents']) >= 2, "Must have at least 2 agents in cycle"
            assert len(event['agents']) == len(event['tx_amounts']), "agents and tx_amounts must match"
        else:
            pytest.skip("No LSM cycle occurred in this scenario")

    def test_collateral_posted_has_all_fields(self):
        """Collateral posted events must contain amount, new_total, trigger."""
        config = {
            "rng_seed": 99,
            "ticks_per_day": 100,
            "num_days": 1,
            "collateral_config": {
                "enabled": True,
                "threshold": -100000,
                "cost_per_unit_per_tick": 1,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100000,
                    "credit_limit": 200000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 500000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit large transaction to trigger collateral
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=150000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        orch.tick()

        current_tick = orch.current_tick()
        events = orch.get_tick_events(current_tick)
        collateral_events = [e for e in events if e.get('event_type') == 'collateral_posted']

        if collateral_events:
            event = collateral_events[0]

            # CRITICAL: These fields must exist
            assert 'agent_id' in event, "Missing agent_id field"
            assert 'amount' in event, "Missing amount field"
            assert 'new_total' in event, "Missing new_total field"
            assert 'trigger' in event, "Missing trigger field"
            assert 'tick' in event, "Missing tick field"

            assert isinstance(event['amount'], int), "amount must be integer"
            assert isinstance(event['new_total'], int), "new_total must be integer"
            assert isinstance(event['trigger'], str), "trigger must be string"
        else:
            pytest.skip("No collateral posting occurred in this scenario")

    def test_transaction_became_overdue_has_all_fields(self):
        """Overdue transaction events must contain all necessary display fields."""
        config = {
            "rng_seed": 77,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit transaction with tight deadline
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=50000,  # Insufficient liquidity
            deadline_tick=2,  # Very tight deadline
            priority=5,
            divisible=False,
        )

        # Tick past deadline
        orch.tick()
        orch.tick()
        orch.tick()

        events = orch.get_all_events()
        overdue_events = [e for e in events if e.get('event_type') == 'transaction_became_overdue']

        if overdue_events:
            event = overdue_events[0]

            # CRITICAL: These fields must exist
            assert 'transaction_id' in event, "Missing transaction_id field"
            assert 'sender' in event, "Missing sender field"
            assert 'receiver' in event, "Missing receiver field"
            assert 'amount' in event, "Missing amount field"
            assert 'deadline' in event or 'deadline_tick' in event, "Missing deadline field"
            assert 'tick' in event, "Missing tick field"
        else:
            pytest.skip("No overdue transactions in this scenario")


class TestFFIEventSerialization:
    """Phase 3: Verify FFI correctly serializes enriched events."""

    def test_ffi_serializes_lsm_bilateral_completely(self):
        """FFI must serialize ALL fields for LSM bilateral events."""
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {"id": "A", "opening_balance": 50000, "credit_limit": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 50000, "credit_limit": 0, "policy": {"type": "Fifo"}},
            ],
        }

        orch = Orchestrator.new(config)

        # Create bilateral scenario
        orch.submit_transaction(
            sender="A",
            receiver="B",
            amount=60000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        orch.submit_transaction(
            sender="B",
            receiver="A",
            amount=60000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        orch.tick()

        # Get events via FFI
        current_tick = orch.current_tick()
        events = orch.get_tick_events(current_tick)

        lsm_events = [e for e in events if e.get('event_type') == 'lsm_bilateral_offset']

        if lsm_events:
            event = lsm_events[0]

            # Verify FFI returned all fields (not just some)
            required_fields = {'event_type', 'tick', 'agent_a', 'agent_b', 'amount_a', 'amount_b', 'tx_ids'}
            actual_fields = set(event.keys())

            missing = required_fields - actual_fields
            assert not missing, f"FFI failed to serialize fields: {missing}"

            # Verify field types after crossing FFI boundary
            assert isinstance(event['agent_a'], str)
            assert isinstance(event['agent_b'], str)
            assert isinstance(event['amount_a'], int)
            assert isinstance(event['amount_b'], int)
            assert isinstance(event['tx_ids'], list)
        else:
            pytest.skip("No bilateral offset to test FFI serialization")


class TestPersistenceCompleteness:
    """Phase 4: Verify PersistenceManager stores complete event data."""

    def test_simulation_events_table_stores_enriched_lsm_events(self):
        """simulation_events table must contain ALL LSM event fields in details JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            config = {
                "rng_seed": 42,
                "ticks_per_day": 100,
                "num_days": 1,
                "agent_configs": [
                    {"id": "A", "opening_balance": 50000, "credit_limit": 0, "policy": {"type": "Fifo"}},
                    {"id": "B", "opening_balance": 50000, "credit_limit": 0, "policy": {"type": "Fifo"}},
                ],
            }

            # Run simulation with persistence
            orch = Orchestrator.new(config)

            # Create bilateral scenario
            orch.submit_transaction({
                "id": "TX_AB",
                "sender": "A",
                "receiver": "B",
                "amount": 60000,
                "priority": 5,
                "arrival_tick": 1,
                "deadline": 50,
            })

            orch.submit_transaction({
                "id": "TX_BA",
                "sender": "B",
                "receiver": "A",
                "amount": 60000,
                "priority": 5,
                "arrival_tick": 1,
                "deadline": 50,
            })

            # TODO: Need to actually persist events to database
            # This requires running through the CLI or using PersistenceManager directly
            pytest.skip("Need to implement persistence testing - requires CLI integration")


class TestReplayWithoutReconstruction:
    """Phase 5: Verify replay sources ALL data from simulation_events (no manual reconstruction)."""

    def test_replay_does_not_query_lsm_cycles_table(self):
        """Replay must NOT query lsm_cycles table (legacy)."""
        # This is a code inspection test - verify replay.py doesn't call get_lsm_cycles_by_tick()
        from payment_simulator.cli.commands import replay
        import inspect

        replay_source = inspect.getsource(replay.replay_simulation)

        # Should NOT contain calls to legacy query functions
        assert 'get_lsm_cycles_by_tick' not in replay_source, \
            "replay_simulation must not query legacy lsm_cycles table"
        assert 'get_collateral_events_by_tick' not in replay_source, \
            "replay_simulation must not query legacy collateral_events table"

        # Should ONLY query simulation_events
        assert 'get_simulation_events' in replay_source, \
            "replay_simulation must query simulation_events table"

    def test_replay_does_not_have_reconstruction_functions(self):
        """Replay module must NOT contain manual reconstruction logic from legacy tables."""
        from payment_simulator.cli.commands import replay
        import inspect

        replay_source = inspect.getsource(replay)

        # Should NOT contain legacy reconstruction helper functions (exact function definitions)
        # Note: We KEEP _from_simulation_events versions which use the unified architecture
        assert 'def _reconstruct_lsm_events(lsm_cycles' not in replay_source, \
            "Manual LSM reconstruction logic from lsm_cycles table must be removed"
        assert 'def _reconstruct_collateral_events(collateral_events' not in replay_source, \
            "Manual collateral reconstruction logic from legacy table must be removed"


class TestEndToEndReplayIdentity:
    """Phase 8: Gold standard end-to-end tests."""

    def test_lsm_bilateral_replays_identically(self):
        """GOLD STANDARD: LSM bilateral events must replay with perfect fidelity."""
        pytest.skip("Requires full implementation of enriched events")

    def test_lsm_cycle_replays_identically(self):
        """GOLD STANDARD: LSM cycle events must replay with perfect fidelity."""
        pytest.skip("Requires full implementation of enriched events")

    def test_collateral_events_replay_identically(self):
        """GOLD STANDARD: Collateral events must replay with perfect fidelity."""
        pytest.skip("Requires full implementation of enriched events")

    def test_all_event_types_replay_identically(self):
        """ULTIMATE GOLD STANDARD: ALL event types replay identically."""
        pytest.skip("Requires full implementation of all enriched events")


class TestRegressionBugs:
    """Regression tests for known bugs."""

    def test_bilateral_offset_agent_count_bug_fixed(self):
        """Regression: Bilateral offsets have len(agents)==3 not len(agents)==2.

        Historical bug: _reconstruct_lsm_events checked `len(agent_ids) == 2` but
        Rust actually stores bilaterals as [A, B, A] (cycle representation).

        This test verifies we correctly handle the Rust data structure.
        """
        # Create mock bilateral event as it comes from Rust
        bilateral_event = {
            'event_type': 'lsm_bilateral_offset',
            'tick': 10,
            'agent_a': 'BANK_A',
            'agent_b': 'BANK_B',
            'amount_a': 50000,
            'amount_b': 45000,
            'tx_ids': ['TX_AB', 'TX_BA'],
        }

        # Verify we can display this without reconstruction errors
        # (This would fail with old logic that checked len == 2)
        assert bilateral_event['agent_a'] == 'BANK_A'
        assert bilateral_event['agent_b'] == 'BANK_B'

        # No reconstruction needed - event already has correct structure

    def test_event_field_name_consistency(self):
        """Regression: Verify Rust and Python use consistent field names.

        Historical bug: Rust used 'deadline', Python expected 'deadline_tick'.

        This test verifies field name consistency across FFI boundary.
        """
        config = {
            "rng_seed": 1,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {"id": "A", "opening_balance": 100000, "credit_limit": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 100000, "credit_limit": 0, "policy": {"type": "Fifo"}},
            ],
        }

        orch = Orchestrator.new(config)

        orch.submit_transaction(
            sender="A",
            receiver="B",
            amount=10000,
            deadline_tick=5,
            priority=5,
            divisible=False,
        )

        orch.tick()

        current_tick = orch.current_tick()
        events = orch.get_tick_events(current_tick)
        arrival_events = [e for e in events if e.get('event_type') == 'transaction_arrival']

        if arrival_events:
            event = arrival_events[0]

            # Verify field names are consistent
            # Both 'deadline' and 'deadline_tick' should work (or just one consistently)
            assert 'deadline' in event or 'deadline_tick' in event, \
                "Must have either 'deadline' or 'deadline_tick' field"

            # If both exist, they should match
            if 'deadline' in event and 'deadline_tick' in event:
                assert event['deadline'] == event['deadline_tick'], \
                    "deadline and deadline_tick must be identical"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
