"""
Gold standard tests for determinism.

According to CLAUDE.md Critical Invariant #2: Determinism is Sacred
Same seed + same inputs MUST produce same outputs, always.

This test suite verifies that the simulation is perfectly reproducible.
"""

import pytest
from payment_simulator._core import Orchestrator
from payment_simulator.config import SimulationConfig
import yaml
from pathlib import Path


def test_determinism_five_consecutive_runs_simple():
    """Verify that 5 consecutive runs with same seed produce identical results."""
    config = {
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 10000000,
                "credit_limit": 5000000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.0,
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
                "credit_limit": 5000000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.0,
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

    results = []
    for run_num in range(5):
        orch = Orchestrator.new(config)

        # Run simulation
        ticks_per_day = config["ticks_per_day"]
        num_days = config["num_days"]
        total_ticks = ticks_per_day * num_days

        for _ in range(total_ticks):
            orch.tick()

        # Collect results using system metrics
        metrics = orch.get_system_metrics()
        agent_costs = {
            agent_id: orch.get_agent_accumulated_costs(agent_id)
            for agent_id in ["BANK_A", "BANK_B"]
        }

        result = {
            "total_arrivals": metrics["total_arrivals"],
            "total_settlements": metrics["total_settlements"],
            "agent_balances": {
                agent_id: orch.get_agent_balance(agent_id)
                for agent_id in ["BANK_A", "BANK_B"]
            },
            "total_cost": sum(c["total_cost"] for c in agent_costs.values()),
            "current_tick": orch.current_tick(),
        }
        results.append(result)

        print(f"\nRun {run_num + 1}:")
        print(f"  Arrivals: {result['total_arrivals']}")
        print(f"  Settlements: {result['total_settlements']}")
        print(f"  Bank A balance: {result['agent_balances']['BANK_A']}")
        print(f"  Bank B balance: {result['agent_balances']['BANK_B']}")
        print(f"  Total cost: {result['total_cost']}")
        print(f"  Current tick: {result['current_tick']}")

    # All results must be identical
    reference = results[0]
    for i, result in enumerate(results[1:], start=2):
        assert result == reference, (
            f"Run {i} differs from run 1:\n"
            f"  Run 1: {reference}\n"
            f"  Run {i}: {result}"
        )


def test_determinism_comprehensive_showcase_config():
    """
    Test determinism with the comprehensive_feature_showcase_ultra_stressed config.

    This is the exact scenario from the user's bug report.
    """
    config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "comprehensive_feature_showcase_ultra_stressed.yaml"

    if not config_path.exists():
        pytest.skip(f"Config file not found: {config_path}")

    with open(config_path) as f:
        config_dict = yaml.safe_load(f)

    # Ensure seed is set to 42
    config_dict["simulation"]["rng_seed"] = 42

    # Parse and convert config to FFI format
    sim_config = SimulationConfig.from_dict(config_dict)
    ffi_config = sim_config.to_ffi_dict()

    # Extract parameters for loop
    ticks_per_day = sim_config.simulation.ticks_per_day
    num_days = sim_config.simulation.num_days
    total_ticks = ticks_per_day * num_days
    agent_ids = [agent.id for agent in sim_config.agents]

    results = []
    for run_num in range(5):
        orch = Orchestrator.new(ffi_config)

        # Run simulation
        for _ in range(total_ticks):
            orch.tick()

        # Collect comprehensive results
        metrics = orch.get_system_metrics()
        agent_costs = {
            agent_id: orch.get_agent_accumulated_costs(agent_id)
            for agent_id in agent_ids
        }

        result = {
            "total_arrivals": metrics["total_arrivals"],
            "total_settlements": metrics["total_settlements"],
            "agent_balances": {
                agent_id: orch.get_agent_balance(agent_id)
                for agent_id in agent_ids
            },
            "total_cost": sum(c["total_cost"] for c in agent_costs.values()),
            "current_tick": orch.current_tick(),
        }
        results.append(result)

        print(f"\nRun {run_num + 1}:")
        print(f"  Arrivals: {result['total_arrivals']}")
        print(f"  Settlements: {result['total_settlements']}")
        for agent_id, balance in result['agent_balances'].items():
            print(f"  {agent_id}: {balance}")
        print(f"  Total cost: {result['total_cost']}")

    # All results must be identical
    reference = results[0]
    for i, result in enumerate(results[1:], start=2):
        if result != reference:
            # Detailed error reporting
            print("\n=== DETERMINISM VIOLATION DETECTED ===")
            print(f"\nDifferences between Run 1 and Run {i}:")

            for key in reference:
                if reference[key] != result[key]:
                    print(f"\n{key}:")
                    print(f"  Run 1: {reference[key]}")
                    print(f"  Run {i}: {result[key]}")

            pytest.fail(f"Run {i} differs from run 1 - see details above")


def test_determinism_tick_by_tick():
    """Verify determinism at each tick, not just final results."""
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 50,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "A",
                "opening_balance": 5000000,
                "credit_limit": 2000000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,
                    "amount_distribution": {"type": "Uniform", "min": 50000, "max": 200000},
                    "counterparty_weights": {"B": 0.7, "C": 0.3},
                },
            },
            {
                "id": "B",
                "opening_balance": 5000000,
                "credit_limit": 2000000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,
                    "amount_distribution": {"type": "Uniform", "min": 50000, "max": 200000},
                    "counterparty_weights": {"A": 0.5, "C": 0.5},
                },
            },
            {
                "id": "C",
                "opening_balance": 5000000,
                "credit_limit": 2000000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,
                    "amount_distribution": {"type": "Uniform", "min": 50000, "max": 200000},
                    "counterparty_weights": {"A": 0.6, "B": 0.4},
                },
            },
        ],
    }

    # Run two simulations in parallel, tick by tick
    orch1 = Orchestrator.new(config)
    orch2 = Orchestrator.new(config)

    # Calculate total ticks
    total_ticks = config["ticks_per_day"] * config["num_days"]

    for tick in range(1, total_ticks + 1):
        # Execute tick on both
        orch1.tick()
        orch2.tick()

        # Verify state is identical after each tick
        assert orch1.current_tick() == orch2.current_tick() == tick

        for agent_id in ["A", "B", "C"]:
            balance1 = orch1.get_agent_balance(agent_id)
            balance2 = orch2.get_agent_balance(agent_id)
            assert balance1 == balance2, (
                f"Tick {tick}: Agent {agent_id} balance differs: "
                f"{balance1} vs {balance2}"
            )

        # Check global metrics
        metrics1 = orch1.get_system_metrics()
        metrics2 = orch2.get_system_metrics()
        assert metrics1["total_arrivals"] == metrics2["total_arrivals"], (
            f"Tick {tick}: Total arrivals differ"
        )
        assert metrics1["total_settlements"] == metrics2["total_settlements"], (
            f"Tick {tick}: Total settlements differ"
        )


