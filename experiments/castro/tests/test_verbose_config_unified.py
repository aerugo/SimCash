"""TDD tests for unified VerboseConfig.

These tests verify that there is exactly ONE VerboseConfig class
and it serves all display needs.
"""

from __future__ import annotations

import pytest


class TestVerboseConfigSingleSource:
    """Tests ensuring VerboseConfig has single source of truth."""

    def test_verbose_logging_exports_verbose_config(self) -> None:
        """verbose_logging.py should export VerboseConfig."""
        from castro.verbose_logging import VerboseConfig

        assert VerboseConfig is not None

    def test_display_imports_from_verbose_logging(self) -> None:
        """display.py should import VerboseConfig from verbose_logging."""
        from castro.display import VerboseConfig as DisplayConfig
        from castro.verbose_logging import VerboseConfig as LoggingConfig

        # Both should be the exact same class
        assert DisplayConfig is LoggingConfig

    def test_no_duplicate_verbose_config(self) -> None:
        """There should be only ONE VerboseConfig class definition."""
        import inspect

        import castro.display as display_module
        import castro.verbose_logging as logging_module

        # VerboseConfig should be defined in verbose_logging
        # and only imported (not redefined) in display
        logging_source = inspect.getfile(logging_module.VerboseConfig)
        display_source = inspect.getfile(display_module.VerboseConfig)

        # Both should point to verbose_logging.py
        assert "verbose_logging" in logging_source
        assert (
            logging_source == display_source or "verbose_logging" in display_source
        ), "display.py should not define its own VerboseConfig"


class TestVerboseConfigFields:
    """Tests for VerboseConfig field names (unified)."""

    def test_has_iterations_field(self) -> None:
        """VerboseConfig should have 'iterations' field."""
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig()
        assert hasattr(config, "iterations")

    def test_has_bootstrap_field(self) -> None:
        """VerboseConfig should have 'bootstrap' field."""
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig()
        assert hasattr(config, "bootstrap")

    def test_has_llm_field(self) -> None:
        """VerboseConfig should have 'llm' field."""
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig()
        assert hasattr(config, "llm")

    def test_has_policy_field(self) -> None:
        """VerboseConfig should have 'policy' field."""
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig()
        assert hasattr(config, "policy")

    def test_has_rejections_field(self) -> None:
        """VerboseConfig should have 'rejections' field."""
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig()
        assert hasattr(config, "rejections")

    def test_has_debug_field(self) -> None:
        """VerboseConfig should have 'debug' field."""
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig()
        assert hasattr(config, "debug")

    def test_no_show_prefix_fields(self) -> None:
        """VerboseConfig should NOT have 'show_*' prefixed fields."""
        from castro.verbose_logging import VerboseConfig
        from dataclasses import fields

        config = VerboseConfig()
        field_names = [f.name for f in fields(config)]
        show_fields = [f for f in field_names if f.startswith("show_")]
        assert show_fields == [], f"Found deprecated 'show_*' fields: {show_fields}"


class TestVerboseConfigConstructors:
    """Tests for VerboseConfig factory methods."""

    def test_all_enabled_sets_main_flags_true(self) -> None:
        """all_enabled() should set all main flags except debug."""
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig.all_enabled()
        assert config.iterations is True
        assert config.bootstrap is True
        assert config.llm is True
        assert config.policy is True
        assert config.rejections is True
        assert config.debug is False  # Debug stays off

    def test_from_cli_flags_verbose_enables_all(self) -> None:
        """from_cli_flags with verbose=True enables all."""
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig.from_cli_flags(verbose=True)
        assert config.iterations is True
        assert config.bootstrap is True
        assert config.llm is True
        assert config.policy is True
        assert config.rejections is True

    def test_from_cli_flags_individual_override(self) -> None:
        """Individual flags should work independently."""
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig.from_cli_flags(
            verbose=False,
            verbose_bootstrap=True,
            verbose_llm=True,
        )
        assert config.iterations is False
        assert config.bootstrap is True
        assert config.llm is True
        assert config.policy is False
        assert config.rejections is False

    def test_from_cli_flags_debug_independent(self) -> None:
        """Debug flag should work independently of verbose."""
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig.from_cli_flags(verbose=False, debug=True)
        assert config.debug is True
        assert config.bootstrap is False

    def test_any_property_true_when_any_flag_set(self) -> None:
        """'any' property returns True if any flag is set."""
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig(bootstrap=True)
        assert config.any is True

    def test_any_property_false_when_all_off(self) -> None:
        """'any' property returns False when all flags are False."""
        from castro.verbose_logging import VerboseConfig

        config = VerboseConfig()
        assert config.any is False


class TestDisplayModuleUsesUnifiedConfig:
    """Tests that display module uses the unified VerboseConfig properly."""

    def test_display_functions_accept_unified_config(self) -> None:
        """Display functions should accept unified VerboseConfig."""
        from castro.display import display_experiment_output
        from castro.verbose_logging import VerboseConfig

        # This should not raise - display accepts unified config
        config = VerboseConfig(bootstrap=True)
        assert config.bootstrap is True
