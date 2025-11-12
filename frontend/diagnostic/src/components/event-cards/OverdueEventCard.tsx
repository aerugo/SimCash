import { Link } from 'react-router-dom'
import { formatCurrency } from '@/utils/currency'
import type { BaseEventCardProps, OverdueDetails } from '@/types/events'

export function OverdueEventCard({ event, simId, isSelected = false }: BaseEventCardProps) {
  const details = event.details as OverdueDetails
  const { tx_id, sender_id, receiver_id, amount, remaining_amount, deadline_tick, deadline_penalty_cost } = details

  const ticksOverdue = event.tick - deadline_tick

  return (
    <div
      className={`bg-white rounded-lg p-6 transition-all border-l-4 border-l-red-500 ${
        isSelected
          ? 'border-blue-500 border-2 shadow-lg'
          : 'border border-gray-200 hover:shadow-md'
      }`}
    >
      {/* Header with warning */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
          ⚠️ Overdue
        </span>
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
          Tick {event.tick}
        </span>
        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-50 text-gray-700">
          Day {event.day}
        </span>
        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-red-50 text-red-700 border border-red-200">
          {ticksOverdue} ticks overdue
        </span>
      </div>

      {/* Transaction flow */}
      <div className="mb-4">
        <div className="flex items-center gap-3 text-base">
          <span className="font-semibold text-gray-900">{sender_id}</span>
          <svg className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
          <span className="font-semibold text-gray-900">{receiver_id}</span>
        </div>
      </div>

      {/* Amount and costs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div>
          <div className="text-sm text-gray-600 mb-1">Original Amount</div>
          <div className="text-lg font-bold text-gray-900">{formatCurrency(amount)}</div>
        </div>
        <div>
          <div className="text-sm text-gray-600 mb-1">Remaining</div>
          <div className="text-base font-medium text-gray-900">{formatCurrency(remaining_amount)}</div>
        </div>
        <div>
          <div className="text-sm text-gray-600 mb-1">Penalty Cost</div>
          <div className="text-lg font-bold text-red-700">{formatCurrency(deadline_penalty_cost)}</div>
        </div>
      </div>

      {/* Deadline info */}
      <div className="mb-4 p-3 bg-red-50 rounded-lg border border-red-200">
        <div className="text-sm">
          <span className="text-red-800 font-medium">Deadline missed:</span>
          <span className="text-red-700 ml-2">Tick {deadline_tick}</span>
          <span className="text-gray-600 ml-2">({ticksOverdue} ticks ago)</span>
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
