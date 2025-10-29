#!/bin/bash
# Demonstration: AI-driven parameter tuning
# This script shows how an AI model can iterate on simulation parameters

# IMPORTANT: This script must be run from the project root directory
# cd /path/to/cashman && examples/cli/demo_ai_integration.sh

echo "=== AI Integration Pattern Demo ==="
echo ""

# Pattern 1: Extract single metric for decision-making
echo "Pattern 1: Extract settlement rate"
source api/.venv/bin/activate
payment-sim run --config examples/configs/minimal.yaml --quiet | jq -r '.metrics.settlement_rate'
echo ""

# Pattern 2: Test multiple seeds and find best performance
echo "Pattern 2: Test multiple seeds (batch experiment)"
echo "Seed | Ticks/Second"
echo "-----|-------------"
for seed in 42 123 456 789; do
    tps=$(payment-sim run --config examples/configs/minimal.yaml --seed $seed --quiet | jq -r '.performance.ticks_per_second')
    echo "$seed  | $tps"
done
echo ""

# Pattern 3: Parameter sweep - vary tick count
echo "Pattern 3: Parameter sweep (varying ticks)"
echo "Ticks | Duration (s)"
echo "------|------------"
for ticks in 10 50 100 500; do
    duration=$(payment-sim run --config examples/configs/minimal.yaml --ticks $ticks --quiet | jq -r '.simulation.duration_seconds')
    echo "$ticks   | $duration"
done
echo ""

# Pattern 4: Streaming mode for real-time monitoring
echo "Pattern 4: Streaming mode (first 3 ticks)"
payment-sim run --config examples/configs/minimal.yaml --stream --quiet | head -3
echo ""

echo "=== All patterns demonstrated! ==="
echo ""
echo "AI models can:"
echo "  1. Run simulations programmatically"
echo "  2. Parse JSON output with jq or Python"
echo "  3. Iterate on parameters to optimize policies"
echo "  4. Monitor long-running simulations in real-time"
