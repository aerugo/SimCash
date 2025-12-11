# Phase 14: Verbose Logging, Audit Display, and CLI Integration to Core

**Status:** PLANNED
**Created:** 2025-12-11
**Prerequisites:** Phase 13 (Complete StateProvider Migration)

---

## Goal

Complete the extraction of reusable experiment infrastructure from Castro to core SimCash modules:
1. Move `VerboseConfig` and `VerboseLogger` to `experiments/runner/verbose.py`
2. Move `display_experiment_output()` to `experiments/runner/display.py`
3. Move `display_audit_output()` to `experiments/runner/audit.py`
4. Create generic experiment CLI in `experiments/cli/`
5. Update Castro to be a thin wrapper using core infrastructure
6. Delete redundant Castro files

---

## Background: Why Move to Core?

Currently, Castro contains significant infrastructure that should be generic:

| Component | Lines | Why Generic |
|-----------|-------|-------------|
| `VerboseConfig` | ~80 | Any experiment needs verbose output control |
| `VerboseLogger` | ~350 | Any experiment needs structured logging |
| `display_experiment_output()` | ~200 | Works with any StateProvider |
| `display_audit_output()` | ~200 | Works with any LLM experiment |
| CLI commands | ~500 | Generic run/replay/results work for any experiment |

After Phase 14, Castro becomes ~1200 lines lighter and truly experiment-specific.

---

## Tasks

### Task 14.1: Move VerboseConfig and VerboseLogger to Core

**Goal:** Move verbose logging infrastructure to core `experiments/runner/verbose.py`

**TDD Tests First:**
```python
# api/tests/experiments/runner/test_verbose_core.py
"""Tests for core verbose logging infrastructure."""

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
        console = Console(file=output, force_terminal=True)
        config = VerboseConfig(iterations=True)
        logger = VerboseLogger(config, console=console)

        logger.log_iteration_start(1, 10000)  # 10000 cents = $100.00

        assert "Iteration 1" in output.getvalue()

    def test_log_iteration_start_when_enabled(self) -> None:
        """log_iteration_start outputs when any flag is True."""
        from payment_simulator.experiments.runner import VerboseConfig, VerboseLogger

        output = StringIO()
        console = Console(file=output, force_terminal=True)
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
        console = Console(file=output, force_terminal=True)
        config = VerboseConfig()  # All disabled
        logger = VerboseLogger(config, console=console)

        logger.log_iteration_start(1, 10000)

        assert output.getvalue() == ""

    def test_log_policy_change_when_enabled(self) -> None:
        """log_policy_change outputs when policy flag is True."""
        from payment_simulator.experiments.runner import VerboseConfig, VerboseLogger

        output = StringIO()
        console = Console(file=output, force_terminal=True)
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
        console = Console(file=output, force_terminal=True)
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
        console = Console(file=output, force_terminal=True)
        config = VerboseConfig(debug=True)
        logger = VerboseLogger(config, console=console)

        logger.log_debug_llm_request_start("BANK_A", 1)

        assert "BANK_A" in output.getvalue()

    def test_log_debug_methods_silent_when_disabled(self) -> None:
        """Debug methods silent when debug flag is False."""
        from payment_simulator.experiments.runner import VerboseConfig, VerboseLogger

        output = StringIO()
        console = Console(file=output, force_terminal=True)
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
```

**Steps:**
1. Write TDD tests → Run tests → FAIL (24+ tests)
2. Create `api/payment_simulator/experiments/runner/verbose.py`
   - Copy `VerboseConfig` from Castro
   - Copy `VerboseLogger` from Castro
   - Copy helper dataclasses (`BootstrapSampleResult`, `LLMCallMetadata`, `RejectionDetail`)
3. Update `api/payment_simulator/experiments/runner/__init__.py`:
   ```python
   from payment_simulator.experiments.runner.verbose import (
       VerboseConfig,
       VerboseLogger,
       BootstrapSampleResult,
       LLMCallMetadata,
       RejectionDetail,
   )
   ```
4. Run tests → PASS
5. Update Castro `verbose_logging.py` to re-export from core (Phase 14.6)

---

### Task 14.2: Move display_experiment_output() to Core

**Goal:** Move display function to core `experiments/runner/display.py`

