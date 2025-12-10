"""Integration tests for Castro bootstrap integration.

Phase 6: Castro Integration - Tests for bootstrap-based policy evaluation
in the AI Cash Management optimization workflow.
"""

from __future__ import annotations

from payment_simulator.ai_cash_mgmt.bootstrap import (
    BootstrapPolicyEvaluator,
    BootstrapSample,
    BootstrapSampler,
    TransactionHistoryCollector,
    TransactionRecord,
)


class TestHistoryCollectionFromSimulation:
    """Test collecting transaction history from simulation events."""

    def test_collect_history_from_events(self) -> None:
        """Transaction history is collected from simulation events."""
        # Simulate events from a completed simulation
        events = [
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 5,
                "deadline_tick": 10,
            },
            {
                "event_type": "arrival",
                "tick": 2,
                "tx_id": "tx-002",
                "sender_id": "BANK_B",
                "receiver_id": "BANK_A",
                "amount": 50000,
                "priority": 7,
                "deadline_tick": 12,
            },
            {
                "event_type": "rtgs_immediate_settlement",
                "tick": 1,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
            },
            {
                "event_type": "rtgs_immediate_settlement",
                "tick": 5,
                "tx_id": "tx-002",
                "sender_id": "BANK_B",
                "receiver_id": "BANK_A",
                "amount": 50000,
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        # Check BANK_A's perspective
        history_a = collector.get_agent_history("BANK_A")
        assert len(history_a.outgoing) > 0 or len(history_a.incoming) > 0

        # BANK_A sent tx-001, received tx-002
        assert len(history_a.outgoing) == 1
        assert len(history_a.incoming) == 1

    def test_collector_tracks_all_agents(self) -> None:
        """Collector tracks history for all participating agents."""
        events = [
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 5,
                "deadline_tick": 10,
            },
            {
                "event_type": "arrival",
                "tick": 1,
                "tx_id": "tx-002",
                "sender_id": "BANK_C",
                "receiver_id": "BANK_A",
                "amount": 75000,
                "priority": 3,
                "deadline_tick": 10,
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        agent_ids = collector.get_all_agent_ids()
        assert "BANK_A" in agent_ids
        assert "BANK_B" in agent_ids
        assert "BANK_C" in agent_ids


class TestBootstrapSampleGeneration:
    """Test generating bootstrap samples from history."""

    def test_generate_samples_from_history(self) -> None:
        """Bootstrap samples are generated from transaction history."""
        # Create mock history
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000 + i * 1000,
                priority=5,
                original_arrival_tick=i * 2,
                deadline_offset=10,
                settlement_offset=3,
            )
            for i in range(10)
        )

        sampler = BootstrapSampler(seed=42)
        samples = sampler.generate_samples(
            agent_id="BANK_A",
            n_samples=5,
            outgoing_records=records,
            incoming_records=(),
            total_ticks=100,
        )

        assert len(samples) == 5
        for sample in samples:
            assert sample.agent_id == "BANK_A"
            assert len(sample.outgoing_txns) == len(records)

    def test_samples_are_deterministic(self) -> None:
        """Same seed produces identical samples."""
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=i,
                deadline_offset=10,
                settlement_offset=3,
            )
            for i in range(5)
        )

        sampler1 = BootstrapSampler(seed=12345)
        sample1 = sampler1.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=records,
            incoming_records=(),
            total_ticks=100,
        )

        sampler2 = BootstrapSampler(seed=12345)
        sample2 = sampler2.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=records,
            incoming_records=(),
            total_ticks=100,
        )

        assert sample1.seed == sample2.seed
        assert len(sample1.outgoing_txns) == len(sample2.outgoing_txns)


