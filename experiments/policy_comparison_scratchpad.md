# Policy Comparison Experiment - Scratchpad

## Experiment Run Log

**Date**: 2025-11-20
**Scenario**: 25-day resilient scenario with policy variations
**Purpose**: Analyze cost and performance differences when individual agents adopt different policies

---

## Simulation Runs

### Run Configuration Template
```
Scenario: 25 days, 100 ticks/day = 2,500 ticks
Agents: BIG_BANK_A, BIG_BANK_B, SMALL_BANK_A, SMALL_BANK_B
Cost Structure:
  - delay_cost_per_tick_per_cent: 0.00022
  - overdraft_bps_per_tick: 0.5
  - collateral_cost_per_tick_bps: 0.0005
  - deadline_penalty: 5000
  - overdue_delay_multiplier: 2.5
  - split_friction_cost: 7500
```

---

## Results Summary

### Run Results
(To be filled during execution)

| Run ID | Test Agent | Policy | Total Cost | Delay Cost | Overdraft Cost | Collateral Cost | Settlement Rate | Notes |
|--------|------------|--------|------------|------------|----------------|-----------------|-----------------|-------|
| baseline | SMALL_BANK_A | efficient_memory | - | - | - | - | - | Original config |
| | BIG_BANK_A | cautious | - | - | - | - | - | |
| | BIG_BANK_B | cautious | - | - | - | - | - | |
| | SMALL_BANK_B | cautious | - | - | - | - | - | |

---

## Observations

### Initial Observations
-

### Cost Analysis
-

### Performance Patterns
-

### Stress Period Behavior
-

---

## Key Findings

### Per-Agent Results
-

### Policy Effectiveness Ranking
-

### Cost Driver Analysis
-

---

## Questions for Further Investigation
-

---

## Data Files

Database files saved to:
- `experiments/results/*.db`

Query examples:
```sql
-- Get agent final costs
SELECT agent_id, total_cost, cost_delay, cost_overdraft, cost_collateral
FROM agent_final_states
WHERE simulation_id = ?;

-- Get per-tick costs
SELECT tick, agent_id, cost_this_tick
FROM agent_tick_snapshots
WHERE simulation_id = ?
ORDER BY tick, agent_id;
```
