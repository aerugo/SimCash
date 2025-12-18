"""Tests for prompt section hierarchy.

INV-12: All evaluation modes now provide a SINGLE simulation trace.
The initial_simulation and worst_seed sections were removed to ensure
consistent context across bootstrap, deterministic-pairwise, and
deterministic-temporal modes.

This file tests the unified section structure after INV-12.
"""

from __future__ import annotations

import pytest


class TestUnifiedSimulationOutputSection:
    """Tests that simulation output section is unified across modes (INV-12)."""

    def test_simulation_output_section_exists(self) -> None:
        """Prompt should have SIMULATION OUTPUT section."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {}},
            current_metrics={"total_cost_mean": 5000},
            agent_id="BANK_A",
            simulation_trace="[tick 0] Event log here",
            sample_seed=12345,
            sample_cost=5000,
        )

        # Should have unified SIMULATION OUTPUT section
        assert "SIMULATION OUTPUT" in prompt

    def test_no_initial_simulation_section(self) -> None:
        """INV-12: Initial simulation section should NOT exist (removed for consistency)."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {}},
            current_metrics={"total_cost_mean": 5000},
            agent_id="BANK_A",
            # Deprecated parameter - should be ignored
            initial_simulation_output="Initial simulation event log here",
            simulation_trace="Best seed event log here",
            sample_seed=12345,
            sample_cost=5000,
        )

        # Initial simulation section should NOT exist (removed in INV-12)
        assert "INITIAL SIMULATION" not in prompt
        # But simulation output section should exist
        assert "SIMULATION OUTPUT" in prompt

    def test_no_worst_seed_section(self) -> None:
        """INV-12: Worst seed section should NOT exist (only show one trace)."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {}},
            current_metrics={"total_cost_mean": 5000},
            agent_id="BANK_A",
            simulation_trace="Event log",
            sample_seed=12345,
            sample_cost=5000,
        )

        # Worst seed section should NOT exist (removed in INV-12)
        assert "Worst Performing Seed" not in prompt
        assert "worst_seed" not in prompt.lower() or "worst_seed_output" not in prompt


class TestSimulationTraceSectionContent:
    """Tests for simulation trace section content."""

    def test_simulation_trace_shows_seed_number(self) -> None:
        """Simulation trace section should show the seed number."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {}},
            current_metrics={"total_cost_mean": 5000},
            agent_id="BANK_A",
            simulation_trace="[tick 0] Event log here",
            sample_seed=42,
            sample_cost=5000,
        )

        # Should show seed number
        assert "#42" in prompt or "Seed #42" in prompt or "seed #42" in prompt.lower()

    def test_simulation_trace_content_included(self) -> None:
        """Simulation trace content should be included in prompt."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {}},
            current_metrics={"total_cost_mean": 5000},
            agent_id="BANK_A",
            simulation_trace="[tick 0] Posted collateral...",
            sample_seed=12345,
            sample_cost=5000,
        )

        # Should include trace content
        assert "Posted collateral" in prompt


class TestDeprecatedParametersStillAccepted:
    """Tests that deprecated parameters are still accepted for backward compatibility."""

    def test_initial_simulation_output_parameter_accepted(self) -> None:
        """build_single_agent_context accepts initial_simulation_output (deprecated)."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )
        import inspect

        sig = inspect.signature(build_single_agent_context)
        params = list(sig.parameters.keys())

        # Deprecated but still accepted for backward compatibility
        assert "initial_simulation_output" in params

    def test_best_seed_output_parameter_accepted(self) -> None:
        """build_single_agent_context accepts best_seed_output (deprecated, use simulation_trace)."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )
        import inspect

        sig = inspect.signature(build_single_agent_context)
        params = list(sig.parameters.keys())

        # Deprecated but still accepted for backward compatibility
        assert "best_seed_output" in params
        # New preferred parameter
        assert "simulation_trace" in params


class TestSectionNumbering:
    """Tests that section numbering is correct after INV-12 simplification."""

    def test_section_numbers_are_sequential(self) -> None:
        """Section numbers should be sequential (1-7 after INV-12)."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentIterationRecord,
        )

        prompt = build_single_agent_context(
            current_iteration=2,
            current_policy={"parameters": {}},
            current_metrics={"total_cost_mean": 5000},
            agent_id="BANK_A",
            simulation_trace="Simulation log",
            sample_seed=12345,
            sample_cost=5000,
            cost_breakdown={"delay": 3000, "overdraft": 2000},
            iteration_history=[
                SingleAgentIterationRecord(
                    iteration=1,
                    metrics={"total_cost_mean": 6000},
                    policy={"parameters": {"threshold": 5.0}},
                ),
            ],
        )

        # Check that required sections are present
        import re
        section_numbers = re.findall(r"## (\d+)\.", prompt)
        numbers = [int(n) for n in section_numbers]

        # After INV-12: 7 sections total
        # 1. Current State Summary
        # 2. Cost Analysis
        # 3. Optimization Guidance
        # 4. Simulation Output (unified)
        # 5. Full Iteration History
        # 6. Parameter Trajectories
        # 7. Final Instructions
        assert 4 in numbers, "Simulation Output should be section 4"
        assert 5 in numbers, "Full Iteration History should be section 5"
        assert 7 in numbers, "Final Instructions should be section 7"

        # Verify sequential ordering
        for i, n in enumerate(numbers):
            if i > 0:
                assert n > numbers[i-1], f"Section {n} should come after {numbers[i-1]}"
