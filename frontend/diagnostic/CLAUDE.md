# Diagnostic Frontend - Claude Code Guide

**Last Updated**: 2025-11-02
**Status**: Active Development
**Layer**: Frontend (React + TypeScript)

---

## Quick Context

This is a **read-only diagnostic client** for exploring saved simulation runs. It's built with React 18, TypeScript, and Tailwind CSS. The application provides deep inspection of transaction lifecycles, agent behavior, and system events.

**Your role**: You're a frontend engineer who writes clean, type-safe React code following modern best practices. You understand that this is a diagnostic tool, not a real-time dashboard - clarity and debuggability trump flashiness.

---

## Quick Start

```bash
# Install Bun (one-time setup) - single binary, no Node.js needed
curl -fsSL https://bun.sh/install | bash

# Install dependencies (20-30x faster than npm)
bun install

# Start development server (Bun runs Vite)
bun dev

# Run tests (Bun runs Vitest)
bun test

# Run e2e tests
bun test:e2e

# Type check
bun run typecheck
```

**Why Bun?**
- **All-in-one**: Package manager, test runner, bundler, and runtime in a single binary
- **Native TypeScript**: Runs .ts files directly, no transpilation needed
- **Fast**: 20-30x faster installs, instant script execution
- **npm-compatible**: Drop-in replacement, works with all npm packages

---

## 🔴 CRITICAL RULES - NEVER VIOLATE

### 1. API-Only Communication
```typescript
// ✅ CORRECT - Always use API client
import { fetchSimulation } from '@/api/simulations'

const { data } = useQuery({
  queryKey: ['simulation', simId],
  queryFn: () => fetchSimulation(simId),
})

// ❌ NEVER DO THIS - No direct database or FFI access
import duckdb from 'duckdb' // NO!
import { Orchestrator } from 'payment-simulator' // NO!
```

**Why**: The frontend must remain decoupled from backend implementation details. All data flows through the FastAPI layer.

**Rule**: Every piece of data comes from the `/api` endpoints. Period.

### 2. Money is ALWAYS i64 Cents (Even in Display)
```typescript
// ✅ CORRECT - Keep cents until display layer
interface Transaction {
  amount: number // cents (i64 from backend)
}

function formatCurrency(cents: number): string {
  const dollars = cents / 100
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(dollars)
}

// Usage
<span>{formatCurrency(transaction.amount)}</span> // "$1,000.00"

// ❌ NEVER DO THIS - Storing as float
interface Transaction {
  amount: number // dollars ← NO! This loses precision
}
```

**Why**: The backend uses i64 cents everywhere to avoid floating-point errors. Frontend must preserve this precision until the final display moment.

**Rule**:
- All amount fields are `number` (representing i64 cents)
- Convert to dollars ONLY in format functions
- NEVER do arithmetic on dollar values
- Use `formatCurrency()` utility for display

### 3. TypeScript Strict Mode - No `any`
```typescript
// ✅ CORRECT - Fully typed
interface SimulationResponse {
  simulation_id: string
  summary: {
    total_ticks: number
    settlement_rate: number
  }
}

async function fetchSimulation(id: string): Promise<SimulationResponse> {
  const response = await fetch(`/api/simulations/${id}`)
  return response.json() as SimulationResponse
}

// ❌ NEVER DO THIS
async function fetchSimulation(id: string): Promise<any> { // NO!
  const response = await fetch(`/api/simulations/${id}`)
  return response.json()
}
```

**Why**: TypeScript is our safety net. `any` defeats the entire purpose of types.

**Rules**:
- `tsconfig.json` has `"strict": true`
- NEVER use `any` - use `unknown` if truly unknown
- Define interfaces for all API responses
- Use type guards for runtime validation
- Prefer `interface` over `type` for objects

### 4. Components Are Pure and Testable
```typescript
// ✅ CORRECT - Pure component, easy to test
interface TransactionCardProps {
  transaction: Transaction
  onClick: (id: string) => void
}

export function TransactionCard({ transaction, onClick }: TransactionCardProps) {
  return (
    <div onClick={() => onClick(transaction.tx_id)}>
      <h3>{transaction.tx_id}</h3>
      <p>{formatCurrency(transaction.amount)}</p>
    </div>
  )
}

// ❌ NEVER DO THIS - Impure, untestable
export function TransactionCard({ transactionId }: { transactionId: string }) {
  const [data, setData] = useState(null) // Mixing concerns

  useEffect(() => {
    fetch(`/api/transactions/${transactionId}`) // API call in component
      .then(r => r.json())
      .then(setData)
  }, [transactionId])

  return <div>{data?.amount}</div> // No type safety
}
```

**Why**: Components should receive props, render UI. Data fetching and state management happen at the page level or in custom hooks.

