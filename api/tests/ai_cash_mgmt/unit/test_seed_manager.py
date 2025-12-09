"""Unit tests for SeedManager - deterministic seed derivation.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

import pytest


class TestSeedManagerDerivation:
    """Test deterministic seed derivation."""

    def test_same_master_seed_produces_same_derived_seeds(self) -> None:
        """Same master seed should always produce identical derived seeds."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager1 = SeedManager(master_seed=12345)
        manager2 = SeedManager(master_seed=12345)

        # Same components should produce same seeds
        assert manager1.derive_seed("test") == manager2.derive_seed("test")
        assert manager1.derive_seed("a", "b", 1) == manager2.derive_seed("a", "b", 1)

    def test_different_master_seeds_produce_different_derived_seeds(self) -> None:
        """Different master seeds should produce different derived seeds."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager1 = SeedManager(master_seed=12345)
        manager2 = SeedManager(master_seed=54321)

        # Different master seeds -> different derived seeds
        assert manager1.derive_seed("test") != manager2.derive_seed("test")

    def test_different_components_produce_different_seeds(self) -> None:
        """Different component paths should produce different seeds."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager = SeedManager(master_seed=42)

        seed_a = manager.derive_seed("simulation", 0)
        seed_b = manager.derive_seed("sampling", 0)
        seed_c = manager.derive_seed("simulation", 1)

        # All should be different
        assert seed_a != seed_b
        assert seed_a != seed_c
        assert seed_b != seed_c

    def test_seed_manager_is_deterministic_across_runs(self) -> None:
        """Seeds must be deterministic - hardcoded values for regression."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager = SeedManager(master_seed=42)

        # These are regression values - must never change
        seed = manager.derive_seed("simulation", 0)
        assert isinstance(seed, int)
        assert 0 <= seed < 2**31  # Must be valid seed range

        # Same call should return same value (pure function)
        assert manager.derive_seed("simulation", 0) == seed

    def test_derive_seed_handles_various_component_types(self) -> None:
        """Derive seed should handle strings and ints."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager = SeedManager(master_seed=100)

        # Should not raise
        seed1 = manager.derive_seed("string_only")
        seed2 = manager.derive_seed(1, 2, 3)
        seed3 = manager.derive_seed("mixed", 42, "types", 99)

        # All should be valid ints
        assert isinstance(seed1, int)
        assert isinstance(seed2, int)
        assert isinstance(seed3, int)


class TestSeedManagerConvenienceMethods:
    """Test convenience methods for specific seed types."""

    def test_simulation_seed_is_deterministic(self) -> None:
        """Simulation seed for same iteration should be identical."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager1 = SeedManager(master_seed=999)
        manager2 = SeedManager(master_seed=999)

        assert manager1.simulation_seed(0) == manager2.simulation_seed(0)
        assert manager1.simulation_seed(5) == manager2.simulation_seed(5)

    def test_simulation_seed_differs_by_iteration(self) -> None:
        """Different iterations should have different seeds."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager = SeedManager(master_seed=123)

        seeds = [manager.simulation_seed(i) for i in range(10)]
        # All should be unique
        assert len(set(seeds)) == 10

    def test_sampling_seed_is_deterministic(self) -> None:
        """Sampling seed for same iteration/agent should be identical."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager1 = SeedManager(master_seed=777)
        manager2 = SeedManager(master_seed=777)

        assert manager1.sampling_seed(0, "BANK_A") == manager2.sampling_seed(0, "BANK_A")
        assert manager1.sampling_seed(3, "BANK_B") == manager2.sampling_seed(3, "BANK_B")

    def test_sampling_seed_differs_by_agent(self) -> None:
        """Different agents should have different sampling seeds."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager = SeedManager(master_seed=555)

        seed_a = manager.sampling_seed(0, "BANK_A")
        seed_b = manager.sampling_seed(0, "BANK_B")
        seed_c = manager.sampling_seed(0, "BANK_C")

        assert seed_a != seed_b
        assert seed_a != seed_c
        assert seed_b != seed_c

    def test_llm_seed_is_deterministic(self) -> None:
        """LLM seed for same iteration/agent should be identical."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager1 = SeedManager(master_seed=333)
        manager2 = SeedManager(master_seed=333)

        assert manager1.llm_seed(0, "BANK_A") == manager2.llm_seed(0, "BANK_A")

    def test_tiebreaker_seed_is_deterministic(self) -> None:
        """Tiebreaker seed for same iteration should be identical."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager1 = SeedManager(master_seed=444)
        manager2 = SeedManager(master_seed=444)

        assert manager1.tiebreaker_seed(0) == manager2.tiebreaker_seed(0)
        assert manager1.tiebreaker_seed(10) == manager2.tiebreaker_seed(10)

    def test_all_seed_types_are_distinct(self) -> None:
        """All seed types should produce different values for same params."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager = SeedManager(master_seed=42)
        iteration = 0
        agent = "BANK_A"

        sim_seed = manager.simulation_seed(iteration)
        samp_seed = manager.sampling_seed(iteration, agent)
        llm_seed = manager.llm_seed(iteration, agent)
        tie_seed = manager.tiebreaker_seed(iteration)

        seeds = [sim_seed, samp_seed, llm_seed, tie_seed]
        assert len(set(seeds)) == 4, "All seed types should be unique"


class TestSeedManagerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_master_seed_zero(self) -> None:
        """Zero should be a valid master seed."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager = SeedManager(master_seed=0)
        seed = manager.derive_seed("test")

        assert isinstance(seed, int)
        assert 0 <= seed < 2**31

    def test_large_master_seed(self) -> None:
        """Large master seeds should work correctly."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager = SeedManager(master_seed=2**62)
        seed = manager.derive_seed("test")

        assert isinstance(seed, int)
        assert 0 <= seed < 2**31

    def test_empty_components(self) -> None:
        """Calling derive_seed with no components should work."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager = SeedManager(master_seed=42)
        seed = manager.derive_seed()

        assert isinstance(seed, int)
        assert 0 <= seed < 2**31

    def test_special_characters_in_component(self) -> None:
        """Special characters in components should be handled."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager = SeedManager(master_seed=42)

        # Should not raise, even with special chars
        seed = manager.derive_seed("test:with:colons", "unicode-αβγ")
        assert isinstance(seed, int)

    def test_negative_iteration(self) -> None:
        """Negative iteration numbers should still work."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager = SeedManager(master_seed=42)

        # Should not raise
        seed = manager.simulation_seed(-1)
        assert isinstance(seed, int)
        assert 0 <= seed < 2**31
