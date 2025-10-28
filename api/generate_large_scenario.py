#!/usr/bin/env python3
"""Generate a large-scale scenario with 200 agents for stress testing."""

import yaml
import random

# Set seed for reproducible generation
random.seed(42)

def generate_large_scenario(
    num_agents: int = 200,
    ticks_per_day: int = 200,
    num_days: int = 10,
    rng_seed: int = 12345,
):
    """Generate a large-scale scenario configuration.

    Creates a tiered banking system:
    - Tier 1: Large banks (10%) - High liquidity, high volume
    - Tier 2: Medium banks (30%) - Medium liquidity, medium volume
    - Tier 3: Small banks (60%) - Low liquidity, low volume
    """

    # Calculate tier sizes
    tier1_count = int(num_agents * 0.10)  # 20 large banks
    tier2_count = int(num_agents * 0.30)  # 60 medium banks
    tier3_count = num_agents - tier1_count - tier2_count  # 120 small banks

    config = {
        "simulation": {
            "ticks_per_day": ticks_per_day,
            "num_days": num_days,
            "rng_seed": rng_seed,
        },
        "agents": [],
        "lsm_config": {
            "bilateral_offsetting": True,
            "cycle_detection": True,
            "max_iterations": 5,
        },
        "cost_rates": {
            "overdraft_bps_per_tick": 10,
            "delay_cost_per_tick_per_cent": 1,
            "eod_penalty_per_transaction": 1000000,
            "deadline_penalty": 500000,
            "split_friction_cost": 10000,
        }
    }

    # Generate agent IDs
    agent_ids = [f"BANK_{i:03d}" for i in range(num_agents)]

    # Create counterparty weight distribution
    # Use uniform weights for simplicity (each bank can pay any other bank)
    def create_counterparty_weights(sender_id: str, all_ids: list) -> dict:
        """Create uniform counterparty weights excluding self."""
        weights = {}
        for agent_id in all_ids:
            if agent_id != sender_id:
                weights[agent_id] = 1.0 / (len(all_ids) - 1)
        return weights

    # Generate Tier 1 agents (Large banks)
    print(f"Generating {tier1_count} Tier 1 (large) banks...")
    for i in range(tier1_count):
        agent_id = agent_ids[i]
        config["agents"].append({
            "id": agent_id,
            "opening_balance": random.randint(5000000, 10000000),  # $50k - $100k
            "credit_limit": random.randint(2000000, 5000000),      # $20k - $50k
            "policy": {"type": "Fifo"},
            "arrival_config": {
                "rate_per_tick": round(random.uniform(0.8, 1.5), 2),  # High volume
                "amount_distribution": {
                    "type": "Uniform",
                    "min": random.randint(50000, 100000),    # $500 - $1k min
                    "max": random.randint(1000000, 2000000), # $10k - $20k max
                },
                "counterparty_weights": create_counterparty_weights(agent_id, agent_ids),
                "deadline_range": [20, 50],
                "priority": 5,
                "divisible": False,
            }
        })

    # Generate Tier 2 agents (Medium banks)
    print(f"Generating {tier2_count} Tier 2 (medium) banks...")
    for i in range(tier1_count, tier1_count + tier2_count):
        agent_id = agent_ids[i]
        config["agents"].append({
            "id": agent_id,
            "opening_balance": random.randint(2000000, 5000000),  # $20k - $50k
            "credit_limit": random.randint(500000, 2000000),      # $5k - $20k
            "policy": {"type": "Fifo"},
            "arrival_config": {
                "rate_per_tick": round(random.uniform(0.3, 0.8), 2),  # Medium volume
                "amount_distribution": {
                    "type": "Uniform",
                    "min": random.randint(20000, 50000),     # $200 - $500 min
                    "max": random.randint(500000, 1000000),  # $5k - $10k max
                },
                "counterparty_weights": create_counterparty_weights(agent_id, agent_ids),
                "deadline_range": [15, 40],
                "priority": 5,
                "divisible": False,
            }
        })

    # Generate Tier 3 agents (Small banks)
    print(f"Generating {tier3_count} Tier 3 (small) banks...")
    for i in range(tier1_count + tier2_count, num_agents):
        agent_id = agent_ids[i]
        config["agents"].append({
            "id": agent_id,
            "opening_balance": random.randint(500000, 2000000),  # $5k - $20k
            "credit_limit": random.randint(200000, 500000),      # $2k - $5k
            "policy": {"type": "Fifo"},
            "arrival_config": {
                "rate_per_tick": round(random.uniform(0.1, 0.3), 2),  # Low volume
                "amount_distribution": {
                    "type": "Uniform",
                    "min": random.randint(10000, 30000),     # $100 - $300 min
                    "max": random.randint(200000, 500000),   # $2k - $5k max
                },
                "counterparty_weights": create_counterparty_weights(agent_id, agent_ids),
                "deadline_range": [10, 30],
                "priority": 5,
                "divisible": False,
            }
        })

    return config


if __name__ == "__main__":
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║   Large-Scale Scenario Generator                             ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()
    print("Generating 200-agent scenario with:")
    print("  • 200 ticks per day")
    print("  • 10 days (2000 ticks total)")
    print("  • 200 agents (tiered by size)")
    print()

    config = generate_large_scenario(
        num_agents=200,
        ticks_per_day=200,
        num_days=10,
        rng_seed=12345,
    )

    output_file = "scenarios/large_scale_200_agents.yaml"

    print(f"Writing configuration to {output_file}...")
    with open(output_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print()
    print("✅ Configuration generated!")
    print()
    print(f"File size: {len(yaml.dump(config, default_flow_style=False)) / 1024:.1f} KB")
    print()
    print("Agent breakdown:")
    print(f"  Tier 1 (Large):  20 banks  (10%)")
    print(f"  Tier 2 (Medium): 60 banks  (30%)")
    print(f"  Tier 3 (Small):  120 banks (60%)")
    print()
    print("Run it with:")
    print(f"  payment-sim run --config {output_file}")
    print()
    print("Or with verbose mode (first 50 ticks):")
    print(f"  payment-sim run --config {output_file} --verbose --ticks 50")
    print()
