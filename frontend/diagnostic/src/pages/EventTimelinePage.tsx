import { useParams, Link } from 'react-router-dom'
import { useEvents } from '@/hooks/useSimulations'
import { formatCurrency } from '@/utils/currency'
import type { EventRecord } from '@/types/api'

export function EventTimelinePage() {
  const { simId } = useParams<{ simId: string }>()
  const { data, isLoading, error } = useEvents(simId!, {
    limit: 100,
    offset: 0,
  })

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

  const { events, total, limit, offset } = data
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

      {/* Pagination info */}
      {total > 0 && (
        <div className="mb-4 text-sm text-gray-600">
          Showing {showingFrom}-{showingTo} of {total} events
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
            <EventCard key={index} event={event} simId={simId!} />
          ))}
        </div>
      )}
    </div>
  )
}

interface EventCardProps {
  event: EventRecord
  simId: string
}

function EventCard({ event, simId }: EventCardProps) {
  const {
    tick,
    event_type,
    tx_id,
    sender_id,
    receiver_id,
    amount,
    priority,
    deadline_tick,
  } = event

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        {/* Left side: Event info */}
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-3">
            {/* Tick badge */}
            <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
              Tick {tick}
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
                  {deadline_tick !== undefined && (
                    <div>
                      <span className="text-gray-600">Deadline: </span>
                      <span className="font-medium">Tick {deadline_tick}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function getEventTypeBadgeColor(eventType: string): string {
  switch (eventType) {
    case 'Arrival':
      return 'bg-blue-100 text-blue-800'
    case 'Settlement':
      return 'bg-green-100 text-green-800'
    case 'Drop':
      return 'bg-red-100 text-red-800'
    case 'PolicyHold':
      return 'bg-yellow-100 text-yellow-800'
    case 'LSMAttempt':
      return 'bg-purple-100 text-purple-800'
    default:
      return 'bg-gray-100 text-gray-800'
  }
}
