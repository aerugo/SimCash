"""Tests for Rust FFI seed propagation.

Phase 0 of bootstrap-seed-fix implementation.

These tests verify that different seeds passed to the Rust simulation
actually produce different stochastic arrivals. This is a prerequisite
for the bootstrap seed hierarchy to work correctly.

INV-2: Determinism is Sacred - Same seed must produce identical results.
"""

from __future__ import annotations

import pytest

from payment_simulator._core import Orchestrator


class TestRustFFISeedPropagation:
    """Verify seeds affect stochastic arrivals in Rust simulation."""

    @pytest.fixture
    def stochastic_config(self) -> dict:
        """Create a config with stochastic arrivals enabled.

        Uses Poisson arrivals to generate random transactions.
        """
        return {
            "ticks_per_day": 10,
            "num_days": 1,
            "rng_seed": 42,  # Will be overridden in tests
            "cost_config": {
                "delay_cost_rate": 1,
                "deadline_penalty": 100,
                "overdue_delay_multiplier": 5.0,
                "eod_penalty": 1000,
                "overdraft_cost_bps": 50,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1000000,
                    "unsecured_cap": 500000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 2.0,  # Poisson arrivals
                        "amount_distribution": {
                            "type": "Uniform",
                            "min": 1000,
                            "max": 10000,
                        },
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [5, 10],
                        "priority": 5,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1000000,
                    "unsecured_cap": 500000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 2.0,
                        "amount_distribution": {
                            "type": "Uniform",
                            "min": 1000,
                            "max": 10000,
                        },
                        "counterparty_weights": {"BANK_A": 1.0},
                        "deadline_range": [5, 10],
                        "priority": 5,
                    },
                },
            ],
        }

    def _run_simulation_and_collect_arrivals(
        self, config: dict, seed: int
    ) -> list[dict]:
        """Run simulation with given seed and collect arrival events.

        Args:
            config: Simulation configuration.
            seed: RNG seed to use.

        Returns:
            List of TransactionArrival events.
        """
        config["rng_seed"] = seed
        orch = Orchestrator.new(config)

        # Run for all ticks
        ticks = config["ticks_per_day"]
        for _ in range(ticks):
            orch.tick()

        # Collect all events and filter for arrivals
        all_events = orch.get_all_events()
        arrivals = [
            e for e in all_events
            if e.get("event_type") == "Arrival"
        ]
        return arrivals

    def test_different_seeds_produce_different_arrival_events(
        self, stochastic_config: dict
    ) -> None:
        """Different seeds must produce different stochastic arrivals.

        This is the critical test - if this fails, the Rust FFI has a bug
        where seeds don't propagate to the arrival generator.
        """
        # Run with seed 1
        arrivals_seed_1 = self._run_simulation_and_collect_arrivals(
            stochastic_config.copy(), seed=1
        )

        # Run with seed 2
        arrivals_seed_2 = self._run_simulation_and_collect_arrivals(
            stochastic_config.copy(), seed=2
        )

        # Both should have arrivals (Poisson with rate 2.0 per tick)
        assert len(arrivals_seed_1) > 0, "Seed 1 should produce arrivals"
        assert len(arrivals_seed_2) > 0, "Seed 2 should produce arrivals"

        # The arrivals should differ
        # Compare by extracting key fields (amount, tick, etc.)
        def arrival_signature(events: list[dict]) -> list[tuple]:
            return sorted([
                (e.get("tick"), e.get("amount"), e.get("sender_id"))
                for e in events
            ])

        sig_1 = arrival_signature(arrivals_seed_1)
        sig_2 = arrival_signature(arrivals_seed_2)

        assert sig_1 != sig_2, (
            "Different seeds must produce different arrivals. "
            f"Seed 1 produced {len(arrivals_seed_1)} arrivals, "
            f"Seed 2 produced {len(arrivals_seed_2)} arrivals, "
            "but they are identical. This indicates the Rust FFI "
            "seed propagation bug still exists."
        )

    def test_same_seed_produces_identical_arrival_events(
        self, stochastic_config: dict
    ) -> None:
        """Same seed must produce identical arrivals (INV-2: Determinism).

        This verifies the simulation is deterministic given the same seed.
        Note: tx_id (UUID) is excluded since UUIDs are generated fresh each run,
        but the stochastic properties (tick, amount, sender, receiver) must match.
        """
        seed = 42

        # Run twice with same seed
        arrivals_run_1 = self._run_simulation_and_collect_arrivals(
            stochastic_config.copy(), seed=seed
        )
        arrivals_run_2 = self._run_simulation_and_collect_arrivals(
            stochastic_config.copy(), seed=seed
        )

        # Both should produce arrivals
        assert len(arrivals_run_1) > 0, "Should produce arrivals"

        # Must be identical (excluding tx_id which is a fresh UUID each run)
        def arrival_signature(events: list[dict]) -> list[tuple]:
            return sorted([
                (
                    e.get("tick"),
                    e.get("amount"),
                    e.get("sender_id"),
                    e.get("receiver_id"),
                    # tx_id excluded - UUIDs are fresh each run
                )
                for e in events
            ])

        sig_1 = arrival_signature(arrivals_run_1)
        sig_2 = arrival_signature(arrivals_run_2)

        assert sig_1 == sig_2, (
            f"Same seed ({seed}) must produce identical arrivals. "
            f"Run 1: {len(arrivals_run_1)} arrivals, "
            f"Run 2: {len(arrivals_run_2)} arrivals. "
            "INV-2 (Determinism) is violated."
        )

    def test_seed_affects_arrival_counts(
        self, stochastic_config: dict
    ) -> None:
        """Different seeds should produce statistically different arrival counts.

        With Poisson(λ=2.0) per tick × 10 ticks × 2 agents = ~40 expected arrivals.
        Different seeds should produce varying counts.
        """
        seeds = [100, 200, 300, 400, 500]
        counts = []

        for seed in seeds:
            arrivals = self._run_simulation_and_collect_arrivals(
                stochastic_config.copy(), seed=seed
            )
            counts.append(len(arrivals))

        # Not all counts should be identical (statistical variation)
        unique_counts = set(counts)
        assert len(unique_counts) > 1, (
            f"All {len(seeds)} seeds produced identical arrival counts: {counts}. "
            "This suggests seeds are not affecting stochastic arrivals."
        )

    def test_seed_affects_arrival_amounts(
        self, stochastic_config: dict
    ) -> None:
        """Different seeds should produce different transaction amounts.

        Amount distribution is Uniform(1000, 10000), so amounts should vary.
        """
        arrivals_seed_1 = self._run_simulation_and_collect_arrivals(
            stochastic_config.copy(), seed=111
        )
        arrivals_seed_2 = self._run_simulation_and_collect_arrivals(
            stochastic_config.copy(), seed=222
        )

        # Extract amounts
        amounts_1 = sorted([e.get("amount", 0) for e in arrivals_seed_1])
        amounts_2 = sorted([e.get("amount", 0) for e in arrivals_seed_2])

        # Should have different amounts (unless very unlucky)
        assert amounts_1 != amounts_2, (
            "Different seeds should produce different transaction amounts. "
            f"Seed 111: {amounts_1[:5]}... "
            f"Seed 222: {amounts_2[:5]}..."
        )
