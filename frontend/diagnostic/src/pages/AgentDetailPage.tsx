import { useParams, Link } from 'react-router-dom'
import { useAgentTimeline } from '@/hooks/useSimulations'
import { formatCurrency } from '@/utils/currency'

export function AgentDetailPage() {
  const { simId, agentId } = useParams<{ simId: string; agentId: string }>()
  const { data, isLoading, error } = useAgentTimeline(simId!, agentId!)

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="text-lg text-gray-600">Loading agent data...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          <h2 className="font-bold mb-2">Error loading agent</h2>
          <p>{error instanceof Error ? error.message : 'Unknown error occurred'}</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return null
  }

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
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Agent: {data.agent_id}</h1>
        <p className="text-gray-600">Simulation: {simId}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
        {/* Summary Metrics */}
        <section className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Summary Metrics</h2>
          <dl className="space-y-3">
            <div className="flex justify-between">
              <dt className="text-gray-600">Total Sent:</dt>
              <dd className="font-medium">{data.total_sent}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Total Received:</dt>
              <dd className="font-medium">{data.total_received}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Total Settled:</dt>
              <dd className="font-medium text-green-600">{data.total_settled}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Total Dropped:</dt>
              <dd className="font-medium text-red-600">{data.total_dropped}</dd>
            </div>
            <div className="flex justify-between border-t pt-3">
              <dt className="text-gray-600">Total Cost:</dt>
              <dd className="font-medium">{formatCurrency(data.total_cost_cents)}</dd>
            </div>
          </dl>
        </section>

        {/* Balance Metrics */}
        <section className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Balance Metrics</h2>
          <dl className="space-y-3">
            <div className="flex justify-between">
              <dt className="text-gray-600">Average Balance:</dt>
              <dd className="font-medium">{formatCurrency(data.avg_balance_cents)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Peak Overdraft:</dt>
              <dd className="font-medium text-red-600">
                {formatCurrency(data.peak_overdraft_cents)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Credit Limit:</dt>
              <dd className="font-medium">{formatCurrency(data.credit_limit_cents)}</dd>
            </div>
          </dl>
        </section>
      </div>

      {/* Daily Metrics Table */}
      {data.daily_metrics.length > 0 && (
        <section className="bg-white rounded-lg shadow mb-8">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">Daily Metrics</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Day
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Opening Balance
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Closing Balance
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Min Balance
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Max Balance
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Sent
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Received
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Cost
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data.daily_metrics.map((metric) => (
                  <tr key={metric.day} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap font-medium text-gray-900">
                      Day {metric.day}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatCurrency(metric.opening_balance)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatCurrency(metric.closing_balance)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatCurrency(metric.min_balance)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatCurrency(metric.max_balance)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {metric.transactions_sent}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {metric.transactions_received}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatCurrency(metric.total_cost_cents)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Collateral Events */}
      {data.collateral_events.length > 0 && (
        <section className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">Collateral Events</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Tick
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Event Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Amount
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data.collateral_events.map((event, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {event.tick}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          event.event_type === 'Pledge'
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-green-100 text-green-800'
                        }`}
                      >
                        {event.event_type}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatCurrency(event.amount_cents)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
