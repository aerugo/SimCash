# Phase 3: Enhanced Dashboard + Events + Config Views

**Status**: Pending
**Started**: —

## Objective

Upgrade the simulation dashboard with richer visualizations, and build full-page Events and Config inspector views.

## Implementation Steps

### Step 3.1: Enhanced Balance Chart
- Area fills under lines (semi-transparent)
- Toggleable agents (click legend to show/hide)
- Hover tooltips with exact tick + dollar values
- Y-axis in dollars

### Step 3.2: Cost Progression Chart
- New line chart showing cost accumulation over ticks (not just final bar)
- Keep existing bar chart as secondary view
- Toggle between line/bar views

### Step 3.3: Queue Visualization
Create `src/components/QueueDisplay.tsx`:
- Per-agent: show pending payment count
- Color-code by urgency (ticks until deadline: green→yellow→red)
- Show total queued value

### Step 3.4: Live Tick Detail Panel
Create `src/components/TickDetail.tsx`:
- Expandable panel below controls
- Shows everything from current tick: arrivals, policy decisions, settlements, cost accruals
- Formatted with icons and colors (similar to EventLog but for single tick)

### Step 3.5: Agent Detail Modal
Create `src/components/AgentDetailModal.tsx`:
- Click an agent card → opens modal overlay
- Shows: all payments sent/received, balance over time (mini chart), cost breakdown over time
- Close on Escape or click outside

### Step 3.6: Full-Page Events View
Create `src/views/EventsView.tsx`:
- All events from entire simulation
- Filters: event type (dropdown multi-select), agent, tick range (slider)
- Search box for text search
- Grouped by tick with collapsible sections
- Event count per type summary at top

### Step 3.7: Config Inspector View
Create `src/views/ConfigView.tsx`:
- Full FFI config displayed as formatted JSON (with syntax highlighting via pre+spans)
- Payment schedule timeline visualization (horizontal bar per payment)
- Agent setup table (id, liquidity_pool, opening_balance, policy)
- Cost rates displayed with visual scale

## Files

| File | Action |
|------|--------|
| `src/components/BalanceChart.tsx` | MODIFY |
| `src/components/CostChart.tsx` | MODIFY — add line chart mode |
| `src/components/QueueDisplay.tsx` | CREATE |
| `src/components/TickDetail.tsx` | CREATE |
| `src/components/AgentDetailModal.tsx` | CREATE |
| `src/views/EventsView.tsx` | CREATE |
| `src/views/ConfigView.tsx` | CREATE |
| `src/views/DashboardView.tsx` | MODIFY — integrate new components |

## Completion Criteria
- [ ] Balance chart has area fills and toggleable agents
- [ ] Cost chart shows progression over time
- [ ] Queue visualization shows pending payments
- [ ] Tick detail panel shows current tick breakdown
- [ ] Agent detail modal shows full history
- [ ] Events view filters and searches correctly
- [ ] Config view displays full scenario setup