**TDD Tests First:**
```python
# api/tests/experiments/runner/test_display_core.py
"""Tests for core experiment display functions."""

from __future__ import annotations

import pytest
from io import StringIO
from rich.console import Console


class TestDisplayImport:
    """Tests for display function importability."""

    def test_import_from_experiments_runner(self) -> None:
        """display_experiment_output importable from experiments.runner."""
        from payment_simulator.experiments.runner import display_experiment_output
        assert display_experiment_output is not None

    def test_import_from_display_module(self) -> None:
        """display_experiment_output importable from display module."""
        from payment_simulator.experiments.runner.display import display_experiment_output
        assert display_experiment_output is not None


class TestDisplayExperimentOutput:
    """Tests for display_experiment_output function."""

    def test_displays_header_with_run_id(self) -> None:
        """Display includes run ID in header."""
        from payment_simulator.experiments.runner import (
            LiveStateProvider,
            display_experiment_output,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            run_id="exp1-123",
        )
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        display_experiment_output(provider, console)

        assert "exp1-123" in output.getvalue()

    def test_displays_experiment_name(self) -> None:
        """Display includes experiment name in header."""
        from payment_simulator.experiments.runner import (
            LiveStateProvider,
            display_experiment_output,
        )

        provider = LiveStateProvider(
            experiment_name="my_experiment",
            experiment_type="castro",
            config={},
            run_id="run-123",
        )
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        display_experiment_output(provider, console)

        assert "my_experiment" in output.getvalue()

    def test_displays_events_from_provider(self) -> None:
        """Display iterates over events from provider."""
        from payment_simulator.experiments.runner import (
            LiveStateProvider,
            VerboseConfig,
            display_experiment_output,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            run_id="exp1-123",
        )
        provider.record_event(0, "experiment_start", {"experiment_name": "exp1"})

        output = StringIO()
        console = Console(file=output, force_terminal=True)
        config = VerboseConfig.all_enabled()

        display_experiment_output(provider, console, config)

        assert "exp1" in output.getvalue()

    def test_respects_verbose_config_iterations(self) -> None:
        """Display respects VerboseConfig.iterations setting."""
        from payment_simulator.experiments.runner import (
            LiveStateProvider,
            VerboseConfig,
            display_experiment_output,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            run_id="exp1-123",
        )
        provider.record_event(0, "iteration_start", {"iteration": 1, "total_cost": 10000})

        # With iterations=True
        output1 = StringIO()
        console1 = Console(file=output1, force_terminal=True)
        config1 = VerboseConfig(iterations=True)
        display_experiment_output(provider, console1, config1)
        assert "Iteration" in output1.getvalue()

        # Reset provider position
        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            run_id="exp1-123",
        )
        provider.record_event(0, "iteration_start", {"iteration": 1, "total_cost": 10000})

        # With iterations=False
        output2 = StringIO()
        console2 = Console(file=output2, force_terminal=True)
        config2 = VerboseConfig(iterations=False)
        display_experiment_output(provider, console2, config2)
        # May still show header, but not iteration details
        # (depends on implementation)

    def test_displays_final_results(self) -> None:
        """Display shows final results from provider."""
        from payment_simulator.experiments.runner import (
            LiveStateProvider,
            display_experiment_output,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            run_id="exp1-123",
        )
        provider.set_final_result(
            final_cost=15000,
            best_cost=14000,
            converged=True,
            convergence_reason="stability",
        )

        output = StringIO()
        console = Console(file=output, force_terminal=True)

        display_experiment_output(provider, console)

        result = output.getvalue()
        assert "Complete" in result or "Final" in result


class TestEventDisplayFunctions:
    """Tests for individual event display functions."""

    def test_display_iteration_start(self) -> None:
        """display_iteration_start shows iteration info."""
        from payment_simulator.experiments.runner.display import display_iteration_start

        output = StringIO()
        console = Console(file=output, force_terminal=True)

        display_iteration_start(
            {"iteration": 5, "total_cost": 25000},
            console,
        )

        result = output.getvalue()
        assert "5" in result
        assert "$250.00" in result

    def test_display_policy_change(self) -> None:
        """display_policy_change shows policy comparison."""
        from payment_simulator.experiments.runner.display import display_policy_change

        output = StringIO()
        console = Console(file=output, force_terminal=True)

        display_policy_change(
            {
                "agent_id": "BANK_A",
                "old_cost": 10000,
                "new_cost": 8000,
                "accepted": True,
                "old_policy": {"parameters": {"threshold": 3}},
                "new_policy": {"parameters": {"threshold": 2}},
            },
            console,
        )

        result = output.getvalue()
        assert "BANK_A" in result
        assert "$100.00" in result  # old_cost
        assert "$80.00" in result   # new_cost


class TestFormatCost:
    """Tests for cost formatting helper."""

    def test_format_cost_integer_cents(self) -> None:
        """_format_cost formats integer cents correctly."""
        from payment_simulator.experiments.runner.display import _format_cost

        assert _format_cost(10000) == "$100.00"
        assert _format_cost(12345) == "$123.45"
        assert _format_cost(0) == "$0.00"

    def test_format_cost_large_amounts(self) -> None:
        """_format_cost handles large amounts with commas."""
        from payment_simulator.experiments.runner.display import _format_cost

        assert _format_cost(100000000) == "$1,000,000.00"
```

