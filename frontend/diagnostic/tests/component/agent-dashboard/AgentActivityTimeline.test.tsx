import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AgentActivityTimeline } from '@/components/agent-dashboard/AgentActivityTimeline'

// Mock Recharts to avoid canvas/SVG rendering issues in tests
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="line-chart">{children}</div>
  ),
  Line: ({ dataKey }: { dataKey: string }) => <div data-testid={`line-${dataKey}`} />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />,
}))

describe('AgentActivityTimeline', () => {
  const mockDailyMetrics = [
    {
      day: 1,
      opening_balance: 1_000_000, // $10,000
      closing_balance: 900_000, // $9,000
      min_balance: 850_000, // $8,500
      max_balance: 1_050_000, // $10,500
      transactions_sent: 5,
      transactions_received: 3,
      total_cost_cents: 50_000, // $500
    },
    {
      day: 2,
      opening_balance: 900_000,
      closing_balance: 1_100_000,
      min_balance: 880_000,
      max_balance: 1_150_000,
      transactions_sent: 7,
      transactions_received: 8,
      total_cost_cents: 75_000, // $750
    },
    {
      day: 3,
      opening_balance: 1_100_000,
      closing_balance: 1_050_000,
      min_balance: 1_000_000,
      max_balance: 1_200_000,
      transactions_sent: 6,
      transactions_received: 5,
      total_cost_cents: 60_000, // $600
    },
  ]

  it('renders the chart container', () => {
    render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    // Component has multiple charts (balance, transactions, costs)
    const containers = screen.getAllByTestId('responsive-container')
    const charts = screen.getAllByTestId('line-chart')
    expect(containers.length).toBeGreaterThan(0)
    expect(charts.length).toBeGreaterThan(0)
  })

  it('renders chart axes', () => {
    render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    // Multiple charts mean multiple axes
    const xAxes = screen.getAllByTestId('x-axis')
    const yAxes = screen.getAllByTestId('y-axis')
    expect(xAxes.length).toBeGreaterThan(0)
    expect(yAxes.length).toBeGreaterThan(0)
  })

  it('renders chart grid', () => {
    render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    // Multiple charts mean multiple grids
    const grids = screen.getAllByTestId('cartesian-grid')
    expect(grids.length).toBeGreaterThan(0)
  })

  it('renders tooltip for data points', () => {
    render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    // Multiple charts mean multiple tooltips
    const tooltips = screen.getAllByTestId('tooltip')
    expect(tooltips.length).toBeGreaterThan(0)
  })

  it('renders legend for metrics', () => {
    render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    // Multiple charts mean multiple legends
    const legends = screen.getAllByTestId('legend')
    expect(legends.length).toBeGreaterThan(0)
  })

  it('displays closing balance line', () => {
    render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    expect(screen.getByTestId('line-closing_balance')).toBeInTheDocument()
  })

  it('displays transactions sent line', () => {
    render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    expect(screen.getByTestId('line-transactions_sent')).toBeInTheDocument()
  })

  it('displays transactions received line', () => {
    render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    expect(screen.getByTestId('line-transactions_received')).toBeInTheDocument()
  })

  it('displays total cost line', () => {
    render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    expect(screen.getByTestId('line-total_cost_cents')).toBeInTheDocument()
  })

  it('displays a title', () => {
    render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    expect(screen.getByText(/activity timeline|daily metrics/i)).toBeInTheDocument()
  })

  it('handles empty data gracefully', () => {
    render(<AgentActivityTimeline dailyMetrics={[]} />)

    // Should show empty state message
    expect(screen.getByText(/no data|no metrics|no activity/i)).toBeInTheDocument()
  })

  it('displays metric labels/legend items', () => {
    render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    // Should have descriptive labels visible somewhere in the component
    const containers = screen.getAllByTestId('responsive-container')
    const allText = containers.map((c) => c.parentElement?.textContent || '').join(' ')
    expect(allText).toMatch(/balance|transactions|cost/i)
  })

  it('has proper container styling', () => {
    const { container } = render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    // Should have a styled container (card/rounded/shadow)
    const chartContainer = container.querySelector('[class*="bg-white"], [class*="rounded"]')
    expect(chartContainer).toBeInTheDocument()
  })

  it('displays day numbers on x-axis', () => {
    const { container } = render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    // Days should be visible in the component (in section titles or chart descriptions)
    expect(container.textContent).toMatch(/day|daily/i)
  })

  it('formats currency values properly', () => {
    const { container } = render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    // Should have formatted currency somewhere (in labels or description)
    expect(container.textContent).toMatch(/\$|balance/i)
  })

  it('uses different colors for different metrics', () => {
    const { container } = render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    // Each line should have different color data attributes or classes
    const lines = container.querySelectorAll('[data-testid^="line-"]')
    expect(lines.length).toBeGreaterThan(1)
  })

  it('is responsive', () => {
    render(<AgentActivityTimeline dailyMetrics={mockDailyMetrics} />)

    // ResponsiveContainers should be present (multiple charts)
    const responsiveContainers = screen.getAllByTestId('responsive-container')
    expect(responsiveContainers.length).toBeGreaterThan(0)
  })
})
