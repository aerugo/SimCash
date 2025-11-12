import { Link } from 'react-router-dom'
import { formatCurrency } from '@/utils/currency'
import type { BaseEventCardProps, PolicyDecisionDetails } from '@/types/events'

export function PolicyDecisionCard({ event, simId, isSelected = false }: BaseEventCardProps) {
  const details = event.details as PolicyDecisionDetails
  const { tx_id, sender_id, receiver_id, amount, decision, reason } = details

  // Get decision icon and color
  const decisionConfig = {
    Submit: { icon: '↗', color: 'bg-green-100 text-green-800', label: 'Submitted to RTGS' },
    Hold: { icon: '⏸', color: 'bg-yellow-100 text-yellow-800', label: 'Held in Queue' },
    Drop: { icon: '✕', color: 'bg-red-100 text-red-800', label: 'Dropped' },
    Split: { icon: '⚡', color: 'bg-purple-100 text-purple-800', label: 'Split' },
  }

  const config = decisionConfig[decision] || { icon: '?', color: 'bg-gray-100 text-gray-800', label: decision }

  return (
    <div
      className={`bg-white rounded-lg p-6 transition-all ${
        isSelected
          ? 'border-blue-500 border-2 shadow-lg'
          : 'border border-gray-200 hover:shadow-md'
      }`}
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${config.color}`}>
          <span className="mr-2 text-lg">{config.icon}</span>
          {config.label}
        </span>
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
          Tick {event.tick}
        </span>
        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-50 text-gray-700">
          Day {event.day}
        </span>
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

      {/* Amount and reason */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <div className="text-sm text-gray-600 mb-1">Amount</div>
          <div className="text-xl font-bold text-gray-900">{formatCurrency(amount)}</div>
        </div>
        {reason && (
          <div>
            <div className="text-sm text-gray-600 mb-1">Reason</div>
            <div className="text-sm text-gray-900 italic">{reason}</div>
          </div>
        )}
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
