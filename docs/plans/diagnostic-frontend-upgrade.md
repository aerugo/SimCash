# Diagnostic Frontend Upgrade Plan

**Created**: 2025-11-11  
**Status**: Planning  
**Priority**: High  
**Goal**: Upgrade diagnostic frontend to match and exceed verbose CLI capabilities

---

## Executive Summary

The verbose CLI tool (`payment-sim run --verbose`) provides comprehensive real-time diagnostics that far exceed what the current diagnostic frontend offers. This plan details bringing the frontend to feature parity with the CLI and adding web-specific enhancements.

**Key Finding**: The CLI uses a unified `display_tick_verbose_output()` function that works for both live and replay modes via the `StateProvider` protocol. The frontend should follow the same pattern.

---

## Current State Analysis

### Verbose CLI Output (12 Major Sections)

The CLI displays rich diagnostic information categorized into:

1. **Transaction Arrivals** - TX ID, Sender→Receiver, Amount, Priority (HIGH/MED/LOW), Deadline tick
2. **Near-Deadline Warnings** - Transactions within 2 ticks of deadline  
3. **Policy Decisions** - Submit/Hold/Drop/Split with reasons, grouped by agent
4. **Settlement Details** - Categorized by mechanism (RTGS/LSM Bilateral/LSM Cycle)
5. **Queued RTGS** - Transactions in Queue 2 with details
6. **LSM Cycle Visualization** - Cycle diagram, transaction details, liquidity metrics
7. **Collateral Activity** - Post/Withdraw events with reasons
8. **Scenario Events** - Custom scenario execution details
9. **Overdue Transactions** - Went overdue events, settled while overdue, cost summary
10. **Agent Financial Stats** - Comprehensive table with balance, credit, liquidity, headroom, costs
11. **Agent State Details** - Queue 1 and Queue 2 contents with transaction details
12. **Cost Breakdown** - Per-agent costs by category
13. **Tick Summary** - One-line summary (arrivals | settlements | LSM | queued)

### Current Frontend Capabilities

**SimulationDashboardPage**:
- Basic config (ticks_per_day, num_days, seed, agents)
- Summary metrics (total_ticks, settlement_rate, total_cost)
- Agent list with minimal info
- Navigation links

**EventTimelinePage**:
- Paginated event cards with basic info
- Filters (tick range, day, agent, tx, event type)
- Keyboard navigation
- CSV export

**Major Gaps**:
- No transaction arrival details visualization
- No policy decision tracking
- No settlement mechanism breakdown
- No LSM cycle visualization  
- No agent financial stats
- No queue contents view
- No cost breakdown
- No overdue tracking
- No near-deadline warnings

### Available Backend Data

**Event Types** (17 total, all stored in `simulation_events` table):
- Arrival, PolicySubmit, PolicyHold, PolicyDrop, PolicySplit
- Settlement, QueuedRtgs, LsmBilateralOffset, LsmCycleSettlement
- CollateralPost, CollateralWithdraw, CostAccrual
- TransactionWentOverdue, OverdueTransactionSettled
- TransactionReprioritized, EndOfDay, ScenarioEventExecuted

**API Endpoints** (existing):
- GET /simulations/{id} - metadata
- GET /simulations/{id}/events - paginated with filters
- GET /simulations/{id}/agents - agent summary
- GET /simulations/{id}/transactions - transaction list
- GET /simulations/{id}/costs - per-agent cost breakdown
- GET /simulations/{id}/metrics - system metrics

**Missing API Endpoints** (need to add):
- Agent queue contents
- Transactions near deadline
- Overdue transactions
- Tick-specific state snapshots

---

## Implementation Plan

### Phase 1: API Enhancements (Week 1, 3-4 days)

Add endpoints to match StateProvider capabilities:

1. **GET /simulations/{id}/agents/{agentId}/queues**
   - Queue 1 and Queue 2 contents
   - Transaction details for each queued item
   - Total value calculations

2. **GET /simulations/{id}/transactions/near-deadline?within_ticks=2**
   - Transactions approaching deadline
   - Countdown information

3. **GET /simulations/{id}/transactions/overdue**
   - All overdue transactions
   - Cost breakdown
   - Ticks overdue