**Rules**:
- Data fetching ONLY in pages or custom hooks
- Components receive data via props
- Use TanStack Query for server state
- Keep components pure (same props = same output)

---

## Architecture Overview

```
src/
├── api/              ← API client layer
│   ├── client.ts     ← Base fetch wrapper with error handling
│   ├── simulations.ts ← Simulation endpoints
│   ├── agents.ts     ← Agent endpoints
│   ├── transactions.ts ← Transaction endpoints
│   └── events.ts     ← Event endpoints
├── components/       ← React components
│   ├── ui/          ← shadcn/ui primitives (Button, Card, etc.)
│   ├── layout/      ← Layout components (Header, Sidebar, etc.)
│   ├── simulation/  ← Simulation-specific components
│   ├── agent/       ← Agent-specific components
│   ├── transaction/ ← Transaction-specific components
│   └── shared/      ← Shared components (LoadingSpinner, ErrorBoundary)
├── hooks/           ← Custom React hooks
│   ├── useSimulation.ts
│   ├── useAgents.ts
│   └── usePagination.ts
├── pages/           ← Route pages (one per route)
│   ├── SimulationListPage.tsx
│   ├── SimulationDashboardPage.tsx
│   ├── AgentDetailPage.tsx
│   ├── EventTimelinePage.tsx
│   └── TransactionDetailPage.tsx
├── types/           ← TypeScript type definitions
│   ├── api.ts       ← API response types
│   ├── domain.ts    ← Domain model types
│   └── index.ts     ← Re-exports
├── utils/           ← Pure utility functions
│   ├── currency.ts  ← Money formatting
│   ├── date.ts      ← Date/time formatting
│   └── format.ts    ← General formatting
├── lib/             ← Third-party library configs
│   └── queryClient.ts ← TanStack Query setup
├── App.tsx          ← Root component with routes
├── main.tsx         ← Entry point
└── index.css        ← Global styles (Tailwind imports)
```

---

## Domain Model (Frontend Types)

### Core Entities

```typescript
// src/types/domain.ts

/** Simulation run metadata */
interface Simulation {
  simulation_id: string
  created_at: string // ISO 8601
  config: SimulationConfig
  summary: SimulationSummary
}

interface SimulationConfig {
  ticks_per_day: number
  num_days: number
  rng_seed: number
  agents: AgentConfig[]
  lsm_config: LsmConfig
}

interface SimulationSummary {
  total_ticks: number
  total_transactions: number
  settlement_rate: number // 0.0 to 1.0
  total_cost_cents: number
  duration_seconds: number
  ticks_per_second: number
}

/** Agent (bank) in the system */
interface Agent {
  agent_id: string
  total_sent: number
  total_received: number
  total_settled: number
  total_dropped: number
  total_cost_cents: number
  avg_balance_cents: number
  peak_overdraft_cents: number
  credit_limit_cents: number
}

/** Transaction between agents */
interface Transaction {
  tx_id: string
  sender_id: string
  receiver_id: string
  amount: number // cents
  priority: number
  arrival_tick: number
  deadline_tick: number
  settlement_tick: number | null
  status: 'pending' | 'settled' | 'partially_settled' | 'dropped'
  drop_reason: string | null
  delay_cost: number // cents
  amount_settled: number // cents
  parent_tx_id: string | null
  split_index: number | null
}

/** Event types */
type EventType =
  | 'Arrival'
  | 'Settlement'
  | 'LsmBilateralOffset'
  | 'LsmCycleSettlement'
  | 'PolicySubmit'
  | 'PolicyHold'
  | 'PolicyDrop'
  | 'PolicySplit'
  | 'CollateralPost'
  | 'CollateralWithdraw'

interface Event {
  tick: number
  day: number
  event_type: EventType
  tx_id?: string
  sender_id?: string
  receiver_id?: string
  agent_id?: string
  amount?: number // cents
  priority?: number
  deadline_tick?: number
  timestamp: string // ISO 8601
}

/** Agent timeline data */
interface AgentTimeline {
  agent_id: string
  daily_metrics: DailyAgentMetric[]
  collateral_events: CollateralEvent[]
}

interface DailyAgentMetric {
  day: number
  opening_balance: number // cents
  closing_balance: number // cents
  min_balance: number // cents
  max_balance: number // cents
  transactions_sent: number
  transactions_received: number
  total_cost_cents: number
}

interface CollateralEvent {
  tick: number
  day: number
  action: 'post' | 'withdraw' | 'hold'
  amount: number // cents
  reason: string
  balance_before: number // cents
}

/** Transaction lifecycle */
interface TransactionLifecycle {
  transaction: Transaction
  events: Event[]
  related_transactions: RelatedTransaction[]
}

interface RelatedTransaction {
  tx_id: string
  relationship: 'split_from' | 'split_to' | 'offset_with'
}
```

### API Response Types

