#!/usr/bin/env python3
"""Fast policy comparison using JSON output (no persistence)."""

import json
import subprocess
import sys
from pathlib import Path

CLI = "api/.venv/bin/payment-sim"
BASE_CONFIG = "examples/configs/suboptimal_policies_25day.yaml"
RESULTS_DIR = Path("experiments/results")

RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def run_sim(config_path, name):
    """Run simulation and return JSON results."""
    print(f"\n{'='*60}")
    print(f"Running: {name}")
    print(f"{'='*60}")

    result = subprocess.run(
        [CLI, "run", "-c", str(config_path), "--quiet", "--output", "json"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"❌ Error: {result.stderr}")
        return None

    data = json.loads(result.stdout)
    print(f"✓ {name} complete")
    print(f"  Total cost: ${data['costs']['total_cost']/100:,.2f}")
    print(f"  Settlement rate: {data['metrics']['settlement_rate']:.2%}")

    return data

# Store results
all_results = {}

# 1. Baseline (original config)
print("\n" + "="*60)
print(" POLICY COMPARISON EXPERIMENT - FAST MODE")
print("="*60)

all_results["baseline"] = run_sim(BASE_CONFIG, "Baseline (SMALL_BANK_A=efficient_memory)")

# 2. All cautious
print("\nCreating all-cautious config...")
all_cautious_cfg = """
simulation: {ticks_per_day: 100, num_days: 25, rng_seed: 42}
agents:
  - {id: "BIG_BANK_A", opening_balance: 12000000, unsecured_cap: 4000000, policy: {type: "FromJson", json_path: "backend/policies/cautious_liquidity_preserver.json"}, arrival_config: {rate_per_tick: 0.13, amount_distribution: {type: "LogNormal", mean: 11.51, std_dev: 0.8}, counterparty_weights: {SMALL_BANK_A: 0.32, BIG_BANK_B: 0.35, SMALL_BANK_B: 0.32}, deadline_range: [40, 80], priority: 6, divisible: false}}
  - {id: "BIG_BANK_B", opening_balance: 13000000, unsecured_cap: 4500000, policy: {type: "FromJson", json_path: "backend/policies/cautious_liquidity_preserver.json"}, arrival_config: {rate_per_tick: 0.13, amount_distribution: {type: "LogNormal", mean: 11.51, std_dev: 0.8}, counterparty_weights: {BIG_BANK_A: 0.35, SMALL_BANK_A: 0.35, SMALL_BANK_B: 0.35}, deadline_range: [30, 70], priority: 5, divisible: false}}
  - {id: "SMALL_BANK_A", opening_balance: 13000000, unsecured_cap: 4500000, policy: {type: "FromJson", json_path: "backend/policies/cautious_liquidity_preserver.json"}, arrival_config: {rate_per_tick: 0.11, amount_distribution: {type: "Uniform", min: 100000, max: 400000}, counterparty_weights: {BIG_BANK_A: 0.35, BIG_BANK_B: 0.30, SMALL_BANK_B: 0.35}, deadline_range: [35, 75], priority: 6, divisible: true}}
  - {id: "SMALL_BANK_B", opening_balance: 13000000, unsecured_cap: 4500000, policy: {type: "FromJson", json_path: "backend/policies/cautious_liquidity_preserver.json"}, arrival_config: {rate_per_tick: 0.11, amount_distribution: {type: "Uniform", min: 100000, max: 400000}, counterparty_weights: {BIG_BANK_A: 0.35, SMALL_BANK_A: 0.35, BIG_BANK_B: 0.30}, deadline_range: [35, 75], priority: 6, divisible: true}}
lsm_config: {enable_bilateral: true, enable_cycles: true, max_cycle_length: 4, max_cycles_per_tick: 10}
cost_rates: {delay_cost_per_tick_per_cent: 0.00022, overdraft_bps_per_tick: 0.5, collateral_cost_per_tick_bps: 0.0005, eod_penalty_per_transaction: 0, deadline_penalty: 5000, overdue_delay_multiplier: 2.5, split_friction_cost: 7500}
"""

(RESULTS_DIR / "all_cautious.yaml").write_text(all_cautious_cfg)
all_results["all_cautious"] = run_sim(RESULTS_DIR / "all_cautious.yaml", "All Cautious")

# 3. SMALL_BANK_A = efficient_proactive
print("\nCreating SMALL_BANK_A=efficient_proactive config...")
subprocess.run(["sed", "s|efficient_memory_adaptive|efficient_proactive|", BASE_CONFIG], stdout=open(RESULTS_DIR / "sba_proactive.yaml", "w"))
all_results["sba_proactive"] = run_sim(RESULTS_DIR / "sba_proactive.yaml", "SMALL_BANK_A=efficient_proactive")

# 4. SMALL_BANK_A = aggressive_market_maker
print("\nCreating SMALL_BANK_A=aggressive config...")
subprocess.run(["sed", "s|efficient_memory_adaptive|aggressive_market_maker|", BASE_CONFIG], stdout=open(RESULTS_DIR / "sba_aggressive.yaml", "w"))
all_results["sba_aggressive"] = run_sim(RESULTS_DIR / "sba_aggressive.yaml", "SMALL_BANK_A=aggressive_market_maker")

# 5. BIG_BANK_A = efficient_proactive (instead of cautious)
print("\nCreating BIG_BANK_A=efficient_proactive config...")
subprocess.run(["sed", "0,/cautious_liquidity_preserver/{s|cautious_liquidity_preserver|efficient_proactive|}", BASE_CONFIG], stdout=open(RESULTS_DIR / "bba_proactive.yaml", "w"))
all_results["bba_proactive"] = run_sim(RESULTS_DIR / "bba_proactive.yaml", "BIG_BANK_A=efficient_proactive")

# 6. BIG_BANK_A = aggressive_market_maker
print("\nCreating BIG_BANK_A=aggressive config...")
subprocess.run(["sed", "0,/cautious_liquidity_preserver/{s|cautious_liquidity_preserver|aggressive_market_maker|}", BASE_CONFIG], stdout=open(RESULTS_DIR / "bba_aggressive.yaml", "w"))
all_results["bba_aggressive"] = run_sim(RESULTS_DIR / "bba_aggressive.yaml", "BIG_BANK_A=aggressive_market_maker")

# Save results
with open(RESULTS_DIR / "comparison_results.json", "w") as f:
    json.dump(all_results, f, indent=2)

print("\n" + "="*60)
print(" RESULTS SUMMARY")
print("="*60)

# Extract and display key metrics
for name, data in all_results.items():
    if data:
        print(f"\n{name}:")
        print(f"  Total Cost: ${data['costs']['total_cost']/100:,.2f}")
        print(f"  Settlement Rate: {data['metrics']['settlement_rate']:.2%}")
        print(f"  Ticks/sec: {data['performance']['ticks_per_second']:.1f}")

print(f"\nResults saved to: {RESULTS_DIR}/comparison_results.json")
