# Diagnostic Frontend Development Plan

**Created**: 2025-11-02
**Status**: Planning
**Type**: New Feature - Frontend Application

---

## Executive Summary

Build a read-only React diagnostic client for exploring saved simulation runs. The application enables deep inspection of transaction lifecycles, agent behavior, and system events without running new simulations.

**Key Principle**: Frontend ONLY talks to API. No direct database or Rust FFI access.

---

## Quick Start

```bash
# Install Bun (one-time setup) - single binary, no Node.js needed
curl -fsSL https://bun.sh/install | bash

# Navigate to diagnostic frontend
cd frontend/diagnostic

# Install dependencies (20-30x faster than npm)
bun install

# Start dev server (Bun runs Vite)
bun dev

# Run tests (Bun runs Vitest)
bun test

# Run e2e tests (Bun runs Playwright)
bun test:e2e

# Build for production
bun run build
```

**Bun is all-in-one**: Package manager + test runner + script runner + TypeScript runtime in a single binary.

---

## Goals

### Primary Goals
1. **Simulation Explorer**: Browse and select from saved simulation runs
2. **Event Inspector**: View paginated, filterable event timeline (like CLI `--verbose`)
3. **Agent Dashboard**: Inspect individual agent metrics, costs, and transaction history
4. **Transaction Tracer**: Follow complete lifecycle of individual transactions
5. **Read-Only**: No simulation execution, only exploration

### Non-Goals (Phase 1)
- Real-time simulation running
- Simulation creation/configuration
- Policy editing
- Comparative analysis (multiple simulations)
- Export functionality

---

## Architecture Decisions

### Technology Stack

#### Package Manager & Runtime
- **Bun** - All-in-one JavaScript tooling
  - **Single binary**: Package manager, test runner, bundler, and runtime combined
  - **No Node.js needed**: Bun replaces Node.js entirely
  - **20-30x faster**: Package installation, script execution, and test running
  - **Native TypeScript**: Runs .ts files directly without transpilation
  - **npm-compatible**: Works with all npm packages
  - **Install**: `curl -fsSL https://bun.sh/install | bash`

#### Frontend Framework
- **React 18** with **TypeScript** (strict mode)
- **Vite** for build tooling (fast HMR, modern defaults)
- **React Router v6** for navigation
- **TanStack Query (React Query)** for server state management
  - Automatic caching, background refetching
  - Excellent for paginated/filtered data
  - Built-in loading/error states

#### UI & Styling
- **Tailwind CSS** for utility-first styling
  - Fast development, consistent design
  - Tree-shakeable (small bundle)
- **shadcn/ui** for component primitives
  - Accessible, customizable components
  - Copy-paste architecture (no dependency lock-in)
- **Lucide React** for icons

#### Data Visualization
- **Recharts** for charts (built on D3, React-friendly)
- **React Flow** for transaction network diagrams (future)

#### Testing
- **Vitest** for unit/component tests (Vite-native, fast)
- **Playwright** for e2e browser tests
- **Testing Library (React)** for component testing

#### Code Quality
- **ESLint** + **Prettier** for formatting
- **TypeScript strict mode** for type safety
- **Husky** for pre-commit hooks

### Project Structure
```
frontend/diagnostic/
├── src/
│   ├── api/               # API client (fetch wrappers)
│   ├── components/        # React components
│   │   ├── ui/           # shadcn/ui primitives
│   │   ├── layout/       # Layout components
│   │   ├── simulation/   # Simulation-specific components
│   │   ├── agent/        # Agent-specific components
│   │   └── transaction/  # Transaction-specific components
│   ├── hooks/            # Custom React hooks
│   ├── pages/            # Route pages
│   ├── types/            # TypeScript types
│   ├── utils/            # Utility functions
│   ├── App.tsx           # Root component
│   └── main.tsx          # Entry point
├── tests/
│   ├── unit/             # Vitest unit tests
│   ├── component/        # Component integration tests
│   └── e2e/              # Playwright browser tests
├── public/               # Static assets
├── playwright.config.ts  # Playwright configuration
├── vite.config.ts        # Vite configuration
├── tsconfig.json         # TypeScript configuration
├── tailwind.config.js    # Tailwind configuration
└── package.json          # Dependencies
```

### API Strategy

#### Existing Endpoints (Sufficient for Phase 1)
✅ Already available:
- `GET /simulations` - List all simulations
- `GET /simulations/{sim_id}/state` - Current state
- `GET /simulations/{sim_id}/transactions` - List transactions (with filters)
- `GET /simulations/{sim_id}/transactions/{tx_id}` - Transaction details
- `GET /simulations/{sim_id}/metrics` - System metrics
- `GET /simulations/{sim_id}/costs` - Per-agent costs
- `GET /simulations/{sim_id}/checkpoints` - List checkpoints