```typescript
// src/types/api.ts

/** Paginated response wrapper */
interface PaginatedResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

/** API response types */
interface SimulationListResponse {
  simulations: Simulation[]
}

interface AgentListResponse {
  agents: Agent[]
}

interface EventListResponse extends PaginatedResponse<Event> {}

interface TransactionListResponse extends PaginatedResponse<Transaction> {}

/** Query parameters */
interface EventQueryParams {
  tick?: number
  tick_min?: number
  tick_max?: number
  agent_id?: string
  event_type?: EventType
  limit?: number
  offset?: number
}

interface TransactionQueryParams {
  sender_id?: string
  receiver_id?: string
  status?: Transaction['status']
  limit?: number
  offset?: number
}
```

---

## API Client Patterns

### Base Client Setup

```typescript
// src/api/client.ts

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

/** API error with status code */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public response?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/** Base fetch wrapper with error handling */
export async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new ApiError(
        error.message || `HTTP ${response.status}`,
        response.status,
        error,
      )
    }

    return response.json()
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Network error', 0, error)
  }
}

/** GET request helper */
export async function apiGet<T>(
  endpoint: string,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  const query = params
    ? '?' + new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)])
      ).toString()
    : ''

  return apiFetch<T>(`${endpoint}${query}`)
}
```

### Endpoint Modules

```typescript
// src/api/simulations.ts

import { apiGet } from './client'
import type { Simulation, SimulationListResponse } from '@/types'

export async function fetchSimulations(): Promise<Simulation[]> {
  const response = await apiGet<SimulationListResponse>('/simulations')
  return response.simulations
}

export async function fetchSimulation(id: string): Promise<Simulation> {
  return apiGet<Simulation>(`/simulations/${id}`)
}

export async function fetchSimulationMetrics(id: string) {
  return apiGet(`/simulations/${id}/metrics`)
}
```

```typescript
// src/api/events.ts

import { apiGet } from './client'
import type { EventListResponse, EventQueryParams } from '@/types'

export async function fetchEvents(
  simulationId: string,
  params?: EventQueryParams,
): Promise<EventListResponse> {
  return apiGet<EventListResponse>(
    `/simulations/${simulationId}/events`,
    params,
  )
}
```

---

## React Query Patterns

### Query Hooks

```typescript
// src/hooks/useSimulation.ts

import { useQuery } from '@tanstack/react-query'
import { fetchSimulation } from '@/api/simulations'

export function useSimulation(simulationId: string) {
  return useQuery({
    queryKey: ['simulation', simulationId],
    queryFn: () => fetchSimulation(simulationId),
    staleTime: 5 * 60 * 1000, // 5 minutes (data doesn't change)
    // Read-only app, so data is effectively static once loaded
  })
}
```

```typescript
// src/hooks/useEvents.ts

import { useQuery } from '@tanstack/react-query'
import { fetchEvents } from '@/api/events'
import type { EventQueryParams } from '@/types'

export function useEvents(
  simulationId: string,
  params?: EventQueryParams,
) {
  return useQuery({
    queryKey: ['events', simulationId, params],
    queryFn: () => fetchEvents(simulationId, params),
    keepPreviousData: true, // Smooth pagination transitions
  })
}
```

### Pagination Hook

```typescript
// src/hooks/usePagination.ts

import { useState } from 'react'

interface UsePaginationOptions {
  initialLimit?: number
  initialOffset?: number
}

export function usePagination(options: UsePaginationOptions = {}) {
  const [limit, setLimit] = useState(options.initialLimit ?? 100)
  const [offset, setOffset] = useState(options.initialOffset ?? 0)

  const nextPage = () => setOffset(prev => prev + limit)
  const prevPage = () => setOffset(prev => Math.max(0, prev - limit))
  const goToPage = (page: number) => setOffset(page * limit)
  const reset = () => setOffset(0)

  const currentPage = Math.floor(offset / limit)

  return {
    limit,
    offset,
    currentPage,
    setLimit,
    nextPage,
    prevPage,
    goToPage,
    reset,
  }
}
```

---

## Component Patterns

### Page Component Structure

```typescript
// src/pages/SimulationDashboardPage.tsx

import { useParams, Navigate } from 'react-router-dom'
import { useSimulation, useAgents } from '@/hooks'
import {
  SimulationHeader,
  MetricsSummaryCard,
  AgentSummaryTable,
  RecentEventsList,
} from '@/components/simulation'
import { LoadingSpinner, ErrorMessage } from '@/components/shared'

export function SimulationDashboardPage() {
  const { simId } = useParams<{ simId: string }>()

  if (!simId) {
    return <Navigate to="/" replace />
  }

  const simulation = useSimulation(simId)
  const agents = useAgents(simId)

  if (simulation.isLoading || agents.isLoading) {
    return <LoadingSpinner />
  }

  if (simulation.error) {
    return <ErrorMessage error={simulation.error} />
  }

  return (
    <div className="container mx-auto py-8 space-y-6">
      <SimulationHeader simulation={simulation.data} />

      <MetricsSummaryCard summary={simulation.data.summary} />

      <section>
        <h2 className="text-2xl font-bold mb-4">Agents</h2>
        <AgentSummaryTable
          agents={agents.data?.agents ?? []}
          onRowClick={(agentId) => {
            // Navigation handled by component
          }}
        />
      </section>

      <section>
        <h2 className="text-2xl font-bold mb-4">Recent Events</h2>
        <RecentEventsList simulationId={simId} limit={20} />
      </section>
    </div>
  )
}
```

