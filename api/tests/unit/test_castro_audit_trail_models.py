"""
TDD Cycle 1: Castro Audit Trail Pydantic Model Tests

These tests define the requirements for audit trail persistence models
used in the Castro experiment for LLM-driven policy optimization.

Following the RED phase: these tests will fail until we implement the models.
"""

from __future__ import annotations

from datetime import datetime

import pytest


class TestLLMInteractionRecordMetadata:
    """Test LLMInteractionRecord model has proper metadata for DDL generation."""

    def test_llm_interaction_record_has_table_metadata(self) -> None:
        """Verify Pydantic model includes table configuration."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            LLMInteractionRecord,
        )

        assert hasattr(LLMInteractionRecord, "model_config"), (
            "LLMInteractionRecord should have model_config attribute"
        )

        config = LLMInteractionRecord.model_config
        assert "table_name" in config, "Config should specify table_name"
        assert config["table_name"] == "llm_interaction_log", (
            "Table name should be 'llm_interaction_log'"
        )

        assert "primary_key" in config, "Config should specify primary_key"
        assert config["primary_key"] == ["interaction_id"], (
            "Primary key should be interaction_id"
        )

    def test_llm_interaction_record_has_required_fields(self) -> None:
        """Verify LLMInteractionRecord has all required fields from schema."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            LLMInteractionRecord,
        )

        fields = LLMInteractionRecord.model_fields

        # Identity fields
        assert "interaction_id" in fields
        assert "game_id" in fields
        assert "agent_id" in fields
        assert "iteration_number" in fields

        # Prompt fields
        assert "system_prompt" in fields
        assert "user_prompt" in fields

        # Response fields
        assert "raw_response" in fields
        assert "parsed_policy_json" in fields
        assert "parsing_error" in fields
        assert "llm_reasoning" in fields

        # Timing fields
        assert "request_timestamp" in fields
        assert "response_timestamp" in fields

    def test_llm_interaction_record_field_types(self) -> None:
        """Verify LLMInteractionRecord fields have correct types."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            LLMInteractionRecord,
        )

        fields = LLMInteractionRecord.model_fields

        # Required string fields
        assert fields["interaction_id"].annotation is str
        assert fields["game_id"].annotation is str
        assert fields["agent_id"].annotation is str
        assert fields["system_prompt"].annotation is str
        assert fields["user_prompt"].annotation is str
        assert fields["raw_response"].annotation is str

        # Optional string fields
        assert fields["parsed_policy_json"].annotation == str | None
        assert fields["parsing_error"].annotation == str | None
        assert fields["llm_reasoning"].annotation == str | None

        # Integer field
        assert fields["iteration_number"].annotation is int

        # Datetime fields
        assert fields["request_timestamp"].annotation is datetime
        assert fields["response_timestamp"].annotation is datetime

    def test_llm_interaction_record_instantiation(self) -> None:
        """Verify LLMInteractionRecord can be instantiated with required fields."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            LLMInteractionRecord,
        )

        now = datetime.now()
        record = LLMInteractionRecord(
            interaction_id="game1_agentA_1",
            game_id="game1",
            agent_id="agentA",
            iteration_number=1,
            system_prompt="You are a policy optimizer.",
            user_prompt="Optimize this policy: {...}",
            raw_response='{"policy": {...}}',
            parsed_policy_json='{"policy": {...}}',
            parsing_error=None,
            llm_reasoning="I optimized X because Y.",
            request_timestamp=now,
            response_timestamp=now,
        )

        assert record.interaction_id == "game1_agentA_1"
        assert record.game_id == "game1"
        assert record.agent_id == "agentA"
        assert record.iteration_number == 1
        assert record.parsing_error is None


