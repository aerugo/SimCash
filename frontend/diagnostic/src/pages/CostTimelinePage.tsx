import { useParams, Link } from 'react-router-dom'
import { useCosts } from '@/hooks/useSimulations'
import { AgentCostBreakdown } from '@/components/agent-dashboard/AgentCostBreakdown'
import { formatCurrency } from '@/utils/currency'

export function CostTimelinePage() {
  const { simId } = useParams<{ simId: string }>()
  const { data, isLoading, error } = useCosts(simId!)

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="text-lg text-gray-600">Loading cost data...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Link
          to={`/simulations/${simId}`}
          className="text-blue-600 hover:text-blue-800 mb-4 inline-block"
        >
          ← Back to Simulation Dashboard
        </Link>
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          <h2 className="font-bold mb-2">Error loading costs</h2>
          <p>{error instanceof Error ? error.message : 'Unknown error occurred'}</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return null
  }

  const { simulation_id, tick, day, agents, total_system_cost } = data

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <Link
          to={`/simulations/${simulation_id}`}
          className="text-blue-600 hover:text-blue-800 mb-4 inline-block"
        >
          ← Back to Simulation Dashboard
        </Link>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Cost Breakdown</h1>
        <p className="text-gray-600">
          Simulation: {simulation_id} | Tick: {tick} | Day: {day}
        </p>
      </div>

      {/* Total System Cost */}
      <div className="bg-gradient-to-r from-purple-500 to-purple-600 text-white rounded-lg shadow-lg p-6 mb-8">
        <h2 className="text-xl font-semibold mb-2">Total System Cost</h2>
        <div className="text-4xl font-bold">{formatCurrency(total_system_cost)}</div>
        <p className="text-purple-100 mt-2">
          Accumulated costs across all {Object.keys(agents).length} agents
        </p>
      </div>

      {/* Agent Cost Breakdowns */}
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-gray-900">Agent Breakdowns</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {Object.entries(agents).map(([agentId, costs]) => (
            <div key={agentId}>
              <div className="mb-2">
                <Link
                  to={`/simulations/${simulation_id}/agents/${agentId}`}
                  className="text-lg font-semibold text-blue-600 hover:text-blue-800 hover:underline"
                >
                  {agentId}
                </Link>
              </div>
              <AgentCostBreakdown
                liquidity_cost={costs.liquidity_cost}
                delay_cost={costs.delay_cost}
                collateral_cost={costs.collateral_cost}
                split_friction_cost={costs.split_friction_cost}
                deadline_penalty={costs.deadline_penalty}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