**Steps:**
1. Write TDD tests → Run tests → FAIL (15+ tests)
2. Create `api/payment_simulator/experiments/runner/display.py`
   - Copy `display_experiment_output()` from Castro
   - Copy individual event display functions
   - Copy `_format_cost()` helper
   - Update imports to use core `VerboseConfig`
3. Update `api/payment_simulator/experiments/runner/__init__.py`
4. Run tests → PASS

---

### Task 14.3: Move display_audit_output() to Core

**Goal:** Move audit display to core `experiments/runner/audit.py`

**TDD Tests First:**
```python
# api/tests/experiments/runner/test_audit_core.py
"""Tests for core audit display functions."""

from __future__ import annotations

import pytest
from io import StringIO
from rich.console import Console


class TestAuditImport:
    """Tests for audit display importability."""

    def test_import_from_experiments_runner(self) -> None:
        """display_audit_output importable from experiments.runner."""
        from payment_simulator.experiments.runner import display_audit_output
        assert display_audit_output is not None


class TestDisplayAuditOutput:
    """Tests for display_audit_output function."""

    def test_displays_audit_header(self, tmp_path) -> None:
        """Audit display shows audit header."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        from payment_simulator.experiments.runner import display_audit_output

        # Create test database with experiment
        repo = ExperimentRepository(tmp_path / "test.db")
        from payment_simulator.experiments.persistence import ExperimentRecord
        from datetime import datetime

        record = ExperimentRecord(
            run_id="test-run-123",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at=datetime.now().isoformat(),
        )
        repo.save_experiment(record)

        provider = repo.as_state_provider("test-run-123")
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        display_audit_output(provider, console)

        result = output.getvalue()
        assert "AUDIT" in result or "test-run-123" in result

    def test_filters_to_llm_interaction_events(self, tmp_path) -> None:
        """Audit display filters to llm_interaction events."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        from payment_simulator.experiments.runner import display_audit_output

        repo = ExperimentRepository(tmp_path / "test.db")
        from payment_simulator.experiments.persistence import ExperimentRecord, EventRecord
        from datetime import datetime

        record = ExperimentRecord(
            run_id="test-run-123",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at=datetime.now().isoformat(),
        )
        repo.save_experiment(record)

        # Save an LLM interaction event
        event = EventRecord(
            run_id="test-run-123",
            iteration=1,
            event_type="llm_interaction",
            event_data={
                "agent_id": "BANK_A",
                "system_prompt": "You are an expert...",
                "user_prompt": "Optimize this policy...",
                "raw_response": '{"parameters": {}}',
            },
            timestamp=datetime.now().isoformat(),
        )
        repo.save_event(event)

        provider = repo.as_state_provider("test-run-123")
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        display_audit_output(provider, console)

        result = output.getvalue()
        assert "BANK_A" in result

    def test_respects_iteration_range(self, tmp_path) -> None:
        """Audit display respects start_iteration and end_iteration."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        from payment_simulator.experiments.runner import display_audit_output

        repo = ExperimentRepository(tmp_path / "test.db")
        from payment_simulator.experiments.persistence import ExperimentRecord, EventRecord
        from datetime import datetime

        record = ExperimentRecord(
            run_id="test-run-123",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at=datetime.now().isoformat(),
        )
        repo.save_experiment(record)

        # Save events for multiple iterations
        for i in [1, 2, 3]:
            event = EventRecord(
                run_id="test-run-123",
                iteration=i,
                event_type="llm_interaction",
                event_data={"agent_id": f"BANK_{i}", "iteration": i},
                timestamp=datetime.now().isoformat(),
            )
            repo.save_event(event)

        provider = repo.as_state_provider("test-run-123")
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        # Only show iteration 2
        display_audit_output(provider, console, start_iteration=2, end_iteration=2)

        result = output.getvalue()
        # Should show iteration 2, but not 1 or 3
        assert "BANK_2" in result or "Iteration 2" in result
```