class TestPolicyDiffRecordMetadata:
    """Test PolicyDiffRecord model has proper metadata for DDL generation."""

    def test_policy_diff_record_has_table_metadata(self) -> None:
        """Verify Pydantic model includes table configuration."""
        from payment_simulator.ai_cash_mgmt.persistence.models import PolicyDiffRecord

        assert hasattr(PolicyDiffRecord, "model_config"), (
            "PolicyDiffRecord should have model_config attribute"
        )

        config = PolicyDiffRecord.model_config
        assert "table_name" in config, "Config should specify table_name"
        assert config["table_name"] == "policy_diffs", (
            "Table name should be 'policy_diffs'"
        )

        assert "primary_key" in config, "Config should specify primary_key"
        assert config["primary_key"] == ["game_id", "agent_id", "iteration_number"], (
            "Primary key should be composite: game_id + agent_id + iteration_number"
        )

    def test_policy_diff_record_has_required_fields(self) -> None:
        """Verify PolicyDiffRecord has all required fields from schema."""
        from payment_simulator.ai_cash_mgmt.persistence.models import PolicyDiffRecord

        fields = PolicyDiffRecord.model_fields

        # Identity fields
        assert "game_id" in fields
        assert "agent_id" in fields
        assert "iteration_number" in fields

        # Diff fields
        assert "diff_summary" in fields
        assert "parameter_changes_json" in fields

        # Tree modification flags
        assert "payment_tree_changed" in fields
        assert "collateral_tree_changed" in fields

        # Snapshot field
        assert "parameters_snapshot_json" in fields

    def test_policy_diff_record_field_types(self) -> None:
        """Verify PolicyDiffRecord fields have correct types."""
        from payment_simulator.ai_cash_mgmt.persistence.models import PolicyDiffRecord

        fields = PolicyDiffRecord.model_fields

        # Required string fields
        assert fields["game_id"].annotation is str
        assert fields["agent_id"].annotation is str
        assert fields["diff_summary"].annotation is str
        assert fields["parameters_snapshot_json"].annotation is str

        # Optional string field
        assert fields["parameter_changes_json"].annotation == str | None

        # Integer field
        assert fields["iteration_number"].annotation is int

        # Boolean fields
        assert fields["payment_tree_changed"].annotation is bool
        assert fields["collateral_tree_changed"].annotation is bool

    def test_policy_diff_record_instantiation(self) -> None:
        """Verify PolicyDiffRecord can be instantiated with required fields."""
        from payment_simulator.ai_cash_mgmt.persistence.models import PolicyDiffRecord

        record = PolicyDiffRecord(
            game_id="game1",
            agent_id="agentA",
            iteration_number=1,
            diff_summary="Changed 'threshold': 5.0 → 3.0 (↓2.00)",
            parameter_changes_json='[{"param": "threshold", "old": 5.0, "new": 3.0}]',
            payment_tree_changed=False,
            collateral_tree_changed=True,
            parameters_snapshot_json='{"threshold": 3.0}',
        )

        assert record.game_id == "game1"
        assert record.payment_tree_changed is False
        assert record.collateral_tree_changed is True


class TestIterationContextRecordMetadata:
    """Test IterationContextRecord model has proper metadata for DDL generation."""

    def test_iteration_context_record_has_table_metadata(self) -> None:
        """Verify Pydantic model includes table configuration."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            IterationContextRecord,
        )

        assert hasattr(IterationContextRecord, "model_config"), (
            "IterationContextRecord should have model_config attribute"
        )

        config = IterationContextRecord.model_config
        assert "table_name" in config, "Config should specify table_name"
        assert config["table_name"] == "iteration_context", (
            "Table name should be 'iteration_context'"
        )

        assert "primary_key" in config, "Config should specify primary_key"
        assert config["primary_key"] == ["game_id", "agent_id", "iteration_number"], (
            "Primary key should be composite: game_id + agent_id + iteration_number"
        )

    def test_iteration_context_record_has_required_fields(self) -> None:
        """Verify IterationContextRecord has all required fields from schema."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            IterationContextRecord,
        )

        fields = IterationContextRecord.model_fields

        # Identity fields
        assert "game_id" in fields
        assert "agent_id" in fields
        assert "iteration_number" in fields

        # Monte Carlo fields
        assert "monte_carlo_seeds" in fields
        assert "num_samples" in fields

        # Best/worst seed fields
        assert "best_seed" in fields
        assert "worst_seed" in fields
        assert "best_seed_cost" in fields
        assert "worst_seed_cost" in fields

        # Verbose output fields
        assert "best_seed_verbose_output" in fields
        assert "worst_seed_verbose_output" in fields

        # Aggregated metrics
        assert "cost_mean" in fields
        assert "cost_std" in fields
        assert "settlement_rate_mean" in fields

    def test_iteration_context_record_field_types(self) -> None:
        """Verify IterationContextRecord fields have correct types."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            IterationContextRecord,
        )

        fields = IterationContextRecord.model_fields

        # Required string fields
        assert fields["game_id"].annotation is str
        assert fields["agent_id"].annotation is str
        assert fields["monte_carlo_seeds"].annotation is str  # JSON array stored as str

        # Optional string fields
        assert fields["best_seed_verbose_output"].annotation == str | None
        assert fields["worst_seed_verbose_output"].annotation == str | None

        # Integer fields
        assert fields["iteration_number"].annotation is int
        assert fields["num_samples"].annotation is int
        assert fields["best_seed"].annotation is int
        assert fields["worst_seed"].annotation is int

        # Float fields
        assert fields["best_seed_cost"].annotation is float
        assert fields["worst_seed_cost"].annotation is float
        assert fields["cost_mean"].annotation is float
        assert fields["cost_std"].annotation is float
        assert fields["settlement_rate_mean"].annotation is float

    def test_iteration_context_record_instantiation(self) -> None:
        """Verify IterationContextRecord can be instantiated with required fields."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            IterationContextRecord,
        )

        record = IterationContextRecord(
            game_id="game1",
            agent_id="agentA",
            iteration_number=1,
            monte_carlo_seeds="[123, 456, 789]",
            num_samples=3,
            best_seed=123,
            worst_seed=789,
            best_seed_cost=100.5,
            worst_seed_cost=500.0,
            best_seed_verbose_output="Verbose output for best seed...",
            worst_seed_verbose_output="Verbose output for worst seed...",
            cost_mean=250.0,
            cost_std=150.0,
            settlement_rate_mean=0.95,
        )

        assert record.game_id == "game1"
        assert record.num_samples == 3
        assert record.best_seed == 123
        assert record.cost_mean == 250.0
