"""Tests for agent LLM call isolation.

CRITICAL: These tests verify that the LLM optimizing AGENT A never sees
information about AGENT B, and vice versa. This is essential for proper
competitive agent simulation.

Test categories:
1. SingleAgentIterationRecord contains only single-agent data
2. _filter_iteration_history_for_agent properly isolates data
3. build_single_agent_context excludes cross-agent information
4. Generated prompts contain NO references to other agents
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from experiments.castro.prompts.context import (
    IterationRecord,
    SingleAgentIterationRecord,
    SingleAgentContext,
    SingleAgentContextBuilder,
    build_single_agent_context,
    compute_policy_diff,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_policy_a() -> dict[str, Any]:
    """Sample policy for Bank A."""
    return {
        "version": "2.0",
        "policy_id": "bank_a_policy",
        "description": "Bank A optimized policy",
        "parameters": {
            "urgency_threshold": 5.0,
            "liquidity_buffer": 1.5,
            "initial_collateral_fraction": 0.3,
        },
        "payment_tree": {
            "type": "action",
            "node_id": "A1",
            "action": "Release",
        },
    }


@pytest.fixture
def sample_policy_b() -> dict[str, Any]:
    """Sample policy for Bank B."""
    return {
        "version": "2.0",
        "policy_id": "bank_b_policy",
        "description": "Bank B optimized policy",
        "parameters": {
            "urgency_threshold": 3.0,
            "liquidity_buffer": 2.0,
            "initial_collateral_fraction": 0.25,
        },
        "payment_tree": {
            "type": "action",
            "node_id": "B1",
            "action": "Hold",
        },
    }


@pytest.fixture
def sample_metrics() -> dict[str, Any]:
    """Sample metrics for an iteration."""
    return {
        "total_cost_mean": 50000,
        "total_cost_std": 5000,
        "risk_adjusted_cost": 55000,
        "settlement_rate_mean": 1.0,
        "failure_rate": 0.0,
        "best_seed_cost": 45000,
        "worst_seed_cost": 60000,
    }


@pytest.fixture
def dual_agent_iteration_record(
    sample_policy_a: dict[str, Any],
    sample_policy_b: dict[str, Any],
    sample_metrics: dict[str, Any],
) -> IterationRecord:
    """Create an IterationRecord containing both agents' data."""
    return IterationRecord(
        iteration=1,
        metrics=sample_metrics,
        policy_a=sample_policy_a,
        policy_b=sample_policy_b,
        policy_a_changes=["Changed urgency_threshold: 3.0 -> 5.0", "Modified payment_tree"],
        policy_b_changes=["Changed liquidity_buffer: 1.5 -> 2.0", "Added collateral tree"],
        was_accepted=True,
        is_best_so_far=True,
        comparison_to_best="New best policy",
    )


@pytest.fixture
def iteration_history(
    sample_policy_a: dict[str, Any],
    sample_policy_b: dict[str, Any],
) -> list[IterationRecord]:
    """Create a list of IterationRecords for testing."""
    records = []
    for i in range(3):
        # Modify policies slightly for each iteration
        policy_a = sample_policy_a.copy()
        policy_a["parameters"] = sample_policy_a["parameters"].copy()
        policy_a["parameters"]["urgency_threshold"] = 3.0 + i * 1.0

        policy_b = sample_policy_b.copy()
        policy_b["parameters"] = sample_policy_b["parameters"].copy()
        policy_b["parameters"]["liquidity_buffer"] = 1.5 + i * 0.25

        records.append(IterationRecord(
            iteration=i,
            metrics={
                "total_cost_mean": 60000 - i * 5000,
                "total_cost_std": 5000,
                "settlement_rate_mean": 1.0,
                "best_seed_cost": 55000 - i * 5000,
                "worst_seed_cost": 70000 - i * 5000,
            },
            policy_a=policy_a,
            policy_b=policy_b,
            policy_a_changes=[f"Iteration {i} Bank A change"],
            policy_b_changes=[f"Iteration {i} Bank B change"],
            was_accepted=True,
            is_best_so_far=(i == 2),
        ))
    return records


# ============================================================================
# Test SingleAgentIterationRecord
# ============================================================================


