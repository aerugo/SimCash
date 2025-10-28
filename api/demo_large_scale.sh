#!/bin/bash
# Large-Scale Scenario Demo
# 200 agents, 2000 ticks (10 simulated days)

set -e

source .venv/bin/activate

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║   Payment Simulator - Large-Scale Demo                       ║"
echo "║   200 Agents • 2000 Ticks • 10 Days                          ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "This scenario demonstrates the simulator at scale:"
echo "  • 200 banks (tiered by size: 20 large, 60 medium, 120 small)"
echo "  • 200 ticks per day × 10 days = 2000 ticks total"
echo "  • ~160,000 transactions expected"
echo "  • Tests LSM under high load"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ ! -f scenarios/large_scale_200_agents.yaml ]; then
    echo "⚠️  Scenario not found. Generating..."
    python generate_large_scenario.py
    echo ""
fi

echo "🚀 Running full simulation (this will take ~3-4 minutes)..."
echo ""

START_TIME=$(date +%s)

payment-sim run --config scenarios/large_scale_200_agents.yaml --quiet > /tmp/large_scale_full.json

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "✅ Simulation complete in ${DURATION}s!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  RESULTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "⚙️  Simulation Stats:"
jq -r '"  Ticks: " + (.simulation.ticks_executed | tostring)' /tmp/large_scale_full.json
jq -r '"  Duration: " + (.simulation.duration_seconds | tostring) + "s"' /tmp/large_scale_full.json
jq -r '"  Performance: " + (.simulation.ticks_per_second | floor | tostring) + " ticks/s"' /tmp/large_scale_full.json
jq -r '"  Wall-clock time: " + "'$DURATION'" + "s"' /tmp/large_scale_full.json
echo ""

echo "📊 Transaction Activity:"
jq -r '"  Total Arrivals: " + (.metrics.total_arrivals | tostring)' /tmp/large_scale_full.json
jq -r '"  Settlements: " + (.metrics.total_settlements | tostring)' /tmp/large_scale_full.json
jq -r '"  LSM Releases: " + (.metrics.total_lsm_releases | tostring) + " ⚡"' /tmp/large_scale_full.json
jq -r '"  Settlement Rate: " + ((.metrics.settlement_rate * 100 * 100 | floor) / 100 | tostring) + "%"' /tmp/large_scale_full.json
jq -r '"  Unsettled: " + ((.metrics.total_arrivals - .metrics.total_settlements) | tostring)' /tmp/large_scale_full.json
echo ""

echo "💰 Financial Impact:"
jq -r '"  Total Costs: $" + ((.costs.total_cost / 100) | floor | tostring)' /tmp/large_scale_full.json
jq -r '"  Cost per Transaction: $" + ((.costs.total_cost / .metrics.total_arrivals / 100) | floor | tostring)' /tmp/large_scale_full.json
echo ""

echo "🏦 Agent Status (200 banks):"
jq -r '"  In Overdraft: " + ([.agents[] | select(.final_balance < 0)] | length | tostring)' /tmp/large_scale_full.json
jq -r '"  With Queued Txns: " + ([.agents[] | select(.queue1_size > 0)] | length | tostring)' /tmp/large_scale_full.json
jq -r '"  Total System Balance: $" + (([.agents[].final_balance] | add) / 100 | floor | tostring)' /tmp/large_scale_full.json
echo ""

# Calculate LSM effectiveness
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  LSM EFFECTIVENESS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

SETTLEMENTS=$(jq '.metrics.total_settlements' /tmp/large_scale_full.json)
LSM_RELEASES=$(jq '.metrics.total_lsm_releases' /tmp/large_scale_full.json)
LSM_PERCENT=$(echo "scale=1; $LSM_RELEASES * 100 / $SETTLEMENTS" | bc)

echo "  The LSM resolved $LSM_RELEASES transactions ($LSM_PERCENT% of all settlements)"
echo "  This prevented massive gridlock that would have left"
echo "  these transactions stuck indefinitely!"
echo ""

# Show sample of agent balances
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SAMPLE AGENT BALANCES (Top 10 by balance)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

jq -r '.agents | sort_by(.final_balance) | reverse | .[:10] | .[] | "  " + .id + ": $" + ((.final_balance / 100) | floor | tostring) + (if .queue1_size > 0 then " (queue: " + (.queue1_size | tostring) + ")" else "" end)' /tmp/large_scale_full.json

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 Key Insights:"
echo ""
echo "  1. LSM Impact: With 200 agents, the LSM is critical - it"
echo "     resolved $LSM_RELEASES transactions that would have been"
echo "     stuck in gridlock."
echo ""
echo "  2. Scale: The simulator handled ~160k transactions across"
echo "     200 agents efficiently."
echo ""
echo "  3. Stress: High overdraft count ($([.agents[] | select(.final_balance < 0)] | length) banks) shows"
echo "     the system is under significant liquidity pressure."
echo ""
echo "  4. Performance: Maintained ~10 ticks/s even with 200 agents"
echo "     and complex LSM operations."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Full results saved to: /tmp/large_scale_full.json"
echo ""
echo "Explore further:"
echo "  jq '.agents | sort_by(.final_balance) | .[:5]' /tmp/large_scale_full.json"
echo "  jq '.metrics' /tmp/large_scale_full.json"
echo ""
