"""Integration tests for policy evolution feature.

End-to-end tests validating the full flow from database to JSON output.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from payment_simulator.experiments.analysis import (
    PolicyEvolutionService,
    build_evolution_output,
)
from payment_simulator.experiments.persistence import (
    EventRecord,
    ExperimentRecord,
    ExperimentRepository,
    IterationRecord,
)


@pytest.fixture
def complex_policy_db(tmp_path: Path) -> Path:
    """Create database with complex nested policy structures."""
    db_path = tmp_path / "complex_policies.db"
    repo = ExperimentRepository(db_path)

    # Create experiment
    repo.save_experiment(
        ExperimentRecord(
            run_id="complex-run",
            experiment_name="complex_exp",
            experiment_type="generic",
            config={"description": "Test with complex policies"},
            created_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            num_iterations=3,
            converged=True,
            convergence_reason="stability_reached",
        )
    )

    # Create iterations with complex nested policies
    policies_progression = [
        # Iteration 0: Initial policy
        {
            "version": "2.0",
            "parameters": {
                "urgency_threshold": 5,
                "initial_liquidity_fraction": 0.3,
            },
            "payment_tree": {
                "condition": {"field": "balance", "op": ">", "threshold": 0},
                "on_true": {"action": "Release"},
                "on_false": {
                    "condition": {"field": "priority", "op": ">=", "threshold": 8},
                    "on_true": {"action": "Release"},
                    "on_false": {"action": "Hold"},
                },
            },
        },
        # Iteration 1: Changed urgency threshold and tree
        {
            "version": "2.0",
            "parameters": {
                "urgency_threshold": 7,
                "initial_liquidity_fraction": 0.3,
            },
            "payment_tree": {
                "condition": {"field": "balance", "op": ">", "threshold": 1000},  # Changed
                "on_true": {"action": "Release"},
                "on_false": {
                    "condition": {"field": "priority", "op": ">=", "threshold": 8},
                    "on_true": {"action": "Release"},
                    "on_false": {"action": "Hold"},
                },
            },
        },
        # Iteration 2: Changed liquidity and deeper tree change
        {
            "version": "2.0",
            "parameters": {
                "urgency_threshold": 7,
                "initial_liquidity_fraction": 0.5,  # Changed
            },
            "payment_tree": {
                "condition": {"field": "balance", "op": ">", "threshold": 1000},
                "on_true": {"action": "Release"},
                "on_false": {
                    "condition": {"field": "priority", "op": ">=", "threshold": 6},  # Changed
                    "on_true": {"action": "Split"},  # Changed action
                    "on_false": {"action": "Hold"},
                },
            },
        },
    ]

    for i, policy in enumerate(policies_progression):
        repo.save_iteration(
            IterationRecord(
                run_id="complex-run",
                iteration=i,
                costs_per_agent={"BANK_A": 100000 - i * 10000},
                accepted_changes={"BANK_A": True},
                policies={"BANK_A": policy},
                timestamp=datetime.now().isoformat(),
            )
        )

        # Add LLM events
        repo.save_event(
            EventRecord(
                run_id="complex-run",
                iteration=i,
                event_type="llm_interaction",
                event_data={
                    "agent_id": "BANK_A",
                    "system_prompt": f"Iteration {i}: Optimize the payment policy for BANK_A...",
                    "user_prompt": f"Current policy: {json.dumps(policy)}...",
                    "raw_response": json.dumps(policy),
                },
                timestamp=datetime.now().isoformat(),
            )
        )

    repo.close()
    return db_path


class TestPolicyEvolutionIntegration:
    """Integration tests for full policy evolution flow."""

    def test_full_evolution_extraction_round_trip(
        self, complex_policy_db: Path
    ) -> None:
        """Test saving and extracting evolution data round-trip."""
        repo = ExperimentRepository(complex_policy_db)
        service = PolicyEvolutionService(repo)

        # Extract evolution
        evolutions = service.get_evolution("complex-run")
        output = build_evolution_output(evolutions)

        repo.close()

        # Verify structure
        assert "BANK_A" in output
        assert "iteration_1" in output["BANK_A"]
        assert "iteration_2" in output["BANK_A"]
        assert "iteration_3" in output["BANK_A"]

        # Verify policies are preserved
        iter1_policy = output["BANK_A"]["iteration_1"]["policy"]
        assert iter1_policy["parameters"]["urgency_threshold"] == 5
        assert iter1_policy["payment_tree"]["condition"]["field"] == "balance"

    def test_evolution_with_complex_policies(self, complex_policy_db: Path) -> None:
        """Test handling of deeply nested policy structures."""
        repo = ExperimentRepository(complex_policy_db)
        service = PolicyEvolutionService(repo)

        evolutions = service.get_evolution("complex-run", agent_filter="BANK_A")
        output = build_evolution_output(evolutions)

        repo.close()

        # Verify iteration 3 has the final policy state
        iter3_policy = output["BANK_A"]["iteration_3"]["policy"]
        assert iter3_policy["parameters"]["initial_liquidity_fraction"] == 0.5
        assert iter3_policy["payment_tree"]["on_false"]["on_true"]["action"] == "Split"

    def test_evolution_preserves_iteration_order(
        self, complex_policy_db: Path
    ) -> None:
        """Test that iterations are returned in correct order."""
        repo = ExperimentRepository(complex_policy_db)
        service = PolicyEvolutionService(repo)

        evolutions = service.get_evolution("complex-run")
        output = build_evolution_output(evolutions)

        repo.close()

        # Get iteration keys
        agent_data = output["BANK_A"]
        iteration_keys = list(agent_data.keys())

        # Should be in order: iteration_1, iteration_2, iteration_3
        assert iteration_keys == ["iteration_1", "iteration_2", "iteration_3"]

    def test_evolution_diff_content(self, complex_policy_db: Path) -> None:
        """Test that diff content shows meaningful changes."""
        repo = ExperimentRepository(complex_policy_db)
        service = PolicyEvolutionService(repo)

        evolutions = service.get_evolution("complex-run", agent_filter="BANK_A")
        output = build_evolution_output(evolutions)

        repo.close()

        # First iteration has no diff
        iter1_diff = output["BANK_A"]["iteration_1"].get("diff", "")
        assert iter1_diff == ""

        # Second iteration should show urgency_threshold change (5 -> 7)
        iter2_diff = output["BANK_A"]["iteration_2"].get("diff", "")
        assert "urgency_threshold" in iter2_diff
        assert "5" in iter2_diff
        assert "7" in iter2_diff

        # Third iteration should show liquidity change (0.3 -> 0.5)
        iter3_diff = output["BANK_A"]["iteration_3"].get("diff", "")
        assert "liquidity" in iter3_diff.lower() or "0.5" in iter3_diff

    def test_llm_data_extraction_complete(self, complex_policy_db: Path) -> None:
        """Test complete LLM data extraction and round-trip."""
        repo = ExperimentRepository(complex_policy_db)
        service = PolicyEvolutionService(repo)

        evolutions = service.get_evolution(
            "complex-run", include_llm=True, agent_filter="BANK_A"
        )
        output = build_evolution_output(evolutions)

        repo.close()

        # Verify LLM data is present and complete
        for iter_key in ["iteration_1", "iteration_2", "iteration_3"]:
            iter_data = output["BANK_A"][iter_key]
            assert "llm" in iter_data
            llm = iter_data["llm"]
            assert "system_prompt" in llm
            assert "user_prompt" in llm
            assert "raw_response" in llm
            assert "Optimize" in llm["system_prompt"] or "Iteration" in llm["system_prompt"]
            assert "Current policy" in llm["user_prompt"]

    def test_json_serialization_complete(self, complex_policy_db: Path) -> None:
        """Test that complete output is JSON serializable."""
        repo = ExperimentRepository(complex_policy_db)
        service = PolicyEvolutionService(repo)

        evolutions = service.get_evolution("complex-run", include_llm=True)
        output = build_evolution_output(evolutions)

        repo.close()

        # Should serialize without error
        json_str = json.dumps(output, indent=2)
        assert isinstance(json_str, str)
        assert len(json_str) > 100  # Non-trivial output

        # Round-trip should preserve data
        parsed = json.loads(json_str)
        assert parsed == output

    def test_cost_and_accepted_propagation(self, complex_policy_db: Path) -> None:
        """Test that cost and accepted fields are correctly propagated."""
        repo = ExperimentRepository(complex_policy_db)
        service = PolicyEvolutionService(repo)

        evolutions = service.get_evolution("complex-run", agent_filter="BANK_A")
        output = build_evolution_output(evolutions)

        repo.close()

        # Verify costs are decreasing (as set up in fixture)
        assert output["BANK_A"]["iteration_1"]["cost"] == 100000
        assert output["BANK_A"]["iteration_2"]["cost"] == 90000
        assert output["BANK_A"]["iteration_3"]["cost"] == 80000

        # All should be accepted
        for iter_key in ["iteration_1", "iteration_2", "iteration_3"]:
            assert output["BANK_A"][iter_key]["accepted"] is True


class TestPolicyEvolutionIntegrationEdgeCases:
    """Edge case integration tests."""

    def test_handles_unicode_in_prompts(self, tmp_path: Path) -> None:
        """Test handling of unicode characters in LLM data."""
        db_path = tmp_path / "unicode.db"
        repo = ExperimentRepository(db_path)

        repo.save_experiment(
            ExperimentRecord(
                run_id="unicode-run",
                experiment_name="unicode_exp",
                experiment_type="generic",
                config={},
                created_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
                num_iterations=1,
                converged=True,
                convergence_reason="done",
            )
        )

        repo.save_iteration(
            IterationRecord(
                run_id="unicode-run",
                iteration=0,
                costs_per_agent={"BANK_A": 5000},
                accepted_changes={"BANK_A": True},
                policies={"BANK_A": {"version": "1.0"}},
                timestamp=datetime.now().isoformat(),
            )
        )

        # Add LLM event with unicode
        repo.save_event(
            EventRecord(
                run_id="unicode-run",
                iteration=0,
                event_type="llm_interaction",
                event_data={
                    "agent_id": "BANK_A",
                    "system_prompt": "Optimize für Bank A: émojis: 🎉💰",
                    "user_prompt": "Current policy: données spéciales",
                    "raw_response": '{"status": "réussi ✓"}',
                },
                timestamp=datetime.now().isoformat(),
            )
        )

        repo.close()

        # Extract and verify
        repo = ExperimentRepository(db_path)
        service = PolicyEvolutionService(repo)
        evolutions = service.get_evolution("unicode-run", include_llm=True)
        output = build_evolution_output(evolutions)
        repo.close()

        # Should handle unicode correctly
        llm = output["BANK_A"]["iteration_1"]["llm"]
        assert "🎉" in llm["system_prompt"]
        assert "données" in llm["user_prompt"]
        assert "réussi" in llm["raw_response"]

        # JSON serialization should work
        json_str = json.dumps(output, ensure_ascii=False)
        assert "🎉" in json_str

    def test_handles_very_large_policies(self, tmp_path: Path) -> None:
        """Test handling of very large policy structures."""
        db_path = tmp_path / "large.db"
        repo = ExperimentRepository(db_path)

        # Create a large nested policy
        large_policy = {
            "version": "2.0",
            "parameters": {f"param_{i}": i * 100 for i in range(50)},
            "payment_tree": {"action": "Release"},
        }

        repo.save_experiment(
            ExperimentRecord(
                run_id="large-run",
                experiment_name="large_exp",
                experiment_type="generic",
                config={},
                created_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
                num_iterations=1,
                converged=True,
                convergence_reason="done",
            )
        )

        repo.save_iteration(
            IterationRecord(
                run_id="large-run",
                iteration=0,
                costs_per_agent={"BANK_A": 5000},
                accepted_changes={"BANK_A": True},
                policies={"BANK_A": large_policy},
                timestamp=datetime.now().isoformat(),
            )
        )

        repo.close()

        # Extract and verify
        repo = ExperimentRepository(db_path)
        service = PolicyEvolutionService(repo)
        evolutions = service.get_evolution("large-run")
        output = build_evolution_output(evolutions)
        repo.close()

        # Should handle large policy
        policy = output["BANK_A"]["iteration_1"]["policy"]
        assert len(policy["parameters"]) == 50
        assert policy["parameters"]["param_49"] == 4900