class TestSingleAgentIterationRecord:
    """Tests for SingleAgentIterationRecord dataclass."""

    def test_single_agent_record_has_no_other_agent_fields(self) -> None:
        """Verify SingleAgentIterationRecord has no fields for other agents."""
        record = SingleAgentIterationRecord(
            iteration=1,
            metrics={"total_cost_mean": 50000},
            policy={"parameters": {"urgency": 5.0}},
            policy_changes=["Changed urgency"],
        )

        # Check that there are no "policy_a", "policy_b" or similar fields
        field_names = [f.name for f in record.__dataclass_fields__.values()]

        # Should have 'policy' (singular), NOT 'policy_a' or 'policy_b'
        assert "policy" in field_names
        assert "policy_a" not in field_names
        assert "policy_b" not in field_names

        # Should have 'policy_changes' (singular), NOT 'policy_a_changes' or 'policy_b_changes'
        assert "policy_changes" in field_names
        assert "policy_a_changes" not in field_names
        assert "policy_b_changes" not in field_names

    def test_single_agent_record_contains_only_specified_data(self) -> None:
        """Verify SingleAgentIterationRecord stores only single agent's data."""
        policy = {"parameters": {"threshold": 5.0}, "policy_id": "my_policy"}
        changes = ["Change 1", "Change 2"]

        record = SingleAgentIterationRecord(
            iteration=3,
            metrics={"cost": 1000},
            policy=policy,
            policy_changes=changes,
            was_accepted=True,
            is_best_so_far=False,
        )

        assert record.iteration == 3
        assert record.policy == policy
        assert record.policy_changes == changes
        assert record.was_accepted is True
        assert record.is_best_so_far is False


# ============================================================================
# Test _filter_iteration_history_for_agent
# ============================================================================


class TestFilterIterationHistoryForAgent:
    """Tests for the iteration history filtering function."""

    def test_filter_extracts_only_bank_a_data(
        self,
        iteration_history: list[IterationRecord],
    ) -> None:
        """Verify filtering for BANK_A extracts only Bank A's data."""
        # Import the function from the experiment script
        from experiments.castro.scripts.reproducible_experiment import (
            ReproducibleExperiment,
        )

        filtered = ReproducibleExperiment._filter_iteration_history_for_agent(
            iteration_history, "BANK_A"
        )

        assert len(filtered) == len(iteration_history)

        for i, record in enumerate(filtered):
            original = iteration_history[i]

            # Should have Bank A's policy, NOT Bank B's
            assert record.policy == original.policy_a
            assert record.policy != original.policy_b

            # Should have Bank A's changes, NOT Bank B's
            assert record.policy_changes == original.policy_a_changes
            assert record.policy_changes != original.policy_b_changes

            # Metadata should be preserved
            assert record.iteration == original.iteration
            assert record.metrics == original.metrics
            assert record.was_accepted == original.was_accepted
            assert record.is_best_so_far == original.is_best_so_far

    def test_filter_extracts_only_bank_b_data(
        self,
        iteration_history: list[IterationRecord],
    ) -> None:
        """Verify filtering for BANK_B extracts only Bank B's data."""
        from experiments.castro.scripts.reproducible_experiment import (
            ReproducibleExperiment,
        )

        filtered = ReproducibleExperiment._filter_iteration_history_for_agent(
            iteration_history, "BANK_B"
        )

        assert len(filtered) == len(iteration_history)

        for i, record in enumerate(filtered):
            original = iteration_history[i]

            # Should have Bank B's policy, NOT Bank A's
            assert record.policy == original.policy_b
            assert record.policy != original.policy_a

            # Should have Bank B's changes, NOT Bank A's
            assert record.policy_changes == original.policy_b_changes
            assert record.policy_changes != original.policy_a_changes

    def test_filtered_records_are_single_agent_type(
        self,
        iteration_history: list[IterationRecord],
    ) -> None:
        """Verify filtered records are SingleAgentIterationRecord instances."""
        from experiments.castro.scripts.reproducible_experiment import (
            ReproducibleExperiment,
        )

        filtered = ReproducibleExperiment._filter_iteration_history_for_agent(
            iteration_history, "BANK_A"
        )

        for record in filtered:
            assert isinstance(record, SingleAgentIterationRecord)

    def test_bank_a_filter_excludes_all_bank_b_references(
        self,
        iteration_history: list[IterationRecord],
    ) -> None:
        """Verify BANK_A filtered data contains NO Bank B references."""
        from experiments.castro.scripts.reproducible_experiment import (
            ReproducibleExperiment,
        )

        filtered = ReproducibleExperiment._filter_iteration_history_for_agent(
            iteration_history, "BANK_A"
        )

        for record in filtered:
            # Serialize to JSON and check for Bank B references
            json_str = json.dumps({
                "policy": record.policy,
                "changes": record.policy_changes,
            })

            # Should not contain Bank B identifiers
            assert "bank_b" not in json_str.lower()
            assert "Bank B" not in json_str
            assert "BANK_B" not in json_str

            # Should not contain Bank B's unique policy values
            # (Bank B has liquidity_buffer=2.0, Bank A has 1.5)
            assert "bank_b_policy" not in json_str


