# Phase 4: Replay + Analysis Views

**Status**: Pending
**Started**: —

## Objective

Build post-completion replay scrubber and analysis dashboard with deep metrics.

## Implementation Steps

### Step 4.1: Replay View
Create `src/views/ReplayView.tsx`:
- Tick scrubber slider (0 to total_ticks)
- Displays: agent cards, balance chart, cost chart, events — all at the scrubbed tick
- Play/pause replay with speed control
- Keyboard: Left/Right arrows to step through ticks

### Step 4.2: Simulation Summary Card
Create `src/components/SimSummary.tsx`:
- Shown on Dashboard when simulation completes
- Key metrics: total ticks, settlement rate, total costs per agent, winner (lowest cost)
- Cost comparison bar (who paid what)

### Step 4.3: Cost Breakdown Analysis
In `src/views/AnalysisView.tsx`:
- Pie chart per agent: liquidity vs delay vs penalty costs
- Stacked bar comparison across agents
- Cost efficiency ratio (total cost / total settled value)

### Step 4.4: Payment Flow Table
- Table of ALL payments in the simulation
- Columns: tx_id, sender, receiver, amount, arrival_tick, deadline, settlement_tick, status
- Sortable by any column
- Color-code by status (settled=green, overdue=yellow, unsettled=red)

### Step 4.5: Efficiency Metrics
- Settlement rate (% of payments settled on time)
- Average delay (ticks between arrival and settlement)
- Queue utilization (avg queue size / total payments)
- Liquidity efficiency (total settled / total liquidity allocated)

## Files

| File | Action |
|------|--------|
| `src/views/ReplayView.tsx` | CREATE |
| `src/views/AnalysisView.tsx` | CREATE |
| `src/components/SimSummary.tsx` | CREATE |
| `src/components/PaymentTable.tsx` | CREATE |

## Completion Criteria
- [ ] Replay scrubber jumps to any tick with correct state
- [ ] Replay play/pause works with speed control
- [ ] Cost breakdown pie charts render per agent
- [ ] Payment flow table shows all payments with status
- [ ] Efficiency metrics calculated and displayed
- [ ] Summary card appears on completion
