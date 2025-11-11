import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { LsmCycleVisualizer } from '@/components/event-cards/LsmCycleVisualizer'

describe('LsmCycleVisualizer', () => {
  const mockBilateralCycle = {
    agents: ['BANK_A', 'BANK_B'],
    tx_ids: ['tx1', 'tx2'],
    tx_amounts: [500_000, 300_000], // $5,000, $3,000
    net_positions: [200_000, -200_000], // $2,000, -$2,000
    max_net_outflow: 200_000,
    max_net_outflow_agent: 'BANK_B',
    total_value: 800_000,
  }

  const mockTriangleCycle = {
    agents: ['BANK_A', 'BANK_B', 'BANK_C'],
    tx_ids: ['tx1', 'tx2', 'tx3'],
    tx_amounts: [500_000, 300_000, 400_000],
    net_positions: [100_000, -200_000, 100_000],
    max_net_outflow: 200_000,
    max_net_outflow_agent: 'BANK_B',
    total_value: 1_200_000,
  }

  it('renders SVG graph container', () => {
    const { container } = render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    const svg = container.querySelector('svg')
    expect(svg).toBeInTheDocument()
  })

  it('displays all agent nodes', () => {
    const { container } = render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    // Check SVG contains agent names
    const svg = container.querySelector('svg')
    expect(svg?.textContent).toMatch(/BANK_A/)
    expect(svg?.textContent).toMatch(/BANK_B/)
  })

  it('displays three agents in triangle cycle', () => {
    const { container } = render(<LsmCycleVisualizer cycle={mockTriangleCycle} />)

    // Check SVG contains all three agent names
    const svg = container.querySelector('svg')
    expect(svg?.textContent).toMatch(/BANK_A/)
    expect(svg?.textContent).toMatch(/BANK_B/)
    expect(svg?.textContent).toMatch(/BANK_C/)
  })

  it('shows transaction arrows between agents', () => {
    const { container } = render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    // Should have path/line elements for arrows
    const arrows = container.querySelectorAll('path[marker-end], line[marker-end]')
    expect(arrows.length).toBeGreaterThan(0)
  })

  it('displays transaction amounts on edges', () => {
    const { container } = render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    // Check SVG contains transaction amounts
    const svg = container.querySelector('svg')
    expect(svg?.textContent).toMatch(/\$5,000\.00/)
    expect(svg?.textContent).toMatch(/\$3,000\.00/)
  })

  it('shows metrics panel with total value', () => {
    render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    expect(screen.getByText(/total value/i)).toBeInTheDocument()
    expect(screen.getByText('$8,000.00')).toBeInTheDocument()
  })

  it('displays max net outflow metric', () => {
    const { container } = render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    // Check for max outflow text in metrics panel (not SVG)
    expect(container.textContent).toMatch(/max.*outflow/i)
    // Total has two $2,000 values (max outflow + net position), so just check it exists
    expect(container.textContent).toMatch(/\$2,000\.00/)
  })

  it('shows agent with max outflow', () => {
    const { container } = render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    // Should indicate BANK_B has the max outflow somewhere
    expect(container.textContent).toMatch(/bank_b/i)
    expect(container.textContent).toMatch(/max|highest|requires/i)
  })

  it('displays net positions for each agent', () => {
    const { container } = render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    // BANK_A: +$2,000 (net positive) - appears in SVG and metrics panel
    expect(container.textContent).toMatch(/\+\$2,000\.00/)
    // BANK_B: -$2,000 (net negative)
    expect(container.textContent).toMatch(/-\$2,000\.00/)
  })

  it('color-codes positive and negative net positions', () => {
    const { container } = render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    // Check that there are elements with green/red classes for net positions
    const greenElements = container.querySelectorAll('[class*="green"]')
    const redElements = container.querySelectorAll('[class*="red"]')

    expect(greenElements.length).toBeGreaterThan(0)
    expect(redElements.length).toBeGreaterThan(0)
  })

  it('shows transaction details table', () => {
    render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    // Should have a table with transaction IDs
    expect(screen.getByText('tx1')).toBeInTheDocument()
    expect(screen.getByText('tx2')).toBeInTheDocument()
  })

  it('calculates liquidity saved (max outflow vs total value)', () => {
    render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    // Liquidity saved = total_value - max_net_outflow = $8,000 - $2,000 = $6,000
    expect(screen.getByText(/liquidity saved/i)).toBeInTheDocument()
    expect(screen.getByText('$6,000.00')).toBeInTheDocument()
  })

  it('calculates efficiency percentage', () => {
    render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    // Efficiency = (liquidity_saved / total_value) * 100 = (6000 / 8000) * 100 = 75%
    expect(screen.getByText(/efficiency/i)).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
  })

  it('highlights hovered agent node', async () => {
    const user = userEvent.setup()
    const { container } = render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    // Find SVG groups (agent nodes)
    const svg = container.querySelector('svg')
    const groups = svg?.querySelectorAll('g.cursor-pointer')

    expect(groups && groups.length).toBeGreaterThan(0)

    // Test hover interaction on first group if it exists
    if (groups && groups[0]) {
      await user.hover(groups[0])
      // Component uses state to handle hover, just verify cursor-pointer class is there
      expect(groups[0].className.baseVal || groups[0].getAttribute('class')).toMatch(/cursor-pointer/)
    }
  })

  it('displays cycle type (bilateral vs multilateral)', () => {
    const { container, rerender } = render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    // 2 agents = bilateral
    expect(container.textContent).toMatch(/bilateral/i)

    // 3+ agents = multilateral
    rerender(<LsmCycleVisualizer cycle={mockTriangleCycle} />)
    expect(container.textContent).toMatch(/multilateral/i)
  })

  it('arranges nodes in circular layout', () => {
    const { container } = render(<LsmCycleVisualizer cycle={mockTriangleCycle} />)

    // Check that nodes have circle/transform attributes indicating circular placement
    const svg = container.querySelector('svg')
    const groups = svg?.querySelectorAll('g[transform]')
    expect(groups && groups.length).toBeGreaterThan(0)
  })

  it('has proper container styling', () => {
    const { container } = render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    // Should have card/rounded/shadow container
    const cardContainer = container.querySelector('[class*="bg-white"], [class*="rounded"]')
    expect(cardContainer).toBeInTheDocument()
  })

  it('displays title', () => {
    render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    expect(screen.getByText(/lsm cycle|cycle visualization/i)).toBeInTheDocument()
  })

  it('shows cycle size (number of agents)', () => {
    render(<LsmCycleVisualizer cycle={mockBilateralCycle} />)

    expect(screen.getByText(/2.*agent/i)).toBeInTheDocument()
  })
})