# ============================================================================
# Test build_single_agent_context
# ============================================================================


class TestBuildSingleAgentContext:
    """Tests for the build_single_agent_context function."""

    def test_context_contains_only_specified_agent_id(self) -> None:
        """Verify context header shows only the specified agent."""
        context = build_single_agent_context(
            current_iteration=5,
            current_policy={"parameters": {"threshold": 3.0}},
            current_metrics={"total_cost_mean": 50000, "settlement_rate_mean": 1.0},
            agent_id="BANK_A",
        )

        # Should contain BANK_A references
        assert "BANK_A" in context

        # Should NOT contain BANK_B references
        assert "BANK_B" not in context
        assert "Bank B" not in context

    def test_context_excludes_other_agent_policy(
        self,
        sample_policy_a: dict[str, Any],
        sample_policy_b: dict[str, Any],
    ) -> None:
        """Verify context only shows the current agent's policy."""
        context = build_single_agent_context(
            current_iteration=1,
            current_policy=sample_policy_a,
            current_metrics={"total_cost_mean": 50000, "settlement_rate_mean": 1.0},
            agent_id="BANK_A",
        )

        # Bank A's policy ID should be present
        assert "bank_a_policy" in context or "urgency_threshold" in context

        # Bank B's policy ID should NOT be present
        assert "bank_b_policy" not in context

    def test_context_with_history_excludes_other_agent(self) -> None:
        """Verify context with iteration history excludes other agent data."""
        # Create single-agent history for BANK_A only
        history = [
            SingleAgentIterationRecord(
                iteration=0,
                metrics={"total_cost_mean": 60000, "settlement_rate_mean": 1.0},
                policy={"parameters": {"urgency": 3.0}},
                policy_changes=["Bank A initial policy"],
            ),
            SingleAgentIterationRecord(
                iteration=1,
                metrics={"total_cost_mean": 55000, "settlement_rate_mean": 1.0},
                policy={"parameters": {"urgency": 4.0}},
                policy_changes=["Bank A changed urgency"],
                is_best_so_far=True,
            ),
        ]

        context = build_single_agent_context(
            current_iteration=2,
            current_policy={"parameters": {"urgency": 5.0}},
            current_metrics={"total_cost_mean": 50000, "settlement_rate_mean": 1.0},
            iteration_history=history,
            agent_id="BANK_A",
        )

        # Should contain Bank A changes
        assert "Bank A" in context or "BANK_A" in context

        # Should NOT contain any Bank B references
        assert "Bank B" not in context
        assert "BANK_B" not in context
        assert "policy_b" not in context.lower()

    def test_context_shows_single_policy_section(self) -> None:
        """Verify context shows only one policy section, not two."""
        context = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {"threshold": 5.0}},
            current_metrics={"total_cost_mean": 50000, "settlement_rate_mean": 1.0},
            agent_id="BANK_A",
        )

        # Should have ONE "Current Policy Parameters" section
        policy_sections = context.count("Current Policy Parameters")
        assert policy_sections == 1

        # Should NOT have separate Bank A / Bank B sections
        assert "Bank A:" not in context or context.count("Bank A:") <= 1
        assert "Bank B:" not in context


# ============================================================================
# Test SingleAgentContextBuilder
# ============================================================================