def test_determinism_different_seeds_produce_different_results():
    """Verify that different seeds produce different results (sanity check)."""
    config_template = {
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "X",
                "opening_balance": 10000000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.0,
                    "amount_distribution": {"type": "Uniform", "min": 100000, "max": 500000},
                    "counterparty_weights": {"Y": 1.0},
                },
            },
            {
                "id": "Y",
                "opening_balance": 10000000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.0,
                    "amount_distribution": {"type": "Uniform", "min": 100000, "max": 500000},
                    "counterparty_weights": {"X": 1.0},
                },
            },
        ],
    }

    results = []
    for seed in [42, 123, 999]:
        config = config_template.copy()
        config["rng_seed"] = seed

        orch = Orchestrator.new(config)

        # Run simulation for specified duration
        total_ticks = config["ticks_per_day"] * config["num_days"]
        for _ in range(total_ticks):
            orch.tick()

        metrics = orch.get_system_metrics()
        results.append({
            "seed": seed,
            "arrivals": metrics["total_arrivals"],
            "settlements": metrics["total_settlements"],
            "balance_X": orch.get_agent_balance("X"),
        })

    # Different seeds should produce different results
    assert len(set(r["arrivals"] for r in results)) > 1, (
        "Different seeds produced identical arrival counts - RNG may not be working"
    )

    print("\nDifferent seeds produced different results (as expected):")
    for r in results:
        print(f"  Seed {r['seed']}: {r['arrivals']} arrivals, {r['settlements']} settlements")
