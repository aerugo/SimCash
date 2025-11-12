import { Link } from 'react-router-dom'
import { formatCurrency } from '@/utils/currency'
import type { BaseEventCardProps, LsmCycleDetails } from '@/types/events'

export function LsmCycleCard({ event, simId, isSelected = false }: BaseEventCardProps) {
  const details = event.details as LsmCycleDetails
  const {
    tx_ids,
    agents,
    tx_amounts,
    net_positions,
    max_net_outflow,
    max_net_outflow_agent,
    total_value,
    cycle_size,
  } = details

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
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-purple-100 text-purple-800">
          🔄 LSM Cycle Settlement
        </span>
        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200">
          {cycle_size}-way cycle
        </span>
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
          Tick {event.tick}
        </span>
        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-50 text-gray-700">
          Day {event.day}
        </span>
      </div>

      {/* Cycle diagram - agents in circle */}
      <div className="mb-4 p-4 bg-purple-50 rounded-lg">
        <div className="text-sm font-medium text-purple-900 mb-2">Cycle Participants</div>
        <div className="flex flex-wrap items-center gap-2">
          {agents.map((agent, index) => (
            <React.Fragment key={agent}>
              <span className="px-3 py-1 bg-white rounded-md border border-purple-200 font-medium text-gray-900">
                {agent}
              </span>
              {index < agents.length - 1 && (
                <svg className="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              )}
              {index === agents.length - 1 && (
                <svg className="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Cycle metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div>
          <div className="text-sm text-gray-600 mb-1">Total Value</div>
          <div className="text-lg font-bold text-purple-700">{formatCurrency(total_value)}</div>
        </div>
        <div>
          <div className="text-sm text-gray-600 mb-1">Max Outflow</div>
          <div className="text-base font-medium text-gray-900">{formatCurrency(max_net_outflow)}</div>
        </div>
        <div>
          <div className="text-sm text-gray-600 mb-1">Liquidity Saver</div>
          <div className="text-base font-medium text-purple-700">{max_net_outflow_agent}</div>
        </div>
      </div>

      {/* Transaction list */}
      <details className="text-sm">
        <summary className="cursor-pointer text-purple-700 font-medium hover:text-purple-900">
          View {tx_ids.length} transactions in cycle
        </summary>
        <div className="mt-2 space-y-1 pl-4">
          {tx_ids.map((txId, index) => (
            <div key={txId} className="flex items-center justify-between py-1">
              <Link
                to={`/simulations/${simId}/transactions/${txId}`}
                className="text-blue-600 hover:text-blue-800 font-medium hover:underline"
              >
                {txId}
              </Link>
              <span className="text-gray-600">{formatCurrency(tx_amounts[index])}</span>
            </div>
          ))}
        </div>
      </details>
    </div>
  )
}