**Steps:**
1. Write TDD tests → Run tests → FAIL (10+ tests)
2. Create `api/payment_simulator/experiments/runner/audit.py`
   - Copy `display_audit_output()` from Castro
   - Copy helper functions
   - Update imports to use core types
3. Update `api/payment_simulator/experiments/runner/__init__.py`
4. Run tests → PASS
5. Delete Castro `audit_display.py`

---

### Task 14.4: Create Generic Experiment CLI in Core

**Goal:** Create generic CLI commands in `experiments/cli/`

**TDD Tests First:**
```python
# api/tests/experiments/cli/test_cli_core.py
"""Tests for core experiment CLI commands."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner


class TestExperimentAppImport:
    """Tests for experiment app importability."""

    def test_import_experiment_app(self) -> None:
        """experiment_app importable from experiments.cli."""
        from payment_simulator.experiments.cli import experiment_app
        assert experiment_app is not None


class TestRunCommand:
    """Tests for experiment run command."""

    def test_run_command_exists(self) -> None:
        """run command exists in experiment_app."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", "--help"])
        assert result.exit_code == 0
        assert "config" in result.output.lower() or "path" in result.output.lower()

    def test_run_requires_config_path(self) -> None:
        """run command requires config path argument."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run"])
        assert result.exit_code != 0  # Should fail without argument

    def test_run_has_model_option(self) -> None:
        """run command has --model option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", "--help"])
        assert "--model" in result.output

    def test_run_has_verbose_options(self) -> None:
        """run command has verbose options."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", "--help"])
        assert "--verbose" in result.output


class TestReplayCommand:
    """Tests for experiment replay command."""

    def test_replay_command_exists(self) -> None:
        """replay command exists in experiment_app."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["replay", "--help"])
        assert result.exit_code == 0

    def test_replay_requires_run_id(self) -> None:
        """replay command requires run_id argument."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["replay"])
        assert result.exit_code != 0  # Should fail without argument

    def test_replay_has_audit_option(self) -> None:
        """replay command has --audit option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["replay", "--help"])
        assert "--audit" in result.output

    def test_replay_has_db_option(self) -> None:
        """replay command has --db option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["replay", "--help"])
        assert "--db" in result.output


class TestResultsCommand:
    """Tests for experiment results command."""

    def test_results_command_exists(self) -> None:
        """results command exists in experiment_app."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["results", "--help"])
        assert result.exit_code == 0

    def test_results_has_db_option(self) -> None:
        """results command has --db option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["results", "--help"])
        assert "--db" in result.output

    def test_results_lists_experiments(self, tmp_path) -> None:
        """results command lists experiments from database."""
        from payment_simulator.experiments.cli import experiment_app
        from payment_simulator.experiments.persistence import ExperimentRepository, ExperimentRecord
        from datetime import datetime

        # Create test database with experiment
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)
        record = ExperimentRecord(
            run_id="test-run-123",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at=datetime.now().isoformat(),
        )
        repo.save_experiment(record)

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["results", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "test-run-123" in result.output or "exp1" in result.output
```

**Steps:**
1. Write TDD tests → Run tests → FAIL (25+ tests)
2. Create `api/payment_simulator/experiments/cli/` package:
   - `__init__.py` - exports `experiment_app`
   - `run.py` - run command
   - `replay.py` - replay command
   - `results.py` - results listing
   - `common.py` - shared utilities (verbose flag building, etc.)
3. Implement generic commands that work with any experiment type
4. Run tests → PASS

---

### Task 14.5: Update Castro CLI to Use Core

**Goal:** Castro CLI becomes thin wrapper using core