#### New Endpoints Required

##### 1. Simulation Metadata Endpoint
```
GET /simulations/{sim_id}
```
**Purpose**: Get complete simulation metadata (config, parameters, summary stats)

**Response**:
```json
{
  "simulation_id": "uuid",
  "created_at": "2025-11-02T10:30:00Z",
  "config": {
    "ticks_per_day": 100,
    "num_days": 5,
    "rng_seed": 12345,
    "agents": [...],
    "lsm_config": {...}
  },
  "summary": {
    "total_ticks": 500,
    "total_transactions": 15420,
    "settlement_rate": 0.98,
    "total_cost_cents": 500000,
    "duration_seconds": 45.2,
    "ticks_per_second": 11.06
  }
}
```

##### 2. Agent List Endpoint
```
GET /simulations/{sim_id}/agents
```
**Purpose**: List all agents with summary statistics

**Response**:
```json
{
  "agents": [
    {
      "agent_id": "BANK_A",
      "total_sent": 5420,
      "total_received": 4980,
      "total_settled": 5200,
      "total_dropped": 200,
      "total_cost_cents": 125000,
      "avg_balance_cents": 5000000,
      "peak_overdraft_cents": -200000,
      "credit_limit_cents": 1000000
    },
    ...
  ]
}
```

##### 3. Events Endpoint (Paginated)
```
GET /simulations/{sim_id}/events?tick=10&limit=100&offset=0&agent_id=BANK_A&event_type=Settlement
```
**Purpose**: Paginated, filterable event stream

**Query Parameters**:
- `tick` (optional): Filter to specific tick
- `tick_min`, `tick_max` (optional): Tick range
- `agent_id` (optional): Filter by agent (sender OR receiver)
- `event_type` (optional): Filter by event type
- `limit` (default: 100, max: 1000)
- `offset` (default: 0)

**Response**:
```json
{
  "events": [
    {
      "tick": 10,
      "day": 0,
      "event_type": "Arrival",
      "tx_id": "tx-123",
      "sender_id": "BANK_A",
      "receiver_id": "BANK_B",
      "amount": 100000,
      "priority": 8,
      "deadline_tick": 50,
      "timestamp": "2025-11-02T10:30:15Z"
    },
    ...
  ],
  "total": 15420,
  "limit": 100,
  "offset": 0
}
```

##### 4. Agent Timeline Endpoint
```
GET /simulations/{sim_id}/agents/{agent_id}/timeline
```
**Purpose**: Complete agent activity timeline

**Response**:
```json
{
  "agent_id": "BANK_A",
  "daily_metrics": [
    {
      "day": 0,
      "opening_balance": 5000000,
      "closing_balance": 4800000,
      "min_balance": 4500000,
      "max_balance": 5200000,
      "transactions_sent": 250,
      "transactions_received": 240,
      "total_cost_cents": 25000
    },
    ...
  ],
  "collateral_events": [
    {
      "tick": 15,
      "day": 0,
      "action": "post",
      "amount": 500000,
      "reason": "strategic",
      "balance_before": 4500000
    },
    ...
  ]
}
```

##### 5. Transaction Lifecycle Endpoint
```
GET /simulations/{sim_id}/transactions/{tx_id}/lifecycle
```
**Purpose**: Complete transaction lifecycle with all events

**Response**:
```json
{
  "transaction": {
    "tx_id": "tx-123",
    "sender_id": "BANK_A",
    "receiver_id": "BANK_B",
    "amount": 100000,
    "priority": 8,
    "arrival_tick": 10,
    "deadline_tick": 50,
    "settlement_tick": 25,
    "status": "settled",
    "delay_cost": 150,
    "amount_settled": 100000
  },
  "events": [
    {
      "tick": 10,
      "event_type": "Arrival",
      "details": {...}
    },
    {
      "tick": 11,
      "event_type": "PolicyHold",
      "details": {"reason": "insufficient_liquidity"}
    },
    {
      "tick": 25,
      "event_type": "Settlement",
      "details": {"method": "rtgs"}
    }
  ],
  "related_transactions": [
    {
      "tx_id": "tx-124",
      "relationship": "split_from",
      "split_index": 1
    }
  ]
}
```

---

## Component Architecture

### Route Structure
```
/                                    # Simulation list
/simulations/:simId                  # Simulation dashboard
/simulations/:simId/agents           # Agent list
/simulations/:simId/agents/:agentId  # Agent detail
/simulations/:simId/events           # Event timeline
/simulations/:simId/transactions/:txId # Transaction detail
```

