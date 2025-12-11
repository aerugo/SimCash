"""Tests for verbose experiment logging.

TDD tests for the verbose logging feature that shows:
1. Policy parameter changes (--verbose-policy)
2. Bootstrap evaluation details (--verbose-bootstrap)
3. LLM interaction metadata (--verbose-llm)
4. Rejection analysis (--verbose-rejections)

These tests drive the implementation of:
- VerboseConfig: Configuration dataclass for verbose flags
- VerboseLogger: Logger class for structured verbose output
- Integration with ExperimentRunner
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any

import pytest
from rich.console import Console


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


class TestVerboseConfig:
    """Tests for VerboseConfig dataclass."""

    def test_verbose_config_defaults_all_false(self) -> None:
        """Default VerboseConfig has all flags disabled."""
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig()

        assert config.policy is False
        assert config.bootstrap is False
        assert config.llm is False
        assert config.rejections is False

    def test_verbose_config_all_enables_all_flags(self) -> None:
        """VerboseConfig.all() creates config with all flags enabled."""
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig.all()

        assert config.policy is True
        assert config.bootstrap is True
        assert config.llm is True
        assert config.rejections is True

    def test_verbose_config_any_property(self) -> None:
        """VerboseConfig.any returns True if any flag is enabled."""
        from castro.verbose_logging import VerboseConfig

        # No flags
        config = VerboseConfig()
        assert config.any is False

        # One flag
        config = VerboseConfig(policy=True)
        assert config.any is True

        # All flags
        config = VerboseConfig.all()
        assert config.any is True

    def test_verbose_config_from_flags(self) -> None:
        """VerboseConfig.from_flags creates config from CLI flags."""
        from castro.verbose_logging import VerboseConfig

        # All verbose
        config = VerboseConfig.from_flags(verbose=True)
        assert config.policy is True
        assert config.bootstrap is True
        assert config.llm is True
        assert config.rejections is True

        # Specific flags
        config = VerboseConfig.from_flags(
            verbose_policy=True,
            verbose_bootstrap=True,
        )
        assert config.policy is True
        assert config.bootstrap is True
        assert config.llm is False
        assert config.rejections is False

        # verbose=True but specific flag overrides
        config = VerboseConfig.from_flags(
            verbose=True,
            verbose_policy=False,
        )
        # When verbose=True, individual flags control
        # If verbose=True and no individual flags, all are True
        # If verbose=True and some individual flags, use those
        assert config.bootstrap is True
        assert config.llm is True
        assert config.rejections is True


class TestVerboseLogger:
    """Tests for VerboseLogger class."""

    @pytest.fixture
    def string_console(self) -> tuple[Console, io.StringIO]:
        """Create a console that writes to a string buffer."""
        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=True, width=120)
        return console, buffer

    def test_logger_respects_config_flags(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """VerboseLogger only logs when config flag is enabled."""
        from castro.verbose_logging import VerboseConfig, VerboseLogger

        console, buffer = string_console

        # Policy disabled
        config = VerboseConfig(policy=False)
        logger = VerboseLogger(config, console)
        logger.log_policy_change(
            agent_id="BANK_A",
            old_policy={"parameters": {"urgency_threshold": 3.0}},
            new_policy={"parameters": {"urgency_threshold": 2.0}},
            old_cost=1000,
            new_cost=800,
            accepted=True,
        )
        assert buffer.getvalue() == ""

        # Policy enabled
        config = VerboseConfig(policy=True)
        logger = VerboseLogger(config, console)
        logger.log_policy_change(
            agent_id="BANK_A",
            old_policy={"parameters": {"urgency_threshold": 3.0}},
            new_policy={"parameters": {"urgency_threshold": 2.0}},
            old_cost=1000,
            new_cost=800,
            accepted=True,
        )
        output = buffer.getvalue()
        assert "BANK_A" in output
        assert "urgency_threshold" in output


class TestPolicyChangeLogging:
    """Tests for policy change verbose logging."""

    @pytest.fixture
    def string_console(self) -> tuple[Console, io.StringIO]:
        """Create a console that writes to a string buffer."""
        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=True, width=120)
        return console, buffer

    def test_log_policy_change_shows_parameter_diff(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """Policy change log shows before/after parameters with delta."""
        from castro.verbose_logging import VerboseConfig, VerboseLogger

        console, buffer = string_console
        config = VerboseConfig(policy=True)
        logger = VerboseLogger(config, console)

        old_policy = {
            "parameters": {
                "initial_liquidity_fraction": 0.25,
                "urgency_threshold": 3.0,
            }
        }
        new_policy = {
            "parameters": {
                "initial_liquidity_fraction": 0.18,
                "urgency_threshold": 2.0,
            }
        }

        logger.log_policy_change(
            agent_id="BANK_A",
            old_policy=old_policy,
            new_policy=new_policy,
            old_cost=672320,
            new_cost=651322,
            accepted=True,
        )

        output = strip_ansi(buffer.getvalue())

        # Should show agent ID
        assert "BANK_A" in output

        # Should show parameter names
        assert "initial_liquidity_fraction" in output
        assert "urgency_threshold" in output

        # Should show old values
        assert "0.25" in output
        assert "3.0" in output

        # Should show new values
        assert "0.18" in output
        assert "2.0" in output

        # Should show delta/percentage change
        assert "-" in output  # Indicates decrease

        # Should show cost change
        assert "6723.20" in output or "6,723.20" in output
        assert "6513.22" in output or "6,513.22" in output

        # Should show decision
        assert "ACCEPTED" in output or "accepted" in output.lower()

    def test_log_policy_change_shows_rejection(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """Policy change log shows rejection status."""
        from castro.verbose_logging import VerboseConfig, VerboseLogger

        console, buffer = string_console
        config = VerboseConfig(policy=True)
        logger = VerboseLogger(config, console)

        old_policy = {"parameters": {"urgency_threshold": 3.0}}
        new_policy = {"parameters": {"urgency_threshold": 2.5}}

        logger.log_policy_change(
            agent_id="BANK_A",
            old_policy=old_policy,
            new_policy=new_policy,
            old_cost=672320,
            new_cost=700000,
            accepted=False,
        )

        output = buffer.getvalue()
        assert "REJECTED" in output or "rejected" in output.lower()


class TestBootstrapLogging:
    """Tests for bootstrap evaluation details logging."""

    @pytest.fixture
    def string_console(self) -> tuple[Console, io.StringIO]:
        """Create a console that writes to a string buffer."""
        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=True, width=120)
        return console, buffer

    def test_log_bootstrap_shows_per_seed_results(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """Bootstrap log shows individual seed results."""
        from castro.verbose_logging import (
            BootstrapSampleResult,
            VerboseConfig,
            VerboseLogger,
        )

        console, buffer = string_console
        config = VerboseConfig(bootstrap=True)
        logger = VerboseLogger(config, console)

        seed_results = [
            BootstrapSampleResult(
                seed=0x7A3B1234,
                cost=1320000,
                settled=12,
                total=12,
                settlement_rate=1.0,
            ),
            BootstrapSampleResult(
                seed=0x2F1C5678,
                cost=1380000,
                settled=11,
                total=12,
                settlement_rate=11 / 12,
            ),
            BootstrapSampleResult(
                seed=0x8E4D9ABC,
                cost=1340000,
                settled=12,
                total=12,
                settlement_rate=1.0,
            ),
        ]

        logger.log_bootstrap_evaluation(
            seed_results=seed_results,
            mean_cost=1346666,
            std_cost=24944,
        )

        output = buffer.getvalue()

        # Should show "Bootstrap" header
        assert "Bootstrap" in output

        # Should show number of samples
        assert "3" in output

        # Should show seed values (at least partial)
        assert "7a3b" in output.lower() or "0x7a3b" in output.lower()

        # Should show costs
        assert "13200" in output or "13,200" in output

        # Should show settlement rates
        assert "100%" in output or "100.0%" in output

        # Should show mean and std
        assert "Mean" in output or "mean" in output
        assert "std" in output.lower()

    def test_log_bootstrap_identifies_best_worst_seeds(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """Bootstrap log identifies best and worst seeds for debugging.

        Note: Best/Worst are now determined by delta_percent (improvement vs baseline),
        not raw cost. This test provides baseline_cost to enable comparison.
        """
        from castro.verbose_logging import (
            BootstrapSampleResult,
            VerboseConfig,
            VerboseLogger,
        )

        console, buffer = string_console
        config = VerboseConfig(bootstrap=True)
        logger = VerboseLogger(config, console)

        # Provide baseline_cost so Best/Worst are determined by delta
        # Best = highest improvement (10% improvement for 0x7A3B)
        # Worst = lowest improvement (3% improvement for 0x2F1C)
        seed_results = [
            BootstrapSampleResult(
                seed=0x7A3B,
                cost=1320000,
                settled=12,
                total=12,
                settlement_rate=1.0,
                baseline_cost=1466666,  # ~10% improvement
            ),  # Best
            BootstrapSampleResult(
                seed=0x2F1C,
                cost=1380000,
                settled=11,
                total=12,
                settlement_rate=11 / 12,
                baseline_cost=1420000,  # ~3% improvement
            ),  # Worst
            BootstrapSampleResult(
                seed=0x8E4D,
                cost=1340000,
                settled=12,
                total=12,
                settlement_rate=1.0,
                baseline_cost=1440000,  # ~7% improvement
            ),
        ]

        logger.log_bootstrap_evaluation(
            seed_results=seed_results,
            mean_cost=1346666,
            std_cost=24944,
        )

        output = buffer.getvalue()

        # Should identify best seed
        assert "best" in output.lower() or "Best" in output
        # Should identify worst seed
        assert "worst" in output.lower() or "Worst" in output


class TestLLMInteractionLogging:
    """Tests for LLM interaction logging."""

    @pytest.fixture
    def string_console(self) -> tuple[Console, io.StringIO]:
        """Create a console that writes to a string buffer."""
        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=True, width=120)
        return console, buffer

    def test_log_llm_call_shows_metadata(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """LLM interaction log shows model, tokens, latency."""
        from castro.verbose_logging import LLMCallMetadata, VerboseConfig, VerboseLogger

        console, buffer = string_console
        config = VerboseConfig(llm=True)
        logger = VerboseLogger(config, console)

        metadata = LLMCallMetadata(
            agent_id="BANK_A",
            model="gpt-4o",
            prompt_tokens=2847,
            completion_tokens=1203,
            latency_seconds=34.2,
        )

        logger.log_llm_call(metadata)

        output = strip_ansi(buffer.getvalue())

        # Should show agent
        assert "BANK_A" in output

        # Should show model
        assert "gpt-4o" in output

        # Should show token counts
        assert "2847" in output or "2,847" in output
        assert "1203" in output or "1,203" in output

        # Should show latency
        assert "34.2" in output

    def test_log_llm_call_shows_context_summary(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """LLM interaction log shows key context provided."""
        from castro.verbose_logging import LLMCallMetadata, VerboseConfig, VerboseLogger

        console, buffer = string_console
        config = VerboseConfig(llm=True)
        logger = VerboseLogger(config, console)

        metadata = LLMCallMetadata(
            agent_id="BANK_A",
            model="claude-sonnet-4-5-20250929",
            prompt_tokens=2847,
            completion_tokens=1203,
            latency_seconds=12.5,
            context_summary={
                "iteration_history_count": 5,
                "current_cost": 672320,
                "best_seed_cost": 640000,
                "worst_seed_cost": 720000,
            },
        )

        logger.log_llm_call(metadata)

        output = strip_ansi(buffer.getvalue())

        # Should show context details
        assert "5" in output  # iteration history count
        assert "6723.20" in output or "6,723.20" in output  # current cost


class TestRejectionAnalysisLogging:
    """Tests for rejection analysis logging."""

    @pytest.fixture
    def string_console(self) -> tuple[Console, io.StringIO]:
        """Create a console that writes to a string buffer."""
        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=True, width=120)
        return console, buffer

    def test_log_rejection_shows_invalid_parameters(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """Rejection log shows which parameters are invalid."""
        from castro.verbose_logging import (
            RejectionDetail,
            VerboseConfig,
            VerboseLogger,
        )

        console, buffer = string_console
        config = VerboseConfig(rejections=True)
        logger = VerboseLogger(config, console)

        rejection = RejectionDetail(
            agent_id="BANK_B",
            proposed_policy={
                "parameters": {
                    "initial_liquidity_fraction": -0.05,
                    "urgency_threshold": 25,
                }
            },
            validation_errors=[
                "Parameter 'initial_liquidity_fraction' value -0.05 below minimum 0.0",
                "Parameter 'urgency_threshold' value 25 above maximum 20",
            ],
            retry_count=1,
            max_retries=3,
        )

        logger.log_rejection(rejection)

        output = buffer.getvalue()

        # Should show agent
        assert "BANK_B" in output

        # Should show invalid parameter values
        assert "-0.05" in output
        assert "25" in output

        # Should show validation errors
        assert "minimum" in output.lower() or "below" in output.lower()
        assert "maximum" in output.lower() or "above" in output.lower()

        # Should show retry info
        assert "1" in output and "3" in output

    def test_log_rejection_shows_cost_rejection(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """Rejection log shows when policy rejected for not improving cost."""
        from castro.verbose_logging import (
            RejectionDetail,
            VerboseConfig,
            VerboseLogger,
        )

        console, buffer = string_console
        config = VerboseConfig(rejections=True)
        logger = VerboseLogger(config, console)

        rejection = RejectionDetail(
            agent_id="BANK_A",
            proposed_policy={"parameters": {"urgency_threshold": 4.0}},
            validation_errors=[],
            rejection_reason="cost_not_improved",
            old_cost=672320,
            new_cost=700000,
        )

        logger.log_rejection(rejection)

        output = strip_ansi(buffer.getvalue())

        # Should indicate cost didn't improve
        assert "cost" in output.lower()
        assert "6723.20" in output or "6,723.20" in output
        assert "7000.00" in output or "7,000.00" in output


class TestVerboseLoggerIntegration:
    """Integration tests for verbose logging with runner."""

    @pytest.fixture
    def string_console(self) -> tuple[Console, io.StringIO]:
        """Create a console that writes to a string buffer."""
        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=True, width=120)
        return console, buffer

    def test_log_iteration_summary(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """VerboseLogger can log complete iteration summary."""
        from castro.verbose_logging import VerboseConfig, VerboseLogger

        console, buffer = string_console
        config = VerboseConfig.all()
        logger = VerboseLogger(config, console)

        logger.log_iteration_start(iteration=3, total_cost=1346640)

        output = strip_ansi(buffer.getvalue())
        assert "Iteration 3" in output or "iteration 3" in output.lower()
        assert "13466.40" in output or "13,466.40" in output

    def test_logger_no_output_when_disabled(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """VerboseLogger produces no output when all flags disabled."""
        from castro.verbose_logging import (
            BootstrapSampleResult,
            LLMCallMetadata,
            RejectionDetail,
            VerboseConfig,
            VerboseLogger,
        )

        console, buffer = string_console
        config = VerboseConfig()  # All disabled
        logger = VerboseLogger(config, console)

        # Call all logging methods
        logger.log_policy_change(
            agent_id="BANK_A",
            old_policy={},
            new_policy={},
            old_cost=1000,
            new_cost=900,
            accepted=True,
        )
        logger.log_bootstrap_evaluation(
            seed_results=[
                BootstrapSampleResult(seed=1, cost=1000, settled=10, total=10, settlement_rate=1.0)
            ],
            mean_cost=1000,
            std_cost=0,
        )
        logger.log_llm_call(
            LLMCallMetadata(
                agent_id="BANK_A",
                model="test",
                prompt_tokens=100,
                completion_tokens=50,
                latency_seconds=1.0,
            )
        )
        logger.log_rejection(
            RejectionDetail(
                agent_id="BANK_A",
                proposed_policy={},
                validation_errors=["test"],
            )
        )

        # Should produce no output
        assert buffer.getvalue() == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