**TDD Tests First:**
```python
# experiments/castro/tests/test_cli_uses_core.py
"""Tests for Castro CLI using core infrastructure."""

from __future__ import annotations

from pathlib import Path
import pytest


def _get_cli_source() -> str:
    cli_path = Path(__file__).parent.parent / "cli.py"
    return cli_path.read_text()


class TestCLIImportsCore:
    """Tests for Castro CLI importing from core."""

    def test_cli_imports_verbose_config_from_core(self) -> None:
        """CLI imports VerboseConfig from core."""
        source = _get_cli_source()
        # Should import from core, not castro.verbose_logging
        assert "from payment_simulator.experiments.runner" in source
        assert "VerboseConfig" in source

    def test_cli_imports_display_from_core(self) -> None:
        """CLI imports display functions from core."""
        source = _get_cli_source()
        assert "from payment_simulator.experiments.runner" in source

    def test_cli_does_not_import_castro_verbose_logging(self) -> None:
        """CLI does not import from castro.verbose_logging directly."""
        source = _get_cli_source()
        # Should not have direct import from castro.verbose_logging
        # (may have re-export, but not direct use)
        assert "from castro.verbose_logging import VerboseLogger" not in source


class TestCLICastroDefaults:
    """Tests for Castro-specific CLI defaults."""

    def test_cli_has_default_model(self) -> None:
        """CLI has Castro-specific DEFAULT_MODEL."""
        source = _get_cli_source()
        assert "DEFAULT_MODEL" in source
        assert "anthropic:" in source  # Castro default is Anthropic

    def test_cli_has_castro_experiments_dir(self) -> None:
        """CLI references Castro experiments directory."""
        source = _get_cli_source()
        assert "experiments" in source.lower()
```

**Steps:**
1. Write TDD tests → Run tests → FAIL
2. Update Castro `cli.py`:
   - Import `VerboseConfig` from core instead of `castro.verbose_logging`
   - Import display functions from core
   - Keep Castro-specific defaults (DEFAULT_MODEL, experiments directory)
   - Reduce to ~100 lines (from ~500)
3. Run tests → PASS

---

### Task 14.6: Update Castro Runner to Import from Core

**Goal:** Runner uses core verbose/display imports

**TDD Tests First:**
```python
# experiments/castro/tests/test_runner_uses_core_verbose.py
"""Tests for runner using core verbose infrastructure."""

from __future__ import annotations

from pathlib import Path


def _get_runner_source() -> str:
    runner_path = Path(__file__).parent.parent / "castro" / "runner.py"
    return runner_path.read_text()


class TestRunnerImportsCore:
    """Tests for runner importing from core."""

    def test_runner_imports_verbose_config_from_core(self) -> None:
        """Runner imports VerboseConfig from core."""
        source = _get_runner_source()
        # Should import from core
        assert "from payment_simulator.experiments.runner" in source
        # Or via castro re-export (also acceptable)

    def test_runner_does_not_import_castro_verbose_logging_directly(self) -> None:
        """Runner doesn't import VerboseLogger from castro directly."""
        source = _get_runner_source()
        # Should not have: from castro.verbose_logging import VerboseLogger
        assert "from castro.verbose_logging import VerboseLogger" not in source
```

**Steps:**
1. Write TDD tests → Run tests → FAIL
2. Update `runner.py` imports to use core `VerboseConfig` and `VerboseLogger`
3. Run tests → PASS

---

### Task 14.7: Delete Redundant Castro Files

**Goal:** Delete files now provided by core

**TDD Tests First:**
```python
# experiments/castro/tests/test_castro_verbose_deleted.py
"""Tests for deleted Castro files."""

from __future__ import annotations

from pathlib import Path


class TestFilesDeleted:
    """Tests for deleted files."""

    def test_verbose_logging_deleted(self) -> None:
        """castro/verbose_logging.py should be deleted."""
        path = Path(__file__).parent.parent / "castro" / "verbose_logging.py"
        assert not path.exists(), "verbose_logging.py should be deleted"

    def test_audit_display_deleted(self) -> None:
        """castro/audit_display.py should be deleted."""
        path = Path(__file__).parent.parent / "castro" / "audit_display.py"
        assert not path.exists(), "audit_display.py should be deleted"


class TestDisplayIsThinWrapper:
    """Tests for display.py being thin re-export."""

    def test_display_is_small(self) -> None:
        """display.py should be small (thin re-export)."""
        path = Path(__file__).parent.parent / "castro" / "display.py"
        if path.exists():
            content = path.read_text()
            line_count = len(content.splitlines())
            assert line_count < 50, f"display.py should be <50 lines, got {line_count}"

    def test_display_reexports_from_core(self) -> None:
        """display.py re-exports from core."""
        path = Path(__file__).parent.parent / "castro" / "display.py"
        if path.exists():
            content = path.read_text()
            assert "from payment_simulator.experiments.runner" in content
```

