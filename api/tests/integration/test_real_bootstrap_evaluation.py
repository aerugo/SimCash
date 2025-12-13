"""Integration tests for REAL bootstrap evaluation.

Tests verify that the bootstrap evaluation:
1. Runs ONE initial simulation to collect historical transactions
2. Resamples FROM that historical data (not generates new transactions)
3. Provides 3 event streams to LLM (initial sim, best sample, worst sample)
4. Uses paired comparison on the SAME bootstrap samples

This is DIFFERENT from parametric Monte Carlo which generates new transactions
each time. True bootstrap resamples from observed data.

Reference: docs/requests/implement-real-bootstrap-evaluation.md
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from payment_simulator._core import Orchestrator


class TestInitialSimulationCollectsHistory:
    """Test that initial simulation runs ONCE and collects historical data."""

    def test_initial_simulation_collects_transactions(self) -> None:
        """Initial simulation should collect all historical transactions."""
        from payment_simulator.ai_cash_mgmt.bootstrap.history_collector import (
            TransactionHistoryCollector,
        )

        # Run a simple simulation
        config = {
            "rng_seed": 42,
            "ticks_per_day": 50,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10000000,
                    "unsecured_cap": 5000000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 0.5,
                        "amount_distribution": {
                            "type": "Uniform",
                            "min": 100000,
                            "max": 500000,
                        },
                        "counterparty_weights": {"BANK_B": 1.0},
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10000000,
                    "unsecured_cap": 5000000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 0.5,
                        "amount_distribution": {
                            "type": "Uniform",
                            "min": 100000,
                            "max": 500000,
                        },
                        "counterparty_weights": {"BANK_A": 1.0},
                    },
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run simulation and collect events
        all_events: list[dict] = []
        for tick in range(50):
            orch.tick()
            events = orch.get_tick_events(tick)
            all_events.extend(events)

        # Collect history using TransactionHistoryCollector
        collector = TransactionHistoryCollector()
        collector.process_events(all_events)

        # Get history for BANK_A
        history_a = collector.get_agent_history("BANK_A")

        # Should have collected transactions
        assert len(history_a.outgoing) > 0, "Should have outgoing transactions"
        assert len(history_a.incoming) > 0, "Should have incoming transactions"

        # Verify transaction records have correct structure
        for tx in history_a.outgoing:
            assert tx.sender_id == "BANK_A"
            assert isinstance(tx.amount, int), "Amount must be integer (INV-1)"
            assert tx.deadline_offset >= 0, "Deadline offset must be non-negative"

        for tx in history_a.incoming:
            assert tx.receiver_id == "BANK_A"

    def test_history_collector_computes_offsets(self) -> None:
        """Verify that deadline_offset and settlement_offset are computed correctly."""
        from payment_simulator.ai_cash_mgmt.bootstrap.history_collector import (
            TransactionHistoryCollector,
        )

        # Create sample events with known timing
        events = [
            {
                "event_type": "arrival",
                "tx_id": "TX001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "tick": 10,
                "deadline_tick": 25,  # offset = 15
                "amount": 100000,
                "priority": 5,
            },
            {
                "event_type": "rtgs_immediate_settlement",
                "tx_id": "TX001",
                "tick": 12,  # settlement_offset = 2
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        history = collector.get_agent_history("BANK_A")
        assert len(history.outgoing) == 1

        tx = history.outgoing[0]
        assert tx.deadline_offset == 15  # 25 - 10
        assert tx.settlement_offset == 2  # 12 - 10


class TestBootstrapSamplingFromHistory:
    """Test that bootstrap samples come FROM historical data, not new generation."""

    def test_bootstrap_sampler_uses_historical_records(self) -> None:
        """Bootstrap sampler should resample from provided historical records."""
        from payment_simulator.ai_cash_mgmt.bootstrap.models import TransactionRecord
        from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler

        # Create historical records
        historical_records = tuple([
            TransactionRecord(
                tx_id=f"TX{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000 * (i + 1),  # Different amounts to verify resampling
                priority=5,
                original_arrival_tick=i * 10,
                deadline_offset=15,
                settlement_offset=5 if i % 2 == 0 else None,
            )
            for i in range(10)
        ])

        # Create sampler
        sampler = BootstrapSampler(seed=42)

        # Generate bootstrap sample
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=historical_records,
            incoming_records=(),
            total_ticks=100,
        )

        # Verify: bootstrap sample contains ONLY transactions from history
        historical_amounts = {r.amount for r in historical_records}

        for tx in sample.outgoing_txns:
            assert tx.amount in historical_amounts, (
                f"Bootstrap transaction amount {tx.amount} not in historical data. "
                "Bootstrap must resample from history, not generate new transactions."
            )

    def test_bootstrap_sample_count_matches_history(self) -> None:
        """Standard bootstrap: resample n items from n items."""
        from payment_simulator.ai_cash_mgmt.bootstrap.models import TransactionRecord
        from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler

        # 5 historical transactions
        historical_records = tuple([
            TransactionRecord(
                tx_id=f"TX{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=i * 10,
                deadline_offset=15,
                settlement_offset=5,
            )
            for i in range(5)
        ])

        sampler = BootstrapSampler(seed=42)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=historical_records,
            incoming_records=(),
            total_ticks=100,
        )

        # Should have same count as original (standard bootstrap)
        assert len(sample.outgoing_txns) == 5

    def test_bootstrap_preserves_deadline_offsets(self) -> None:
        """Remapped transactions must preserve deadline_offset from original."""
        from payment_simulator.ai_cash_mgmt.bootstrap.models import TransactionRecord
        from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler

        # Historical record with specific deadline_offset
        historical_records = tuple([
            TransactionRecord(
                tx_id="TX001",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=10,
                deadline_offset=15,  # Key: this should be preserved
                settlement_offset=None,
            )
        ])

        sampler = BootstrapSampler(seed=42)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=historical_records,
            incoming_records=(),
            total_ticks=100,
        )

        # Verify deadline_offset preserved
        for tx in sample.outgoing_txns:
            # deadline_tick - arrival_tick should equal original deadline_offset
            expected_offset = 15
            actual_offset = tx.deadline_tick - tx.arrival_tick
            assert actual_offset == expected_offset, (
                f"Deadline offset not preserved: expected {expected_offset}, "
                f"got {actual_offset}. arrival={tx.arrival_tick}, deadline={tx.deadline_tick}"
            )

    def test_bootstrap_determinism_same_seed(self) -> None:
        """Same seed should produce identical bootstrap samples."""
        from payment_simulator.ai_cash_mgmt.bootstrap.models import TransactionRecord
        from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler

        historical_records = tuple([
            TransactionRecord(
                tx_id=f"TX{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000 * (i + 1),
                priority=5,
                original_arrival_tick=i * 10,
                deadline_offset=15,
                settlement_offset=None,
            )
            for i in range(10)
        ])

        # Generate with same seed twice
        sampler1 = BootstrapSampler(seed=12345)
        sample1 = sampler1.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=historical_records,
            incoming_records=(),
            total_ticks=100,
        )

        sampler2 = BootstrapSampler(seed=12345)
        sample2 = sampler2.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=historical_records,
            incoming_records=(),
            total_ticks=100,
        )

        # Should be identical
        assert len(sample1.outgoing_txns) == len(sample2.outgoing_txns)
        for tx1, tx2 in zip(sample1.outgoing_txns, sample2.outgoing_txns):
            assert tx1.amount == tx2.amount
            assert tx1.arrival_tick == tx2.arrival_tick
            assert tx1.deadline_tick == tx2.deadline_tick


class TestSandboxConfigBuilder:
    """Test that sandbox configs correctly convert bootstrap samples to scenario events."""

    def test_outgoing_transactions_become_scenario_events(self) -> None:
        """Outgoing transactions should become CustomTransactionArrival events."""
        from payment_simulator.ai_cash_mgmt.bootstrap.models import (
            BootstrapSample,
            RemappedTransaction,
            TransactionRecord,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.sandbox_config import (
            SandboxConfigBuilder,
        )

        # Create a bootstrap sample
        record = TransactionRecord(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100000,
            priority=5,
            original_arrival_tick=10,
            deadline_offset=15,
            settlement_offset=None,
        )
        remapped = record.remap_to_tick(new_arrival=20, eod_tick=100)

        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=42,
            outgoing_txns=(remapped,),
            incoming_settlements=(),
            total_ticks=100,
        )

        # Build config
        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=10000000,
            credit_limit=5000000,
        )

        # Verify scenario_events present
        assert config.scenario_events is not None
        assert len(config.scenario_events) > 0

    def test_three_agent_sandbox_structure(self) -> None:
        """Config should have exactly 3 agents: SOURCE, target, SINK."""
        from payment_simulator.ai_cash_mgmt.bootstrap.models import (
            BootstrapSample,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.sandbox_config import (
            SandboxConfigBuilder,
        )

        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=42,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=10000000,
            credit_limit=5000000,
        )

        # Should have exactly 3 agents
        assert len(config.agents) == 3

        agent_ids = {a.id for a in config.agents}
        assert "SOURCE" in agent_ids
        assert "SINK" in agent_ids
        assert "BANK_A" in agent_ids


class TestPairedComparison:
    """Test that paired comparison evaluates both policies on SAME samples."""

    def test_evaluator_paired_deltas_uses_same_samples(self) -> None:
        """compute_paired_deltas must use identical samples for old and new policy."""
        from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import (
            BootstrapPolicyEvaluator,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.models import (
            BootstrapSample,
            RemappedTransaction,
            TransactionRecord,
        )

        # Create sample with known transactions
        record = TransactionRecord(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100000,
            priority=5,
            original_arrival_tick=10,
            deadline_offset=15,
            settlement_offset=5,
        )
        remapped = record.remap_to_tick(new_arrival=20, eod_tick=100)

        samples = [
            BootstrapSample(
                agent_id="BANK_A",
                sample_idx=i,
                seed=42 + i,
                outgoing_txns=(remapped,),
                incoming_settlements=(),
                total_ticks=100,
            )
            for i in range(3)
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=10000000,
            credit_limit=5000000,
        )

        old_policy = {"type": "Fifo"}
        new_policy = {"type": "Fifo"}  # Same policy = deltas should be ~0

        # Run paired comparison
        deltas = evaluator.compute_paired_deltas(
            samples=samples,
            policy_a=old_policy,
            policy_b=new_policy,
        )

        # Should have one delta per sample
        assert len(deltas) == 3

        # With same policy, deltas should be zero (same sample, same policy = same cost)
        for delta in deltas:
            assert delta.delta == 0, (
                f"Same policy should produce zero delta, got {delta.delta}. "
                "This suggests old and new policies weren't evaluated on same sample."
            )


class TestIntegerCentsInvariant:
    """Test that all costs remain integers (INV-1: Money is i64)."""

    def test_evaluation_result_costs_are_integers(self) -> None:
        """All cost fields in evaluation results must be integers."""
        from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import (
            EvaluationResult,
        )

        result = EvaluationResult(
            sample_idx=0,
            seed=42,
            total_cost=150000,  # Integer cents
            settlement_rate=0.95,
            avg_delay=2.5,
        )

        assert isinstance(result.total_cost, int)
        assert isinstance(result.seed, int)

    def test_bootstrap_sample_amounts_are_integers(self) -> None:
        """Transaction amounts in bootstrap samples must be integers."""
        from payment_simulator.ai_cash_mgmt.bootstrap.models import (
            BootstrapSample,
            RemappedTransaction,
            TransactionRecord,
        )

        record = TransactionRecord(
            tx_id="TX001",
            sender_id="A",
            receiver_id="B",
            amount=100000,  # Integer cents
            priority=5,
            original_arrival_tick=10,
            deadline_offset=15,
            settlement_offset=None,
        )

        # Verify amount is integer
        assert isinstance(record.amount, int)

        remapped = record.remap_to_tick(new_arrival=20, eod_tick=100)
        assert isinstance(remapped.amount, int)

        sample = BootstrapSample(
            agent_id="A",
            sample_idx=0,
            seed=42,
            outgoing_txns=(remapped,),
            incoming_settlements=(),
            total_ticks=100,
        )

        for tx in sample.outgoing_txns:
            assert isinstance(tx.amount, int)


class TestLLMContextStreams:
    """Test that LLM receives 3 event streams: initial sim, best sample, worst sample."""

    def test_context_builder_identifies_best_worst(self) -> None:
        """Context builder should correctly identify best and worst samples."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        # Create results with known costs
        results = [
            EnrichedEvaluationResult(
                sample_idx=0,
                seed=100,
                total_cost=5000,  # Best (lowest)
                settlement_rate=1.0,
                avg_delay=0.0,
                event_trace=(),
                cost_breakdown=CostBreakdown(
                    delay_cost=1000,
                    overdraft_cost=2000,
                    deadline_penalty=1000,
                    eod_penalty=1000,
                ),
            ),
            EnrichedEvaluationResult(
                sample_idx=1,
                seed=200,
                total_cost=15000,  # Worst (highest)
                settlement_rate=0.8,
                avg_delay=5.0,
                event_trace=(),
                cost_breakdown=CostBreakdown(
                    delay_cost=5000,
                    overdraft_cost=5000,
                    deadline_penalty=3000,
                    eod_penalty=2000,
                ),
            ),
            EnrichedEvaluationResult(
                sample_idx=2,
                seed=300,
                total_cost=10000,  # Middle
                settlement_rate=0.9,
                avg_delay=2.0,
                event_trace=(),
                cost_breakdown=CostBreakdown(
                    delay_cost=3000,
                    overdraft_cost=3000,
                    deadline_penalty=2000,
                    eod_penalty=2000,
                ),
            ),
        ]

        builder = EnrichedBootstrapContextBuilder(results=results, agent_id="BANK_A")

        best = builder.get_best_result()
        worst = builder.get_worst_result()

        assert best.total_cost == 5000
        assert best.seed == 100
        assert worst.total_cost == 15000
        assert worst.seed == 200

    def test_agent_simulation_context_has_best_worst_output(self) -> None:
        """AgentSimulationContext should have best and worst seed outputs."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            AgentSimulationContext,
        )

        # Verify the data structure has required fields
        context = AgentSimulationContext(
            agent_id="BANK_A",
            best_seed=100,
            best_seed_cost=5000,
            best_seed_output="[tick 0] Arrival: ...",  # Stream 2
            worst_seed=200,
            worst_seed_cost=15000,
            worst_seed_output="[tick 0] Arrival: ...",  # Stream 3
            mean_cost=10000,
            cost_std=5000,
        )

        assert context.best_seed_output is not None
        assert context.worst_seed_output is not None


# Mark tests that require implementation as xfail for now
# These will pass once Phase 7 implementation is complete
class TestOptimizationLoopBootstrapIntegration:
    """Test OptimizationLoop integration with bootstrap infrastructure.

    These tests verify the main integration work from Phase 7.
    They will fail until the implementation is complete.
    """

    @pytest.mark.skip(reason="Phase 7 implementation not yet complete")
    def test_optimization_loop_runs_initial_simulation_once(self) -> None:
        """OptimizationLoop should run initial simulation exactly ONCE."""
        # This test will verify that:
        # 1. Initial simulation is called at start of run()
        # 2. It's not called again in subsequent iterations
        # 3. Historical data is collected and stored
        pass

    @pytest.mark.skip(reason="Phase 7 implementation not yet complete")
    def test_evaluate_policies_uses_bootstrap_samples(self) -> None:
        """_evaluate_policies should use BootstrapPolicyEvaluator, not new sims."""
        # This test will verify that:
        # 1. No new full simulations are created for evaluation
        # 2. Bootstrap samples from initial sim are used
        # 3. SandboxConfigBuilder creates 3-agent configs
        pass

    @pytest.mark.skip(reason="Phase 7 implementation not yet complete")
    def test_llm_context_includes_initial_simulation_output(self) -> None:
        """LLM context should include initial simulation as Stream 1."""
        # This test will verify that:
        # 1. Context has initial_simulation_output field
        # 2. It contains events from the initial simulation
        # 3. It's the SAME output regardless of iteration
        pass

    @pytest.mark.skip(reason="Phase 7 implementation not yet complete")
    def test_deterministic_mode_unchanged(self) -> None:
        """Deterministic mode (num_samples=1) should continue to work as before."""
        # This test ensures backward compatibility
        pass


# Phase 7b TDD Tests - Agent Config Helpers and Evaluation Wiring
class TestAgentConfigHelpers:
    """Test helper methods for extracting agent config from scenario.

    These tests verify that OptimizationLoop can extract agent configuration
    values (opening_balance, credit_limit) needed for BootstrapPolicyEvaluator.
    """

    def test_get_agent_opening_balance_extracts_from_scenario(self) -> None:
        """_get_agent_opening_balance should extract from scenario config."""
        from unittest.mock import MagicMock, patch

        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        # Create minimal mock config
        mock_config = MagicMock()
        mock_config.name = "test"
        mock_config.master_seed = 42
        mock_config.convergence.max_iterations = 1
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.num_samples = 1
        mock_config.evaluation.ticks = 10
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm.model = "test"
        mock_config.prompt_customization = None

        # Create loop
        loop = OptimizationLoop(config=mock_config)

        # Mock scenario config
        scenario = {
            "agents": [
                {"id": "BANK_A", "opening_balance": 10000000, "unsecured_cap": 5000000},
                {"id": "BANK_B", "opening_balance": 8000000, "unsecured_cap": 3000000},
            ]
        }

        with patch.object(loop, "_load_scenario_config", return_value=scenario):
            balance = loop._get_agent_opening_balance("BANK_A")
            assert balance == 10000000
            assert isinstance(balance, int)

            balance_b = loop._get_agent_opening_balance("BANK_B")
            assert balance_b == 8000000

    def test_get_agent_opening_balance_returns_zero_for_unknown_agent(self) -> None:
        """_get_agent_opening_balance should return 0 for unknown agent."""
        from unittest.mock import MagicMock, patch

        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        mock_config = MagicMock()
        mock_config.name = "test"
        mock_config.master_seed = 42
        mock_config.convergence.max_iterations = 1
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.num_samples = 1
        mock_config.evaluation.ticks = 10
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm.model = "test"
        mock_config.prompt_customization = None

        loop = OptimizationLoop(config=mock_config)

        scenario = {"agents": [{"id": "BANK_A", "opening_balance": 10000000}]}

        with patch.object(loop, "_load_scenario_config", return_value=scenario):
            balance = loop._get_agent_opening_balance("UNKNOWN_AGENT")
            assert balance == 0

    def test_get_agent_credit_limit_extracts_unsecured_cap(self) -> None:
        """_get_agent_credit_limit should extract unsecured_cap from scenario."""
        from unittest.mock import MagicMock, patch

        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        mock_config = MagicMock()
        mock_config.name = "test"
        mock_config.master_seed = 42
        mock_config.convergence.max_iterations = 1
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.num_samples = 1
        mock_config.evaluation.ticks = 10
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm.model = "test"
        mock_config.prompt_customization = None

        loop = OptimizationLoop(config=mock_config)

        scenario = {
            "agents": [
                {"id": "BANK_A", "opening_balance": 10000000, "unsecured_cap": 5000000},
            ]
        }

        with patch.object(loop, "_load_scenario_config", return_value=scenario):
            credit_limit = loop._get_agent_credit_limit("BANK_A")
            assert credit_limit == 5000000
            assert isinstance(credit_limit, int)


class TestEvaluatePolicyPairUsesBootstrapSamples:
    """Test that _evaluate_policy_pair uses pre-computed bootstrap samples.

    When bootstrap samples are available, _evaluate_policy_pair should use
    BootstrapPolicyEvaluator.compute_paired_deltas() instead of running
    new simulations.
    """

    def test_evaluate_policy_pair_returns_correct_delta_format(self) -> None:
        """_evaluate_policy_pair should return (deltas, delta_sum) tuple."""
        from unittest.mock import MagicMock, patch

        from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import PairedDelta
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        mock_config = MagicMock()
        mock_config.name = "test"
        mock_config.master_seed = 42
        mock_config.convergence.max_iterations = 1
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation.mode = "bootstrap"
        mock_config.evaluation.num_samples = 3
        mock_config.evaluation.ticks = 10
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm.model = "test"
        mock_config.prompt_customization = None

        loop = OptimizationLoop(config=mock_config)
        loop._current_iteration = 1

        # Mock bootstrap samples
        mock_sample = MagicMock()
        loop._bootstrap_samples = {"BANK_A": [mock_sample, mock_sample, mock_sample]}

        # Mock helper methods
        loop._get_agent_opening_balance = MagicMock(return_value=10000000)
        loop._get_agent_credit_limit = MagicMock(return_value=5000000)
        loop._cost_rates = {}

        # Mock the evaluator's compute_paired_deltas to return known deltas
        mock_deltas = [
            PairedDelta(sample_idx=0, seed=100, cost_a=5000, cost_b=4000, delta=1000),
            PairedDelta(sample_idx=1, seed=200, cost_a=6000, cost_b=5500, delta=500),
            PairedDelta(sample_idx=2, seed=300, cost_a=4500, cost_b=5000, delta=-500),
        ]

        with patch(
            "payment_simulator.experiments.runner.optimization.BootstrapPolicyEvaluator"
        ) as MockEvaluator:
            mock_evaluator_instance = MagicMock()
            mock_evaluator_instance.compute_paired_deltas.return_value = mock_deltas
            MockEvaluator.return_value = mock_evaluator_instance

            old_policy = {"type": "Fifo"}
            new_policy = {"type": "LiquidityAware", "target_buffer": 50000}

            deltas, delta_sum = loop._evaluate_policy_pair(
                agent_id="BANK_A",
                old_policy=old_policy,
                new_policy=new_policy,
            )

            # Verify format
            assert isinstance(deltas, list)
            assert len(deltas) == 3
            assert delta_sum == 1000  # 1000 + 500 + (-500) = 1000

            # Verify BootstrapPolicyEvaluator was used
            MockEvaluator.assert_called_once()
            mock_evaluator_instance.compute_paired_deltas.assert_called_once()

    def test_evaluate_policy_pair_raises_without_samples(self) -> None:
        """Without bootstrap samples, should raise RuntimeError.

        Design decision: No fallback to Monte Carlo. Real bootstrap only.
        See: docs/plans/bootstrap/phases/phase_7b.md
        """
        from unittest.mock import MagicMock

        import pytest

        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        mock_config = MagicMock()
        mock_config.name = "test"
        mock_config.master_seed = 42
        mock_config.convergence.max_iterations = 1
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation.mode = "bootstrap"
        mock_config.evaluation.num_samples = 3
        mock_config.evaluation.ticks = 10
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm.model = "test"
        mock_config.prompt_customization = None

        loop = OptimizationLoop(config=mock_config)
        loop._current_iteration = 1

        # NO bootstrap samples - should raise error, not fall back
        loop._bootstrap_samples = {}

        old_policy = {"type": "Fifo"}
        new_policy = {"type": "LiquidityAware"}

        with pytest.raises(
            RuntimeError,
            match="No bootstrap samples available for agent BANK_A",
        ):
            loop._evaluate_policy_pair(
                agent_id="BANK_A",
                old_policy=old_policy,
                new_policy=new_policy,
            )