### Core Components

#### 1. Simulation List Page
**File**: `src/pages/SimulationListPage.tsx`

**Features**:
- Table of all saved simulations
- Sortable by date, duration, transaction count
- Search/filter by config hash, seed
- Click row to navigate to simulation dashboard

**Tests**:
- Unit: Renders empty state, renders list, sorting works
- E2E: Navigate from list to detail, filter simulations

#### 2. Simulation Dashboard
**File**: `src/pages/SimulationDashboardPage.tsx`

**Features**:
- **Header**: Simulation ID, creation date, duration
- **Configuration Card**: Display full config (collapsible JSON)
- **Summary Metrics**: Settlement rate, total transactions, total cost
- **Agent Summary Table**: All agents with key metrics
- **Recent Events**: Last 20 events (link to full event timeline)
- **Navigation**: Links to agents page, events page

**Components**:
- `SimulationHeader`
- `ConfigurationCard`
- `MetricsSummaryCard`
- `AgentSummaryTable` (sortable, clickable rows)
- `RecentEventsList`

**Tests**:
- Unit: Each card renders correctly with mock data
- Component: AgentSummaryTable sorting and clicking
- E2E: Load dashboard, navigate to agent, navigate to events

#### 3. Agent List Page
**File**: `src/pages/AgentListPage.tsx`

**Features**:
- Table of all agents with summary statistics
- Sortable by sent/received/cost
- Click row to navigate to agent detail

**Components**:
- `AgentTable` (reusable from dashboard)

**Tests**:
- Unit: Renders agent list
- E2E: Navigate to agent detail

#### 4. Agent Detail Page
**File**: `src/pages/AgentDetailPage.tsx`

**Features**:
- **Agent Header**: Agent ID, total sent/received
- **Daily Metrics Chart**: Balance over time (line chart)
- **Cost Breakdown Chart**: Pie/bar chart of cost types
- **Collateral Events Timeline**: List of collateral posts/withdrawals
- **Transaction History**: Paginated table of sent/received transactions
  - Filter: sent only, received only, all
  - Filter: settled, dropped, pending
- **Queue History**: Queue depth over time (if available)

**Components**:
- `AgentHeader`
- `BalanceChart` (Recharts LineChart)
- `CostBreakdownChart` (Recharts PieChart)
- `CollateralEventsList`
- `TransactionHistoryTable` (paginated, filterable)

**Tests**:
- Unit: Each component renders with mock data
- Component: Filter and pagination work
- E2E: Load agent detail, filter transactions, view transaction

#### 5. Event Timeline Page
**File**: `src/pages/EventTimelinePage.tsx`

**Features**:
- **Filters**:
  - Tick range slider
  - Agent dropdown (filter by sender/receiver)
  - Event type dropdown
  - Search by transaction ID
- **Event List**: Paginated, virtualized list
  - Each event shows: tick, day, type, agents, amount
  - Click transaction to view detail
- **Real-time mode**: Auto-refresh (future)

**Components**:
- `EventFilters`
- `EventList` (virtualized with react-window or similar)
- `EventCard` (individual event display)

**Tests**:
- Unit: EventCard renders different event types
- Component: Filters work, pagination works
- E2E: Apply filters, click event, navigate to transaction

#### 6. Transaction Detail Page
**File**: `src/pages/TransactionDetailPage.tsx`

**Features**:
- **Transaction Header**: ID, amount, sender → receiver
- **Status Badge**: settled/pending/dropped with color
- **Timeline View**: Vertical timeline of all events
  - Arrival → Policy decisions → Settlement/Drop
  - Tick numbers on left
  - Event descriptions on right
- **Related Transactions**: If split, show parent/children
- **Cost Breakdown**: Delay cost, split cost, etc.

**Components**:
- `TransactionHeader`
- `TransactionStatusBadge`
- `TransactionTimeline` (vertical stepper)
- `RelatedTransactionsList`
- `TransactionCostBreakdown`

**Tests**:
- Unit: Each component renders
- Component: Timeline renders events in order
- E2E: Load transaction, navigate to related transaction

---

## Test-Driven Development Strategy

### Testing Pyramid

```
         /\
        /  \
       / E2E \ ← Playwright (5-10 critical paths)
      /______\
     /        \
    / Compon-  \ ← Testing Library (component integration)
   /    ent     \
  /_____________ \
 /                \
/      Unit        \ ← Vitest (pure functions, hooks)
/___________________\
```

### Test Categories

#### 1. Unit Tests (Vitest)
**Coverage**: Pure functions, custom hooks, utilities

