import { useState } from 'react'
import { formatCurrency } from '@/utils/currency'

export interface LsmCycle {
  agents: string[]
  tx_ids: string[]
  tx_amounts: number[] // in cents
  net_positions: number[] // in cents
  max_net_outflow: number // in cents
  max_net_outflow_agent: string
  total_value: number // in cents
}

export interface LsmCycleVisualizerProps {
  cycle: LsmCycle
}

interface NodePosition {
  x: number
  y: number
  agent: string
  netPosition: number
}

function calculateNodePositions(agents: string[], netPositions: number[], centerX: number, centerY: number, radius: number): NodePosition[] {
  const angleStep = (2 * Math.PI) / agents.length
  return agents.map((agent, i) => {
    const angle = i * angleStep - Math.PI / 2 // Start from top
    return {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
      agent,
      netPosition: netPositions[i],
    }
  })
}

export function LsmCycleVisualizer({ cycle }: LsmCycleVisualizerProps) {
  const [hoveredAgent, setHoveredAgent] = useState<string | null>(null)

  const { agents, tx_ids, tx_amounts, net_positions, max_net_outflow, max_net_outflow_agent, total_value } = cycle

  // Calculate derived metrics
  const liquiditySaved = total_value - max_net_outflow
  const efficiency = total_value > 0 ? Math.round((liquiditySaved / total_value) * 100) : 0
  const cycleType = agents.length === 2 ? 'Bilateral' : 'Multilateral'

  // SVG dimensions
  const width = 500
  const height = 500
  const centerX = width / 2
  const centerY = height / 2
  const radius = 150

  // Calculate node positions
  const nodePositions = calculateNodePositions(agents, net_positions, centerX, centerY, radius)

  // Node radius
  const nodeRadius = 40

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">LSM Cycle Visualization</h2>
          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
            {cycleType}
          </span>
        </div>
        <p className="text-sm text-gray-600 mt-1">{agents.length} agents in cycle</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Graph Visualization */}
        <div className="flex justify-center items-center">
          <svg width={width} height={height} className="border border-gray-200 rounded-lg bg-gray-50">
            {/* Define arrow marker */}
            <defs>
              <marker
                id="arrowhead"
                markerWidth="10"
                markerHeight="10"
                refX="9"
                refY="3"
                orient="auto"
                markerUnits="strokeWidth"
              >
                <path d="M0,0 L0,6 L9,3 z" fill="#3b82f6" />
              </marker>
            </defs>

            {/* Draw edges (transactions) */}
            {agents.map((agent, i) => {
              const from = nodePositions[i]
              const to = nodePositions[(i + 1) % agents.length] // Next node in cycle

              // Calculate control point for curved arrow
              const midX = (from.x + to.x) / 2
              const midY = (from.y + to.y) / 2
              const dx = to.x - from.x
              const dy = to.y - from.y
              const curveOffset = 30
              const controlX = midX - dy / Math.sqrt(dx * dx + dy * dy) * curveOffset
              const controlY = midY + dx / Math.sqrt(dx * dx + dy * dy) * curveOffset

              // Adjust start and end points to node boundaries
              const angleToTarget = Math.atan2(to.y - from.y, to.x - from.x)
              const angleFromSource = Math.atan2(from.y - to.y, from.x - to.x)
              const startX = from.x + nodeRadius * Math.cos(angleToTarget)
              const startY = from.y + nodeRadius * Math.sin(angleToTarget)
              const endX = to.x + nodeRadius * Math.cos(angleFromSource)
              const endY = to.y + nodeRadius * Math.sin(angleFromSource)

              return (
                <g key={`edge-${i}`}>
                  {/* Curved arrow */}
                  <path
                    d={`M ${startX},${startY} Q ${controlX},${controlY} ${endX},${endY}`}
                    stroke="#3b82f6"
                    strokeWidth="2"
                    fill="none"
                    markerEnd="url(#arrowhead)"
                  />
                  {/* Amount label */}
                  <text
                    x={controlX}
                    y={controlY}
                    textAnchor="middle"
                    className="text-xs font-medium fill-blue-700"
                    dy="-5"
                  >
                    {formatCurrency(tx_amounts[i])}
                  </text>
                </g>
              )
            })}

            {/* Draw nodes (agents) */}
            {nodePositions.map((node) => {
              const isHovered = hoveredAgent === node.agent
              const isMaxOutflow = node.agent === max_net_outflow_agent

              return (
                <g
                  key={node.agent}
                  transform={`translate(${node.x},${node.y})`}
                  onMouseEnter={() => setHoveredAgent(node.agent)}
                  onMouseLeave={() => setHoveredAgent(null)}
                  className="cursor-pointer"
                >
                  {/* Node circle */}
                  <circle
                    r={nodeRadius}
                    fill={isMaxOutflow ? '#fee2e2' : isHovered ? '#dbeafe' : 'white'}
                    stroke={isMaxOutflow ? '#dc2626' : isHovered ? '#3b82f6' : '#9ca3af'}
                    strokeWidth={isMaxOutflow || isHovered ? 3 : 2}
                  />
                  {/* Agent name */}
                  <text
                    textAnchor="middle"
                    dy="-5"
                    className="text-xs font-semibold fill-gray-900"
                  >
                    {node.agent}
                  </text>
                  {/* Net position */}
                  <text
                    textAnchor="middle"
                    dy="10"
                    className={`text-xs font-medium ${
                      node.netPosition >= 0 ? 'fill-green-700' : 'fill-red-700'
                    }`}
                  >
                    {node.netPosition >= 0 ? '+' : ''}{formatCurrency(node.netPosition)}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>

        {/* Metrics Panel */}
        <div className="space-y-4">
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Cycle Metrics</h3>
            <dl className="space-y-2">
              <div className="flex justify-between">
                <dt className="text-sm text-gray-600">Total Value:</dt>
                <dd className="text-sm font-semibold text-gray-900">
                  {formatCurrency(total_value)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-600">Max Net Outflow:</dt>
                <dd className="text-sm font-semibold text-gray-900">
                  {formatCurrency(max_net_outflow)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-600">Liquidity Saved:</dt>
                <dd className="text-sm font-semibold text-green-700">
                  {formatCurrency(liquiditySaved)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-600">Efficiency:</dt>
                <dd className="text-sm font-semibold text-blue-700">{efficiency}%</dd>
              </div>
            </dl>
          </div>

          <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
            <div className="flex items-start gap-2">
              <svg className="w-5 h-5 text-orange-600 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
              <div>
                <p className="text-sm font-medium text-orange-900">Max Outflow Agent</p>
                <p className="text-sm text-orange-800 mt-1">
                  {max_net_outflow_agent} requires the most liquidity
                </p>
              </div>
            </div>
          </div>

          {/* Net Positions */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Net Positions</h3>
            <div className="space-y-2">
              {agents.map((agent, i) => (
                <div key={agent} className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">{agent}:</span>
                  <span
                    className={`text-sm font-semibold ${
                      net_positions[i] >= 0 ? 'text-green-700' : 'text-red-700'
                    }`}
                  >
                    {net_positions[i] >= 0 ? '+' : ''}{formatCurrency(net_positions[i])}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Transaction Details Table */}
      <div className="mt-6 pt-6 border-t border-gray-200">
        <h3 className="text-md font-medium text-gray-900 mb-4">Transaction Details</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                  Transaction ID
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                  From
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                  To
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                  Amount
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {tx_ids.map((txId, i) => (
                <tr key={txId} className="hover:bg-gray-50">
                  <td className="px-4 py-2 whitespace-nowrap text-sm font-mono text-gray-900">
                    {txId}
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">
                    {agents[i]}
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">
                    {agents[(i + 1) % agents.length]}
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap text-sm font-medium text-gray-900">
                    {formatCurrency(tx_amounts[i])}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