**Pattern**:
1. Extract route params
2. Fetch data with hooks (at page level)
3. Handle loading/error states
4. Pass data to presentational components
5. Keep components pure and testable

### Presentational Component Structure

```typescript
// src/components/simulation/MetricsSummaryCard.tsx

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import type { SimulationSummary } from '@/types'

interface MetricsSummaryCardProps {
  summary: SimulationSummary
}

export function MetricsSummaryCard({ summary }: MetricsSummaryCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Summary Metrics</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Metric
            label="Settlement Rate"
            value={formatPercentage(summary.settlement_rate)}
            data-testid="settlement-rate"
          />
          <Metric
            label="Total Transactions"
            value={summary.total_transactions.toLocaleString()}
            data-testid="total-transactions"
          />
          <Metric
            label="Total Cost"
            value={formatCurrency(summary.total_cost_cents)}
            data-testid="total-cost"
          />
          <Metric
            label="Performance"
            value={`${summary.ticks_per_second.toFixed(1)} tps`}
            data-testid="ticks-per-second"
          />
        </div>
      </CardContent>
    </Card>
  )
}

function Metric({ label, value, ...props }: {
  label: string
  value: string
  'data-testid'?: string
}) {
  return (
    <div {...props}>
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="text-2xl font-bold">{value}</div>
    </div>
  )
}

function formatPercentage(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}
```

**Pattern**:
1. Single responsibility (one card, one concern)
2. Receive data via props
3. No API calls or complex state
4. Use data-testid for testing
5. Extract sub-components for reusability

### Table Component with Sorting

```typescript
// src/components/simulation/AgentSummaryTable.tsx

import { useState, useMemo } from 'react'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table'
import { formatCurrency } from '@/utils/currency'
import type { Agent } from '@/types'

interface AgentSummaryTableProps {
  agents: Agent[]
  onRowClick?: (agentId: string) => void
}

type SortField = keyof Agent
type SortDirection = 'asc' | 'desc'

export function AgentSummaryTable({ agents, onRowClick }: AgentSummaryTableProps) {
  const [sortField, setSortField] = useState<SortField>('agent_id')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')

  const sortedAgents = useMemo(() => {
    const sorted = [...agents].sort((a, b) => {
      const aVal = a[sortField]
      const bVal = b[sortField]

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal)
      }

      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal
      }

      return 0
    })
    return sorted
  }, [agents, sortField, sortDirection])

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  return (
    <Table data-testid="agent-table">
      <TableHeader>
        <TableRow>
          <TableHead
            onClick={() => handleSort('agent_id')}
            className="cursor-pointer"
          >
            Agent ID {sortField === 'agent_id' && (sortDirection === 'asc' ? '↑' : '↓')}
          </TableHead>
          <TableHead
            onClick={() => handleSort('total_sent')}
            className="cursor-pointer"
          >
            Total Sent {sortField === 'total_sent' && (sortDirection === 'asc' ? '↑' : '↓')}
          </TableHead>
          <TableHead
            onClick={() => handleSort('total_cost_cents')}
            className="cursor-pointer"
          >
            Total Cost {sortField === 'total_cost_cents' && (sortDirection === 'asc' ? '↑' : '↓')}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sortedAgents.map((agent) => (
          <TableRow
            key={agent.agent_id}
            onClick={() => onRowClick?.(agent.agent_id)}
            className="cursor-pointer hover:bg-muted/50"
          >
            <TableCell>{agent.agent_id}</TableCell>
            <TableCell>{agent.total_sent.toLocaleString()}</TableCell>
            <TableCell>{formatCurrency(agent.total_cost_cents)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
```

**Pattern**:
1. Client-side sorting (data is small)
2. useMemo for expensive computations
3. Click handlers passed via props
4. Accessible (keyboard navigation, ARIA)

### Chart Component

