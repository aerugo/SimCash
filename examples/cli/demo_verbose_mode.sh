#!/bin/bash
# Verbose Mode Demo
# Shows detailed real-time event logging

# IMPORTANT: This script must be run from the project root directory
# cd /path/to/cashman && examples/cli/demo_verbose_mode.sh

set -e

source api/.venv/bin/activate

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║   Payment Simulator - Verbose Mode Demo                      ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "Verbose mode shows detailed events in real-time:"
echo "  • Tick-by-tick progress"
echo "  • Transaction arrivals and settlements"
echo "  • LSM activity (bilateral offsetting, cycle detection)"
echo "  • Balance changes per agent"
echo "  • Cost accumulation"
echo "  • Queue sizes"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Running 15 ticks of high-stress scenario with verbose output..."
echo ""
sleep 1

# Run with verbose mode (only show stderr, suppress JSON stdout)
payment-sim run --config scenarios/high_stress_gridlock.yaml --verbose --ticks 15 2>&1 >/dev/null

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Demo complete!"
echo ""
echo "Try it yourself:"
echo "  payment-sim run --config scenarios/realistic_demo.yaml --verbose --ticks 20"
echo "  payment-sim run --config scenarios/high_stress_gridlock.yaml --verbose --ticks 30"
echo ""
echo "Compare modes:"
echo "  Normal:    payment-sim run --config scenarios/realistic_demo.yaml"
echo "  Streaming: payment-sim run --config scenarios/realistic_demo.yaml --stream"
echo "  Verbose:   payment-sim run --config scenarios/realistic_demo.yaml --verbose"
echo ""
