import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AgentFinancialOverview } from '@/components/agent-dashboard/AgentFinancialOverview'

describe('AgentFinancialOverview', () => {
  const mockData = {
    balance: 1_500_000, // $15,000.00
    credit_limit: 500_000, // $5,000.00
    liquidity: 2_000_000, // $20,000.00 (balance + credit)
    headroom: 500_000, // $5,000.00 (unused credit)
  }

  it('displays balance with proper formatting', () => {
    render(<AgentFinancialOverview {...mockData} />)

    expect(screen.getByText('Balance')).toBeInTheDocument()
    expect(screen.getByText('$15,000.00')).toBeInTheDocument()
  })

  it('displays credit limit', () => {
    render(<AgentFinancialOverview {...mockData} />)

    expect(screen.getByText('Credit Limit')).toBeInTheDocument()
    // Check credit limit section contains the value
    const creditSection = screen.getByText('Credit Limit').parentElement
    expect(creditSection?.textContent).toMatch(/\$5,000\.00/)
  })

  it('displays liquidity (balance + available credit)', () => {
    render(<AgentFinancialOverview {...mockData} />)

    expect(screen.getByText('Liquidity')).toBeInTheDocument()
    const liquiditySection = screen.getByText('Liquidity').parentElement
    expect(liquiditySection?.textContent).toMatch(/\$20,000\.00/)
  })

  it('displays headroom (unused credit)', () => {
    render(<AgentFinancialOverview {...mockData} />)

    expect(screen.getByText('Headroom')).toBeInTheDocument()
    const headroomSection = screen.getByText('Headroom').parentElement
    expect(headroomSection?.textContent).toMatch(/\$5,000\.00/)
  })

  it('displays positive balance with green styling', () => {
    render(<AgentFinancialOverview {...mockData} />)

    // Find balance value element and check it has green text
    const balanceValue = screen.getByText('$15,000.00').closest('div')
    expect(balanceValue?.className).toMatch(/text-green/)
  })

  it('displays negative balance with red styling', () => {
    const overdraftData = { ...mockData, balance: -200_000 }
    render(<AgentFinancialOverview {...overdraftData} />)

    const balanceValue = screen.getByText('-$2,000.00').closest('div')
    expect(balanceValue?.className).toMatch(/text-red/)
  })

  it('shows credit usage percentage', () => {
    render(<AgentFinancialOverview {...mockData} />)

    // Credit used = 0, so 0% usage
    expect(screen.getByText('0% used')).toBeInTheDocument()
  })

  it('calculates credit usage correctly when in overdraft', () => {
    const overdraftData = {
      ...mockData,
      balance: -300_000, // -$3,000.00 overdraft
    }
    render(<AgentFinancialOverview {...overdraftData} />)

    // Using $3,000 of $5,000 credit = 60%
    expect(screen.getByText('60% used')).toBeInTheDocument()
  })

  it('shows warning when credit usage is high (>80%)', () => {
    const highUsageData = {
      ...mockData,
      balance: -450_000, // Using $4,500 of $5,000 = 90%
    }
    render(<AgentFinancialOverview {...highUsageData} />)

    // Should show warning indicator
    expect(screen.getByText(/90% used/i)).toBeInTheDocument()
    // Should show high credit utilization warning
    expect(screen.getByText(/high credit utilization/i)).toBeInTheDocument()
  })

  it('renders liquidity gauge visualization', () => {
    const { container } = render(<AgentFinancialOverview {...mockData} />)

    // Should have gauge elements (SVG or progress bars)
    const gauges = container.querySelectorAll('[role="progressbar"], svg')
    expect(gauges.length).toBeGreaterThan(0)
  })

  it('handles zero credit limit gracefully', () => {
    const noCreditData = {
      ...mockData,
      credit_limit: 0,
      liquidity: 1_500_000,
      headroom: 0,
    }
    render(<AgentFinancialOverview {...noCreditData} />)

    // Credit limit should be $0.00
    expect(screen.getByText('Credit Limit')).toBeInTheDocument()
    const creditSection = screen.getByText('Credit Limit').parentElement
    expect(creditSection?.textContent).toMatch(/\$0\.00/)

    // Should not show credit usage when credit limit is 0
    expect(screen.queryByText(/% used/)).not.toBeInTheDocument()
  })

  it('displays all metrics in a grid layout', () => {
    const { container } = render(<AgentFinancialOverview {...mockData} />)

    // Should use grid layout
    const grid = container.querySelector('[class*="grid"]')
    expect(grid).toBeInTheDocument()
  })
})