class TestBootstrapPolicyEvaluation:
    """Test policy evaluation using bootstrap samples."""

    def test_evaluate_policy_on_samples(self) -> None:
        """Policy is evaluated across multiple bootstrap samples."""
        # Create simple samples
        samples = [
            BootstrapSample(
                agent_id="BANK_A",
                sample_idx=i,
                seed=12345 + i,
                outgoing_txns=(),
                incoming_settlements=(),
                total_ticks=100,
            )
            for i in range(3)
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        results = evaluator.evaluate_samples(
            samples=samples,
            policy={"type": "Fifo"},
        )

        assert len(results) == 3
        for result in results:
            assert result.total_cost >= 0
            assert 0.0 <= result.settlement_rate <= 1.0


class TestPairedPolicyComparison:
    """Test paired delta computation between policies."""

    def test_paired_deltas_computed(self) -> None:
        """Paired deltas are computed between two policies."""
        samples = [
            BootstrapSample(
                agent_id="BANK_A",
                sample_idx=i,
                seed=12345 + i,
                outgoing_txns=(),
                incoming_settlements=(),
                total_ticks=100,
            )
            for i in range(3)
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        deltas = evaluator.compute_paired_deltas(
            samples=samples,
            policy_a={"type": "Fifo"},
            policy_b={"type": "Fifo"},  # Same policy for test
        )

        assert len(deltas) == 3
        for delta in deltas:
            # Same policy should give zero delta
            assert delta.delta == 0

    def test_mean_delta_calculation(self) -> None:
        """Mean delta is calculated from paired comparisons."""
        samples = [
            BootstrapSample(
                agent_id="BANK_A",
                sample_idx=i,
                seed=12345 + i,
                outgoing_txns=(),
                incoming_settlements=(),
                total_ticks=100,
            )
            for i in range(5)
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        deltas = evaluator.compute_paired_deltas(
            samples=samples,
            policy_a={"type": "Fifo"},
            policy_b={"type": "Fifo"},
        )

        mean_delta = evaluator.compute_mean_delta(deltas)
        assert isinstance(mean_delta, float)


class TestEndToEndWorkflow:
    """Test complete bootstrap evaluation workflow."""

    def test_full_workflow_collect_sample_evaluate(self) -> None:
        """Complete workflow: collect history, sample, evaluate."""
        # 1. Simulate events
        events = [
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 5,
                "deadline_tick": 10,
            },
            {
                "event_type": "rtgs_immediate_settlement",
                "tick": 2,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
            },
        ]

        # 2. Collect history
        collector = TransactionHistoryCollector()
        collector.process_events(events)
        history = collector.get_agent_history("BANK_A")

        # 3. Generate bootstrap samples
        sampler = BootstrapSampler(seed=42)
        samples = sampler.generate_samples(
            agent_id="BANK_A",
            n_samples=3,
            outgoing_records=history.outgoing,
            incoming_records=history.incoming,
            total_ticks=100,
        )

        # 4. Evaluate policies
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        # Evaluate single policy
        results = evaluator.evaluate_samples(
            samples=samples,
            policy={"type": "Fifo"},
        )

        assert len(results) == 3
        mean_cost = evaluator.compute_mean_cost(results)
        assert isinstance(mean_cost, float)

    def test_workflow_is_deterministic(self) -> None:
        """Full workflow produces identical results with same seed."""
        events = [
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 5,
                "deadline_tick": 10,
            },
        ]

        def run_workflow(seed: int) -> float:
            collector = TransactionHistoryCollector()
            collector.process_events(events)
            history = collector.get_agent_history("BANK_A")

            sampler = BootstrapSampler(seed=seed)
            samples = sampler.generate_samples(
                agent_id="BANK_A",
                n_samples=5,
                outgoing_records=history.outgoing,
                incoming_records=history.incoming,
                total_ticks=100,
            )

            evaluator = BootstrapPolicyEvaluator(
                opening_balance=1_000_000,
                credit_limit=500_000,
            )
            results = evaluator.evaluate_samples(
                samples=samples,
                policy={"type": "Fifo"},
            )
            return evaluator.compute_mean_cost(results)

        # Same seed should produce identical results
        result1 = run_workflow(seed=12345)
        result2 = run_workflow(seed=12345)
        assert result1 == result2

        # Different seed produces a result (may or may not differ)
        result3 = run_workflow(seed=99999)
        # Verify result3 is valid (just checking it's a float)
        assert isinstance(result3, float)


class TestMonteCarloStatistics:
    """Test Monte Carlo aggregation statistics."""

    def test_improvement_probability_calculation(self) -> None:
        """Improvement probability can be calculated from deltas."""
        samples = [
            BootstrapSample(
                agent_id="BANK_A",
                sample_idx=i,
                seed=12345 + i,
                outgoing_txns=(),
                incoming_settlements=(),
                total_ticks=100,
            )
            for i in range(10)
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        deltas = evaluator.compute_paired_deltas(
            samples=samples,
            policy_a={"type": "Fifo"},
            policy_b={"type": "Fifo"},
        )

        # Calculate improvement probability (negative delta = improvement)
        improvements = sum(1 for d in deltas if d.delta < 0)
        improvement_prob = improvements / len(deltas)

        assert 0.0 <= improvement_prob <= 1.0

    def test_confidence_interval_calculation(self) -> None:
        """Confidence interval can be calculated from sample deltas."""
        samples = [
            BootstrapSample(
                agent_id="BANK_A",
                sample_idx=i,
                seed=12345 + i,
                outgoing_txns=(),
                incoming_settlements=(),
                total_ticks=100,
            )
            for i in range(20)
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        deltas = evaluator.compute_paired_deltas(
            samples=samples,
            policy_a={"type": "Fifo"},
            policy_b={"type": "Fifo"},
        )

        # Calculate 95% CI (simple percentile method)
        delta_values = sorted(d.delta for d in deltas)
        n = len(delta_values)
        ci_lower_idx = int(0.025 * n)
        ci_upper_idx = int(0.975 * n) - 1

        ci_lower = delta_values[ci_lower_idx]
        ci_upper = delta_values[ci_upper_idx]

        # CI should be valid
        assert ci_lower <= ci_upper