**Examples**:
- `formatCurrency(cents: number) → string`
- `calculateSettlementRate(settled, total) → number`
- `useSimulationQuery(simId: string)` hook
- `groupEventsByTick(events: Event[]) → Map<number, Event[]>`

**Pattern**:
```typescript
// src/utils/__tests__/currency.test.ts
import { describe, it, expect } from 'vitest'
import { formatCurrency } from '../currency'

describe('formatCurrency', () => {
  it('formats cents as dollars with 2 decimals', () => {
    expect(formatCurrency(100000)).toBe('$1,000.00')
  })

  it('handles negative amounts', () => {
    expect(formatCurrency(-50000)).toBe('-$500.00')
  })

  it('handles zero', () => {
    expect(formatCurrency(0)).toBe('$0.00')
  })
})
```

#### 2. Component Tests (Testing Library + Vitest)
**Coverage**: Component integration, user interactions, data flow

**Examples**:
- `AgentSummaryTable` sorting
- `EventFilters` applying filters
- `TransactionTimeline` rendering events
- `TransactionHistoryTable` pagination

**Pattern**:
```typescript
// src/components/simulation/__tests__/AgentSummaryTable.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { AgentSummaryTable } from '../AgentSummaryTable'

describe('AgentSummaryTable', () => {
  const mockAgents = [
    { agent_id: 'BANK_A', total_sent: 100, total_cost_cents: 5000 },
    { agent_id: 'BANK_B', total_sent: 200, total_cost_cents: 3000 },
  ]

  it('renders all agents', () => {
    render(<AgentSummaryTable agents={mockAgents} />)
    expect(screen.getByText('BANK_A')).toBeInTheDocument()
    expect(screen.getByText('BANK_B')).toBeInTheDocument()
  })

  it('sorts by total_sent descending when column clicked', () => {
    render(<AgentSummaryTable agents={mockAgents} />)
    const sentHeader = screen.getByText('Total Sent')
    fireEvent.click(sentHeader)

    const rows = screen.getAllByRole('row')
    expect(rows[1]).toHaveTextContent('BANK_B') // Higher value first
  })

  it('navigates to agent detail when row clicked', () => {
    const mockNavigate = vi.fn()
    render(<AgentSummaryTable agents={mockAgents} onRowClick={mockNavigate} />)

    fireEvent.click(screen.getByText('BANK_A'))
    expect(mockNavigate).toHaveBeenCalledWith('BANK_A')
  })
})
```

#### 3. E2E Tests (Playwright)
**Coverage**: Critical user journeys, API integration, full flow

**Priority Scenarios**:
1. **Simulation Browse & Select**
   - Load simulation list
   - Click simulation
   - View dashboard
2. **Agent Inspection**
   - Navigate to agent detail
   - View balance chart
   - Filter transaction history
3. **Transaction Tracing**
   - Click transaction from event list
   - View transaction lifecycle
   - Navigate to related transactions
4. **Event Filtering**
   - Apply tick range filter
   - Apply agent filter
   - Apply event type filter
   - Results update correctly
5. **Error Handling**
   - Load non-existent simulation (404)
   - API error (500)
   - Empty simulation (no data)

**Pattern**:
```typescript
// tests/e2e/simulation-dashboard.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Simulation Dashboard', () => {
  test('loads simulation and displays summary metrics', async ({ page }) => {
    // Navigate to simulation list
    await page.goto('/')

    // Wait for simulations to load
    await expect(page.locator('table tbody tr')).toHaveCount(3)

    // Click first simulation
    await page.locator('table tbody tr').first().click()

    // Verify dashboard loaded
    await expect(page.locator('h1')).toContainText('Simulation')

    // Check metrics are displayed
    await expect(page.locator('[data-testid="settlement-rate"]')).toBeVisible()
    await expect(page.locator('[data-testid="total-transactions"]')).toBeVisible()

    // Check agent table has rows
    await expect(page.locator('[data-testid="agent-table"] tbody tr')).not.toHaveCount(0)
  })

  test('navigates to agent detail from agent table', async ({ page }) => {
    await page.goto('/simulations/test-sim-id')

    // Click first agent row
    await page.locator('[data-testid="agent-table"] tbody tr').first().click()

    // Verify navigation to agent page
    await expect(page).toHaveURL(/\/agents\//)
    await expect(page.locator('h1')).toContainText('BANK_')
  })

  test('shows recent events and links to full timeline', async ({ page }) => {
    await page.goto('/simulations/test-sim-id')

    // Check recent events section
    await expect(page.locator('[data-testid="recent-events"]')).toBeVisible()

    // Click "View All Events" link
    await page.locator('[data-testid="view-all-events"]').click()

    // Verify navigation to events page
    await expect(page).toHaveURL(/\/events/)
    await expect(page.locator('h1')).toContainText('Events')
  })
})
```