```typescript
// src/components/agent/BalanceChart.tsx

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts'
import { formatCurrency } from '@/utils/currency'
import type { DailyAgentMetric } from '@/types'

interface BalanceChartProps {
  metrics: DailyAgentMetric[]
  width?: number
  height?: number
}

export function BalanceChart({ metrics, width = 800, height = 400 }: BalanceChartProps) {
  const data = metrics.map((m) => ({
    day: m.day,
    balance: m.closing_balance / 100, // Convert to dollars for display
    min: m.min_balance / 100,
    max: m.max_balance / 100,
  }))

  return (
    <div data-testid="balance-chart">
      <LineChart width={width} height={height} data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="day" label={{ value: 'Day', position: 'insideBottom', offset: -5 }} />
        <YAxis
          label={{ value: 'Balance ($)', angle: -90, position: 'insideLeft' }}
          tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
        />
        <Tooltip
          formatter={(value: number) => formatCurrency(value * 100)}
          labelFormatter={(label) => `Day ${label}`}
        />
        <Legend />
        <Line type="monotone" dataKey="balance" stroke="#8884d8" name="Closing Balance" />
        <Line type="monotone" dataKey="min" stroke="#82ca9d" name="Min Balance" strokeDasharray="3 3" />
        <Line type="monotone" dataKey="max" stroke="#ffc658" name="Max Balance" strokeDasharray="3 3" />
      </LineChart>
    </div>
  )
}
```

**Pattern**:
1. Transform data for chart (keep raw data in state)
2. Convert cents to dollars for Y-axis readability
3. Use Recharts components
4. Custom tooltips for better UX
5. Responsive sizing via props

---

## Utility Functions

### Currency Formatting

```typescript
// src/utils/currency.ts

/**
 * Format cents as currency string
 * @param cents - Amount in cents (i64 from backend)
 * @returns Formatted string like "$1,000.00"
 */
export function formatCurrency(cents: number): string {
  const dollars = cents / 100
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(dollars)
}

/**
 * Format cents as abbreviated currency (for charts)
 * @param cents - Amount in cents
 * @returns Formatted string like "$1.2M" or "$500K"
 */
export function formatCurrencyShort(cents: number): string {
  const dollars = cents / 100

  if (dollars >= 1_000_000) {
    return `$${(dollars / 1_000_000).toFixed(1)}M`
  }
  if (dollars >= 1_000) {
    return `$${(dollars / 1_000).toFixed(1)}K`
  }
  return formatCurrency(cents)
}
```

### Date Formatting

```typescript
// src/utils/date.ts

/**
 * Format ISO 8601 timestamp as human-readable string
 */
export function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 60) return `${diffMins} minutes ago`
  if (diffMins < 1440) return `${Math.floor(diffMins / 60)} hours ago`
  return `${Math.floor(diffMins / 1440)} days ago`
}
```

---

## Testing Patterns

### Unit Tests (Vitest)

```typescript
// src/utils/__tests__/currency.test.ts

import { describe, it, expect } from 'vitest'
import { formatCurrency, formatCurrencyShort } from '../currency'

describe('formatCurrency', () => {
  it('formats positive amounts correctly', () => {
    expect(formatCurrency(100000)).toBe('$1,000.00')
    expect(formatCurrency(50)).toBe('$0.50')
    expect(formatCurrency(1)).toBe('$0.01')
  })

  it('formats negative amounts correctly', () => {
    expect(formatCurrency(-100000)).toBe('-$1,000.00')
  })

  it('formats zero correctly', () => {
    expect(formatCurrency(0)).toBe('$0.00')
  })

  it('handles large amounts', () => {
    expect(formatCurrency(1234567890)).toBe('$12,345,678.90')
  })
})

describe('formatCurrencyShort', () => {
  it('formats millions with M suffix', () => {
    expect(formatCurrencyShort(150000000)).toBe('$1.5M')
  })

  it('formats thousands with K suffix', () => {
    expect(formatCurrencyShort(250000)).toBe('$2.5K')
  })

  it('formats small amounts without suffix', () => {
    expect(formatCurrencyShort(50000)).toBe('$500.00')
  })
})
```

### Component Tests (Testing Library)

```typescript
// src/components/simulation/__tests__/MetricsSummaryCard.test.tsx

import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { MetricsSummaryCard } from '../MetricsSummaryCard'
import type { SimulationSummary } from '@/types'

describe('MetricsSummaryCard', () => {
  const mockSummary: SimulationSummary = {
    total_ticks: 500,
    total_transactions: 15420,
    settlement_rate: 0.98,
    total_cost_cents: 500000,
    duration_seconds: 45.2,
    ticks_per_second: 11.06,
  }

  it('renders all metrics', () => {
    render(<MetricsSummaryCard summary={mockSummary} />)

    expect(screen.getByTestId('settlement-rate')).toHaveTextContent('98.0%')
    expect(screen.getByTestId('total-transactions')).toHaveTextContent('15,420')
    expect(screen.getByTestId('total-cost')).toHaveTextContent('$5,000.00')
    expect(screen.getByTestId('ticks-per-second')).toHaveTextContent('11.1 tps')
  })

  it('formats settlement rate as percentage', () => {
    render(<MetricsSummaryCard summary={mockSummary} />)
    const element = screen.getByTestId('settlement-rate')
    expect(element).toHaveTextContent('%')
  })

  it('formats total cost as currency', () => {
    render(<MetricsSummaryCard summary={mockSummary} />)
    const element = screen.getByTestId('total-cost')
    expect(element).toHaveTextContent('$')
  })
})
```

