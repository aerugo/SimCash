"""Tests for web bootstrap policy evaluation."""
import pytest
from app.bootstrap_eval import WebBootstrapEvaluator, EvaluationResult
from app.scenario_pack import get_scenario_by_id


def make_policy(fraction: float) -> dict:
    return {
        "version": "2.0",
        "policy_id": f"test_{fraction}",
        "parameters": {"initial_liquidity_fraction": fraction},
        "bank_tree": {"type": "action", "node_id": "bank_root", "action": "NoAction"},
        "payment_tree": {"type": "action", "node_id": "pay_root", "action": "Release"},
    }


SCENARIO = get_scenario_by_id("2bank_12tick")


class TestPairedComparison:

    def test_identical_policies_zero_delta(self):
        ev = WebBootstrapEvaluator(num_samples=3, cv_threshold=0.5)
        result = ev.evaluate(
            raw_yaml=SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.5), new_policy=make_policy(0.5),
            base_seed=42,
        )
        assert result.delta_sum == 0
        assert result.accepted is True

    def test_better_policy_negative_delta(self):
        ev = WebBootstrapEvaluator(num_samples=5, cv_threshold=2.0)
        result = ev.evaluate(
            raw_yaml=SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(1.0), new_policy=make_policy(0.3),
            base_seed=42,
        )
        assert result.delta_sum < 0
        assert result.mean_delta < 0

    def test_paired_on_same_seeds(self):
        ev = WebBootstrapEvaluator(num_samples=3, cv_threshold=0.5)
        result = ev.evaluate(
            raw_yaml=SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.8), new_policy=make_policy(0.4),
            base_seed=42,
        )
        assert len(result.paired_deltas) == 3
        for d in result.paired_deltas:
            assert d["seed"] == 42 + d["sample_idx"] * 1000

    def test_determinism(self):
        ev = WebBootstrapEvaluator(num_samples=3, cv_threshold=0.5)
        r1 = ev.evaluate(
            raw_yaml=SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.5), new_policy=make_policy(0.3), base_seed=42,
        )
        r2 = ev.evaluate(
            raw_yaml=SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.5), new_policy=make_policy(0.3), base_seed=42,
        )
        assert r1.delta_sum == r2.delta_sum
        assert r1.cv == r2.cv


class TestAcceptanceCriteria:

    def test_reject_positive_delta(self):
        ev = WebBootstrapEvaluator(num_samples=5, cv_threshold=10.0)
        result = ev.evaluate(
            raw_yaml=SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.3), new_policy=make_policy(1.0),
            base_seed=42,
        )
        assert result.delta_sum > 0
        assert result.accepted is False

    def test_accept_clear_improvement(self):
        ev = WebBootstrapEvaluator(num_samples=10, cv_threshold=2.0)
        result = ev.evaluate(
            raw_yaml=SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(1.0), new_policy=make_policy(0.3),
            base_seed=42,
        )
        assert result.delta_sum < 0
        assert result.accepted is True


class TestEvaluationResult:

    def test_result_has_all_fields(self):
        ev = WebBootstrapEvaluator(num_samples=3, cv_threshold=0.5)
        result = ev.evaluate(
            raw_yaml=SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.5), new_policy=make_policy(0.3), base_seed=42,
        )
        assert hasattr(result, 'delta_sum')
        assert hasattr(result, 'mean_delta')
        assert hasattr(result, 'cv')
        assert hasattr(result, 'ci_lower')
        assert hasattr(result, 'ci_upper')
        assert hasattr(result, 'accepted')
        assert hasattr(result, 'rejection_reason')
        assert hasattr(result, 'paired_deltas')
        assert hasattr(result, 'num_samples')

    def test_costs_are_integers(self):
        ev = WebBootstrapEvaluator(num_samples=3, cv_threshold=0.5)
        result = ev.evaluate(
            raw_yaml=SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.5), new_policy=make_policy(0.3), base_seed=42,
        )
        assert isinstance(result.delta_sum, int)
        assert isinstance(result.ci_lower, int)
        assert isinstance(result.ci_upper, int)
        assert isinstance(result.old_mean_cost, int)
        assert isinstance(result.new_mean_cost, int)