4. **GET /simulations/{id}/ticks/{tick}/state**
   - Complete state snapshot at specific tick
   - Agent balances, queues, costs

**Implementation**: Add routes in `api/main.py`, query Orchestrator for live sims, database for persisted sims

### Phase 2: Enhanced Event Visualization (Week 2, 5-6 days)

Build rich event cards based on event type:

**Components**:
- `ArrivalEventCard` - TX details with priority badge, deadline countdown
- `PolicyDecisionCard` - Decision type with icon, reason
- `SettlementCard` - Method badge, timing info
- `LsmBilateralCard` - Both TXs, bidirectional arrow, amounts
- `LsmCycleCard` - Cycle diagram, each TX, liquidity metrics
- `CollateralEventCard` - Action, amount, reason, new total
- `OverdueEventCard` - Costs, warnings, status
- `EventCategoryFilter` - Filter by category
- `EventTimeline` - Visual timeline view (optional)

**Enhancement Strategy**: Extend existing EventTimelinePage with type-specific rendering

### Phase 3: Agent Dashboard (Week 3, 6-7 days)

New page: `/simulations/{simId}/agents/{agentId}`

**Sections**:
1. **Financial Overview** - Balance, credit usage, liquidity, headroom (with gauge)
2. **Cost Breakdown** - Total + category breakdown with chart
3. **Queue 1 Card** - Internal queue with table of transactions
4. **Queue 2 Card** - RTGS queue filtered to this agent  
5. **Activity Timeline** - Daily metrics chart
6. **Transaction History** - Recent sent/received

**Components**:
- `AgentFinancialOverview` - Key metrics with visual indicators
- `AgentCostBreakdown` - Pie/bar chart of costs
- `AgentQueueCard` - Reusable for both queues
- `AgentActivityTimeline` - Recharts line/area chart
- `TransactionTable` - Sortable, filterable table

### Phase 4: LSM Cycle Visualization (Week 4, 5-6 days)

**Component**: `LsmCycleVisualizer`

**Features**:
- Cycle graph (nodes=agents, edges=transactions)
- Interactive (hover, click)
- Metrics panel (total value, max outflow, liquidity saved, efficiency)
- Transaction details table
- Net position analysis

**Library Options**: D3.js, React Flow, or Cytoscape.js

**Integration**: Embedded in event cards, dedicated LSM analysis page

### Phase 5: Deadline Tracking (Week 5, 3-4 days)

**Components**:
- `DeadlineWarningBanner` - Global alert banner
- `NearDeadlineTransactionsCard` - Table with countdown
- `OverdueTransactionsCard` - Cost-focused table
- `DeadlineStatusBadge` - Reusable status indicator

**Placement**: Banner on all pages, cards on dashboard, badges everywhere

### Phase 6: Metrics Dashboard (Week 6, 4-5 days)

New page: `/simulations/{simId}/metrics`

**Sections**:
1. System Health - Settlement rate gauge, delay charts, queue sizes
2. Throughput Metrics - Arrivals, settlements, LSM effectiveness
3. Agent Performance Comparison - Multi-agent table
4. Cost Analysis - Pie chart, bar chart, trend line
5. Performance Diagnostics - Tick execution time (if available)

**Charts**: Gauges, line/area for trends, bar for comparisons, pie for breakdown

### Phase 7: Enhanced Transaction Detail (Week 7, 4-5 days)

Enhance existing TransactionDetailPage:

**Additions**:
- Lifecycle timeline (visual)
- Cost summary card (if costs incurred)
- Related transactions tree (for splits)
- Settlement details (LSM context)
- Agent context (sender balance history)

### Phase 8: Real-Time Updates (Week 8, 5-6 days)

**Features**:
- WebSocket or SSE for live event stream
- Auto-refresh metrics
- Animations (transaction flows, queue updates, balance changes)
- Activity indicators (tick counter, events/sec)

**Library**: Framer Motion or React Spring for animations

### Phase 9: Advanced Filtering (Week 9, 4-5 days)

**Features**:
- Global search bar (TX ID, agent, amount range, event type)
- Advanced filters modal (multi-select, sliders)
- Saved views (localStorage + URL params)
- Pattern detection (optional: recurring issues)