### Test Data Strategy

#### Mock Data Location
- `tests/fixtures/simulations.json` - Mock simulation list
- `tests/fixtures/simulation-detail.json` - Mock dashboard data
- `tests/fixtures/events.json` - Mock event timeline
- `tests/fixtures/transactions.json` - Mock transaction data
- `tests/fixtures/agents.json` - Mock agent data

#### Mock Server (MSW - Mock Service Worker)
For component tests, use MSW to mock API responses:

```typescript
// tests/mocks/handlers.ts
import { rest } from 'msw'

export const handlers = [
  rest.get('/api/simulations', (req, res, ctx) => {
    return res(ctx.json({ simulations: [...] }))
  }),
  rest.get('/api/simulations/:simId', (req, res, ctx) => {
    return res(ctx.json({ simulation_id: req.params.simId, ... }))
  }),
]
```

#### Real API Tests (Playwright)
For e2e tests, use real API with test database:
- Seed database with known test data before tests
- Clean up after tests
- Use fixtures in `examples/configs/` as test scenarios

---

## Development Phases

### Phase 0: Setup & Infrastructure (TDD Foundation)
**Goal**: Working dev environment with testing infrastructure

**Tasks**:
1. Initialize Vite + React + TypeScript project
   - Test: `bun run dev` starts dev server
2. Configure Tailwind CSS
   - Test: Apply utility class, verify styling
3. Install shadcn/ui
   - Test: Render Button component
4. Configure Vitest
   - Test: Write + run simple unit test
5. Configure Playwright
   - Test: Write + run simple e2e test
6. Set up React Router
   - Test: Navigate between routes
7. Set up TanStack Query
   - Test: Fetch mock data, verify caching
8. Create API client base
   - Test: Mock fetch, verify error handling

**Files**:
- `frontend/diagnostic/package.json`
- `frontend/diagnostic/bunfig.toml` (optional Bun config)
- `frontend/diagnostic/vite.config.ts`
- `frontend/diagnostic/tsconfig.json`
- `frontend/diagnostic/tailwind.config.js`
- `frontend/diagnostic/playwright.config.ts`
- `frontend/diagnostic/src/api/client.ts`

**Acceptance Criteria**:
- ✅ Dev server runs with `bun dev` (Bun runs Vite)
- ✅ Tests run with `bun test` (Bun runs Vitest)
- ✅ E2E tests run with `bun test:e2e` (Bun runs Playwright)
- ✅ TypeScript strict mode enabled, no errors
- ✅ Tailwind utilities work correctly
- ✅ shadcn/ui Button component renders
- ✅ All dependencies install in seconds with `bun install`

---

### Phase 1: API Endpoints (Backend TDD)
**Goal**: Implement missing API endpoints with tests

#### Task 1.1: Simulation Metadata Endpoint
**Test First** (Python):
```python
# api/tests/integration/test_diagnostic_endpoints.py
def test_get_simulation_metadata(client, sample_simulation):
    response = client.get(f"/simulations/{sample_simulation.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["simulation_id"] == sample_simulation.id
    assert "config" in data
    assert "summary" in data
    assert data["summary"]["total_ticks"] == 500
```

**Implementation**:
- Add route to `api/payment_simulator/api/main.py`
- Query database for simulation metadata
- Combine config + summary stats

**Files**:
- `api/payment_simulator/api/main.py` (add route)
- `api/payment_simulator/persistence/queries.py` (add query)
- `api/tests/integration/test_diagnostic_endpoints.py`

#### Task 1.2: Agent List Endpoint
**Test First**:
```python
def test_get_agent_list(client, sample_simulation):
    response = client.get(f"/simulations/{sample_simulation.id}/agents")
    assert response.status_code == 200
    data = response.json()
    assert len(data["agents"]) == 3
    assert data["agents"][0]["agent_id"] == "BANK_A"
    assert "total_sent" in data["agents"][0]
```

**Implementation**:
- Aggregate daily_agent_metrics by agent_id
- Join with transaction counts
- Return sorted list

#### Task 1.3: Events Endpoint (Paginated)
**Test First**:
```python
def test_get_events_paginated(client, sample_simulation):
    response = client.get(
        f"/simulations/{sample_simulation.id}/events",
        params={"limit": 10, "offset": 0}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 10
    assert data["total"] > 10
    assert data["limit"] == 10
    assert data["offset"] == 0

def test_get_events_filtered_by_agent(client, sample_simulation):
    response = client.get(
        f"/simulations/{sample_simulation.id}/events",
        params={"agent_id": "BANK_A"}
    )
    data = response.json()
    for event in data["events"]:
        assert event["sender_id"] == "BANK_A" or event["receiver_id"] == "BANK_A"
```