### Testing with React Query

```typescript
// src/components/simulation/__tests__/AgentSummaryTable.test.tsx

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi } from 'vitest'
import { AgentSummaryTable } from '../AgentSummaryTable'

// Create a test query client
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  )
}

describe('AgentSummaryTable', () => {
  const mockAgents = [
    {
      agent_id: 'BANK_A',
      total_sent: 100,
      total_received: 90,
      total_settled: 95,
      total_dropped: 5,
      total_cost_cents: 5000,
      avg_balance_cents: 1000000,
      peak_overdraft_cents: -50000,
      credit_limit_cents: 100000,
    },
    {
      agent_id: 'BANK_B',
      total_sent: 200,
      total_received: 180,
      total_settled: 190,
      total_dropped: 10,
      total_cost_cents: 3000,
      avg_balance_cents: 2000000,
      peak_overdraft_cents: 0,
      credit_limit_cents: 200000,
    },
  ]

  it('renders all agents', () => {
    renderWithQueryClient(<AgentSummaryTable agents={mockAgents} />)
    expect(screen.getByText('BANK_A')).toBeInTheDocument()
    expect(screen.getByText('BANK_B')).toBeInTheDocument()
  })

  it('sorts by total_sent descending when clicked', () => {
    renderWithQueryClient(<AgentSummaryTable agents={mockAgents} />)

    const sentHeader = screen.getByText(/Total Sent/)
    fireEvent.click(sentHeader)

    const rows = screen.getAllByRole('row')
    // First row is header, so data starts at index 1
    expect(rows[1]).toHaveTextContent('BANK_B') // Higher value first
    expect(rows[2]).toHaveTextContent('BANK_A')
  })

  it('calls onRowClick with agent_id when row clicked', () => {
    const mockOnRowClick = vi.fn()
    renderWithQueryClient(
      <AgentSummaryTable agents={mockAgents} onRowClick={mockOnRowClick} />
    )

    const bankARow = screen.getByText('BANK_A').closest('tr')
    fireEvent.click(bankARow!)

    expect(mockOnRowClick).toHaveBeenCalledWith('BANK_A')
  })
})
```

### E2E Tests (Playwright)

```typescript
// tests/e2e/simulation-dashboard.spec.ts

import { test, expect } from '@playwright/test'

test.describe('Simulation Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Assume API is running with test data
    await page.goto('/')
  })

  test('navigates from list to dashboard', async ({ page }) => {
    // Wait for simulation list to load
    await expect(page.locator('table tbody tr')).toHaveCount(3)

    // Click first simulation
    const firstRow = page.locator('table tbody tr').first()
    const simId = await firstRow.getAttribute('data-sim-id')
    await firstRow.click()

    // Verify navigation
    await expect(page).toHaveURL(`/simulations/${simId}`)
    await expect(page.locator('h1')).toContainText('Simulation')
  })

  test('displays summary metrics', async ({ page }) => {
    await page.goto('/simulations/test-sim-id')

    // Check all metric cards are visible
    await expect(page.locator('[data-testid="settlement-rate"]')).toBeVisible()
    await expect(page.locator('[data-testid="total-transactions"]')).toBeVisible()
    await expect(page.locator('[data-testid="total-cost"]')).toBeVisible()
    await expect(page.locator('[data-testid="ticks-per-second"]')).toBeVisible()

    // Verify values are formatted correctly
    const settlementRate = page.locator('[data-testid="settlement-rate"]')
    await expect(settlementRate).toContainText('%')
  })

  test('agent table is interactive', async ({ page }) => {
    await page.goto('/simulations/test-sim-id')

    // Click agent row
    const firstAgent = page.locator('[data-testid="agent-table"] tbody tr').first()
    const agentId = await firstAgent.locator('td').first().textContent()
    await firstAgent.click()

    // Verify navigation to agent detail page
    await expect(page).toHaveURL(new RegExp(`/agents/${agentId}`))
    await expect(page.locator('h1')).toContainText(agentId!)
  })

  test('shows recent events with link to full timeline', async ({ page }) => {
    await page.goto('/simulations/test-sim-id')

    // Check recent events section
    const recentEvents = page.locator('[data-testid="recent-events"]')
    await expect(recentEvents).toBeVisible()

    // Should show some events
    const eventCards = recentEvents.locator('[data-testid="event-card"]')
    expect(await eventCards.count()).toBeGreaterThan(0)

    // Click "View All Events"
    await page.locator('[data-testid="view-all-events"]').click()
    await expect(page).toHaveURL(/\/events/)
  })
})
```

