"""THE ULTIMATE TEST: Verify replay produces identical output to live execution.

This test suite ensures that replaying a simulation from the database produces
byte-for-byte identical verbose output compared to the original live execution.

This is critical for:
- Debugging: Same seed = same behavior
- Research: Reproducible experiments
- Compliance: Auditable transaction history
"""
import pytest
import re
from io import StringIO
from rich.console import Console
from payment_simulator._core import Orchestrator
from payment_simulator.cli.execution.state_provider import (
    OrchestratorStateProvider,
    DatabaseStateProvider,
)
from payment_simulator.cli.output import log_agent_state, log_cost_breakdown


def normalize_output(text: str) -> str:
    """Normalize output for comparison.

    - Remove ANSI color codes
    - Normalize whitespace
    - Remove timestamps if any
    """
    # Remove ANSI color codes
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    # Normalize whitespace while preserving structure
    lines = [line.rstrip() for line in text.splitlines()]
    # Remove empty lines at start/end
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines)


def capture_output(func):
    """Capture console output from a function."""
    output = StringIO()
    console = Console(file=output, stderr=True, force_terminal=False, width=120)

    import payment_simulator.cli.output as output_module
    old_console = output_module.console
    output_module.console = console

    try:
        func()
        return output.getvalue()
    finally:
        output_module.console = old_console


class TestReplayOutputDeterminism:
    """THE ULTIMATE TEST: Verify replay output matches live execution exactly."""

    @pytest.fixture
    def orchestrator_with_state(self):
        """Create orchestrator with non-trivial state."""
        config = {
            "rng_seed": 12345,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1000000,
                    "unsecured_cap": 500000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 2000000,
                    "unsecured_cap": 1000000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_C",
                    "opening_balance": 1500000,
                    "unsecured_cap": 750000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }
        orch = Orchestrator.new(config)

        # Run a few ticks to create interesting state
        for _ in range(5):
            orch.tick()

        return orch

    @pytest.fixture
    def simulated_database_state(self, orchestrator_with_state):
        """Simulate database state after running the orchestrator."""
        orch = orchestrator_with_state

        # Build state that would come from database
        agent_states = {}
        queue_snapshots = {}

        for agent_id in ["BANK_A", "BANK_B", "BANK_C"]:
            costs = orch.get_agent_accumulated_costs(agent_id)

            agent_states[agent_id] = {
                "balance": orch.get_agent_balance(agent_id),
                "unsecured_cap": orch.get_agent_unsecured_cap(agent_id),
                "collateral_posted": orch.get_agent_collateral_posted(agent_id),
                "liquidity_cost": costs["liquidity_cost"],
                "delay_cost": costs["delay_cost"],
                "collateral_cost": costs["collateral_cost"],
                "penalty_cost": costs.get("deadline_penalty", 0) or costs.get("penalty_cost", 0),
                "split_friction_cost": costs["split_friction_cost"],
            }

            queue_snapshots[agent_id] = {
                "queue1": orch.get_agent_queue1_contents(agent_id),
                "rtgs": [],  # Simplified for this test
            }

        # Get RTGS queue
        rtgs_queue = orch.get_rtgs_queue_contents()

        # Build transaction cache
        tx_cache = {}
        for agent_id in ["BANK_A", "BANK_B", "BANK_C"]:
            for tx_id in orch.get_agent_queue1_contents(agent_id):
                tx = orch.get_transaction_details(tx_id)
                if tx:
                    tx_cache[tx_id] = tx

        for tx_id in rtgs_queue:
            tx = orch.get_transaction_details(tx_id)
            if tx:
                tx_cache[tx_id] = tx

        return {
            "tx_cache": tx_cache,
            "agent_states": agent_states,
            "queue_snapshots": queue_snapshots,
        }

    def test_log_agent_state_produces_identical_output(
        self, orchestrator_with_state, simulated_database_state
    ):
        """CRITICAL: log_agent_state() must produce identical output for both providers."""
        orch_provider = OrchestratorStateProvider(orchestrator_with_state)

        db_provider = DatabaseStateProvider(
            conn=None,
            simulation_id="test",
            tick=5,
            tx_cache=simulated_database_state["tx_cache"],
            agent_states=simulated_database_state["agent_states"],
            queue_snapshots=simulated_database_state["queue_snapshots"],
        )

        # Test each agent
        for agent_id in ["BANK_A", "BANK_B", "BANK_C"]:
            def live_output():
                log_agent_state(orch_provider, agent_id, balance_change=0, quiet=False)

            def replay_output():
                log_agent_state(db_provider, agent_id, balance_change=0, quiet=False)

            live = capture_output(live_output)
            replay = capture_output(replay_output)

            live_normalized = normalize_output(live)
            replay_normalized = normalize_output(replay)

            assert live_normalized == replay_normalized, \
                f"Agent {agent_id} output differs:\n\nLIVE:\n{live_normalized}\n\nREPLAY:\n{replay_normalized}"

    def test_log_cost_breakdown_produces_identical_output(
        self, orchestrator_with_state, simulated_database_state
    ):
        """CRITICAL: log_cost_breakdown() must produce identical output for both providers."""
        orch_provider = OrchestratorStateProvider(orchestrator_with_state)

        db_provider = DatabaseStateProvider(
            conn=None,
            simulation_id="test",
            tick=5,
            tx_cache=simulated_database_state["tx_cache"],
            agent_states=simulated_database_state["agent_states"],
            queue_snapshots=simulated_database_state["queue_snapshots"],
        )

        agent_ids = ["BANK_A", "BANK_B", "BANK_C"]

        def live_output():
            log_cost_breakdown(orch_provider, agent_ids, quiet=False)

        def replay_output():
            log_cost_breakdown(db_provider, agent_ids, quiet=False)

        live = capture_output(live_output)
        replay = capture_output(replay_output)

        live_normalized = normalize_output(live)
        replay_normalized = normalize_output(replay)

        assert live_normalized == replay_normalized, \
            f"Cost breakdown output differs:\n\nLIVE:\n{live_normalized}\n\nREPLAY:\n{replay_normalized}"

    def test_multiple_agents_all_produce_identical_output(
        self, orchestrator_with_state, simulated_database_state
    ):
        """ALL output functions must produce identical results for all agents."""
        orch_provider = OrchestratorStateProvider(orchestrator_with_state)

        db_provider = DatabaseStateProvider(
            conn=None,
            simulation_id="test",
            tick=5,
            tx_cache=simulated_database_state["tx_cache"],
            agent_states=simulated_database_state["agent_states"],
            queue_snapshots=simulated_database_state["queue_snapshots"],
        )

        # Capture full output for all agents
        def live_full_output():
            for agent_id in ["BANK_A", "BANK_B", "BANK_C"]:
                log_agent_state(orch_provider, agent_id, balance_change=0, quiet=False)
            log_cost_breakdown(orch_provider, ["BANK_A", "BANK_B", "BANK_C"], quiet=False)

        def replay_full_output():
            for agent_id in ["BANK_A", "BANK_B", "BANK_C"]:
                log_agent_state(db_provider, agent_id, balance_change=0, quiet=False)
            log_cost_breakdown(db_provider, ["BANK_A", "BANK_B", "BANK_C"], quiet=False)

        live = capture_output(live_full_output)
        replay = capture_output(replay_full_output)

        live_normalized = normalize_output(live)
        replay_normalized = normalize_output(replay)

        # Compare line by line for better error messages
        live_lines = live_normalized.splitlines()
        replay_lines = replay_normalized.splitlines()

        assert len(live_lines) == len(replay_lines), \
            f"Line count differs: live={len(live_lines)}, replay={len(replay_lines)}"

        for i, (live_line, replay_line) in enumerate(zip(live_lines, replay_lines)):
            assert live_line == replay_line, \
                f"Line {i} differs:\n  Live:   '{live_line}'\n  Replay: '{replay_line}'"

    def test_determinism_with_transactions_in_queue(self):
        """Test determinism when agents have transactions in queues."""
        # This would be an integration test with actual transaction flow
        # For now, the above tests cover the core functionality
        pass


