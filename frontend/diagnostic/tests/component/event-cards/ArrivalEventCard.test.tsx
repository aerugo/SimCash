import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ArrivalEventCard } from '@/components/event-cards/ArrivalEventCard'
import type { EventRecord } from '@/types/api'

// Helper to render component with router
function renderCard(event: EventRecord, simId = 'sim-001', isSelected = false) {
  return render(
    <MemoryRouter>
      <ArrivalEventCard event={event} simId={simId} isSelected={isSelected} />
    </MemoryRouter>
  )
}

describe('ArrivalEventCard', () => {
  const mockEvent: EventRecord = {
    event_id: 'evt-001',
    simulation_id: 'sim-001',
    tick: 10,
    day: 1,
    event_type: 'Arrival',
    event_timestamp: '2025-01-01T10:00:00Z',
    tx_id: 'tx-001',
    agent_id: 'BANK_A',
    details: {
      tx_id: 'tx-001',
      sender_id: 'BANK_A',
      receiver_id: 'BANK_B',
      amount: 100000, // $1,000.00
      priority: 8,
      deadline_tick: 50,
      is_divisible: false,
    },
    created_at: '2025-01-01T10:00:00Z',
  }

  it('renders arrival event with basic information', () => {
    renderCard(mockEvent)

    // Should show event type
    expect(screen.getByText('Arrival')).toBeInTheDocument()

    // Should show tick and day
    expect(screen.getByText(/Tick 10/i)).toBeInTheDocument()
    expect(screen.getByText(/Day 1/i)).toBeInTheDocument()

    // Should show sender and receiver
    expect(screen.getByText('BANK_A')).toBeInTheDocument()
    expect(screen.getByText('BANK_B')).toBeInTheDocument()
  })

  it('displays amount formatted as currency', () => {
    renderCard(mockEvent)

    // Amount should be formatted with $ and commas
    expect(screen.getByText(/\$1,000\.00/i)).toBeInTheDocument()
  })

  it('displays priority with appropriate badge', () => {
    renderCard(mockEvent)

    // Priority 8 is HIGH
    expect(screen.getByText(/priority/i)).toBeInTheDocument()
    expect(screen.getByText(/priority 8/i)).toBeInTheDocument()
    expect(screen.getByText(/high/i)).toBeInTheDocument()
  })

  it('displays deadline tick', () => {
    renderCard(mockEvent)

    expect(screen.getByText(/deadline/i)).toBeInTheDocument()
    expect(screen.getByText(/tick 50/i)).toBeInTheDocument()
  })

  it('calculates and displays ticks until deadline', () => {
    renderCard(mockEvent)

    // Deadline is 50, current tick is 10, so 40 ticks remaining
    expect(screen.getByText(/40 ticks remaining/i)).toBeInTheDocument()
  })

  it('shows transaction ID as a link', () => {
    renderCard(mockEvent)

    const link = screen.getByRole('link', { name: /tx-001/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/simulations/sim-001/transactions/tx-001')
  })

  it('displays different priority levels correctly', () => {
    // Test HIGH priority (8+)
    const highPriorityEvent = { ...mockEvent, details: { ...mockEvent.details, priority: 9 } }
    const { unmount } = renderCard(highPriorityEvent)
    expect(screen.getByText(/high/i)).toBeInTheDocument()
    unmount()

    // Test MEDIUM priority (5-7)
    const mediumPriorityEvent = { ...mockEvent, details: { ...mockEvent.details, priority: 6 } }
    renderCard(mediumPriorityEvent)
    expect(screen.getByText(/medium/i)).toBeInTheDocument()
    unmount()

    // Test LOW priority (0-4)
    const lowPriorityEvent = { ...mockEvent, details: { ...mockEvent.details, priority: 3 } }
    renderCard(lowPriorityEvent)
    expect(screen.getByText(/low/i)).toBeInTheDocument()
  })

  it('shows divisible badge when transaction is divisible', () => {
    const divisibleEvent = { ...mockEvent, details: { ...mockEvent.details, is_divisible: true } }
    renderCard(divisibleEvent)

    expect(screen.getByText(/divisible/i)).toBeInTheDocument()
  })

  it('does not show divisible badge when transaction is not divisible', () => {
    renderCard(mockEvent)

    expect(screen.queryByText(/divisible/i)).not.toBeInTheDocument()
  })

  it('applies selected styling when isSelected is true', () => {
    const { container } = renderCard(mockEvent, 'sim-001', true)

    const card = container.firstChild as HTMLElement
    expect(card).toHaveClass('border-blue-500')
    expect(card).toHaveClass('border-2')
  })

  it('does not apply selected styling when isSelected is false', () => {
    const { container } = renderCard(mockEvent, 'sim-001', false)

    const card = container.firstChild as HTMLElement
    expect(card).not.toHaveClass('border-blue-500')
    expect(card).toHaveClass('border-gray-200')
  })

  it('shows warning when deadline is very close (within 5 ticks)', () => {
    const urgentEvent = { ...mockEvent, tick: 46, details: { ...mockEvent.details } }
    renderCard(urgentEvent)

    // Should show warning badge or indicator
    expect(screen.getByText(/4 ticks remaining/i)).toBeInTheDocument()
    // Could check for warning color or icon here
  })

  it('shows directional arrow between sender and receiver', () => {
    renderCard(mockEvent)

    // Should show both sender and receiver with arrow between them
    expect(screen.getByText('BANK_A')).toBeInTheDocument()
    expect(screen.getByText('BANK_B')).toBeInTheDocument()

    // SVG arrow should be present (check by SVG attributes)
    const svgElements = document.querySelectorAll('svg')
    const hasArrowSvg = Array.from(svgElements).some(svg =>
      svg.querySelector('path[stroke-linecap="round"]')
    )
    expect(hasArrowSvg).toBe(true)
  })
})