---

## Common Workflows

### Adding a New Page

1. **Create route in App.tsx**:
```typescript
// src/App.tsx
<Route path="/simulations/:simId/foo" element={<FooPage />} />
```

2. **Create page component**:
```typescript
// src/pages/FooPage.tsx
export function FooPage() {
  const { simId } = useParams()
  // ... implement page
}
```

3. **Write e2e test FIRST**:
```typescript
// tests/e2e/foo-page.spec.ts
test('loads foo page', async ({ page }) => {
  await page.goto('/simulations/test-sim-id/foo')
  await expect(page.locator('h1')).toContainText('Foo')
})
```

4. **Implement page to pass test**

### Adding a New API Endpoint

1. **Define types**:
```typescript
// src/types/api.ts
interface FooResponse {
  foo: string
}
```

2. **Add API client function**:
```typescript
// src/api/foo.ts
export async function fetchFoo(id: string): Promise<FooResponse> {
  return apiGet(`/foo/${id}`)
}
```

3. **Create React Query hook**:
```typescript
// src/hooks/useFoo.ts
export function useFoo(id: string) {
  return useQuery({
    queryKey: ['foo', id],
    queryFn: () => fetchFoo(id),
  })
}
```

4. **Use in component**:
```typescript
const { data, isLoading, error } = useFoo(simId)
```

### Adding a New Component

1. **Write component test FIRST**:
```typescript
// src/components/foo/__tests__/FooCard.test.tsx
test('renders foo data', () => {
  render(<FooCard data={mockData} />)
  expect(screen.getByText('Foo')).toBeInTheDocument()
})
```

2. **Implement component**:
```typescript
// src/components/foo/FooCard.tsx
export function FooCard({ data }: FooCardProps) {
  return <div>{data.foo}</div>
}
```

3. **Export from index**:
```typescript
// src/components/foo/index.ts
export { FooCard } from './FooCard'
```

---

## Anti-Patterns (Don't Do These)

### ❌ API Calls in Components
```typescript
// BAD: Component makes API call
function TransactionCard({ txId }: { txId: string }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    fetch(`/api/transactions/${txId}`)
      .then(r => r.json())
      .then(setData)
  }, [txId])

  return <div>{data?.amount}</div>
}

// GOOD: Component receives data via props
function TransactionCard({ transaction }: { transaction: Transaction }) {
  return <div>{formatCurrency(transaction.amount)}</div>
}

// Data fetching happens at page level
function TransactionDetailPage() {
  const { txId } = useParams()
  const { data } = useTransaction(txId)
  return <TransactionCard transaction={data} />
}
```

### ❌ Inline Styles
```typescript
// BAD: Inline styles
<div style={{ padding: '16px', backgroundColor: '#f0f0f0' }}>
  Hello
</div>

// GOOD: Tailwind classes
<div className="p-4 bg-gray-100">
  Hello
</div>
```

### ❌ Using `any` Type
```typescript
// BAD: Defeats TypeScript
function processData(data: any) {
  return data.foo.bar // No type safety
}

// GOOD: Proper types
interface Data {
  foo: {
    bar: string
  }
}

function processData(data: Data) {
  return data.foo.bar // Type-safe
}
```

### ❌ Prop Drilling
```typescript
// BAD: Passing props through many levels
<A data={data}>
  <B data={data}>
    <C data={data}>
      <D data={data} /> // Finally used here
    </C>
  </B>
</A>

// GOOD: Use React Query at the component that needs data
function D() {
  const { data } = useQuery(...)
  return <div>{data}</div>
}
```

### ❌ Missing Error Handling
```typescript
// BAD: No error state
function MyPage() {
  const { data } = useQuery(...)
  return <div>{data.value}</div> // Crashes if error
}

// GOOD: Handle all states
function MyPage() {
  const { data, isLoading, error } = useQuery(...)

  if (isLoading) return <LoadingSpinner />
  if (error) return <ErrorMessage error={error} />
  if (!data) return <EmptyState />

  return <div>{data.value}</div>
}
```

### ❌ Mutating Props
```typescript
// BAD: Mutating props
function SortedTable({ data }: { data: Transaction[] }) {
  data.sort((a, b) => a.amount - b.amount) // Mutates prop!
  return <Table data={data} />
}

// GOOD: Create new array
function SortedTable({ data }: { data: Transaction[] }) {
  const sorted = [...data].sort((a, b) => a.amount - b.amount)
  return <Table data={sorted} />
}
```

---

## Performance Optimization

### Memoization

