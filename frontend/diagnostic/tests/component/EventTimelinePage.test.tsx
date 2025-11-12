import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { EventTimelinePage } from '@/pages/EventTimelinePage'
import * as simulationsApi from '@/api/simulations'

// Helper to wrap component with providers and route params
function renderWithProviders(ui: React.ReactElement, { simId = 'sim-001' } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/simulations/${simId}/events`]}>
        <Routes>
          <Route path="/simulations/:simId/events" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('EventTimelinePage', () => {
  it('renders loading state initially', () => {
    vi.spyOn(simulationsApi, 'fetchEvents').mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    renderWithProviders(<EventTimelinePage />)

    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('renders error state when fetch fails', async () => {
    vi.spyOn(simulationsApi, 'fetchEvents').mockRejectedValue(
      new Error('Failed to load events')
    )

    renderWithProviders(<EventTimelinePage />)

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/failed to load events/i)).toBeInTheDocument()
  })

  it('renders event list with pagination info', async () => {
    vi.spyOn(simulationsApi, 'fetchEvents').mockResolvedValue({
      events: [
        {
          event_id: 'evt-001',
          simulation_id: 'sim-001',
          tick: 10,
          day: 1,
          event_type: 'Arrival',
          event_timestamp: '2025-01-01T10:00:00Z',
          tx_id: 'tx-001',
          details: {
            tx_id: 'tx-001',
            sender_id: 'BANK_A',
            receiver_id: 'BANK_B',
            amount: 100000,
            priority: 5,
            deadline_tick: 50,
          },
          created_at: '2025-01-01T10:00:00Z',
        },
        {
          event_id: 'evt-002',
          simulation_id: 'sim-001',
          tick: 15,
          day: 1,
          event_type: 'Settlement',
          event_timestamp: '2025-01-01T10:00:05Z',
          tx_id: 'tx-001',
          details: {
            tx_id: 'tx-001',
            sender_id: 'BANK_A',
            receiver_id: 'BANK_B',
            amount: 100000,
            settlement_type: 'RTGS',
          },
          created_at: '2025-01-01T10:00:05Z',
        },
      ],
      total: 150,
      limit: 100,
      offset: 0,
    })

    renderWithProviders(<EventTimelinePage />)

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    // Should show page title
    expect(screen.getByText(/events/i)).toBeInTheDocument()

    // Should show events (may include icons/badges)
    expect(screen.getByText('Arrival')).toBeInTheDocument()
    expect(screen.getByText(/Settlement/i)).toBeInTheDocument()

    // Should show pagination info
    expect(screen.getByText(/showing/i)).toBeInTheDocument()
    expect(screen.getByText(/150/)).toBeInTheDocument() // total count
  })

  it('displays event details correctly', async () => {
    vi.spyOn(simulationsApi, 'fetchEvents').mockResolvedValue({
      events: [
        {
          event_id: 'evt-001',
          simulation_id: 'sim-001',
          tick: 10,
          day: 1,
          event_type: 'Arrival',
          event_timestamp: '2025-01-01T10:00:00Z',
          tx_id: 'tx-001',
          details: {
            tx_id: 'tx-001',
            sender_id: 'BANK_A',
            receiver_id: 'BANK_B',
            amount: 100000,
            priority: 5,
            deadline_tick: 50,
          },
          created_at: '2025-01-01T10:00:00Z',
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    })

    renderWithProviders(<EventTimelinePage />)

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    // Should show tick number
    expect(screen.getByText(/tick 10/i)).toBeInTheDocument()

    // Should show sender and receiver
    expect(screen.getByText('BANK_A')).toBeInTheDocument()
    expect(screen.getByText('BANK_B')).toBeInTheDocument()

    // Should show transaction ID
    expect(screen.getByText(/tx-001/)).toBeInTheDocument()
  })

  it('shows navigation back to simulation', async () => {
    vi.spyOn(simulationsApi, 'fetchEvents').mockResolvedValue({
      events: [],
      total: 0,
      limit: 100,
      offset: 0,
    })

    renderWithProviders(<EventTimelinePage />)

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    // Should have back link
    expect(screen.getByRole('link', { name: /back/i })).toBeInTheDocument()
  })

  it('renders empty state when no events', async () => {
    vi.spyOn(simulationsApi, 'fetchEvents').mockResolvedValue({
      events: [],
      total: 0,
      limit: 100,
      offset: 0,
    })

    renderWithProviders(<EventTimelinePage />)

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    expect(screen.getByText(/no events found/i)).toBeInTheDocument()
  })
})