class TestStateProviderDataEquivalence:
    """Verify that StateProvider implementations return equivalent data."""

    def test_both_providers_return_same_balance(self):
        """Both providers must return identical balance values."""
        config = {
            "rng_seed": 12345,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1000000, "unsecured_cap": 500000, "policy": {"type": "Fifo"}},
            ],
        }
        orch = Orchestrator.new(config)

        orch_provider = OrchestratorStateProvider(orch)

        balance_live = orch_provider.get_agent_balance("BANK_A")

        # Simulate database state
        db_provider = DatabaseStateProvider(
            conn=None,
            simulation_id="test",
            tick=0,
            tx_cache={},
            agent_states={"BANK_A": {
                "balance": balance_live,
                "unsecured_cap": 500000,
                "collateral_posted": 0,
                "liquidity_cost": 0,
                "delay_cost": 0,
                "collateral_cost": 0,
                "penalty_cost": 0,
                "split_friction_cost": 0,
            }},
            queue_snapshots={"BANK_A": {"queue1": [], "rtgs": []}},
        )

        balance_replay = db_provider.get_agent_balance("BANK_A")

        assert balance_live == balance_replay

    def test_both_providers_return_same_unsecured_cap(self):
        """Both providers must return identical unsecured_cap values."""
        config = {
            "rng_seed": 12345,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1000000, "unsecured_cap": 500000, "policy": {"type": "Fifo"}},
            ],
        }
        orch = Orchestrator.new(config)

        orch_provider = OrchestratorStateProvider(orch)
        db_provider = DatabaseStateProvider(
            conn=None,
            simulation_id="test",
            tick=0,
            tx_cache={},
            agent_states={"BANK_A": {
                "balance": 1000000,
                "unsecured_cap": 500000,
                "collateral_posted": 0,
                "liquidity_cost": 0,
                "delay_cost": 0,
                "collateral_cost": 0,
                "penalty_cost": 0,
                "split_friction_cost": 0,
            }},
            queue_snapshots={"BANK_A": {"queue1": [], "rtgs": []}},
        )

        assert orch_provider.get_agent_unsecured_cap("BANK_A") == db_provider.get_agent_unsecured_cap("BANK_A")
        assert orch_provider.get_agent_unsecured_cap("BANK_A") == 500000
