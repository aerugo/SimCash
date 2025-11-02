import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AgentDetailPage } from '@/pages/AgentDetailPage'
import * as simulationsApi from '@/api/simulations'

// Helper to wrap component with providers and route params
function renderWithProviders(
  ui: React.ReactElement,
  { simId = 'sim-001', agentId = 'BANK_A' } = {}
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/simulations/${simId}/agents/${agentId}`]}>
        <Routes>
          <Route
            path="/simulations/:simId/agents/:agentId"
            element={ui}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('AgentDetailPage', () => {
  it('renders loading state initially', () => {
    vi.spyOn(simulationsApi, 'fetchAgentTimeline').mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    renderWithProviders(<AgentDetailPage />)

    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('renders error state when fetch fails', async () => {
    vi.spyOn(simulationsApi, 'fetchAgentTimeline').mockRejectedValue(
      new Error('Agent not found')
    )

    renderWithProviders(<AgentDetailPage />)

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/agent not found/i)).toBeInTheDocument()
  })

  it('renders agent summary metrics', async () => {
    vi.spyOn(simulationsApi, 'fetchAgentTimeline').mockResolvedValue({
      agent_id: 'BANK_A',
      total_sent: 10,
      total_received: 8,
      total_settled: 15,
      total_dropped: 3,
      total_cost_cents: 150000,
      avg_balance_cents: 800000,
      peak_overdraft_cents: -200000,
      credit_limit_cents: 500000,
      daily_metrics: [],
      collateral_events: [],
    })

    renderWithProviders(<AgentDetailPage />)

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    // Should show agent ID in heading
    expect(screen.getByRole('heading', { name: /BANK_A/i })).toBeInTheDocument()

    // Should show summary metrics
    expect(screen.getByText('10')).toBeInTheDocument() // total_sent
    expect(screen.getByText('8')).toBeInTheDocument() // total_received
    expect(screen.getByText('15')).toBeInTheDocument() // total_settled
    expect(screen.getByText('3')).toBeInTheDocument() // total_dropped
  })

  it('renders daily metrics table', async () => {
    vi.spyOn(simulationsApi, 'fetchAgentTimeline').mockResolvedValue({
      agent_id: 'BANK_A',
      total_sent: 10,
      total_received: 8,
      total_settled: 15,
      total_dropped: 3,
      total_cost_cents: 150000,
      avg_balance_cents: 800000,
      peak_overdraft_cents: -200000,
      credit_limit_cents: 500000,
      daily_metrics: [
        {
          day: 0,
          opening_balance: 1000000,
          closing_balance: 950000,
          min_balance: 900000,
          max_balance: 1000000,
          transactions_sent: 5,
          transactions_received: 3,
          total_cost_cents: 50000,
        },
        {
          day: 1,
          opening_balance: 950000,
          closing_balance: 920000,
          min_balance: 850000,
          max_balance: 950000,
          transactions_sent: 5,
          transactions_received: 5,
          total_cost_cents: 100000,
        },
      ],
      collateral_events: [],
    })

    renderWithProviders(<AgentDetailPage />)

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    // Should show daily metrics header
    expect(screen.getByText(/daily metrics/i)).toBeInTheDocument()

    // Should show day numbers
    expect(screen.getByText('Day 0')).toBeInTheDocument()
    expect(screen.getByText('Day 1')).toBeInTheDocument()
  })

  it('renders collateral events when present', async () => {
    vi.spyOn(simulationsApi, 'fetchAgentTimeline').mockResolvedValue({
      agent_id: 'BANK_A',
      total_sent: 10,
      total_received: 8,
      total_settled: 15,
      total_dropped: 3,
      total_cost_cents: 150000,
      avg_balance_cents: 800000,
      peak_overdraft_cents: -200000,
      credit_limit_cents: 500000,
      daily_metrics: [],
      collateral_events: [
        {
          tick: 50,
          event_type: 'Pledge',
          amount_cents: 100000,
        },
        {
          tick: 100,
          event_type: 'Release',
          amount_cents: 50000,
        },
      ],
    })

    renderWithProviders(<AgentDetailPage />)

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    // Should show collateral events section
    expect(screen.getByText(/collateral events/i)).toBeInTheDocument()

    // Should show event types
    expect(screen.getByText('Pledge')).toBeInTheDocument()
    expect(screen.getByText('Release')).toBeInTheDocument()
  })

  it('shows navigation back to simulation dashboard', async () => {
    vi.spyOn(simulationsApi, 'fetchAgentTimeline').mockResolvedValue({
      agent_id: 'BANK_A',
      total_sent: 10,
      total_received: 8,
      total_settled: 15,
      total_dropped: 3,
      total_cost_cents: 150000,
      avg_balance_cents: 800000,
      peak_overdraft_cents: -200000,
      credit_limit_cents: 500000,
      daily_metrics: [],
      collateral_events: [],
    })

    renderWithProviders(<AgentDetailPage />)

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    // Should have link back to simulation
    expect(screen.getByRole('link', { name: /back to simulation/i })).toBeInTheDocument()
  })
})
