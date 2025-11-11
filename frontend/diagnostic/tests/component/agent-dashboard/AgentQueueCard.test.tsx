import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AgentQueueCard } from '@/components/agent-dashboard/AgentQueueCard'

describe('AgentQueueCard', () => {
  const mockQueue1Transactions = [
    {
      tx_id: 'tx1',
      receiver_id: 'BANK_B',
      amount: 500_000, // $5,000.00
      priority: 8,
      deadline_tick: 150,
    },
    {
      tx_id: 'tx2',
      receiver_id: 'BANK_C',
      amount: 300_000, // $3,000.00
      priority: 5,
      deadline_tick: 200,
    },
  ]

  const mockQueue2Transactions = [
    {
      tx_id: 'tx3',
      receiver_id: 'BANK_D',
      amount: 1_000_000, // $10,000.00
      priority: 9,
      deadline_tick: 180,
    },
  ]

  it('displays Queue 1 title and transaction count', () => {
    render(
      <AgentQueueCard
        queue1Transactions={mockQueue1Transactions}
        queue2Transactions={[]}
        currentTick={100}
      />
    )

    expect(screen.getByText(/Queue 1/i)).toBeInTheDocument()
    expect(screen.getByText(/2 transactions/i)).toBeInTheDocument()
  })

  it('displays Queue 2 title and transaction count', () => {
    render(
      <AgentQueueCard
        queue1Transactions={[]}
        queue2Transactions={mockQueue2Transactions}
        currentTick={100}
      />
    )

    expect(screen.getByText(/Queue 2/i)).toBeInTheDocument()
    expect(screen.getByText(/1 transaction/i)).toBeInTheDocument()
  })

  it('displays transaction IDs in queues', () => {
    render(
      <AgentQueueCard
        queue1Transactions={mockQueue1Transactions}
        queue2Transactions={mockQueue2Transactions}
        currentTick={100}
      />
    )

    expect(screen.getByText('tx1')).toBeInTheDocument()
    expect(screen.getByText('tx2')).toBeInTheDocument()
    expect(screen.getByText('tx3')).toBeInTheDocument()
  })

  it('displays transaction amounts with currency formatting', () => {
    render(
      <AgentQueueCard
        queue1Transactions={mockQueue1Transactions}
        queue2Transactions={[]}
        currentTick={100}
      />
    )

    expect(screen.getByText('$5,000.00')).toBeInTheDocument()
    expect(screen.getByText('$3,000.00')).toBeInTheDocument()
  })

  it('displays receiver IDs for each transaction', () => {
    render(
      <AgentQueueCard
        queue1Transactions={mockQueue1Transactions}
        queue2Transactions={[]}
        currentTick={100}
      />
    )

    expect(screen.getByText(/BANK_B/)).toBeInTheDocument()
    expect(screen.getByText(/BANK_C/)).toBeInTheDocument()
  })

  it('displays priority badges', () => {
    render(
      <AgentQueueCard
        queue1Transactions={mockQueue1Transactions}
        queue2Transactions={[]}
        currentTick={100}
      />
    )

    // Should show priority values
    expect(screen.getByText('P8')).toBeInTheDocument()
    expect(screen.getByText('P5')).toBeInTheDocument()
  })

  it('calculates and displays total value for Queue 1', () => {
    render(
      <AgentQueueCard
        queue1Transactions={mockQueue1Transactions}
        queue2Transactions={[]}
        currentTick={100}
      />
    )

    // Total: $5,000 + $3,000 = $8,000
    const queue1Section = screen.getByText(/Queue 1/i).closest('.bg-white')
    expect(queue1Section?.textContent).toMatch(/\$8,000\.00/)
  })

  it('calculates and displays total value for Queue 2', () => {
    render(
      <AgentQueueCard
        queue1Transactions={[]}
        queue2Transactions={mockQueue2Transactions}
        currentTick={100}
      />
    )

    // Total: $10,000
    const queue2Section = screen.getByText(/Queue 2/i).closest('.bg-white')
    expect(queue2Section?.textContent).toMatch(/\$10,000\.00/)
  })

  it('displays empty state when Queue 1 is empty', () => {
    render(
      <AgentQueueCard
        queue1Transactions={[]}
        queue2Transactions={mockQueue2Transactions}
        currentTick={100}
      />
    )

    const queue1Section = screen.getByText(/Queue 1/i).closest('.bg-white')
    expect(queue1Section?.textContent).toMatch(/empty|no transactions/i)
  })

  it('displays empty state when Queue 2 is empty', () => {
    render(
      <AgentQueueCard
        queue1Transactions={mockQueue1Transactions}
        queue2Transactions={[]}
        currentTick={100}
      />
    )

    const queue2Section = screen.getByText(/Queue 2/i).closest('.bg-white')
    expect(queue2Section?.textContent).toMatch(/empty|no transactions/i)
  })

  it('displays empty state when both queues are empty', () => {
    render(
      <AgentQueueCard queue1Transactions={[]} queue2Transactions={[]} currentTick={100} />
    )

    expect(screen.getByText(/Queue 1/i)).toBeInTheDocument()
    expect(screen.getByText(/Queue 2/i)).toBeInTheDocument()

    // Should show empty indicators
    const allText = screen.getAllByText(/empty|no transactions/i)
    expect(allText.length).toBeGreaterThanOrEqual(2)
  })

  it('calculates ticks until deadline', () => {
    render(
      <AgentQueueCard
        queue1Transactions={mockQueue1Transactions}
        queue2Transactions={[]}
        currentTick={100}
      />
    )

    // tx1: deadline 150, current 100 = 50 ticks remaining
    expect(screen.getByText(/50.*tick/i)).toBeInTheDocument()
    // tx2: deadline 200, current 100 = 100 ticks remaining
    expect(screen.getByText(/100.*tick/i)).toBeInTheDocument()
  })

  it('highlights urgent transactions near deadline', () => {
    const urgentTransactions = [
      {
        tx_id: 'urgent1',
        receiver_id: 'BANK_X',
        amount: 500_000,
        priority: 9,
        deadline_tick: 110, // Only 10 ticks away!
      },
    ]

    const { container } = render(
      <AgentQueueCard
        queue1Transactions={urgentTransactions}
        queue2Transactions={[]}
        currentTick={100}
      />
    )

    // Should have warning/urgent styling on the card container
    const urgentCard = screen.getByText('urgent1').closest('.p-4')
    expect(urgentCard?.className).toMatch(/border-red/)
    expect(urgentCard?.className).toMatch(/bg-red/)
  })

  it('uses different styles for high priority transactions', () => {
    const highPriorityTx = [
      {
        tx_id: 'high_priority',
        receiver_id: 'BANK_Y',
        amount: 500_000,
        priority: 10,
        deadline_tick: 200,
      },
    ]

    render(
      <AgentQueueCard
        queue1Transactions={highPriorityTx}
        queue2Transactions={[]}
        currentTick={100}
      />
    )

    // High priority should have special badge styling
    const priorityBadge = screen.getByText('P10')
    expect(priorityBadge.className).toMatch(/red|orange/)
  })

  it('renders transactions in a list with proper spacing', () => {
    const { container } = render(
      <AgentQueueCard
        queue1Transactions={mockQueue1Transactions}
        queue2Transactions={mockQueue2Transactions}
        currentTick={100}
      />
    )

    // Should have list or grid elements for transactions
    const lists = container.querySelectorAll('[class*="space-y"], [class*="gap"]')
    expect(lists.length).toBeGreaterThan(0)
  })

  it('displays queues side by side on larger screens', () => {
    const { container } = render(
      <AgentQueueCard
        queue1Transactions={mockQueue1Transactions}
        queue2Transactions={mockQueue2Transactions}
        currentTick={100}
      />
    )

    // Should use grid or flex layout for side-by-side display
    const layout = container.querySelector('[class*="grid"], [class*="flex"]')
    expect(layout).toBeInTheDocument()
  })

  it('handles very long transaction IDs gracefully', () => {
    const longIdTransactions = [
      {
        tx_id: 'tx_very_long_id_that_might_overflow_12345678',
        receiver_id: 'BANK_B',
        amount: 500_000,
        priority: 5,
        deadline_tick: 150,
      },
    ]

    render(
      <AgentQueueCard
        queue1Transactions={longIdTransactions}
        queue2Transactions={[]}
        currentTick={100}
      />
    )

    // Should display (possibly truncated) but not break layout
    expect(screen.getByText(/tx_very_long_id/)).toBeInTheDocument()
  })
})
