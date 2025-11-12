import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AgentCostBreakdown } from '@/components/agent-dashboard/AgentCostBreakdown'

describe('AgentCostBreakdown', () => {
  const mockData = {
    liquidity_cost: 500_000, // $5,000.00
    delay_cost: 300_000, // $3,000.00
    collateral_cost: 200_000, // $2,000.00
    split_friction_cost: 100_000, // $1,000.00
    deadline_penalty: 400_000, // $4,000.00
  }

  it('displays all cost categories', () => {
    render(<AgentCostBreakdown {...mockData} />)

    expect(screen.getByText(/Liquidity Cost/i)).toBeInTheDocument()
    expect(screen.getByText(/Delay Cost/i)).toBeInTheDocument()
    expect(screen.getByText(/Collateral Cost/i)).toBeInTheDocument()
    expect(screen.getByText(/Split Friction Cost/i)).toBeInTheDocument()
    expect(screen.getByText(/Deadline Penalty/i)).toBeInTheDocument()
  })

  it('displays cost amounts with proper currency formatting', () => {
    render(<AgentCostBreakdown {...mockData} />)

    expect(screen.getByText('$5,000.00')).toBeInTheDocument()
    expect(screen.getByText('$3,000.00')).toBeInTheDocument()
    expect(screen.getByText('$2,000.00')).toBeInTheDocument()
    expect(screen.getByText('$1,000.00')).toBeInTheDocument()
    expect(screen.getByText('$4,000.00')).toBeInTheDocument()
  })

  it('calculates and displays total cost', () => {
    render(<AgentCostBreakdown {...mockData} />)

    // Total should be $15,000.00
    expect(screen.getByText('Total Cost')).toBeInTheDocument()
    const totalSection = screen.getByText('Total Cost').closest('div')
    expect(totalSection?.textContent).toMatch(/\$15,000\.00/)
  })

  it('displays percentage contribution for each category', () => {
    render(<AgentCostBreakdown {...mockData} />)

    // Liquidity: 5000/15000 = 33.3%
    expect(screen.getByText('33%')).toBeInTheDocument()
    // Delay: 3000/15000 = 20%
    expect(screen.getByText('20%')).toBeInTheDocument()
    // Collateral: 2000/15000 = 13.3%
    expect(screen.getByText('13%')).toBeInTheDocument()
    // Split: 1000/15000 = 6.7%
    expect(screen.getByText('7%')).toBeInTheDocument()
    // Deadline: 4000/15000 = 26.7%
    expect(screen.getByText('27%')).toBeInTheDocument()
  })

  it('handles zero costs gracefully', () => {
    const zeroCostData = {
      ...mockData,
      split_friction_cost: 0,
      deadline_penalty: 0,
    }
    render(<AgentCostBreakdown {...zeroCostData} />)

    // Should still display categories
    expect(screen.getByText(/Split Friction Cost/i)).toBeInTheDocument()
    expect(screen.getByText(/Deadline Penalty/i)).toBeInTheDocument()

    // Should show $0.00 - get the parent container div with p-4 class
    const splitSection = screen.getByText(/Split Friction Cost/i).closest('.p-4')
    expect(splitSection?.textContent).toMatch(/\$0\.00/)
  })

  it('handles all-zero costs', () => {
    const allZeroData = {
      liquidity_cost: 0,
      delay_cost: 0,
      collateral_cost: 0,
      split_friction_cost: 0,
      deadline_penalty: 0,
    }
    render(<AgentCostBreakdown {...allZeroData} />)

    // Should display total of $0.00
    const totalSection = screen.getByText('Total Cost').closest('div')
    expect(totalSection?.textContent).toMatch(/\$0\.00/)

    // Should not show percentages when total is zero
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })

  it('renders visual bars for cost breakdown', () => {
    const { container } = render(<AgentCostBreakdown {...mockData} />)

    // Should have progress/bar elements
    const bars = container.querySelectorAll('[role="progressbar"]')
    expect(bars.length).toBe(5) // One for each cost category
  })

  it('uses different colors for different cost categories', () => {
    const { container } = render(<AgentCostBreakdown {...mockData} />)

    // Check that bars have different color classes
    const bars = container.querySelectorAll('[role="progressbar"]')
    const colors = Array.from(bars).map((bar) => bar.className)

    // Should have variety of colors (not all the same)
    const uniqueColors = new Set(colors)
    expect(uniqueColors.size).toBeGreaterThan(1)
  })

  it('displays cost categories in descending order by amount', () => {
    render(<AgentCostBreakdown {...mockData} />)

    // Get all category labels in order they appear
    const categories = screen
      .getAllByText(/(Liquidity|Delay|Collateral|Split|Deadline)/)
      .map((el) => el.textContent)

    // Should be ordered: Liquidity ($5k), Deadline ($4k), Delay ($3k), Collateral ($2k), Split ($1k)
    expect(categories[0]).toMatch(/Liquidity/)
    expect(categories[1]).toMatch(/Deadline/)
    expect(categories[2]).toMatch(/Delay/)
  })

  it('highlights the highest cost category', () => {
    const { container } = render(<AgentCostBreakdown {...mockData} />)

    // Liquidity ($5k) is highest, should have special styling on the card container
    const liquiditySection = screen.getByText(/Liquidity Cost/i).closest('.p-4')
    expect(liquiditySection?.className).toMatch(/border-gray-400/)
    expect(liquiditySection?.className).toMatch(/ring-2/)
    expect(liquiditySection?.className).toMatch(/font-bold/)
  })

  it('uses a grid or flex layout for responsive design', () => {
    const { container } = render(<AgentCostBreakdown {...mockData} />)

    // Should use grid or flex layout
    const layoutContainer = container.querySelector('[class*="grid"], [class*="flex"]')
    expect(layoutContainer).toBeInTheDocument()
  })
})
