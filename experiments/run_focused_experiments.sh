#!/bin/bash
# Focused policy comparison - 6 key experiments

CLI="api/.venv/bin/payment-sim"
BASE_CONFIG="examples/configs/suboptimal_policies_25day.yaml"
RESULTS_DIR="experiments/results"

mkdir -p "$RESULTS_DIR"

echo "========================================="
echo "Running Focused Policy Experiments"
echo "========================================="

# Baseline: all cautious except SMALL_BANK_A (efficient_memory_adaptive)
echo "1/6: Baseline (all cautious + 1 efficient_memory)"
$CLI run -c "$BASE_CONFIG" --persist --db-path "$RESULTS_DIR/baseline.db" --quiet
echo "✓ Baseline complete"

# All cautious (control)
echo "2/6: All cautious control"
cat > "$RESULTS_DIR/all_cautious.yaml" << 'EOF'
simulation:
  ticks_per_day: 100
  num_days: 25
  rng_seed: 42

agents:
  - id: "BIG_BANK_A"
    opening_balance: 12000000
    unsecured_cap: 4000000
    policy: {type: "FromJson", json_path: "backend/policies/cautious_liquidity_preserver.json"}
    arrival_config: {rate_per_tick: 0.13, amount_distribution: {type: "LogNormal", mean: 11.51, std_dev: 0.8}, counterparty_weights: {SMALL_BANK_A: 0.32, BIG_BANK_B: 0.35, SMALL_BANK_B: 0.32}, deadline_range: [40, 80], priority: 6, divisible: false}

  - id: "BIG_BANK_B"
    opening_balance: 13000000
    unsecured_cap: 4500000
    policy: {type: "FromJson", json_path: "backend/policies/cautious_liquidity_preserver.json"}
    arrival_config: {rate_per_tick: 0.13, amount_distribution: {type: "LogNormal", mean: 11.51, std_dev: 0.8}, counterparty_weights: {BIG_BANK_A: 0.35, SMALL_BANK_A: 0.35, SMALL_BANK_B: 0.35}, deadline_range: [30, 70], priority: 5, divisible: false}

  - id: "SMALL_BANK_A"
    opening_balance: 13000000
    unsecured_cap: 4500000
    policy: {type: "FromJson", json_path: "backend/policies/cautious_liquidity_preserver.json"}
    arrival_config: {rate_per_tick: 0.11, amount_distribution: {type: "Uniform", min: 100000, max: 400000}, counterparty_weights: {BIG_BANK_A: 0.35, BIG_BANK_B: 0.30, SMALL_BANK_B: 0.35}, deadline_range: [35, 75], priority: 6, divisible: true}

  - id: "SMALL_BANK_B"
    opening_balance: 13000000
    unsecured_cap: 4500000
    policy: {type: "FromJson", json_path: "backend/policies/cautious_liquidity_preserver.json"}
    arrival_config: {rate_per_tick: 0.11, amount_distribution: {type: "Uniform", min: 100000, max: 400000}, counterparty_weights: {BIG_BANK_A: 0.35, SMALL_BANK_A: 0.35, BIG_BANK_B: 0.30}, deadline_range: [35, 75], priority: 6, divisible: true}

lsm_config: {enable_bilateral: true, enable_cycles: true, max_cycle_length: 4, max_cycles_per_tick: 10}
cost_rates: {delay_cost_per_tick_per_cent: 0.00022, overdraft_bps_per_tick: 0.5, collateral_cost_per_tick_bps: 0.0005, eod_penalty_per_transaction: 0, deadline_penalty: 5000, overdue_delay_multiplier: 2.5, split_friction_cost: 7500}
EOF

$CLI run -c "$RESULTS_DIR/all_cautious.yaml" --persist --db-path "$RESULTS_DIR/all_cautious.db" --quiet
echo "✓ All cautious complete"

# BIG_BANK_A with efficient_proactive
echo "3/6: BIG_BANK_A efficient_proactive"
sed 's|"backend/policies/cautious_liquidity_preserver.json"|"backend/policies/efficient_proactive.json"|' "$BASE_CONFIG" | sed '0,/cautious_liquidity_preserver/{s/cautious_liquidity_preserver/efficient_proactive/}' > "$RESULTS_DIR/bba_efficient_pro.yaml"
$CLI run -c "$RESULTS_DIR/bba_efficient_pro.yaml" --persist --db-path "$RESULTS_DIR/bba_efficient_pro.db" --quiet
echo "✓ BIG_BANK_A efficient_proactive complete"

# BIG_BANK_A with aggressive_market_maker
echo "4/6: BIG_BANK_A aggressive_market_maker"
sed 's|"backend/policies/cautious_liquidity_preserver.json"|"backend/policies/aggressive_market_maker.json"|' "$BASE_CONFIG" | sed '0,/cautious_liquidity_preserver/{s/cautious_liquidity_preserver/aggressive_market_maker/}' > "$RESULTS_DIR/bba_aggressive.yaml"
$CLI run -c "$RESULTS_DIR/bba_aggressive.yaml" --persist --db-path "$RESULTS_DIR/bba_aggressive.db" --quiet
echo "✓ BIG_BANK_A aggressive complete"

# SMALL_BANK_A with efficient_proactive
echo "5/6: SMALL_BANK_A efficient_proactive"
sed 's|"backend/policies/efficient_memory_adaptive.json"|"backend/policies/efficient_proactive.json"|' "$BASE_CONFIG" > "$RESULTS_DIR/sba_efficient_pro.yaml"
$CLI run -c "$RESULTS_DIR/sba_efficient_pro.yaml" --persist --db-path "$RESULTS_DIR/sba_efficient_pro.db" --quiet
echo "✓ SMALL_BANK_A efficient_proactive complete"

# SMALL_BANK_A with aggressive_market_maker
echo "6/6: SMALL_BANK_A aggressive_market_maker"
sed 's|"backend/policies/efficient_memory_adaptive.json"|"backend/policies/aggressive_market_maker.json"|' "$BASE_CONFIG" > "$RESULTS_DIR/sba_aggressive.yaml"
$CLI run -c "$RESULTS_DIR/sba_aggressive.yaml" --persist --db-path "$RESULTS_DIR/sba_aggressive.db" --quiet
echo "✓ SMALL_BANK_A aggressive complete"

echo "========================================="
echo "All experiments complete!"
echo "Results in: $RESULTS_DIR/*.db"
echo "========================================="