```typescript
// Expensive computation - memoize
const sortedAndFilteredData = useMemo(() => {
  return data
    .filter(item => item.status === filter)
    .sort((a, b) => a.amount - b.amount)
}, [data, filter])

// Callback functions - prevent re-renders
const handleClick = useCallback((id: string) => {
  navigate(`/transactions/${id}`)
}, [navigate])
```

### Virtual Scrolling

```typescript
// For long lists (1000+ items), use virtual scrolling
import { useVirtualizer } from '@tanstack/react-virtual'

function LongList({ items }: { items: Event[] }) {
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 50, // Estimated row height
  })

  return (
    <div ref={parentRef} style={{ height: '600px', overflow: 'auto' }}>
      <div style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}>
        {virtualizer.getVirtualItems().map((virtualItem) => (
          <div
            key={virtualItem.key}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: `${virtualItem.size}px`,
              transform: `translateY(${virtualItem.start}px)`,
            }}
          >
            <EventCard event={items[virtualItem.index]} />
          </div>
        ))}
      </div>
    </div>
  )
}
```

### Code Splitting

```typescript
// src/App.tsx - Lazy load routes
import { lazy, Suspense } from 'react'

const SimulationDashboardPage = lazy(() => import('./pages/SimulationDashboardPage'))
const AgentDetailPage = lazy(() => import('./pages/AgentDetailPage'))

function App() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <Routes>
        <Route path="/simulations/:simId" element={<SimulationDashboardPage />} />
        <Route path="/agents/:agentId" element={<AgentDetailPage />} />
      </Routes>
    </Suspense>
  )
}
```

---

## Accessibility

### Keyboard Navigation

```typescript
// Make clickable elements keyboard-accessible
function ClickableCard({ onClick }: { onClick: () => void }) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick()
        }
      }}
      className="cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      Click me
    </div>
  )
}
```

### ARIA Labels

```typescript
// Add ARIA labels for screen readers
<button aria-label="Close dialog">
  <XIcon />
</button>

<input
  type="search"
  placeholder="Search transactions"
  aria-label="Search transactions by ID or agent"
/>

<div role="status" aria-live="polite">
  {isLoading ? 'Loading...' : `${results.length} results found`}
</div>
```

### Focus Management

```typescript
// Manage focus when opening modals
function Modal({ isOpen, onClose }: ModalProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (isOpen) {
      closeButtonRef.current?.focus()
    }
  }, [isOpen])

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <DialogClose ref={closeButtonRef}>Close</DialogClose>
      </DialogContent>
    </Dialog>
  )
}
```

---

## Environment Variables

```bash
# .env.development
VITE_API_URL=http://localhost:8000/api

# .env.production
VITE_API_URL=https://api.example.com/api
```

```typescript
// src/api/client.ts
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

// Type-safe env vars
interface ImportMetaEnv {
  readonly VITE_API_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
```

---

## Build & Deployment

```bash
# Development
bun dev              # Start dev server (Bun runs Vite)

# Testing
bun test             # Run unit/component tests (Bun runs Vitest)
bun test:e2e         # Run e2e tests (Bun runs Playwright)
bun run test:coverage # Generate coverage report

# Building
bun run build        # Production build
bun run preview      # Preview production build

# Code quality
bun run lint         # ESLint
bun run format       # Prettier

# Installing dependencies
bun install          # 20-30x faster than npm
```

**Bun handles everything**:
- **Package manager**: Installs dependencies 20-30x faster than npm
- **Test runner**: Runs Vitest natively, no configuration needed
- **Script runner**: Executes package.json scripts instantly
- **TypeScript runtime**: Runs .ts files directly, no build step needed

---

## Success Criteria

You're writing good frontend code if:
- ✅ TypeScript has no errors (strict mode)
- ✅ All tests pass (unit + component + e2e)
- ✅ Components are pure (same props = same output)
- ✅ No API calls in components (only in hooks/pages)
- ✅ Money is always in cents until final display
- ✅ All user actions are keyboard-accessible
- ✅ Loading/error states are handled
- ✅ Code is readable and well-organized

Red flags:
- ❌ TypeScript errors or `any` types
- ❌ API calls scattered in components
- ❌ Float arithmetic on money values
- ❌ Missing loading or error states
- ❌ Untested components
- ❌ Accessibility violations
- ❌ Prop drilling through many levels

---

## Questions? Issues?

1. Check this file for patterns
2. Review `docs/plans/diagnostic-frontend.md` for architecture
3. Look at similar components in the codebase
4. Reference React Query and Tailwind docs
5. Write tests first, then implement

**Remember**: This is a diagnostic tool for exploring simulation data. Clarity and debuggability are more important than flashy animations. Make it fast, make it clear, make it testable.

---

*Last updated: 2025-11-02 (Updated to use Bun instead of npm)*
*This is a living document. Update it as patterns evolve.*