**Implementation**:
- This is complex - events are reconstructed from transactions + collateral_events + lsm_cycles
- Need to union multiple tables, filter, paginate
- Consider caching events for performance

**Alternative**:
- Add `simulation_events` table during simulation run
- Persist events as they happen
- Query this table directly (much faster)

#### Task 1.4: Agent Timeline Endpoint
**Test First**:
```python
def test_get_agent_timeline(client, sample_simulation):
    response = client.get(
        f"/simulations/{sample_simulation.id}/agents/BANK_A/timeline"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == "BANK_A"
    assert len(data["daily_metrics"]) == 5  # 5 days
    assert len(data["collateral_events"]) > 0
```

**Implementation**:
- Query daily_agent_metrics for agent
- Query collateral_events for agent
- Return combined timeline

#### Task 1.5: Transaction Lifecycle Endpoint
**Test First**:
```python
def test_get_transaction_lifecycle(client, sample_simulation):
    tx_id = create_test_transaction(sample_simulation)
    response = client.get(
        f"/simulations/{sample_simulation.id}/transactions/{tx_id}/lifecycle"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["transaction"]["tx_id"] == tx_id
    assert len(data["events"]) > 0
    assert data["events"][0]["event_type"] == "Arrival"
```

**Implementation**:
- Get transaction from transactions table
- Reconstruct events (arrival, policy decisions, settlement)
- Find related transactions (splits)

**Acceptance Criteria**:
- ✅ All endpoints have passing tests
- ✅ Pagination works correctly
- ✅ Filters work correctly
- ✅ 404 handling for non-existent resources
- ✅ Performance acceptable (<500ms for typical queries)

---

### Phase 2: Core Frontend Pages (Frontend TDD)

#### Task 2.1: Simulation List Page
**Test First** (E2E):
```typescript
// tests/e2e/simulation-list.spec.ts
test('loads and displays simulation list', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('h1')).toContainText('Simulations')
  await expect(page.locator('table tbody tr')).not.toHaveCount(0)
})

test('navigates to simulation dashboard on row click', async ({ page }) => {
  await page.goto('/')
  await page.locator('table tbody tr').first().click()
  await expect(page).toHaveURL(/\/simulations\//)
})
```

**Implementation**:
1. Create `src/pages/SimulationListPage.tsx`
2. Create `src/api/simulations.ts` (API client)
3. Use TanStack Query for data fetching
4. Create `SimulationTable` component
5. Add route to App.tsx

**Component Test**:
```typescript
// src/components/simulation/__tests__/SimulationTable.test.tsx
test('renders simulation rows', () => {
  const sims = [{ simulation_id: 'sim1', created_at: '...' }]
  render(<SimulationTable simulations={sims} />)
  expect(screen.getByText('sim1')).toBeInTheDocument()
})
```

#### Task 2.2: Simulation Dashboard Page
**Test First** (E2E):
```typescript
test('displays simulation summary', async ({ page }) => {
  await page.goto('/simulations/test-sim-id')
  await expect(page.locator('[data-testid="settlement-rate"]')).toContainText('98%')
  await expect(page.locator('[data-testid="total-transactions"]')).toContainText('15,420')
})

test('displays agent summary table', async ({ page }) => {
  await page.goto('/simulations/test-sim-id')
  const rows = page.locator('[data-testid="agent-table"] tbody tr')
  await expect(rows).not.toHaveCount(0)
})
```

**Implementation**:
1. Create `src/pages/SimulationDashboardPage.tsx`
2. Create component hierarchy:
   - `SimulationHeader`
   - `MetricsSummaryCard`
   - `ConfigurationCard`
   - `AgentSummaryTable`
   - `RecentEventsList`
3. Add API hooks: `useSimulation()`, `useAgents()`
4. Style with Tailwind

**Component Tests**:
```typescript
test('MetricsSummaryCard displays all metrics', () => {
  const metrics = { settlement_rate: 0.98, total_transactions: 15420 }
  render(<MetricsSummaryCard metrics={metrics} />)
  expect(screen.getByText('98%')).toBeInTheDocument()
})
```

#### Task 2.3: Agent Detail Page
**Test First** (E2E):
```typescript
test('displays agent metrics and charts', async ({ page }) => {
  await page.goto('/simulations/test-sim-id/agents/BANK_A')
  await expect(page.locator('h1')).toContainText('BANK_A')
  await expect(page.locator('[data-testid="balance-chart"]')).toBeVisible()
  await expect(page.locator('[data-testid="cost-breakdown"]')).toBeVisible()
})

test('filters transaction history', async ({ page }) => {
  await page.goto('/simulations/test-sim-id/agents/BANK_A')
  await page.selectOption('[data-testid="tx-filter"]', 'sent')
  await page.waitForLoadState('networkidle')
  // Verify only sent transactions shown
})
```