### Phase 10: Mobile & Accessibility (Week 10, 6-7 days)

**Focus**:
- Responsive layouts (desktop/tablet/mobile)
- Accessibility audit and fixes (ARIA, keyboard nav, screen readers)
- Performance optimization (virtual scroll, lazy load, code split)
- Testing across devices and browsers

---

## Technology Stack

**Current** (keep):
- React 18 + TypeScript
- Vite
- Bun (package manager, test runner)
- Tailwind CSS
- TanStack Query
- React Router
- Vitest + Testing Library + Playwright

**Additions**:
- **Charts**: Recharts (use more extensively)
- **Animations**: Framer Motion or React Spring
- **Graph Viz**: React Flow or D3.js
- **WebSocket**: Native API or Socket.io
- **Virtual Scroll**: @tanstack/react-virtual
- **State Management**: Zustand (only if needed)

---

## Design Principles

1. **Clarity Over Flash** - Information density like Bloomberg terminal, clear hierarchy
2. **Performance First** - Virtual scroll, lazy load, optimize re-renders
3. **Data Integrity** - Money=i64 cents, ISO timestamps, type safety
4. **Accessibility** - Keyboard nav, screen readers, high contrast
5. **Responsive** - Desktop-first but mobile-capable

---

## Success Metrics

**Functionality**:
- [ ] All 12 verbose sections represented
- [ ] All 17 event types visualized  
- [ ] All StateProvider methods accessible
- [ ] Feature parity with CLI

**Performance**:
- [ ] Initial load < 2s
- [ ] Time to interactive < 3s
- [ ] 1000 events render in < 500ms
- [ ] 60fps animations

**Quality**:
- [ ] 90%+ test coverage
- [ ] Zero TS errors
- [ ] Zero critical accessibility issues
- [ ] Lighthouse: 90+ performance, 100 accessibility

---

## Schedule

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| 1. API | 4 days | 4 endpoints, tests |
| 2. Events | 6 days | Enhanced cards, filters |
| 3. Agent Dashboard | 7 days | Agent detail page |
| 4. LSM Viz | 6 days | Cycle graph |
| 5. Deadlines | 4 days | Warning system |
| 6. Metrics | 5 days | Metrics dashboard |
| 7. TX Detail | 5 days | Enhanced page |
| 8. Real-Time | 6 days | WebSocket, animations |
| 9. Filtering | 5 days | Search, saved views |
| 10. Polish | 7 days | Mobile, a11y |

**Total**: 10 weeks (55 days) for 1-2 developers

**Milestones**:
- Week 3: Core features (events, agents)
- Week 6: CLI feature parity
- Week 10: Production-ready

---

## Risks & Mitigation

1. **API Performance** → Add indexes, caching, pagination, views
2. **Graph Complexity** → Zoom controls, simplify view, tabular fallback
3. **Real-Time Load** → Throttling, batching, pause option
4. **Browser Performance** → Virtual scroll, lazy load, performance mode
5. **Mobile Experience** → Mobile-first design, simplified visuals, progressive enhancement

---

## Testing Strategy

- **Unit**: Utilities, hooks, transformations
- **Component**: Isolated rendering, interactions, edge cases
- **Integration**: API clients, data fetching, multi-component
- **E2E**: Critical flows, different states, data sizes
- **Accessibility**: axe-core automated + manual testing
- **Performance**: Lighthouse CI, render timings, fps tests

---

## Future Enhancements (Post-Launch)

- Simulation comparison (side-by-side)
- Custom dashboards (drag-and-drop)
- Alerts & notifications (email/Slack)
- Data export (Excel, PDF, JSON)
- Collaboration (annotations, comments)
- Historical analysis (trends, anomalies)
- Policy debugging ("why did this happen?")

---

## Next Steps

1. **Review & Approve** this plan
2. **Setup project board** with tasks
3. **Begin Phase 1** (API enhancements)
4. **Weekly demos** to stakeholders
5. **Iterate based on feedback**

---

**Status**: Ready for Review  
**Version**: 1.0  
**Last Updated**: 2025-11-11
