import { formatCurrency } from '@/utils/currency'
import type { BaseEventCardProps, CollateralDetails } from '@/types/events'

export function CollateralEventCard({ event, simId, isSelected = false }: BaseEventCardProps) {
  const details = event.details as CollateralDetails
  const { agent_id, action, amount, reason, new_total } = details

  const isPost = action === 'Post'

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
        <span
          className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
            isPost ? 'bg-teal-100 text-teal-800' : 'bg-orange-100 text-orange-800'
          }`}
        >
          {isPost ? '📥' : '📤'} Collateral {action}
        </span>
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
          Tick {event.tick}
        </span>
        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-50 text-gray-700">
          Day {event.day}
        </span>
      </div>

      {/* Agent */}
      <div className="mb-4">
        <span className="text-sm text-gray-600">Agent: </span>
        <span className="font-semibold text-lg text-gray-900">{agent_id}</span>
      </div>

      {/* Amount and totals */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div>
          <div className="text-sm text-gray-600 mb-1">Amount</div>
          <div className={`text-xl font-bold ${isPost ? 'text-teal-700' : 'text-orange-700'}`}>
            {isPost ? '+' : '-'}{formatCurrency(amount)}
          </div>
        </div>
        <div>
          <div className="text-sm text-gray-600 mb-1">New Total</div>
          <div className="text-base font-medium text-gray-900">{formatCurrency(new_total)}</div>
        </div>
        {reason && (
          <div className="md:col-span-1">
            <div className="text-sm text-gray-600 mb-1">Reason</div>
            <div className="text-sm text-gray-900 italic">{reason}</div>
          </div>
        )}
      </div>
    </div>
  )
}