**Implementation**:
1. Create `src/pages/AgentDetailPage.tsx`
2. Create charts:
   - `BalanceChart` (Recharts LineChart)
   - `CostBreakdownChart` (Recharts PieChart)
3. Create `TransactionHistoryTable` with filters
4. Add API hooks: `useAgentTimeline()`, `useTransactions()`

**Component Tests**:
```typescript
test('BalanceChart renders with data', () => {
  const data = [{ day: 0, balance: 5000000 }, { day: 1, balance: 4800000 }]
  render(<BalanceChart data={data} />)
  expect(screen.getByTestId('balance-chart')).toBeInTheDocument()
})
```

#### Task 2.4: Event Timeline Page
**Test First** (E2E):
```typescript
test('displays paginated events', async ({ page }) => {
  await page.goto('/simulations/test-sim-id/events')
  const events = page.locator('[data-testid="event-card"]')
  await expect(events).toHaveCount(100) // Default page size
})

test('filters events by agent', async ({ page }) => {
  await page.goto('/simulations/test-sim-id/events')
  await page.selectOption('[data-testid="agent-filter"]', 'BANK_A')
  await page.waitForLoadState('networkidle')
  // Verify filtered results
})

test('navigates to transaction on click', async ({ page }) => {
  await page.goto('/simulations/test-sim-id/events')
  await page.locator('[data-testid="event-card"]').first().click()
  await expect(page).toHaveURL(/\/transactions\//)
})
```

**Implementation**:
1. Create `src/pages/EventTimelinePage.tsx`
2. Create `EventFilters` component
3. Create `EventList` component (virtualized)
4. Create `EventCard` component (different layouts per event type)
5. Add API hooks: `useEvents()` with pagination

**Component Tests**:
```typescript
test('EventCard renders Arrival event', () => {
  const event = { event_type: 'Arrival', tx_id: 'tx1', amount: 100000 }
  render(<EventCard event={event} />)
  expect(screen.getByText('Arrival')).toBeInTheDocument()
  expect(screen.getByText('$1,000.00')).toBeInTheDocument()
})
```

#### Task 2.5: Transaction Detail Page
**Test First** (E2E):
```typescript
test('displays transaction lifecycle', async ({ page }) => {
  await page.goto('/simulations/test-sim-id/transactions/tx-123')
  await expect(page.locator('h1')).toContainText('Transaction')
  await expect(page.locator('[data-testid="timeline"]')).toBeVisible()
  const events = page.locator('[data-testid="timeline-event"]')
  await expect(events).not.toHaveCount(0)
})

test('shows related transactions if split', async ({ page }) => {
  await page.goto('/simulations/test-sim-id/transactions/tx-123')
  await expect(page.locator('[data-testid="related-transactions"]')).toBeVisible()
})
```

**Implementation**:
1. Create `src/pages/TransactionDetailPage.tsx`
2. Create `TransactionTimeline` component (vertical stepper)
3. Create `TransactionStatusBadge` component
4. Create `RelatedTransactionsList` component
5. Add API hooks: `useTransactionLifecycle()`

**Component Tests**:
```typescript
test('TransactionTimeline renders events in order', () => {
  const events = [
    { tick: 10, event_type: 'Arrival' },
    { tick: 15, event_type: 'Settlement' }
  ]
  render(<TransactionTimeline events={events} />)
  const items = screen.getAllByTestId('timeline-event')
  expect(items[0]).toHaveTextContent('Arrival')
  expect(items[1]).toHaveTextContent('Settlement')
})
```

**Acceptance Criteria**:
- ✅ All pages render without errors
- ✅ Navigation between pages works
- ✅ API data fetching works
- ✅ Loading states shown
- ✅ Error states handled
- ✅ All component tests pass
- ✅ All e2e tests pass

---

### Phase 3: Polish & Error Handling

#### Task 3.1: Loading States
- Add skeleton loaders for all data-loading components
- Consistent loading UI across app

#### Task 3.2: Error States
- 404 pages for missing simulations/agents/transactions
- API error handling (500, network errors)
- Empty states (no simulations, no events)

#### Task 3.3: Responsive Design
- Mobile-friendly layouts
- Responsive tables (horizontal scroll or stacked)
- Touch-friendly interactions

#### Task 3.4: Performance Optimization
- Virtual scrolling for long lists
- Debounced filters
- Optimistic updates where applicable
- Code splitting by route

