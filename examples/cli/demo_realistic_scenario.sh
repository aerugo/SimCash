#!/bin/bash
# Realistic Scenario Demo
# Shows a complete RTGS simulation with transaction arrivals, settlements, and costs

# IMPORTANT: This script must be run from the project root directory
# cd /path/to/cashman && examples/cli/demo_realistic_scenario.sh

set -e

source api/.venv/bin/activate

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║   Payment Simulator - Realistic RTGS Scenario Demo           ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "Scenario: 4 banks with different liquidity levels"
echo "         ~150 transactions over 100 ticks (1 simulated day)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Run full simulation
echo "📊 Running full simulation..."
echo ""
payment-sim run --config ../../scenarios/realistic_demo.yaml --quiet > /tmp/sim_results.json

# 2. Extract and display key metrics
echo "📈 SIMULATION RESULTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "⚙️  Configuration:"
jq -r '"  Seed: " + (.simulation.seed | tostring)' /tmp/sim_results.json
jq -r '"  Ticks: " + (.simulation.ticks_executed | tostring)' /tmp/sim_results.json
jq -r '"  Performance: " + (.simulation.ticks_per_second | floor | tostring) + " ticks/s"' /tmp/sim_results.json
echo ""

echo "💸 Transaction Activity:"
jq -r '"  Arrivals: " + (.metrics.total_arrivals | tostring)' /tmp/sim_results.json
jq -r '"  Settlements: " + (.metrics.total_settlements | tostring)' /tmp/sim_results.json
jq -r '"  LSM Releases: " + (.metrics.total_lsm_releases | tostring)' /tmp/sim_results.json
jq -r '"  Settlement Rate: " + ((.metrics.settlement_rate * 100 | floor) | tostring) + "%"' /tmp/sim_results.json
echo ""

echo "💰 Costs:"
jq -r '"  Total: $" + ((.costs.total_cost / 100) | tostring)' /tmp/sim_results.json
echo ""

echo "🏦 Final Bank Balances:"
jq -r '.agents[] | "  " + .id + ": $" + ((.final_balance / 100) | tostring) + " (queue: " + (.queue1_size | tostring) + ")"' /tmp/sim_results.json
echo ""

# 3. Show balance changes
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📉 Balance Changes from Opening:"
echo ""
echo "  Opening → Final"
echo "  BANK_A: \$500.00 → $(jq -r '.agents[] | select(.id=="BANK_A") | ((.final_balance / 100) | tostring)' /tmp/sim_results.json || echo "N/A")"
echo "  BANK_B: \$300.00 → $(jq -r '.agents[] | select(.id=="BANK_B") | ((.final_balance / 100) | tostring)' /tmp/sim_results.json || echo "N/A")"
echo "  BANK_C: \$150.00 → $(jq -r '.agents[] | select(.id=="BANK_C") | ((.final_balance / 100) | tostring)' /tmp/sim_results.json || echo "N/A")"
echo "  BANK_D: \$250.00 → $(jq -r '.agents[] | select(.id=="BANK_D") | ((.final_balance / 100) | tostring)' /tmp/sim_results.json || echo "N/A")"
echo ""

# 4. Demonstrate parameter override
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 Testing Determinism (different seeds):"
echo ""
for seed in 123 456 789; do
    settlement_rate=$(payment-sim run --config scenarios/realistic_demo.yaml --seed $seed --quiet | \
        jq -r '(.metrics.settlement_rate * 100 | floor | tostring) + "%"')
    echo "  Seed $seed: Settlement rate = $settlement_rate"
done
echo ""

# 5. Show streaming mode sample
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📡 Streaming Mode Sample (first 10 ticks):"
echo ""
payment-sim run --config scenarios/realistic_demo.yaml --stream --quiet --ticks 10 2>/dev/null | \
    jq -r '"  Tick " + (.tick | tostring) + ": " + (.arrivals | tostring) + " arrivals, " + (.settlements | tostring) + " settlements"'
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Demo complete!"
echo ""
echo "Try it yourself:"
echo "  payment-sim run --config scenarios/realistic_demo.yaml"
echo "  payment-sim run --config scenarios/realistic_demo.yaml --quiet | jq '.metrics'"
echo "  payment-sim run --config scenarios/realistic_demo.yaml --stream"
echo ""
