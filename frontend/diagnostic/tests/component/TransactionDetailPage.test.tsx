import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { TransactionDetailPage } from '@/pages/TransactionDetailPage'
import * as simulationsApi from '@/api/simulations'

// Helper to wrap component with providers and route params
function renderWithProviders(
  ui: React.ReactElement,
  { simId = 'sim-001', txId = 'tx-001' } = {}
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
      <MemoryRouter initialEntries={[`/simulations/${simId}/transactions/${txId}`]}>
        <Routes>
          <Route
            path="/simulations/:simId/transactions/:txId"
            element={ui}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('TransactionDetailPage', () => {
  it('renders loading state initially', () => {
    vi.spyOn(simulationsApi, 'fetchTransactionLifecycle').mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    renderWithProviders(<TransactionDetailPage />)

    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('renders error state when fetch fails', async () => {
    vi.spyOn(simulationsApi, 'fetchTransactionLifecycle').mockRejectedValue(
      new Error('Transaction not found')
    )

    renderWithProviders(<TransactionDetailPage />)

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/transaction not found/i)).toBeInTheDocument()
  })

  it('renders transaction details and status', async () => {
    vi.spyOn(simulationsApi, 'fetchTransactionLifecycle').mockResolvedValue({
      transaction: {
        tx_id: 'tx-001',
        sender_id: 'BANK_A',
        receiver_id: 'BANK_B',
        amount: 100000,
        priority: 5,
        arrival_tick: 10,
        deadline_tick: 50,
        settlement_tick: 25,
        status: 'settled',
        delay_cost: 150,
        amount_settled: 100000,
      },
      events: [],
      related_transactions: [],
    })

    renderWithProviders(<TransactionDetailPage />)

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    // Should show transaction ID
    expect(screen.getByText(/tx-001/)).toBeInTheDocument()

    // Should show sender and receiver
    expect(screen.getByText('BANK_A')).toBeInTheDocument()
    expect(screen.getByText('BANK_B')).toBeInTheDocument()

    // Should show status badge
    expect(screen.getByText('settled')).toBeInTheDocument()

    // Should show amount (appears multiple times, so check it exists)
    const amounts = screen.getAllByText(/\$1,000\.00/)
    expect(amounts.length).toBeGreaterThan(0)
  })

  it('renders transaction event timeline', async () => {
    vi.spyOn(simulationsApi, 'fetchTransactionLifecycle').mockResolvedValue({
      transaction: {
        tx_id: 'tx-001',
        sender_id: 'BANK_A',
        receiver_id: 'BANK_B',
        amount: 100000,
        priority: 5,
        arrival_tick: 10,
        deadline_tick: 50,
        settlement_tick: 25,
        status: 'settled',
        delay_cost: 150,
        amount_settled: 100000,
      },
      events: [
        {
          tick: 10,
          event_type: 'Arrival',
          details: {},
        },
        {
          tick: 15,
          event_type: 'PolicyHold',
          details: { reason: 'insufficient_liquidity' },
        },
        {
          tick: 25,
          event_type: 'Settlement',
          details: { method: 'rtgs' },
        },
      ],
      related_transactions: [],
    })

    renderWithProviders(<TransactionDetailPage />)

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    // Should show timeline section
    expect(screen.getByText(/event timeline/i)).toBeInTheDocument()

    // Should show all event types (may appear multiple times)
    expect(screen.getAllByText('Arrival').length).toBeGreaterThan(0)
    expect(screen.getAllByText('PolicyHold').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Settlement').length).toBeGreaterThan(0)

    // Should show tick numbers (may appear multiple times)
    expect(screen.getAllByText(/tick 10/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/tick 15/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/tick 25/i).length).toBeGreaterThan(0)
  })

  it('renders related transactions when present', async () => {
    vi.spyOn(simulationsApi, 'fetchTransactionLifecycle').mockResolvedValue({
      transaction: {
        tx_id: 'tx-001',
        sender_id: 'BANK_A',
        receiver_id: 'BANK_B',
        amount: 100000,
        priority: 5,
        arrival_tick: 10,
        deadline_tick: 50,
        settlement_tick: null,
        status: 'split',
        delay_cost: 0,
        amount_settled: 0,
      },
      events: [],
      related_transactions: [
        {
          tx_id: 'tx-001-1',
          relationship: 'split_part',
          split_index: 1,
        },
        {
          tx_id: 'tx-001-2',
          relationship: 'split_part',
          split_index: 2,
        },
      ],
    })

    renderWithProviders(<TransactionDetailPage />)

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    // Should show related transactions section
    expect(screen.getByText(/related transactions/i)).toBeInTheDocument()

    // Should show related transaction IDs
    expect(screen.getByText(/tx-001-1/)).toBeInTheDocument()
    expect(screen.getByText(/tx-001-2/)).toBeInTheDocument()
  })

  it('shows navigation back to simulation', async () => {
    vi.spyOn(simulationsApi, 'fetchTransactionLifecycle').mockResolvedValue({
      transaction: {
        tx_id: 'tx-001',
        sender_id: 'BANK_A',
        receiver_id: 'BANK_B',
        amount: 100000,
        priority: 5,
        arrival_tick: 10,
        deadline_tick: 50,
        settlement_tick: 25,
        status: 'settled',
        delay_cost: 150,
        amount_settled: 100000,
      },
      events: [],
      related_transactions: [],
    })

    renderWithProviders(<TransactionDetailPage />)

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    // Should have back link
    expect(screen.getByRole('link', { name: /back/i })).toBeInTheDocument()
  })

  it('displays cost breakdown', async () => {
    vi.spyOn(simulationsApi, 'fetchTransactionLifecycle').mockResolvedValue({
      transaction: {
        tx_id: 'tx-001',
        sender_id: 'BANK_A',
        receiver_id: 'BANK_B',
        amount: 100000,
        priority: 5,
        arrival_tick: 10,
        deadline_tick: 50,
        settlement_tick: 25,
        status: 'settled',
        delay_cost: 150,
        amount_settled: 100000,
      },
      events: [],
      related_transactions: [],
    })

    renderWithProviders(<TransactionDetailPage />)

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    // Should show delay cost (appears in multiple places)
    expect(screen.getAllByText(/delay cost/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/\$1\.50/).length).toBeGreaterThan(0)
  })
})
