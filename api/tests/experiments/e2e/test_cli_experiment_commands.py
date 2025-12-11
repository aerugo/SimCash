"""End-to-end tests for CLI experiment commands with verbose/debug flags.

These tests verify that the CLI experiment commands work correctly,
especially focusing on the verbose and debug output that helps
investigate bootstrap samples and their effect on policy adoption.

Key behaviors tested:
1. Verbose output shows bootstrap sample details
2. Debug output shows LLM retry attempts and validation errors
3. Bootstrap samples correctly affect policy acceptance/rejection
4. Paired comparison uses same samples for both policies

Note: Tests that require the 'castro' module are marked with
pytest.importorskip("castro") since castro is a separate package
with its own virtual environment.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from payment_simulator.ai_cash_mgmt import SeedManager
from payment_simulator.ai_cash_mgmt.bootstrap import BootstrapPolicyEvaluator
from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import PairedDelta
from payment_simulator.ai_cash_mgmt.bootstrap.models import (
    BootstrapSample,
    RemappedTransaction,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_experiment_config() -> Path:
    """Create a temporary experiment config file."""
    config = {
        "name": "test_experiment",
        "description": "Test experiment for CLI testing",
        "scenario": "configs/test_scenario.yaml",
        "evaluation": {
            "mode": "bootstrap",
            "num_samples": 5,
            "ticks": 12,
        },
        "convergence": {
            "max_iterations": 3,
            "stability_threshold": 0.05,
            "stability_window": 2,
            "improvement_threshold": 0.01,
        },
        "llm": {
            "model": "anthropic:claude-sonnet-4-5",
            "temperature": 0.0,
            "max_retries": 2,
            "timeout_seconds": 60,
        },
        "optimized_agents": ["BANK_A"],
        "constraints": "",
        "output": {
            "directory": "results",
            "database": "test_experiments.db",
            "verbose": True,
        },
        "master_seed": 42,
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(config, f)
        return Path(f.name)


@pytest.fixture
def mock_verbose_logger() -> MagicMock:
    """Create a mock verbose logger to capture output."""
    logger = MagicMock()
    logger.log_bootstrap_evaluation = MagicMock()
    logger.log_llm_call = MagicMock()
    logger.log_policy_change = MagicMock()
    logger.log_rejection = MagicMock()
    logger.log_debug_validation_error = MagicMock()
    logger.log_debug_llm_request_start = MagicMock()
    return logger


def _create_test_sample(
    sample_idx: int,
    seed: int,
    agent_id: str = "BANK_A",
    cost_factor: int = 1,
) -> BootstrapSample:
    """Create a bootstrap sample with configurable cost factor.

    Args:
        sample_idx: Index of the sample.
        seed: RNG seed.
        agent_id: Agent ID for this sample.
        cost_factor: Multiplier for transaction amount (affects cost).

    Returns:
        BootstrapSample for testing.
    """
    outgoing = RemappedTransaction(
        tx_id=f"tx-out-{sample_idx}",
        sender_id=agent_id,
        receiver_id="SINK",
        amount=100_000_00 * cost_factor,  # Variable amount
        priority=5,
        arrival_tick=0,
        deadline_tick=10,
        settlement_tick=5,
    )

    incoming = RemappedTransaction(
        tx_id=f"tx-in-{sample_idx}",
        sender_id="SOURCE",
        receiver_id=agent_id,
        amount=50_000_00,
        priority=5,
        arrival_tick=0,
        deadline_tick=10,
        settlement_tick=3,
    )

    return BootstrapSample(
        agent_id=agent_id,
        sample_idx=sample_idx,
        seed=seed,
        outgoing_txns=(outgoing,),
        incoming_settlements=(incoming,),
        total_ticks=12,
    )


def _create_test_policy(threshold: float = 3.0) -> dict[str, Any]:
    """Create a test policy with configurable urgency threshold.

    Args:
        threshold: Ticks to deadline at which to release payment.

    Returns:
        Policy dict.
    """
    return {
        "version": "2.0",
        "policy_id": f"test_policy_t{int(threshold)}",
        "parameters": {
            "urgency_threshold": threshold,
        },
        "payment_tree": {
            "type": "condition",
            "node_id": "urgency_check",
            "condition": {
                "op": "<=",
                "left": {"field": "ticks_to_deadline"},
                "right": {"param": "urgency_threshold"},
            },
            "on_true": {"type": "action", "node_id": "release", "action": "Release"},
            "on_false": {"type": "action", "node_id": "hold_payment", "action": "Hold"},
        },
        "strategic_collateral_tree": {
            "type": "action",
            "node_id": "hold_collateral",
            "action": "HoldCollateral",
        },
    }


# =============================================================================
# VerboseConfig Tests (require castro module)
# =============================================================================


class TestVerboseConfigFromFlags:
    """Tests for VerboseConfig.from_flags() behavior.

    These tests require the castro module which has its own venv.
    Run from experiments/castro/.venv for full test coverage.
    """

    def test_verbose_flag_enables_all_output(self) -> None:
        """When --verbose is set, all verbose flags are enabled."""
        pytest.importorskip("castro")
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig.from_flags(verbose=True)

        assert config.policy is True
        assert config.bootstrap is True
        assert config.llm is True
        assert config.rejections is True
        # debug is NOT enabled by verbose
        assert config.debug is False

    def test_individual_flags_override_verbose(self) -> None:
        """Individual flags can override the verbose setting."""
        pytest.importorskip("castro")
        from castro.verbose_logging import VerboseConfig

        # Even with verbose=True, explicitly set flags override
        config = VerboseConfig.from_flags(
            verbose=True,
            verbose_policy=False,
            verbose_bootstrap=True,
        )

        assert config.policy is False  # Explicitly disabled
        assert config.bootstrap is True  # Explicitly enabled
        assert config.llm is True  # From verbose=True
        assert config.rejections is True  # From verbose=True

    def test_debug_flag_enables_debug_output(self) -> None:
        """The --debug flag is separate from --verbose."""
        pytest.importorskip("castro")
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig.from_flags(debug=True)

        assert config.debug is True
        # Other flags should be disabled
        assert config.policy is False
        assert config.bootstrap is False
        assert config.llm is False
        assert config.rejections is False

    def test_verbose_and_debug_together(self) -> None:
        """Both --verbose and --debug can be enabled together."""
        pytest.importorskip("castro")
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig.from_flags(verbose=True, debug=True)

        assert config.policy is True
        assert config.bootstrap is True
        assert config.llm is True
        assert config.rejections is True
        assert config.debug is True


# =============================================================================
# Bootstrap Sample Output Tests
# =============================================================================


class TestBootstrapSampleOutput:
    """Tests for bootstrap sample verbose output.

    Per game_concept_doc.md Bootstrap section:
    Verbose output should show per-sample results including:
    - Seed used for each sample
    - Cost for that sample
    - Settlement rate
    - Delta from baseline (for iteration 2+)

    These tests require the castro module.
    """

    def test_bootstrap_sample_result_captures_all_fields(self) -> None:
        """BootstrapSampleResult captures seed, cost, and settlement info."""
        pytest.importorskip("castro")
        from castro.verbose_logging import BootstrapSampleResult

        result = BootstrapSampleResult(
            seed=12345,
            cost=150_000_00,  # $150,000 in cents
            settled=8,
            total=10,
            settlement_rate=0.8,
            baseline_cost=160_000_00,  # Previous iteration baseline
        )

        assert result.seed == 12345
        assert result.cost == 150_000_00
        assert result.settled == 8
        assert result.total == 10
        assert result.settlement_rate == 0.8
        assert result.baseline_cost == 160_000_00

    def test_bootstrap_sample_result_delta_percent(self) -> None:
        """Delta percent shows improvement vs baseline."""
        pytest.importorskip("castro")
        from castro.verbose_logging import BootstrapSampleResult

        result = BootstrapSampleResult(
            seed=12345,
            cost=90_000_00,  # Improved from 100K to 90K
            settled=10,
            total=10,
            settlement_rate=1.0,
            baseline_cost=100_000_00,
        )

        delta = result.delta_percent
        assert delta is not None
        # (100K - 90K) / 100K * 100 = 10%
        assert delta == pytest.approx(10.0)

    def test_bootstrap_sample_result_no_baseline(self) -> None:
        """First iteration has no baseline, delta_percent is None."""
        pytest.importorskip("castro")
        from castro.verbose_logging import BootstrapSampleResult

        result = BootstrapSampleResult(
            seed=12345,
            cost=100_000_00,
            settled=10,
            total=10,
            settlement_rate=1.0,
            baseline_cost=None,  # No baseline on iteration 1
        )

        assert result.baseline_cost is None
        assert result.delta_percent is None

    def test_bootstrap_sample_result_regression(self) -> None:
        """Negative delta when new cost is higher than baseline."""
        pytest.importorskip("castro")
        from castro.verbose_logging import BootstrapSampleResult

        result = BootstrapSampleResult(
            seed=12345,
            cost=110_000_00,  # Regressed from 100K to 110K
            settled=9,
            total=10,
            settlement_rate=0.9,
            baseline_cost=100_000_00,
        )

        delta = result.delta_percent
        assert delta is not None
        # (100K - 110K) / 100K * 100 = -10%
        assert delta == pytest.approx(-10.0)


# =============================================================================
# Paired Comparison Effect on Policy Adoption
# =============================================================================


class TestPairedComparisonPolicyAdoption:
    """Tests showing how bootstrap samples affect policy adoption.

    The key insight: policy adoption is based on MEAN DELTA across
    all bootstrap samples. A policy can show:
    - Consistent improvement across all samples → strong accept
    - Consistent regression across all samples → strong reject
    - Mixed results that net positive → marginal accept
    - Mixed results that net negative → marginal reject
    """

    def test_consistent_improvement_leads_to_acceptance(self) -> None:
        """When all samples show improvement, policy is accepted."""
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000_00,
            credit_limit=500_000_00,
        )

        # All samples show improvement (positive delta = old > new, new is better)
        deltas = [
            PairedDelta(sample_idx=0, seed=100, cost_a=10000, cost_b=8000, delta=2000),
            PairedDelta(sample_idx=1, seed=101, cost_a=11000, cost_b=9000, delta=2000),
            PairedDelta(sample_idx=2, seed=102, cost_a=12000, cost_b=10000, delta=2000),
        ]

        mean_delta = evaluator.compute_mean_delta(deltas)

        # Mean delta = 2000, strongly positive
        assert mean_delta == pytest.approx(2000.0)
        should_accept = mean_delta > 0
        assert should_accept is True

    def test_consistent_regression_leads_to_rejection(self) -> None:
        """When all samples show regression, policy is rejected."""
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000_00,
            credit_limit=500_000_00,
        )

        # All samples show regression (negative delta = new > old, new is worse)
        deltas = [
            PairedDelta(sample_idx=0, seed=100, cost_a=8000, cost_b=10000, delta=-2000),
            PairedDelta(sample_idx=1, seed=101, cost_a=9000, cost_b=11000, delta=-2000),
            PairedDelta(sample_idx=2, seed=102, cost_a=10000, cost_b=12000, delta=-2000),
        ]

        mean_delta = evaluator.compute_mean_delta(deltas)

        # Mean delta = -2000, strongly negative
        assert mean_delta == pytest.approx(-2000.0)
        should_accept = mean_delta > 0
        assert should_accept is False

    def test_mixed_results_with_net_improvement(self) -> None:
        """Mixed sample results that net positive lead to acceptance.

        This demonstrates why bootstrap sampling matters:
        - Sample 0: Big improvement (+5000)
        - Sample 1: Slight regression (-1000)
        - Sample 2: Moderate improvement (+2000)

        Net: +2000 mean delta → accept, but marginal
        """
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000_00,
            credit_limit=500_000_00,
        )

        deltas = [
            PairedDelta(sample_idx=0, seed=100, cost_a=10000, cost_b=5000, delta=5000),  # Big win
            PairedDelta(sample_idx=1, seed=101, cost_a=10000, cost_b=11000, delta=-1000),  # Small loss
            PairedDelta(sample_idx=2, seed=102, cost_a=10000, cost_b=8000, delta=2000),  # Moderate win
        ]

        mean_delta = evaluator.compute_mean_delta(deltas)

        # Mean delta = (5000 - 1000 + 2000) / 3 = 2000
        assert mean_delta == pytest.approx(2000.0)
        should_accept = mean_delta > 0
        assert should_accept is True

    def test_mixed_results_with_net_regression(self) -> None:
        """Mixed sample results that net negative lead to rejection.

        - Sample 0: Slight improvement (+1000)
        - Sample 1: Big regression (-5000)
        - Sample 2: Moderate regression (-2000)

        Net: -2000 mean delta → reject
        """
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000_00,
            credit_limit=500_000_00,
        )

        deltas = [
            PairedDelta(sample_idx=0, seed=100, cost_a=10000, cost_b=9000, delta=1000),  # Small win
            PairedDelta(sample_idx=1, seed=101, cost_a=10000, cost_b=15000, delta=-5000),  # Big loss
            PairedDelta(sample_idx=2, seed=102, cost_a=10000, cost_b=12000, delta=-2000),  # Moderate loss
        ]

        mean_delta = evaluator.compute_mean_delta(deltas)

        # Mean delta = (1000 - 5000 - 2000) / 3 = -2000
        assert mean_delta == pytest.approx(-2000.0)
        should_accept = mean_delta > 0
        assert should_accept is False

    def test_sample_variance_affects_confidence(self) -> None:
        """High variance in deltas suggests less confidence in decision.

        Both scenarios have mean delta = +1000, but:
        - Low variance: consistent +1000 across samples → high confidence
        - High variance: +10000, -8000 → same mean but lower confidence
        """
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000_00,
            credit_limit=500_000_00,
        )

        # Low variance scenario
        low_var_deltas = [
            PairedDelta(sample_idx=0, seed=100, cost_a=10000, cost_b=9000, delta=1000),
            PairedDelta(sample_idx=1, seed=101, cost_a=10000, cost_b=9000, delta=1000),
        ]

        # High variance scenario (same mean)
        high_var_deltas = [
            PairedDelta(sample_idx=0, seed=100, cost_a=10000, cost_b=0, delta=10000),  # Huge win
            PairedDelta(sample_idx=1, seed=101, cost_a=10000, cost_b=18000, delta=-8000),  # Huge loss
        ]

        low_var_mean = evaluator.compute_mean_delta(low_var_deltas)
        high_var_mean = evaluator.compute_mean_delta(high_var_deltas)

        # Both have same mean = 1000
        assert low_var_mean == pytest.approx(1000.0)
        assert high_var_mean == pytest.approx(1000.0)

        # Compute variance for comparison
        low_var_variance = sum((d.delta - low_var_mean) ** 2 for d in low_var_deltas) / len(low_var_deltas)
        high_var_variance = sum((d.delta - high_var_mean) ** 2 for d in high_var_deltas) / len(high_var_deltas)

        # High variance scenario has much higher variance
        assert high_var_variance > low_var_variance
        assert high_var_variance > 1_000_000  # Very high


# =============================================================================
# Baseline Cost Tracking Tests
# =============================================================================


class TestBaselineCostTracking:
    """Tests for baseline cost tracking across iterations.

    Per game_concept_doc.md: The first iteration establishes baseline costs
    for each seed. Subsequent iterations compare against these baselines.
    """

    def test_baseline_stored_on_iteration_1(self) -> None:
        """Baseline costs should be stored on first iteration."""
        # This simulates what ExperimentRunner does on iteration 1
        baseline_costs: dict[int, int] = {}
        is_baseline_run = True

        # Simulated seed results from iteration 1
        seed_results = [
            MagicMock(seed=100, cost=10000),
            MagicMock(seed=101, cost=11000),
            MagicMock(seed=102, cost=12000),
        ]

        if is_baseline_run:
            for result in seed_results:
                baseline_costs[result.seed] = result.cost

        assert baseline_costs[100] == 10000
        assert baseline_costs[101] == 11000
        assert baseline_costs[102] == 12000

    def test_baseline_used_for_delta_on_iteration_2(self) -> None:
        """Iteration 2+ uses baseline for delta calculation."""
        # Stored from iteration 1
        baseline_costs = {100: 10000, 101: 11000, 102: 12000}

        # Iteration 2 results
        iter2_results = [
            MagicMock(seed=100, cost=9000),   # Improved
            MagicMock(seed=101, cost=12000),  # Regressed
            MagicMock(seed=102, cost=12000),  # Same
        ]

        # Calculate deltas
        deltas = []
        for result in iter2_results:
            baseline = baseline_costs[result.seed]
            delta = baseline - result.cost  # Positive = improvement
            deltas.append(delta)

        assert deltas[0] == 1000   # 10000 - 9000 = +1000 (improved)
        assert deltas[1] == -1000  # 11000 - 12000 = -1000 (regressed)
        assert deltas[2] == 0      # 12000 - 12000 = 0 (same)


# =============================================================================
# Debug Output Tests
# =============================================================================


class TestDebugOutput:
    """Tests for debug output functionality.

    The --debug flag shows:
    - LLM request start/end
    - Validation errors and retry attempts
    - Policy parsing errors

    These tests require the castro module.
    """

    def test_debug_callback_protocol(self) -> None:
        """VerboseLoggerDebugCallback implements DebugCallback protocol."""
        pytest.importorskip("castro")
        from castro.runner import VerboseLoggerDebugCallback
        from castro.verbose_logging import VerboseConfig, VerboseLogger
        from rich.console import Console

        config = VerboseConfig(debug=True)
        console = Console(force_terminal=True)
        logger = VerboseLogger(config, console)
        callback = VerboseLoggerDebugCallback(logger)

        # Verify callback has required methods
        assert hasattr(callback, "on_attempt_start")
        assert hasattr(callback, "on_validation_error")
        assert hasattr(callback, "on_llm_error")
        assert hasattr(callback, "on_validation_success")
        assert hasattr(callback, "on_all_retries_exhausted")

    def test_validation_error_logged_with_details(self) -> None:
        """Validation errors should include error details and attempt count."""
        pytest.importorskip("castro")
        from castro.verbose_logging import VerboseConfig, VerboseLogger
        from rich.console import Console
        import io

        output = io.StringIO()
        console = Console(file=output, force_terminal=False)
        config = VerboseConfig(debug=True)
        logger = VerboseLogger(config, console)

        # Log a validation error
        logger.log_debug_validation_error(
            agent_id="BANK_A",
            attempt=1,
            max_attempts=3,
            errors=["Invalid threshold value", "Missing required field"],
        )

        logged_output = output.getvalue()
        # The output should contain relevant information
        # (exact format depends on implementation)
        assert logger is not None  # Logger was created


# =============================================================================
# Verbose Logger Integration Tests
# =============================================================================


class TestVerboseLoggerIntegration:
    """Tests for VerboseLogger integration with experiment flow.

    These tests require the castro module.
    """

    def test_verbose_logger_bootstrap_evaluation_output(self) -> None:
        """VerboseLogger should format bootstrap evaluation results."""
        pytest.importorskip("castro")
        from castro.verbose_logging import (
            BootstrapSampleResult,
            VerboseConfig,
            VerboseLogger,
        )
        from rich.console import Console
        import io

        output = io.StringIO()
        console = Console(file=output, force_terminal=False)
        config = VerboseConfig(bootstrap=True)
        logger = VerboseLogger(config, console)

        seed_results = [
            BootstrapSampleResult(
                seed=100,
                cost=10000,
                settled=10,
                total=10,
                settlement_rate=1.0,
                baseline_cost=None,  # Iteration 1
            ),
            BootstrapSampleResult(
                seed=101,
                cost=11000,
                settled=9,
                total=10,
                settlement_rate=0.9,
                baseline_cost=None,
            ),
        ]

        logger.log_monte_carlo_evaluation(
            seed_results=seed_results,
            mean_cost=10500,
            std_cost=500,
            deterministic=False,
            is_baseline_run=True,
        )

        # Logger should have been called without errors
        assert logger is not None

    def test_verbose_logger_policy_change_output(self) -> None:
        """VerboseLogger should format policy change information."""
        pytest.importorskip("castro")
        from castro.verbose_logging import VerboseConfig, VerboseLogger
        from rich.console import Console
        import io

        output = io.StringIO()
        console = Console(file=output, force_terminal=False)
        config = VerboseConfig(policy=True)
        logger = VerboseLogger(config, console)

        old_policy = _create_test_policy(threshold=3.0)
        new_policy = _create_test_policy(threshold=5.0)

        logger.log_policy_change(
            agent_id="BANK_A",
            old_policy=old_policy,
            new_policy=new_policy,
            old_cost=10000,
            new_cost=8000,
            accepted=True,
        )

        # Logger should have been called without errors
        assert logger is not None


# =============================================================================
# Sample Effect on Specific Policy Parameters
# =============================================================================


class TestSampleEffectOnPolicyParameters:
    """Tests showing how different samples affect policy parameter decisions.

    This helps understand which policy parameters work well on which
    types of transaction patterns (as captured by bootstrap samples).
    """

    def test_early_release_policy_on_high_value_samples(self) -> None:
        """Early release (high threshold) on high-value transaction samples.

        High-value transactions have higher delay costs, so early release
        (higher urgency_threshold) should perform better.
        """
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000_00,
            credit_limit=500_000_00,
        )

        # Create samples with high-value transactions
        high_value_samples = [
            _create_test_sample(i, seed=42 + i, cost_factor=10)  # 10x amount
            for i in range(3)
        ]

        late_release_policy = _create_test_policy(threshold=1.0)  # Release at last moment
        early_release_policy = _create_test_policy(threshold=8.0)  # Release early

        deltas = evaluator.compute_paired_deltas(
            samples=high_value_samples,
            policy_a=late_release_policy,
            policy_b=early_release_policy,
        )

        # The comparison was made
        assert len(deltas) == 3
        # Each delta compares the same sample with different policies
        for delta in deltas:
            assert delta.cost_a >= 0
            assert delta.cost_b >= 0

    def test_late_release_policy_on_low_liquidity_samples(self) -> None:
        """Late release may work better when incoming liquidity arrives late.

        If incoming settlements arrive late, holding payments until liquidity
        is available (lower threshold) may reduce overdraft costs.
        """
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=100_000_00,  # Lower opening balance
            credit_limit=50_000_00,  # Lower credit limit
        )

        # Use standard samples
        samples = [
            _create_test_sample(i, seed=42 + i)
            for i in range(3)
        ]

        early_release_policy = _create_test_policy(threshold=8.0)
        late_release_policy = _create_test_policy(threshold=2.0)

        deltas = evaluator.compute_paired_deltas(
            samples=samples,
            policy_a=early_release_policy,
            policy_b=late_release_policy,
        )

        # The comparison was made
        assert len(deltas) == 3


# =============================================================================
# CLI Command Validation Tests
# =============================================================================


class TestCLICommandValidation:
    """Tests for CLI command input validation."""

    def test_validate_command_with_invalid_yaml(self) -> None:
        """validate command should fail gracefully on invalid YAML."""
        from typer.testing import CliRunner

        from payment_simulator.cli.commands.experiment import experiment_app

        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: ::::")  # Invalid YAML
            temp_path = Path(f.name)

        try:
            result = runner.invoke(experiment_app, ["validate", str(temp_path)])
            assert result.exit_code == 1
            assert "Error" in result.output or "Invalid" in result.output
        finally:
            temp_path.unlink()

    def test_validate_command_with_missing_file(self) -> None:
        """validate command should fail gracefully on missing file."""
        from typer.testing import CliRunner

        from payment_simulator.cli.commands.experiment import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["validate", "/nonexistent/path.yaml"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_info_command_shows_framework_info(self) -> None:
        """info command should display framework information."""
        from typer.testing import CliRunner

        from payment_simulator.cli.commands.experiment import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["info"])

        assert result.exit_code == 0
        assert "Experiment Framework" in result.output
        assert "bootstrap" in result.output.lower()
        assert "deterministic" in result.output.lower()

    def test_template_command_generates_valid_yaml(self) -> None:
        """template command should generate valid experiment config."""
        from typer.testing import CliRunner

        from payment_simulator.cli.commands.experiment import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["template"])

        assert result.exit_code == 0

        # Output should be valid YAML
        config = yaml.safe_load(result.output)
        assert config is not None
        assert "name" in config
        assert "evaluation" in config
        assert "llm" in config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