class TestSingleAgentContextBuilder:
    """Tests for the SingleAgentContextBuilder class."""

    def test_builder_excludes_dual_agent_labels(self) -> None:
        """Verify builder output doesn't use Bank A/Bank B dual labels."""
        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            current_policy={"parameters": {"threshold": 5.0}},
            current_metrics={"total_cost_mean": 50000, "settlement_rate_mean": 1.0},
        )

        builder = SingleAgentContextBuilder(context)
        output = builder.build()

        # Should use "BANK_A" consistently
        assert "BANK_A" in output

        # Should NOT have dual-bank formatting like "Bank A:" and "Bank B:"
        # (A single mention of the agent name is fine, but paired mentions are not)
        bank_a_mentions = output.count("Bank A")
        bank_b_mentions = output.count("Bank B")

        # Bank B should have ZERO mentions
        assert bank_b_mentions == 0, f"Found {bank_b_mentions} mentions of 'Bank B'"

    def test_iteration_history_shows_single_agent_changes(self) -> None:
        """Verify iteration history section shows only single agent's changes."""
        history = [
            SingleAgentIterationRecord(
                iteration=0,
                metrics={"total_cost_mean": 60000, "settlement_rate_mean": 1.0},
                policy={"parameters": {"x": 1.0}},
                policy_changes=["Change for this agent only"],
            ),
        ]

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            current_policy={"parameters": {"x": 2.0}},
            current_metrics={"total_cost_mean": 50000, "settlement_rate_mean": 1.0},
            iteration_history=history,
        )

        builder = SingleAgentContextBuilder(context)
        output = builder.build()

        # Should contain the single agent's changes
        assert "Change for this agent only" in output

        # Should NOT have separate "Bank A Changes" and "Bank B Changes" sections
        assert "Bank B Changes" not in output

    def test_parameter_trajectory_shows_single_agent_params(self) -> None:
        """Verify parameter trajectory section shows only single agent params."""
        history = [
            SingleAgentIterationRecord(
                iteration=0,
                metrics={"total_cost_mean": 60000, "settlement_rate_mean": 1.0},
                policy={"parameters": {"my_param": 1.0}},
                policy_changes=[],
            ),
            SingleAgentIterationRecord(
                iteration=1,
                metrics={"total_cost_mean": 55000, "settlement_rate_mean": 1.0},
                policy={"parameters": {"my_param": 2.0}},
                policy_changes=[],
            ),
        ]

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=2,
            current_policy={"parameters": {"my_param": 3.0}},
            current_metrics={"total_cost_mean": 50000, "settlement_rate_mean": 1.0},
            iteration_history=history,
        )

        builder = SingleAgentContextBuilder(context)
        output = builder.build()

        # Should show parameter trajectory
        assert "my_param" in output
        assert "PARAMETER TRAJECTORIES" in output

        # Trajectory section should reference only the single agent
        trajectory_section_match = re.search(
            r"## 6\. PARAMETER TRAJECTORIES.*?(?=## 7\.|$)",
            output,
            re.DOTALL
        )
        if trajectory_section_match:
            trajectory_section = trajectory_section_match.group(0)
            assert "Bank B" not in trajectory_section
            assert "BANK_B" not in trajectory_section


# ============================================================================
# Test Full Isolation Guarantee
# ============================================================================


