"""Tests for CRITICAL prompt section hierarchy.

The initial simulation output should be a SEPARATE, PROMINENT section
that appears BEFORE bootstrap samples (best/worst seed).

TDD: These tests should FAIL until the fix is applied.
"""

from __future__ import annotations

import pytest


class TestInitialSimulationSection:
    """Tests that initial simulation has its own prominent section."""

    def test_initial_simulation_is_separate_section(self) -> None:
        """Initial simulation must NOT be inside best_seed_output tags."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {}},
            current_metrics={"total_cost_mean": 5000},
            agent_id="BANK_A",
            initial_simulation_output="Initial simulation event log here",
            best_seed_output="Best seed event log here",
            best_seed=12345,
            best_seed_cost=5000,
        )

        # Initial simulation should have its own section header
        assert "INITIAL SIMULATION" in prompt or "Initial Simulation" in prompt

        # It should NOT be inside <best_seed_output> tags
        best_seed_start = prompt.find("<best_seed_output>")
        best_seed_end = prompt.find("</best_seed_output>")

        if best_seed_start != -1 and best_seed_end != -1:
            best_seed_content = prompt[best_seed_start:best_seed_end]
            assert "INITIAL" not in best_seed_content, (
                "Initial simulation content should NOT be inside <best_seed_output> tags"
            )

    def test_initial_simulation_appears_before_bootstrap_samples(self) -> None:
        """Initial simulation section must appear BEFORE best/worst seed sections."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {}},
            current_metrics={"total_cost_mean": 5000},
            agent_id="BANK_A",
            initial_simulation_output="Initial simulation event log",
            best_seed_output="Best seed event log",
            worst_seed_output="Worst seed event log",
            best_seed=12345,
            best_seed_cost=5000,
            worst_seed=54321,
            worst_seed_cost=15000,
        )

        # Find section positions
        initial_pos = prompt.lower().find("initial simulation")
        best_seed_pos = prompt.lower().find("best performing seed")
        worst_seed_pos = prompt.lower().find("worst performing seed")

        # Initial simulation should be found
        assert initial_pos != -1, "Initial simulation section not found in prompt"

        # Initial simulation should appear BEFORE best and worst seed
        if best_seed_pos != -1:
            assert initial_pos < best_seed_pos, (
                f"Initial simulation (pos {initial_pos}) must appear before "
                f"best seed (pos {best_seed_pos})"
            )
        if worst_seed_pos != -1:
            assert initial_pos < worst_seed_pos, (
                f"Initial simulation (pos {initial_pos}) must appear before "
                f"worst seed (pos {worst_seed_pos})"
            )

    def test_initial_simulation_has_prominent_header(self) -> None:
        """Initial simulation should have a prominent markdown header."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {}},
            current_metrics={"total_cost_mean": 5000},
            agent_id="BANK_A",
            initial_simulation_output="Initial simulation event log",
            best_seed=12345,
            best_seed_cost=5000,
        )

        # Check for prominent header (## or ###)
        assert (
            "## " in prompt
            and ("INITIAL SIMULATION" in prompt.upper() or "Initial Simulation" in prompt)
        ) or (
            "### " in prompt
            and ("INITIAL SIMULATION" in prompt.upper() or "Initial Simulation" in prompt)
        ), "Initial simulation should have a markdown header (## or ###)"


class TestBootstrapSampleLabeling:
    """Tests that bootstrap samples are clearly labeled as such."""

    def test_best_seed_labeled_as_bootstrap_sample(self) -> None:
        """Best seed should be labeled as a bootstrap sample, not confusable with initial."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {}},
            current_metrics={"total_cost_mean": 5000},
            agent_id="BANK_A",
            initial_simulation_output="Initial simulation event log",
            best_seed_output="Best seed event log",
            best_seed=12345,
            best_seed_cost=5000,
        )

        # The best seed section should mention "bootstrap" or "sample"
        best_seed_section_start = prompt.lower().find("best performing seed")
        if best_seed_section_start != -1:
            # Look for "bootstrap" or "sample" near the best seed header
            section_context = prompt[best_seed_section_start:best_seed_section_start + 200].lower()
            assert "bootstrap" in section_context or "sample" in section_context, (
                "Best seed section should mention 'bootstrap' or 'sample' to distinguish "
                "from initial simulation"
            )

    def test_worst_seed_labeled_as_bootstrap_sample(self) -> None:
        """Worst seed should be labeled as a bootstrap sample."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {}},
            current_metrics={"total_cost_mean": 5000},
            agent_id="BANK_A",
            initial_simulation_output="Initial simulation event log",
            worst_seed_output="Worst seed event log",
            worst_seed=54321,
            worst_seed_cost=15000,
        )

        # The worst seed section should mention "bootstrap" or "sample"
        worst_seed_section_start = prompt.lower().find("worst performing seed")
        if worst_seed_section_start != -1:
            section_context = prompt[worst_seed_section_start:worst_seed_section_start + 200].lower()
            assert "bootstrap" in section_context or "sample" in section_context, (
                "Worst seed section should mention 'bootstrap' or 'sample' to distinguish "
                "from initial simulation"
            )


class TestContextTypesUpdated:
    """Tests that SingleAgentContext has the new field."""

    def test_single_agent_context_has_initial_simulation_field(self) -> None:
        """SingleAgentContext must have initial_simulation_output field."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )

        # Create context with initial_simulation_output
        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            initial_simulation_output="Test initial simulation",
        )

        assert hasattr(context, "initial_simulation_output")
        assert context.initial_simulation_output == "Test initial simulation"

    def test_build_single_agent_context_accepts_initial_simulation(self) -> None:
        """build_single_agent_context must accept initial_simulation_output parameter."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )
        import inspect

        sig = inspect.signature(build_single_agent_context)
        params = list(sig.parameters.keys())

        assert "initial_simulation_output" in params, (
            "build_single_agent_context must have initial_simulation_output parameter"
        )


class TestSectionNumbering:
    """Tests that section numbering is correct with new section."""

    def test_section_numbers_are_sequential(self) -> None:
        """Section numbers should be sequential when all sections present."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {}},
            current_metrics={"total_cost_mean": 5000},
            agent_id="BANK_A",
            initial_simulation_output="Initial simulation log",
            best_seed_output="Best seed log",
            worst_seed_output="Worst seed log",
            best_seed=12345,
            best_seed_cost=5000,
            worst_seed=54321,
            worst_seed_cost=15000,
            cost_breakdown={"delay": 3000, "overdraft": 2000},  # Include cost breakdown
        )

        # Check that required sections are present
        import re
        section_numbers = re.findall(r"## (\d+)\.", prompt)
        numbers = [int(n) for n in section_numbers]

        # Initial simulation should be section 4
        assert 4 in numbers, "Initial simulation should be section 4"

        # Bootstrap samples should be section 5
        assert 5 in numbers, "Bootstrap samples should be section 5"

        # Initial simulation (4) should come before bootstrap samples (5)
        idx_initial = numbers.index(4)
        idx_bootstrap = numbers.index(5)
        assert idx_initial < idx_bootstrap, (
            "Initial simulation (section 4) must appear before bootstrap samples (section 5)"
        )
