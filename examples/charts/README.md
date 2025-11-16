# Example Cost Charts

This directory contains example PNG charts generated from simulations using the CLI cost tool.

## Charts from Advanced Policy Crisis Simulation

### Accumulated Costs
![Accumulated Costs](crisis_costs_accumulated.png)

**File**: `crisis_costs_accumulated.png`

Shows the running total of costs accumulated by each agent over 300 ticks (3 days). Key observations:

- **REGIONAL_TRUST** (orange): Highest total costs ($342,963), showing steady climb with visible steps
- **CORRESPONDENT_HUB** (blue): Second highest ($295,852), similar stepped pattern
- **METRO_CENTRAL & MOMENTUM_CAPITAL**: Zero costs - perfect liquidity management
- **Sharp steps visible**: Each vertical jump represents a deadline penalty event ($2,500)
- **Day boundaries**: Vertical gray lines mark transitions between days

### Per-Tick Costs
![Per-Tick Costs](crisis_costs_per_tick.png)

**File**: `crisis_costs_per_tick.png`

Shows the cost incurred at each individual tick, revealing the true cost dynamics:

- **Massive spikes**: $2,500+ spikes are deadline penalties when transactions miss deadlines
- **Baseline costs**: Small amounts ($0-30/tick) are continuous liquidity and delay costs
- **Crisis pattern**: Most penalties occur in Day 2 (ticks 200-299) after the crisis intensifies
- **Multiple simultaneous penalties**: Some ticks show $5,000+ when 2+ transactions miss deadlines
- **Contrast with old view**: Previously these were averaged to appear as constant $552/tick

## Generating Your Own Charts

```bash
# Accumulated costs chart
payment-sim db costs <simulation-id> --chart-output costs_accumulated.png

# Per-tick costs chart (shows deadline penalty spikes)
payment-sim db costs <simulation-id> --chart-output costs_per_tick.png --per-tick

# Filter to specific agent
payment-sim db costs <simulation-id> --agent METRO_CENTRAL --chart-output metro_costs.png
```

## Why Two Views?

**Accumulated (default)**: Best for understanding total cost burden and comparing agents over time

**Per-tick (--per-tick)**: Best for identifying when costs occurred and distinguishing continuous costs from discrete penalty events

## Key Insight

The per-tick chart reveals that 99% of costs in this crisis came from **discrete deadline penalty events** ($2,500 each), not from continuous overdraft/delay costs. This is completely hidden when costs are averaged or interpolated linearly.

The stepped appearance in the accumulated chart and the dramatic spikes in the per-tick chart are the actual cost accumulation pattern - not artifacts of the visualization!