**Steps:**
1. Write TDD tests → Run tests → FAIL
2. Delete `castro/verbose_logging.py`
3. Delete `castro/audit_display.py`
4. Update `castro/display.py` to be thin re-export:
   ```python
   """Display functions for Castro experiments.

   Re-exports from core for backward compatibility.
   """
   from payment_simulator.experiments.runner import (
       VerboseConfig,
       display_experiment_output,
   )

   __all__ = ["VerboseConfig", "display_experiment_output"]
   ```
5. Run tests → PASS

---

### Task 14.8: Update Documentation

**Goal:** Document new core modules

**Files to Create:**
- `docs/reference/experiments/verbose.md` - verbose logging reference
- `docs/reference/experiments/display.md` - display functions reference
- `docs/reference/experiments/cli.md` - CLI commands reference

**Files to Update:**
- `docs/reference/experiments/index.md` - add new modules
- `docs/reference/castro/index.md` - note Castro uses core infrastructure

---

## Execution Order

```
Task 14.1: Move VerboseConfig/VerboseLogger
    ├── Write tests
    ├── Run tests → FAIL
    ├── Create verbose.py
    └── Run tests → PASS

Task 14.2: Move display_experiment_output()
    ├── Write tests
    ├── Run tests → FAIL
    ├── Create display.py
    └── Run tests → PASS

Task 14.3: Move display_audit_output()
    ├── Write tests
    ├── Run tests → FAIL
    ├── Create audit.py
    └── Run tests → PASS

Task 14.4: Create Generic CLI
    ├── Write tests
    ├── Run tests → FAIL
    ├── Create experiments/cli/ package
    └── Run tests → PASS

Task 14.5: Update Castro CLI
    ├── Write tests
    ├── Run tests → FAIL
    ├── Update cli.py
    └── Run tests → PASS

Task 14.6: Update Castro Runner
    ├── Write tests
    ├── Run tests → FAIL
    ├── Update runner.py imports
    └── Run tests → PASS

Task 14.7: Delete Redundant Files
    ├── Write tests
    ├── Run tests → FAIL
    ├── Delete files
    └── Run tests → PASS

Task 14.8: Update Documentation
    └── Create/update docs
```

---

## Invariants to Maintain

### INV-1: Integer Cents
All costs in verbose output must be integer cents:
```python
def log_iteration_start(self, iteration: int, total_cost: int) -> None:
    # total_cost is integer cents, format as dollars for display
    cost_str = f"${total_cost / 100:,.2f}"
```

### Replay Identity
Run and replay must produce identical output via shared display code:
```bash
castro run exp1 --verbose > run.txt
castro replay run-id --verbose > replay.txt
diff <(grep -v "Duration:" run.txt) <(grep -v "Duration:" replay.txt)
# Must be empty
```

### Python Code Quality
All new code must:
- Have complete type annotations
- Pass mypy strict mode
- Use modern syntax (`str | None` not `Optional[str]`)

---

## Expected Outcomes

| Category | Before | After | Delta |
|----------|--------|-------|-------|
| Core experiments/runner | ~830 | ~1480 | +650 |
| Core experiments/cli | 0 | ~500 | +500 |
| Castro verbose_logging.py | ~430 | 0 | -430 |
| Castro display.py | ~200 | ~30 | -170 |
| Castro audit_display.py | ~200 | 0 | -200 |
| Castro cli.py | ~500 | ~100 | -400 |
| **Net Core Addition** | | | **+1150** |
| **Net Castro Reduction** | | | **-1200** |

---

## Test Coverage Targets

| Test File | Target Tests | Target Coverage |
|-----------|--------------|-----------------|
| test_verbose_core.py | ~24 | 90% |
| test_display_core.py | ~15 | 85% |
| test_audit_core.py | ~10 | 85% |
| test_cli_core.py | ~25 | 85% |
| **Total New Tests** | **~74** | |

---

## Verification Checklist

- [ ] All API tests pass: `cd api && .venv/bin/python -m pytest`
- [ ] All Castro tests pass: `cd experiments/castro && uv run pytest tests/`
- [ ] Type checking passes: `cd api && .venv/bin/python -m mypy payment_simulator/experiments/`
- [ ] Castro CLI still works: `castro run exp1 --max-iter 1 --dry-run`
- [ ] Castro replay works: `castro replay <run_id> --verbose`
- [ ] Castro audit works: `castro replay <run_id> --audit`
- [ ] Replay identity preserved: run and replay produce identical output
- [ ] Documentation complete and accurate

---

*Phase 14 Plan v1.0 - 2025-12-11*
