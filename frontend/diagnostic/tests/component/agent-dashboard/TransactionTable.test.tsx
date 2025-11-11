import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TransactionTable } from '@/components/agent-dashboard/TransactionTable'

describe('TransactionTable', () => {
  const mockTransactions = [
    {
      tx_id: 'tx1',
      type: 'sent' as const,
      counterparty: 'BANK_B',
      amount: 500_000, // $5,000.00
      status: 'settled' as const,
      tick: 100,
    },
    {
      tx_id: 'tx2',
      type: 'received' as const,
      counterparty: 'BANK_C',
      amount: 300_000, // $3,000.00
      status: 'pending' as const,
      tick: 150,
    },
    {
      tx_id: 'tx3',
      type: 'sent' as const,
      counterparty: 'BANK_D',
      amount: 1_000_000, // $10,000.00
      status: 'dropped' as const,
      tick: 200,
    },
  ]

  it('displays all transactions in a table', () => {
    render(<TransactionTable transactions={mockTransactions} />)

    expect(screen.getByText('tx1')).toBeInTheDocument()
    expect(screen.getByText('tx2')).toBeInTheDocument()
    expect(screen.getByText('tx3')).toBeInTheDocument()
  })

  it('displays transaction type (sent/received)', () => {
    render(<TransactionTable transactions={mockTransactions} />)

    expect(screen.getAllByText(/sent/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/received/i).length).toBeGreaterThan(0)
  })

  it('displays counterparty names', () => {
    render(<TransactionTable transactions={mockTransactions} />)

    expect(screen.getByText('BANK_B')).toBeInTheDocument()
    expect(screen.getByText('BANK_C')).toBeInTheDocument()
    expect(screen.getByText('BANK_D')).toBeInTheDocument()
  })

  it('displays amounts with currency formatting', () => {
    render(<TransactionTable transactions={mockTransactions} />)

    expect(screen.getByText('$5,000.00')).toBeInTheDocument()
    expect(screen.getByText('$3,000.00')).toBeInTheDocument()
    expect(screen.getByText('$10,000.00')).toBeInTheDocument()
  })

  it('displays transaction status', () => {
    render(<TransactionTable transactions={mockTransactions} />)

    expect(screen.getByText(/settled/i)).toBeInTheDocument()
    expect(screen.getByText(/pending/i)).toBeInTheDocument()
    expect(screen.getByText(/dropped/i)).toBeInTheDocument()
  })

  it('displays tick numbers', () => {
    render(<TransactionTable transactions={mockTransactions} />)

    expect(screen.getByText('100')).toBeInTheDocument()
    expect(screen.getByText('150')).toBeInTheDocument()
    expect(screen.getByText('200')).toBeInTheDocument()
  })

  it('has table headers for all columns', () => {
    const { container } = render(<TransactionTable transactions={mockTransactions} />)

    // Look for headers within the table header row
    const thead = container.querySelector('thead')
    expect(thead).toBeInTheDocument()

    expect(within(thead!).getByText(/transaction id/i)).toBeInTheDocument()
    expect(within(thead!).getByText(/^type$/i)).toBeInTheDocument()
    expect(within(thead!).getByText(/counterparty/i)).toBeInTheDocument()
    expect(within(thead!).getByText(/amount/i)).toBeInTheDocument()
    expect(within(thead!).getByText(/status/i)).toBeInTheDocument()
    expect(within(thead!).getByText(/tick/i)).toBeInTheDocument()
  })

  it('displays empty state when no transactions', () => {
    render(<TransactionTable transactions={[]} />)

    expect(screen.getByText(/no transactions/i)).toBeInTheDocument()
  })

  it('sorts by amount when amount header is clicked', async () => {
    const user = userEvent.setup()
    render(<TransactionTable transactions={mockTransactions} />)

    // Click amount header to sort
    const amountHeader = screen.getByText(/amount/i)
    await user.click(amountHeader)

    // Check if transactions are sorted (ascending by default)
    const rows = screen.getAllByRole('row')
    const dataRows = rows.slice(1) // Skip header row

    // After sorting ascending: $3,000 < $5,000 < $10,000
    expect(dataRows[0].textContent).toMatch(/\$3,000\.00/)
    expect(dataRows[1].textContent).toMatch(/\$5,000\.00/)
    expect(dataRows[2].textContent).toMatch(/\$10,000\.00/)
  })

  it('sorts by tick when tick header is clicked', async () => {
    const user = userEvent.setup()
    render(<TransactionTable transactions={mockTransactions} />)

    // Click tick header to toggle sort (default is already tick ascending, so this makes it descending)
    const tickHeader = screen.getByText(/tick/i)
    await user.click(tickHeader)

    // Check if transactions are sorted descending: 200 > 150 > 100
    let rows = screen.getAllByRole('row')
    let dataRows = rows.slice(1)
    expect(dataRows[0].textContent).toMatch(/200/)
    expect(dataRows[1].textContent).toMatch(/150/)
    expect(dataRows[2].textContent).toMatch(/100/)

    // Click again to get ascending
    await user.click(tickHeader)
    rows = screen.getAllByRole('row')
    dataRows = rows.slice(1)
    expect(dataRows[0].textContent).toMatch(/100/)
    expect(dataRows[1].textContent).toMatch(/150/)
    expect(dataRows[2].textContent).toMatch(/200/)
  })

  it('reverses sort order on second click', async () => {
    const user = userEvent.setup()
    render(<TransactionTable transactions={mockTransactions} />)

    const amountHeader = screen.getByText(/amount/i)

    // First click: ascending
    await user.click(amountHeader)
    let rows = screen.getAllByRole('row')
    let dataRows = rows.slice(1)
    expect(dataRows[0].textContent).toMatch(/\$3,000\.00/)

    // Second click: descending
    await user.click(amountHeader)
    rows = screen.getAllByRole('row')
    dataRows = rows.slice(1)
    expect(dataRows[0].textContent).toMatch(/\$10,000\.00/)
  })

  it('filters by transaction type (sent only)', async () => {
    const user = userEvent.setup()
    render(<TransactionTable transactions={mockTransactions} />)

    // Find and click filter dropdown/button for "Sent"
    const filterButton = screen.getByRole('button', { name: /filter.*type/i })
    await user.click(filterButton)

    // Use exact menu item text
    const sentOption = screen.getByRole('menuitem', { name: /sent only/i })
    await user.click(sentOption)

    // Should only show sent transactions (tx1, tx3)
    expect(screen.getByText('tx1')).toBeInTheDocument()
    expect(screen.getByText('tx3')).toBeInTheDocument()
    expect(screen.queryByText('tx2')).not.toBeInTheDocument()
  })

  it('filters by transaction type (received only)', async () => {
    const user = userEvent.setup()
    render(<TransactionTable transactions={mockTransactions} />)

    const filterButton = screen.getByRole('button', { name: /filter.*type/i })
    await user.click(filterButton)

    // Use exact menu item text
    const receivedOption = screen.getByRole('menuitem', { name: /received only/i })
    await user.click(receivedOption)

    // Should only show received transactions (tx2)
    expect(screen.getByText('tx2')).toBeInTheDocument()
    expect(screen.queryByText('tx1')).not.toBeInTheDocument()
    expect(screen.queryByText('tx3')).not.toBeInTheDocument()
  })

  it('uses color coding for different statuses', () => {
    render(<TransactionTable transactions={mockTransactions} />)

    // Settled should be green
    const settledBadge = screen.getByText(/settled/i)
    expect(settledBadge.className).toMatch(/green/)

    // Pending should be yellow/orange
    const pendingBadge = screen.getByText(/pending/i)
    expect(pendingBadge.className).toMatch(/yellow|orange/)

    // Dropped should be red
    const droppedBadge = screen.getByText(/dropped/i)
    expect(droppedBadge.className).toMatch(/red/)
  })

  it('displays sent transactions with different styling than received', () => {
    render(<TransactionTable transactions={mockTransactions} />)

    // Get sent and received type badges
    const typeBadges = screen.getAllByText(/sent|received/i)

    // Should have different colors for sent vs received
    const sentBadges = typeBadges.filter((badge) => badge.textContent?.match(/sent/i))
    const receivedBadges = typeBadges.filter((badge) => badge.textContent?.match(/received/i))

    expect(sentBadges[0].className).not.toBe(receivedBadges[0].className)
  })

  it('shows transaction count', () => {
    render(<TransactionTable transactions={mockTransactions} />)

    expect(screen.getByText(/3 transaction/i)).toBeInTheDocument()
  })

  it('updates count when filtered', async () => {
    const user = userEvent.setup()
    render(<TransactionTable transactions={mockTransactions} />)

    const filterButton = screen.getByRole('button', { name: /filter.*type/i })
    await user.click(filterButton)

    // Use exact menu item text
    const sentOption = screen.getByRole('menuitem', { name: /sent only/i })
    await user.click(sentOption)

    // Should show 2 transactions (only sent)
    expect(screen.getByText(/2 transaction/i)).toBeInTheDocument()
  })

  it('renders table with proper accessibility attributes', () => {
    const { container } = render(<TransactionTable transactions={mockTransactions} />)

    // Should have proper table structure
    const table = container.querySelector('table')
    expect(table).toBeInTheDocument()

    // Should have thead and tbody
    const thead = table?.querySelector('thead')
    const tbody = table?.querySelector('tbody')
    expect(thead).toBeInTheDocument()
    expect(tbody).toBeInTheDocument()
  })
})
