"""Tests for core verbose logging infrastructure.

Task 14.1: TDD tests for VerboseConfig and VerboseLogger.
These tests MUST FAIL before implementation.
"""

from __future__ import annotations

import pytest
from io import StringIO
from rich.console import Console


class TestVerboseConfigImport:
    """Tests for VerboseConfig importability."""

    def test_import_from_experiments_runner(self) -> None:
        """VerboseConfig importable from experiments.runner."""
        from payment_simulator.experiments.runner import VerboseConfig
        assert VerboseConfig is not None

    def test_import_from_verbose_module(self) -> None:
        """VerboseConfig importable from verbose module."""
        from payment_simulator.experiments.runner.verbose import VerboseConfig
        assert VerboseConfig is not None


class TestVerboseConfig:
    """Tests for VerboseConfig dataclass."""

    def test_default_all_disabled(self) -> None:
        """Default config has all flags disabled."""
        from payment_simulator.experiments.runner import VerboseConfig

        config = VerboseConfig()
        assert config.iterations is False
        assert config.policy is False
        assert config.bootstrap is False
        assert config.llm is False
        assert config.rejections is False
        assert config.debug is False

    def test_all_enabled_factory(self) -> None:
        """all_enabled() creates config with all main flags True."""
        from payment_simulator.experiments.runner import VerboseConfig

        config = VerboseConfig.all_enabled()
        assert config.iterations is True
        assert config.policy is True
        assert config.bootstrap is True
        assert config.llm is True
        assert config.rejections is True
        assert config.debug is False  # Debug not enabled by all_enabled()

    def test_from_cli_flags_verbose_enables_all(self) -> None:
        """from_cli_flags(verbose=True) enables all main flags."""
        from payment_simulator.experiments.runner import VerboseConfig

        config = VerboseConfig.from_cli_flags(verbose=True)
        assert config.iterations is True
        assert config.policy is True
        assert config.bootstrap is True
        assert config.llm is True
        assert config.rejections is True

    def test_from_cli_flags_individual_overrides(self) -> None:
        """from_cli_flags with individual flags overrides verbose."""
        from payment_simulator.experiments.runner import VerboseConfig

        config = VerboseConfig.from_cli_flags(
            verbose=True,
            verbose_policy=False,  # Explicitly disable
        )
        assert config.iterations is True
        assert config.policy is False  # Overridden
        assert config.bootstrap is True

    def test_from_cli_flags_debug_separate(self) -> None:
        """debug flag is controlled separately from verbose."""
        from payment_simulator.experiments.runner import VerboseConfig

        config = VerboseConfig.from_cli_flags(verbose=True, debug=True)
        assert config.debug is True

    def test_any_property_detects_any_enabled(self) -> None:
        """any property returns True if any flag is enabled."""
        from payment_simulator.experiments.runner import VerboseConfig

        config = VerboseConfig()
        assert config.any is False

        config = VerboseConfig(policy=True)
        assert config.any is True

        config = VerboseConfig(debug=True)
        assert config.any is True

    def test_backward_compat_all_alias(self) -> None:
        """all() is alias for all_enabled()."""
        from payment_simulator.experiments.runner import VerboseConfig

        config = VerboseConfig.all()
        assert config.iterations is True

    def test_backward_compat_from_flags_alias(self) -> None:
        """from_flags() is alias for from_cli_flags()."""
        from payment_simulator.experiments.runner import VerboseConfig

        config = VerboseConfig.from_flags(verbose=True)
        assert config.iterations is True


class TestVerboseLoggerImport:
    """Tests for VerboseLogger importability."""

    def test_import_from_experiments_runner(self) -> None:
        """VerboseLogger importable from experiments.runner."""
        from payment_simulator.experiments.runner import VerboseLogger
        assert VerboseLogger is not None