class TestFullIsolationGuarantee:
    """End-to-end tests verifying complete isolation."""

    def test_bank_a_context_has_zero_bank_b_references(
        self,
        iteration_history: list[IterationRecord],
    ) -> None:
        """CRITICAL: Verify BANK_A context has ZERO references to Bank B."""
        from experiments.castro.scripts.reproducible_experiment import (
            ReproducibleExperiment,
        )

        # Filter history for Bank A
        filtered_history = ReproducibleExperiment._filter_iteration_history_for_agent(
            iteration_history, "BANK_A"
        )

        # Build context for Bank A
        context = build_single_agent_context(
            current_iteration=len(iteration_history),
            current_policy=iteration_history[-1].policy_a,
            current_metrics=iteration_history[-1].metrics,
            iteration_history=filtered_history,
            best_seed_output="Best seed output for Bank A only",
            worst_seed_output="Worst seed output for Bank A only",
            best_seed=42,
            worst_seed=13,
            best_seed_cost=45000,
            worst_seed_cost=60000,
            cost_breakdown={"delay": 30000, "collateral": 15000},
            agent_id="BANK_A",
        )

        # Count ALL Bank B references (case-insensitive variations)
        bank_b_patterns = [
            "BANK_B",
            "Bank_B",
            "bank_b",
            "Bank B",
            "bank b",
            "BankB",
            "bankB",
            "policy_b",
            "policyB",
        ]

        for pattern in bank_b_patterns:
            count = context.count(pattern)
            assert count == 0, (
                f"Found {count} occurrences of '{pattern}' in BANK_A context!\n"
                f"Context excerpt: {context[:500]}..."
            )

    def test_bank_b_context_has_zero_bank_a_references(
        self,
        iteration_history: list[IterationRecord],
    ) -> None:
        """CRITICAL: Verify BANK_B context has ZERO references to Bank A."""
        from experiments.castro.scripts.reproducible_experiment import (
            ReproducibleExperiment,
        )

        # Filter history for Bank B
        filtered_history = ReproducibleExperiment._filter_iteration_history_for_agent(
            iteration_history, "BANK_B"
        )

        # Build context for Bank B
        context = build_single_agent_context(
            current_iteration=len(iteration_history),
            current_policy=iteration_history[-1].policy_b,
            current_metrics=iteration_history[-1].metrics,
            iteration_history=filtered_history,
            best_seed_output="Best seed output for Bank B only",
            worst_seed_output="Worst seed output for Bank B only",
            best_seed=42,
            worst_seed=13,
            best_seed_cost=45000,
            worst_seed_cost=60000,
            cost_breakdown={"delay": 30000, "collateral": 15000},
            agent_id="BANK_B",
        )

        # Count ALL Bank A references (case-insensitive variations)
        bank_a_patterns = [
            "BANK_A",
            "Bank_A",
            "bank_a",
            "Bank A",
            "bank a",
            "BankA",
            "bankA",
            "policy_a",
            "policyA",
        ]

        for pattern in bank_a_patterns:
            count = context.count(pattern)
            assert count == 0, (
                f"Found {count} occurrences of '{pattern}' in BANK_B context!\n"
                f"Context excerpt: {context[:500]}..."
            )

    def test_filtered_histories_are_disjoint(
        self,
        iteration_history: list[IterationRecord],
    ) -> None:
        """Verify filtered histories for Bank A and Bank B share no policy data."""
        from experiments.castro.scripts.reproducible_experiment import (
            ReproducibleExperiment,
        )

        history_a = ReproducibleExperiment._filter_iteration_history_for_agent(
            iteration_history, "BANK_A"
        )
        history_b = ReproducibleExperiment._filter_iteration_history_for_agent(
            iteration_history, "BANK_B"
        )

        # For each iteration, verify policies are different
        for i in range(len(iteration_history)):
            policy_a_json = json.dumps(history_a[i].policy, sort_keys=True)
            policy_b_json = json.dumps(history_b[i].policy, sort_keys=True)

            assert policy_a_json != policy_b_json, (
                f"Iteration {i}: Bank A and Bank B policies should be different!\n"
                f"Bank A: {policy_a_json}\n"
                f"Bank B: {policy_b_json}"
            )

            # Also verify changes are different
            assert history_a[i].policy_changes != history_b[i].policy_changes

    def test_no_cross_contamination_in_changes(
        self,
        iteration_history: list[IterationRecord],
    ) -> None:
        """Verify policy_changes don't contain references to other bank."""
        from experiments.castro.scripts.reproducible_experiment import (
            ReproducibleExperiment,
        )

        history_a = ReproducibleExperiment._filter_iteration_history_for_agent(
            iteration_history, "BANK_A"
        )
        history_b = ReproducibleExperiment._filter_iteration_history_for_agent(
            iteration_history, "BANK_B"
        )

        for record in history_a:
            changes_str = " ".join(record.policy_changes)
            assert "Bank B" not in changes_str
            assert "BANK_B" not in changes_str

        for record in history_b:
            changes_str = " ".join(record.policy_changes)
            assert "Bank A" not in changes_str
            assert "BANK_A" not in changes_str


# ============================================================================
# Test RobustPolicyDeps
# ============================================================================


class TestRobustPolicyDeps:
    """Tests for RobustPolicyDeps dataclass isolation."""

    def test_deps_has_agent_id_not_other_bank_policy(self) -> None:
        """Verify RobustPolicyDeps uses agent_id, not other_bank_policy."""
        from experiments.castro.generator.robust_policy_agent import RobustPolicyDeps

        # Check field names
        field_names = [f.name for f in RobustPolicyDeps.__dataclass_fields__.values()]

        # Should have agent_id
        assert "agent_id" in field_names

        # Should NOT have other_bank_policy
        assert "other_bank_policy" not in field_names

    def test_deps_can_be_created_with_agent_id(self) -> None:
        """Verify RobustPolicyDeps accepts agent_id parameter."""
        from experiments.castro.generator.robust_policy_agent import RobustPolicyDeps

        deps = RobustPolicyDeps(
            current_policy={"version": "2.0"},
            agent_id="BANK_A",
        )

        assert deps.agent_id == "BANK_A"
        assert deps.current_policy == {"version": "2.0"}


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
