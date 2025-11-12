import { Link } from 'react-router-dom'
import { formatCurrency } from '@/utils/currency'
import type { BaseEventCardProps, ArrivalDetails, PriorityLevel } from '@/types/events'
import { getPriorityLevel, getPriorityColor } from '@/types/events'

export function ArrivalEventCard({ event, simId, isSelected = false }: BaseEventCardProps) {
  // Handle both old test format and new API format
  const details = event.details as Partial<ArrivalDetails>
  const tx_id = details.tx_id || event.tx_id || ''
  const sender_id = details.sender_id || (event.details.sender_id as string) || ''
  const receiver_id = details.receiver_id || (event.details.receiver_id as string) || ''
  const amount = details.amount || (event.details.amount as number) || 0
  const priority = details.priority || (event.details.priority as number) || 0
  const deadline_tick = details.deadline_tick || (event.details.deadline_tick as number) || 0
  const is_divisible = details.is_divisible || false

  // Calculate ticks remaining
  const ticksRemaining = deadline_tick - event.tick
  const isUrgent = ticksRemaining <= 5 && ticksRemaining > 0

  // Priority classification
  const priorityLevel: PriorityLevel = getPriorityLevel(priority)
  const priorityColorClass = getPriorityColor(priorityLevel)

  return (
    <div
      className={`bg-white rounded-lg p-6 transition-all ${
        isSelected
          ? 'border-blue-500 border-2 shadow-lg'
          : 'border border-gray-200 hover:shadow-md'
      }`}
    >
      {/* Header with badges */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
          Arrival
        </span>
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
          Tick {event.tick}
        </span>
        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-50 text-gray-700">
          Day {event.day}
        </span>
        <span
          className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium border ${priorityColorClass}`}
        >
          Priority {priority} ({priorityLevel.toUpperCase()})
        </span>
        {is_divisible && (
          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-purple-100 text-purple-800">
            Divisible
          </span>
        )}
      </div>

      {/* Transaction flow */}
      <div className="mb-4">
        <div className="flex items-center gap-3 text-base">
          <span className="font-semibold text-gray-900">{sender_id}</span>
          <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
          <span className="font-semibold text-gray-900">{receiver_id}</span>
        </div>
      </div>

      {/* Transaction details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <div className="text-sm text-gray-600 mb-1">Amount</div>
          <div className="text-xl font-bold text-gray-900">{formatCurrency(amount)}</div>
        </div>
        <div>
          <div className="text-sm text-gray-600 mb-1">Deadline</div>
          <div className="text-base font-medium text-gray-900">
            Tick {deadline_tick}
            <span
              className={`ml-2 text-sm ${
                isUrgent ? 'text-red-600 font-semibold' : 'text-gray-600'
              }`}
            >
              ({ticksRemaining} ticks remaining)
            </span>
          </div>
        </div>
      </div>

      {/* Transaction ID link */}
      <div className="text-sm">
        <span className="text-gray-600">Transaction ID: </span>
        <Link
          to={`/simulations/${simId}/transactions/${tx_id}`}
          className="text-blue-600 hover:text-blue-800 font-medium hover:underline"
        >
          {tx_id}
        </Link>
      </div>
    </div>
  )
}