class TestVerboseLogger:
    """Tests for VerboseLogger class."""

    def test_creates_with_config(self) -> None:
        """VerboseLogger creates with VerboseConfig."""
        from payment_simulator.experiments.runner import VerboseConfig, VerboseLogger

        config = VerboseConfig(policy=True)
        logger = VerboseLogger(config)
        assert logger._config.policy is True

    def test_creates_with_custom_console(self) -> None:
        """VerboseLogger accepts custom Console."""
        from payment_simulator.experiments.runner import VerboseConfig, VerboseLogger

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)
        config = VerboseConfig(iterations=True)
        logger = VerboseLogger(config, console=console)

        logger.log_iteration_start(1, 10000)  # 10000 cents = $100.00

        assert "Iteration 1" in output.getvalue()

    def test_log_iteration_start_when_enabled(self) -> None:
        """log_iteration_start outputs when any flag is True."""
        from payment_simulator.experiments.runner import VerboseConfig, VerboseLogger

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)
        config = VerboseConfig(iterations=True)
        logger = VerboseLogger(config, console=console)

        logger.log_iteration_start(1, 10000)

        result = output.getvalue()
        assert "Iteration" in result
        assert "$100.00" in result

    def test_log_iteration_start_silent_when_disabled(self) -> None:
        """log_iteration_start is silent when all flags are False."""
        from payment_simulator.experiments.runner import VerboseConfig, VerboseLogger

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)
        config = VerboseConfig()  # All disabled
        logger = VerboseLogger(config, console=console)

        logger.log_iteration_start(1, 10000)

        assert output.getvalue() == ""

    def test_log_policy_change_when_enabled(self) -> None:
        """log_policy_change outputs when policy flag is True."""
        from payment_simulator.experiments.runner import VerboseConfig, VerboseLogger

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)
        config = VerboseConfig(policy=True)
        logger = VerboseLogger(config, console=console)

        logger.log_policy_change(
            agent_id="BANK_A",
            old_policy={"parameters": {"threshold": 3.0}},
            new_policy={"parameters": {"threshold": 2.0}},
            old_cost=10000,
            new_cost=8000,
            accepted=True,
        )

        result = output.getvalue()
        assert "BANK_A" in result
        assert "ACCEPTED" in result

    def test_log_policy_change_silent_when_disabled(self) -> None:
        """log_policy_change is silent when policy flag is False."""
        from payment_simulator.experiments.runner import VerboseConfig, VerboseLogger

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)
        config = VerboseConfig(policy=False)
        logger = VerboseLogger(config, console=console)

        logger.log_policy_change(
            agent_id="BANK_A",
            old_policy={},
            new_policy={},
            old_cost=10000,
            new_cost=8000,
            accepted=True,
        )

        assert output.getvalue() == ""

    def test_log_debug_methods_when_debug_enabled(self) -> None:
        """Debug methods output when debug flag is True."""
        from payment_simulator.experiments.runner import VerboseConfig, VerboseLogger

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)
        config = VerboseConfig(debug=True)
        logger = VerboseLogger(config, console=console)

        logger.log_debug_llm_request_start("BANK_A", 1)

        assert "BANK_A" in output.getvalue()

    def test_log_debug_methods_silent_when_disabled(self) -> None:
        """Debug methods silent when debug flag is False."""
        from payment_simulator.experiments.runner import VerboseConfig, VerboseLogger

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)
        config = VerboseConfig(debug=False)
        logger = VerboseLogger(config, console=console)

        logger.log_debug_llm_request_start("BANK_A", 1)

        assert output.getvalue() == ""


class TestHelperDataclasses:
    """Tests for helper dataclasses."""

    def test_bootstrap_sample_result_exists(self) -> None:
        """BootstrapSampleResult importable and has required fields."""
        from payment_simulator.experiments.runner.verbose import BootstrapSampleResult

        result = BootstrapSampleResult(
            seed=12345,
            cost=10000,  # Integer cents (INV-1)
            settled=80,
            total=100,
            settlement_rate=0.8,
        )
        assert result.cost == 10000

    def test_bootstrap_sample_result_delta_percent(self) -> None:
        """BootstrapSampleResult.delta_percent calculates correctly."""
        from payment_simulator.experiments.runner.verbose import BootstrapSampleResult

        result = BootstrapSampleResult(
            seed=12345,
            cost=8000,
            settled=80,
            total=100,
            settlement_rate=0.8,
            baseline_cost=10000,
        )
        # (10000 - 8000) / 10000 * 100 = 20%
        assert result.delta_percent == 20.0

    def test_llm_call_metadata_exists(self) -> None:
        """LLMCallMetadata importable and has required fields."""
        from payment_simulator.experiments.runner.verbose import LLMCallMetadata

        metadata = LLMCallMetadata(
            agent_id="BANK_A",
            model="anthropic:claude-sonnet-4-5",
            prompt_tokens=1000,
            completion_tokens=200,
            latency_seconds=2.5,
        )
        assert metadata.model == "anthropic:claude-sonnet-4-5"

    def test_rejection_detail_exists(self) -> None:
        """RejectionDetail importable and has required fields."""
        from payment_simulator.experiments.runner.verbose import RejectionDetail

        detail = RejectionDetail(
            agent_id="BANK_A",
            proposed_policy={"parameters": {"threshold": 25}},
            validation_errors=["threshold must be <= 20"],
        )
        assert detail.agent_id == "BANK_A"


class TestCastroBackwardCompatibility:
    """Tests for Castro backward compatibility (skipped in API env)."""

    @pytest.mark.skip(reason="Castro not in API test environment")
    def test_castro_imports_from_core(self) -> None:
        """Castro verbose_logging imports from core."""
        # This would verify Castro's re-export works
        pass
