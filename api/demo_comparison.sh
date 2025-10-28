#!/bin/bash
# Scenario Comparison Demo
# Compares normal liquidity vs. high-stress scenarios

set -e

source .venv/bin/activate

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║   Payment Simulator - Scenario Comparison                    ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Run both scenarios
echo "🔄 Running scenarios..."
echo ""

payment-sim run --config scenarios/realistic_demo.yaml --quiet > /tmp/normal.json
payment-sim run --config scenarios/high_stress_gridlock.yaml --quiet > /tmp/stress.json

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SCENARIO 1: Normal Liquidity (realistic_demo.yaml)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💰 Bank Liquidity: Medium to High (\$150-\$500 opening balance)"
echo "📊 Transaction Rate: ~1.5 txns/tick (moderate)"
echo ""
echo "Results:"
jq -r '"  Arrivals: " + (.metrics.total_arrivals | tostring)' /tmp/normal.json
jq -r '"  Settlements: " + (.metrics.total_settlements | tostring)' /tmp/normal.json
jq -r '"  LSM Releases: " + (.metrics.total_lsm_releases | tostring)' /tmp/normal.json
jq -r '"  Settlement Rate: " + ((.metrics.settlement_rate * 100 | floor) | tostring) + "%"' /tmp/normal.json
jq -r '"  Total Costs: $" + ((.costs.total_cost / 100) | tostring)' /tmp/normal.json
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SCENARIO 2: High-Stress Gridlock (high_stress_gridlock.yaml)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💰 Bank Liquidity: Low (\$40-\$60 opening balance)"
echo "📊 Transaction Rate: ~2.75 txns/tick (high volume)"
echo "💸 Transaction Size: Large relative to liquidity"
echo ""
echo "Results:"
jq -r '"  Arrivals: " + (.metrics.total_arrivals | tostring)' /tmp/stress.json
jq -r '"  Settlements: " + (.metrics.total_settlements | tostring)' /tmp/stress.json
jq -r '"  LSM Releases: " + (.metrics.total_lsm_releases | tostring) + " ← LSM ACTIVE!"' /tmp/stress.json
jq -r '"  Settlement Rate: " + ((.metrics.settlement_rate * 100 | floor) | tostring) + "%"' /tmp/stress.json
jq -r '"  Total Costs: $" + ((.costs.total_cost / 100) | tostring) + " ← High penalties!"' /tmp/stress.json
echo ""

# Calculate unsettled
normal_unsettled=$(jq '(.metrics.total_arrivals - .metrics.total_settlements)' /tmp/normal.json)
stress_unsettled=$(jq '(.metrics.total_arrivals - .metrics.total_settlements)' /tmp/stress.json)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  KEY INSIGHTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎯 Scenario 1 (Normal):"
echo "   • Well-capitalized banks handle most transactions immediately"
echo "   • Minimal LSM intervention needed"
echo "   • Low costs = efficient settlement"
echo "   • $normal_unsettled unsettled at EOD"
echo ""
echo "⚠️  Scenario 2 (High-Stress):"
echo "   • Low liquidity causes significant queueing"
echo "   • LSM actively resolves gridlock (bilateral + cycles)"
echo "   • High costs = penalties for unsettled transactions"
echo "   • $stress_unsettled unsettled at EOD"
echo ""
echo "💡 The LSM saved $(jq '.metrics.total_lsm_releases' /tmp/stress.json) transactions that would"
echo "   have remained gridlocked without offsetting!"
echo ""

# Show streaming comparison for first 5 ticks
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STREAMING VIEW: First 5 Ticks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Normal Liquidity:"
payment-sim run --config scenarios/realistic_demo.yaml --stream --quiet --ticks 5 2>/dev/null | \
    jq -r '"  Tick " + (.tick | tostring) + ": " + (.arrivals | tostring) + " in, " + (.settlements | tostring) + " settled"'
echo ""
echo "High-Stress:"
payment-sim run --config scenarios/high_stress_gridlock.yaml --stream --quiet --ticks 5 2>/dev/null | \
    jq -r '"  Tick " + (.tick | tostring) + ": " + (.arrivals | tostring) + " in, " + (.settlements | tostring) + " settled, " + (.lsm_releases | tostring) + " LSM"'
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Comparison complete!"
echo ""
echo "Try exploring yourself:"
echo "  payment-sim run --config scenarios/realistic_demo.yaml"
echo "  payment-sim run --config scenarios/high_stress_gridlock.yaml"
echo "  payment-sim run --config scenarios/high_stress_gridlock.yaml --seed 999"
echo ""
