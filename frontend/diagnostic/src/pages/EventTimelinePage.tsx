import React, { useState, useRef, useEffect } from 'react'
import { useParams, Link, useSearchParams } from 'react-router-dom'
import { useEvents } from '@/hooks/useSimulations'
import { formatCurrency } from '@/utils/currency'
import { EventFilters, type EventFilterParams } from '@/components/events/EventFilters'
import { EventTypeLegend } from '@/components/events/EventTypeLegend'
import { exportEventsToCSV, generateCSVFilename } from '@/utils/csvExport'
import { useKeyboardNavigation } from '@/hooks/useKeyboardNavigation'
import type { EventRecord } from '@/types/api'

export function EventTimelinePage() {
  const { simId } = useParams<{ simId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()

  // Parse initial filters from URL
  const [filterParams, setFilterParams] = useState<EventFilterParams>(() => {
    const params: EventFilterParams = {}
    const tickMin = searchParams.get('tick_min')
    const tickMax = searchParams.get('tick_max')
    const day = searchParams.get('day')
    const agentId = searchParams.get('agent_id')
    const txId = searchParams.get('tx_id')
    const eventType = searchParams.get('event_type')
    const sort = searchParams.get('sort')

    if (tickMin) params.tick_min = parseInt(tickMin, 10)
    if (tickMax) params.tick_max = parseInt(tickMax, 10)
    if (day) params.day = parseInt(day, 10)
    if (agentId) params.agent_id = agentId
    if (txId) params.tx_id = txId
    if (eventType) params.event_type = eventType
    if (sort) params.sort = sort

    return params
  })

  const { data, isLoading, error } = useEvents(simId!, {
    limit: 100,
    offset: 0,
    ...filterParams,
  })

  // Keyboard navigation state
  const [selectedEventIndex, setSelectedEventIndex] = useState<number>(-1)
  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const filterInputRef = useRef<HTMLInputElement>(null)
  const eventRefs = useRef<Map<number, HTMLDivElement>>(new Map())

  // Reset selected index when events change
  useEffect(() => {
    setSelectedEventIndex(-1)
    eventRefs.current.clear()
  }, [data?.events])

  // Keyboard navigation handlers
  const handleNavigateDown = () => {
    if (!data?.events || data.events.length === 0) return

    const nextIndex = selectedEventIndex + 1
    if (nextIndex < data.events.length) {
      setSelectedEventIndex(nextIndex)
      // Scroll to event
      const eventElement = eventRefs.current.get(nextIndex)
      if (eventElement) {
        eventElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }
  }

  const handleNavigateUp = () => {
    if (!data?.events || data.events.length === 0) return

    const prevIndex = selectedEventIndex - 1
    if (prevIndex >= 0) {
      setSelectedEventIndex(prevIndex)
      // Scroll to event
      const eventElement = eventRefs.current.get(prevIndex)
      if (eventElement) {
        eventElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }
  }

  const handleFocusFilter = () => {
    // Open filter panel if it's closed
    if (!isFilterPanelOpen) {
      setIsFilterPanelOpen(true)
      // Wait for panel to render before focusing
      setTimeout(() => {
        filterInputRef.current?.focus()
      }, 100)
    } else {
      filterInputRef.current?.focus()
    }
  }

  const handleKeyboardClearFilters = () => {
    handleClearFilters()
  }

  // Enable keyboard navigation
  useKeyboardNavigation({
    onNavigateDown: handleNavigateDown,
    onNavigateUp: handleNavigateUp,
    onFocusFilter: handleFocusFilter,
    onClearFilters: handleKeyboardClearFilters,
    enabled: true,
  })

  const handleApplyFilters = (filters: EventFilterParams) => {
    setFilterParams(filters)

    // Update URL with filter params
    const newParams = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        newParams.set(key, String(value))
      }
    })
    setSearchParams(newParams)
  }

  const handleClearFilters = () => {
    setFilterParams({})
    setSearchParams({})
  }

  const handleExportCSV = () => {
    if (!data || data.events.length === 0) {
      return
    }
    const filename = generateCSVFilename(simId!, filterParams)
    exportEventsToCSV(data.events, filename)
  }

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="text-lg text-gray-600">Loading events...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          <h2 className="font-bold mb-2">Error loading events</h2>
          <p>{error instanceof Error ? error.message : 'Unknown error occurred'}</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return null
  }

  const { events, total, limit, offset} = data
  const showingFrom = offset + 1
  const showingTo = Math.min(offset + limit, total)

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header with breadcrumb */}
      <div className="mb-8">
        <Link
          to={`/simulations/${simId}`}
          className="text-blue-600 hover:text-blue-800 mb-4 inline-block"
        >
          ← Back to simulation
        </Link>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Event Timeline</h1>
        <p className="text-gray-600">
          Simulation: {simId}
        </p>
      </div>

      {/* Filters */}
      <EventFilters
        onApplyFilters={handleApplyFilters}
        onClearFilters={handleClearFilters}
        initialFilters={filterParams}
        filterInputRef={filterInputRef}
        isOpen={isFilterPanelOpen}
        onToggle={setIsFilterPanelOpen}
      />

      {/* Event Type Legend */}
      <EventTypeLegend />

      {/* Pagination info and actions */}
      {total > 0 && (
        <div className="mb-4 flex items-center justify-between">
          <div className="text-sm text-gray-600">
            Showing {showingFrom}-{showingTo} of {total} events
          </div>
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            Export to CSV
          </button>
        </div>
      )}

      {/* Empty state */}
      {events.length === 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <p className="text-gray-600">No events found</p>
        </div>
      )}

      {/* Event list */}
      {events.length > 0 && (
        <div className="space-y-4">
          {events.map((event, index) => (
            <EventCard
              key={event.event_id}
              event={event}
              simId={simId!}
              index={index}
              isSelected={selectedEventIndex === index}
              ref={(el) => {
                if (el) {
                  eventRefs.current.set(index, el)
                } else {
                  eventRefs.current.delete(index)
                }
              }}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface EventCardProps {
  event: EventRecord
  simId: string
  index: number
  isSelected: boolean
}

const EventCard = React.forwardRef<HTMLDivElement, EventCardProps>(
  ({ event, simId, isSelected }, ref) => {
  const { tick, event_type, tx_id, details, agent_id, day } = event

  // Extract common fields from details object
  const sender_id = details.sender_id as string | undefined
  const receiver_id = details.receiver_id as string | undefined
  const amount = details.amount as number | undefined
  const priority = details.priority as number | undefined
  const deadline = details.deadline as number | undefined
  const deadline_tick = details.deadline_tick as number | undefined

  return (
    <div
      ref={ref}
      data-event-id={event.event_id}
      className={`bg-white border rounded-lg p-6 transition-all ${
        isSelected
          ? 'border-blue-500 border-2 shadow-lg event-selected'
          : 'border-gray-200 hover:shadow-md'
      }`}
    >
      <div className="flex items-start justify-between">
        {/* Left side: Event info */}
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-3">
            {/* Tick badge */}
            <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
              Tick {tick}
            </span>

            {/* Day badge */}
            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-50 text-gray-700">
              Day {day}
            </span>

            {/* Event type badge */}
            <span
              className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getEventTypeBadgeColor(
                event_type
              )}`}
            >
              {event_type}
            </span>
          </div>

          {/* Agent info (if present) */}
          {agent_id && (
            <div className="mb-2 text-sm">
              <span className="text-gray-600">Agent: </span>
              <span className="font-medium text-gray-900">{agent_id}</span>
            </div>
          )}

          {/* Transaction details */}
          {tx_id && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-gray-600">Transaction:</span>
                <Link
                  to={`/simulations/${simId}/transactions/${tx_id}`}
                  className="text-blue-600 hover:text-blue-800 font-medium"
                >
                  {tx_id}
                </Link>
              </div>

              {sender_id && receiver_id && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium text-gray-900">{sender_id}</span>
                  <span className="text-gray-400">→</span>
                  <span className="font-medium text-gray-900">{receiver_id}</span>
                </div>
              )}

              {amount !== undefined && (
                <div className="flex items-center gap-4 text-sm">
                  <div>
                    <span className="text-gray-600">Amount: </span>
                    <span className="font-medium">{formatCurrency(amount)}</span>
                  </div>
                  {priority !== undefined && (
                    <div>
                      <span className="text-gray-600">Priority: </span>
                      <span className="font-medium">{priority}</span>
                    </div>
                  )}
                  {(deadline !== undefined || deadline_tick !== undefined) && (
                    <div>
                      <span className="text-gray-600">Deadline: </span>
                      <span className="font-medium">Tick {deadline || deadline_tick}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Other event-specific details */}
          {Object.keys(details).length > 0 && !tx_id && (
            <div className="mt-2 text-sm text-gray-600">
              <details>
                <summary className="cursor-pointer hover:text-gray-900">Event Details</summary>
                <pre className="mt-2 p-2 bg-gray-50 rounded text-xs overflow-x-auto">
                  {JSON.stringify(details, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </div>
      </div>
    </div>
  )
})

EventCard.displayName = 'EventCard'

function getEventTypeBadgeColor(eventType: string): string {
  switch (eventType) {
    case 'Arrival':
      return 'bg-blue-100 text-blue-800'
    case 'Settlement':
      return 'bg-green-100 text-green-800'
    case 'PolicyDrop':
      return 'bg-red-100 text-red-800'
    case 'PolicyHold':
      return 'bg-yellow-100 text-yellow-800'
    case 'PolicySubmit':
      return 'bg-indigo-100 text-indigo-800'
    case 'PolicySplit':
      return 'bg-pink-100 text-pink-800'
    case 'LsmBilateralOffset':
    case 'LsmCycleSettlement':
      return 'bg-purple-100 text-purple-800'
    case 'CollateralPost':
    case 'CollateralWithdraw':
      return 'bg-teal-100 text-teal-800'
    case 'QueuedRtgs':
      return 'bg-orange-100 text-orange-800'
    case 'CostAccrual':
      return 'bg-amber-100 text-amber-800'
    case 'EndOfDay':
      return 'bg-slate-100 text-slate-800'
    default:
      return 'bg-gray-100 text-gray-800'
  }
}