#### Task 3.5: Accessibility
- Keyboard navigation
- ARIA labels
- Screen reader support
- Focus management

**Acceptance Criteria**:
- ✅ Lighthouse score > 90 (performance, accessibility)
- ✅ No console errors
- ✅ Smooth interactions on mobile
- ✅ Keyboard navigation works
- ✅ Screen reader compatible

---

## Success Criteria

### Functional Requirements
- ✅ Browse list of saved simulations
- ✅ View simulation dashboard with summary metrics
- ✅ View list of agents with summary statistics
- ✅ View detailed agent metrics, charts, and transaction history
- ✅ View paginated, filterable event timeline
- ✅ Filter events by tick range, agent, event type
- ✅ View complete transaction lifecycle
- ✅ Navigate between related transactions (splits)
- ✅ All interactions use API only (no direct DB/FFI access)

### Non-Functional Requirements
- ✅ TypeScript strict mode, no type errors
- ✅ Unit test coverage > 80%
- ✅ Component test coverage > 70%
- ✅ E2E tests cover critical paths
- ✅ Page load time < 2s on broadband
- ✅ API response time < 500ms (95th percentile)
- ✅ Lighthouse performance score > 90
- ✅ Lighthouse accessibility score > 90

### Developer Experience
- ✅ Clear component structure
- ✅ Consistent naming conventions
- ✅ Well-documented API client
- ✅ Easy to add new pages/components
- ✅ Fast dev server (HMR < 500ms)

---

## Risk Assessment

### Technical Risks

#### 1. Events Table Performance
**Risk**: Querying events from multiple tables could be slow

**Mitigation**:
- Add `simulation_events` table during simulation run
- Index on (simulation_id, tick, agent_id, event_type)
- Consider materialized view

#### 2. Large Simulations
**Risk**: Simulations with millions of transactions could overwhelm UI

**Mitigation**:
- Aggressive pagination (max 100 items)
- Virtual scrolling for long lists
- Server-side filtering only
- Consider data sampling for charts

#### 3. Complex Transaction Lifecycles
**Risk**: Reconstructing lifecycle from multiple tables is complex

**Mitigation**:
- Create helper query in persistence layer
- Cache results in memory
- Pre-compute common queries

### Timeline Risks

#### 1. API Endpoint Development
**Estimate**: 3-5 days
**Risk**: Medium (database queries can be complex)

**Mitigation**:
- Start with simplest endpoints
- Parallelize with frontend work
- Use mock data initially

#### 2. Frontend Component Development
**Estimate**: 5-7 days
**Risk**: Low (standard React patterns)

**Mitigation**:
- Use shadcn/ui for components
- Follow existing patterns
- Start with simple pages

#### 3. Testing
**Estimate**: 2-3 days
**Risk**: Medium (e2e tests can be flaky)

**Mitigation**:
- Write tests alongside components
- Use MSW for stable component tests
- Retry logic for e2e tests

---

## Future Enhancements (Phase 2+)

### 1. Real-Time Simulation Running
- Add WebSocket support
- Stream events in real-time
- Live chart updates
- Pause/resume controls

### 2. Advanced Visualizations
- Transaction flow network diagram (React Flow)
- Heatmaps for agent activity
- 3D queue depth visualization
- Animated timeline playback

### 3. Comparative Analysis
- Select multiple simulations
- Side-by-side comparison
- Diff metrics
- Diff configurations

### 4. Export & Reporting
- Export to CSV
- Generate PDF reports
- Share simulation links
- Embed charts

### 5. Policy Debugging
- View policy decisions
- Compare actual vs expected behavior
- Policy diff view
- LLM-generated policy suggestions

---

## References

### Key Files
- `/Users/hugi/GitRepos/cashman/api/payment_simulator/api/main.py` - Existing API
- `/Users/hugi/GitRepos/cashman/api/payment_simulator/persistence/models.py` - DB schema
- `/Users/hugi/GitRepos/cashman/api/payment_simulator/cli/output.py` - CLI verbose mode
- `/Users/hugi/GitRepos/cashman/examples/configs/minimal.yaml` - Example config

### Documentation
- [React Documentation](https://react.dev)
- [TanStack Query](https://tanstack.com/query)
- [Tailwind CSS](https://tailwindcss.com)
- [shadcn/ui](https://ui.shadcn.com)
- [Playwright](https://playwright.dev)
- [Vitest](https://vitest.dev)

---

**Next Steps**:
1. Review this plan with team
2. Set up Phase 0 (infrastructure)
3. Implement Phase 1 (API endpoints)
4. Begin Phase 2 (frontend pages)

**Estimated Timeline**: 2-3 weeks for Phase 1-2 with one developer
