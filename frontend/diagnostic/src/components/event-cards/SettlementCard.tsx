import { Link } from 'react-router-dom'
import { formatCurrency } from '@/utils/currency'
import type { BaseEventCardProps, SettlementDetails } from '@/types/events'

export function SettlementCard({ event, simId, isSelected = false }: BaseEventCardProps) {
  const details = event.details as SettlementDetails
  const { tx_id, sender_id, receiver_id, amount, settlement_type, ticks_to_settle } = details

  const isLSM = settlement_type === 'LSM'

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
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
          ✓ Settlement
        </span>
        <span
          className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium border ${
            isLSM
              ? 'bg-purple-50 text-purple-800 border-purple-200'
              : 'bg-blue-50 text-blue-800 border-blue-200'
          }`}
        >
          {settlement_type}
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
          <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
          <span className="font-semibold text-gray-900">{receiver_id}</span>
        </div>
      </div>

      {/* Amount and timing */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <div className="text-sm text-gray-600 mb-1">Amount Settled</div>
          <div className="text-xl font-bold text-green-700">{formatCurrency(amount)}</div>
        </div>
        {ticks_to_settle !== undefined && (
          <div>
            <div className="text-sm text-gray-600 mb-1">Time to Settle</div>
            <div className="text-base font-medium text-gray-900">{ticks_to_settle} ticks</div>
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
