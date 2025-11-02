import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { SimulationListPage } from '@/pages/SimulationListPage'
import * as simulationsApi from '@/api/simulations'

// Helper to wrap component with providers
function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {ui}
      </BrowserRouter>
    </QueryClientProvider>
  )
}

describe('SimulationListPage', () => {
  it('renders loading state initially', () => {
    vi.spyOn(simulationsApi, 'fetchSimulations').mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    renderWithProviders(<SimulationListPage />)

    expect(screen.getByText(/loading simulations/i)).toBeInTheDocument()
  })

  it('renders empty state when no simulations exist', async () => {
    vi.spyOn(simulationsApi, 'fetchSimulations').mockResolvedValue({
      simulations: [],
    })

    renderWithProviders(<SimulationListPage />)

    await waitFor(() => {
      expect(screen.getByText(/no simulations found/i)).toBeInTheDocument()
    })
  })

  it('renders simulation list when data is available', async () => {
    vi.spyOn(simulationsApi, 'fetchSimulations').mockResolvedValue({
      simulations: [
        {
          simulation_id: 'sim-001',
          status: 'completed',
          num_agents: 3,
          num_days: 5,
          started_at: '2025-11-02T10:00:00Z',
        },
        {
          simulation_id: 'sim-002',
          status: 'running',
          num_agents: 5,
          num_days: 10,
          current_tick: 250,
          current_day: 2,
        },
      ],
    })

    renderWithProviders(<SimulationListPage />)

    // Wait for data to load (not showing loading state anymore)
    await waitFor(() => {
      expect(screen.queryByText(/loading simulations/i)).not.toBeInTheDocument()
    })

    // Should show page title
    expect(screen.getByText('Simulations')).toBeInTheDocument()

    // Should show truncated simulation IDs (first 8 chars + ...)
    expect(screen.getByText(/sim-001/)).toBeInTheDocument()
    expect(screen.getByText(/sim-002/)).toBeInTheDocument()

    // Should show status badges
    expect(screen.getByText('completed')).toBeInTheDocument()
    expect(screen.getByText('running')).toBeInTheDocument()

    // Should show agent counts and days
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()

    // Should show '5' twice (5 agents for sim-002, 5 days for sim-001)
    const fives = screen.getAllByText('5')
    expect(fives).toHaveLength(2)
  })

  it('renders error state when fetch fails', async () => {
    vi.spyOn(simulationsApi, 'fetchSimulations').mockRejectedValue(
      new Error('Network error')
    )

    renderWithProviders(<SimulationListPage />)

    await waitFor(() => {
      expect(screen.getByText(/error loading simulations/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/network error/i)).toBeInTheDocument()
  })

  it('shows "View" button for each simulation', async () => {
    vi.spyOn(simulationsApi, 'fetchSimulations').mockResolvedValue({
      simulations: [
        {
          simulation_id: 'sim-001',
          status: 'completed',
          num_agents: 3,
          num_days: 5,
        },
      ],
    })

    renderWithProviders(<SimulationListPage />)

    await waitFor(() => {
      const viewButtons = screen.getAllByRole('button', { name: /view/i })
      expect(viewButtons).toHaveLength(1)
    })
  })
})
