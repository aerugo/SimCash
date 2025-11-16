import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useState, useMemo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { fetchCostTimeline } from '@/api/simulations'
import { formatCurrency } from '@/utils/currency'
import type { AgentTimelineResponse } from '@/types/api'

// Color palette for different agents
const AGENT_COLORS = [
  '#3b82f6', // blue-500
  '#ef4444', // red-500
  '#10b981', // green-500
  '#f59e0b', // amber-500
  '#8b5cf6', // violet-500
  '#ec4899', // pink-500
  '#14b8a6', // teal-500
  '#f97316', // orange-500
  '#6366f1', // indigo-500
  '#84cc16', // lime-500
]

interface ChartDataPoint {
  day: number
  [agentId: string]: number // accumulated cost for each agent
}

export function CostChartPage() {
  const { simId } = useParams<{ simId: string }>()
  const [selectedAgents, setSelectedAgents] = useState<Set<string>>(new Set())
  const [showCumulative, setShowCumulative] = useState(true)

  const { data: agentTimelines, isLoading, error } = useQuery({
    queryKey: ['costTimeline', simId],
    queryFn: () => fetchCostTimeline(simId!),
    enabled: !!simId,
  })

  // Transform data for the chart
  const chartData = useMemo(() => {
    if (!agentTimelines || agentTimelines.length === 0) return []

    // Find the maximum number of days across all agents
    const maxDays = Math.max(
      ...agentTimelines.map(timeline => timeline.daily_metrics.length)
    )

    const data: ChartDataPoint[] = []

    // Create a data point for each day
    for (let day = 0; day < maxDays; day++) {
      const dataPoint: ChartDataPoint = { day }

      agentTimelines.forEach((timeline: AgentTimelineResponse) => {
        const metric = timeline.daily_metrics[day]
        if (metric) {
          if (showCumulative) {
            // Calculate accumulated cost up to this day
            const accumulatedCost = timeline.daily_metrics
              .slice(0, day + 1)
              .reduce((sum, m) => sum + m.total_cost_cents, 0)
            dataPoint[timeline.agent_id] = accumulatedCost
          } else {
            // Show daily cost
            dataPoint[timeline.agent_id] = metric.total_cost_cents
          }
        } else {
          dataPoint[timeline.agent_id] = 0
        }
      })

      data.push(dataPoint)
    }

    return data
  }, [agentTimelines, showCumulative])

  // Get list of all agent IDs
  const allAgentIds = useMemo(() => {
    if (!agentTimelines) return []
    return agentTimelines.map((timeline: AgentTimelineResponse) => timeline.agent_id)
  }, [agentTimelines])

  // Get filtered agent IDs (either selected or all)
  const displayedAgentIds = useMemo(() => {
    if (selectedAgents.size === 0) return allAgentIds
    return allAgentIds.filter(id => selectedAgents.has(id))
  }, [allAgentIds, selectedAgents])

  // Toggle agent selection
  const toggleAgent = (agentId: string) => {
    setSelectedAgents(prev => {
      const newSet = new Set(prev)
      if (newSet.has(agentId)) {
        newSet.delete(agentId)
      } else {
        newSet.add(agentId)
      }
      return newSet
    })
  }

  // Select all agents
  const selectAllAgents = () => {
    setSelectedAgents(new Set())
  }

  // Deselect all agents (for clarity, we'll show a message when no agents are selected)
  const deselectAllAgents = () => {
    setSelectedAgents(new Set(allAgentIds))
  }

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
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          <h2 className="font-bold mb-2">Error loading cost data</h2>
          <p>{error instanceof Error ? error.message : 'Unknown error occurred'}</p>
        </div>
      </div>
    )
  }

  if (!agentTimelines || agentTimelines.length === 0) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-700 px-4 py-3 rounded">
          <p>No cost data available for this simulation.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-4 mb-4">
          <Link
            to={`/simulations/${simId}`}
            className="text-blue-600 hover:text-blue-800 font-medium"
          >
            ← Back to Dashboard
          </Link>
        </div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Cost Timeline Analysis
        </h1>
        <p className="text-gray-600">
          {showCumulative ? 'Accumulated' : 'Daily'} cost per agent over time
        </p>
      </div>

      {/* Controls */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex flex-wrap gap-4 items-center">
          {/* Cumulative Toggle */}
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">View:</label>
            <button
              onClick={() => setShowCumulative(true)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                showCumulative
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Accumulated
            </button>
            <button
              onClick={() => setShowCumulative(false)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                !showCumulative
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Daily
            </button>
          </div>

          {/* Agent Filter Controls */}
          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={selectAllAgents}
              className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
            >
              Show All
            </button>
            <button
              onClick={deselectAllAgents}
              className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
            >
              Hide All
            </button>
          </div>
        </div>

        {/* Agent Selection */}
        <div className="mt-4">
          <label className="text-sm font-medium text-gray-700 mb-2 block">
            Filter Agents:
          </label>
          <div className="flex flex-wrap gap-2">
            {allAgentIds.map((agentId, index) => {
              const isSelected = selectedAgents.size === 0 || selectedAgents.has(agentId)
              const color = AGENT_COLORS[index % AGENT_COLORS.length]

              return (
                <button
                  key={agentId}
                  onClick={() => toggleAgent(agentId)}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                    isSelected
                      ? 'ring-2 ring-offset-1'
                      : 'opacity-50 hover:opacity-75'
                  }`}
                  style={{
                    backgroundColor: isSelected ? color : '#e5e7eb',
                    color: isSelected ? '#ffffff' : '#374151',
                    borderColor: color,
                  }}
                >
                  {agentId}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          {showCumulative ? 'Accumulated Cost Over Time' : 'Daily Cost Over Time'}
        </h2>

        {displayedAgentIds.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            No agents selected. Please select at least one agent to view the chart.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={500}>
            <LineChart
              data={chartData}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="day"
                label={{ value: 'Day', position: 'insideBottom', offset: -5 }}
              />
              <YAxis
                label={{
                  value: `Cost (${showCumulative ? 'Accumulated' : 'Daily'})`,
                  angle: -90,
                  position: 'insideLeft',
                }}
                tickFormatter={(value) => {
                  // Format large numbers with K/M suffix
                  if (value >= 1000000) return `$${(value / 100 / 1000000).toFixed(1)}M`
                  if (value >= 1000) return `$${(value / 100 / 1000).toFixed(1)}K`
                  return `$${(value / 100).toFixed(0)}`
                }}
              />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (!active || !payload) return null

                  return (
                    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-4">
                      <p className="font-semibold text-gray-900 mb-2">Day {label}</p>
                      <div className="space-y-1">
                        {payload.map((entry, index) => (
                          <div key={index} className="flex items-center gap-2">
                            <div
                              className="w-3 h-3 rounded-full"
                              style={{ backgroundColor: entry.color }}
                            />
                            <span className="text-sm text-gray-700">
                              {entry.name}:
                            </span>
                            <span className="text-sm font-medium text-gray-900">
                              {formatCurrency(entry.value as number)}
                            </span>
                          </div>
                        ))}
                      </div>
                      {showCumulative && (
                        <div className="mt-2 pt-2 border-t border-gray-200">
                          <div className="flex justify-between">
                            <span className="text-sm font-semibold text-gray-700">Total:</span>
                            <span className="text-sm font-bold text-gray-900">
                              {formatCurrency(
                                payload.reduce((sum, entry) => sum + (entry.value as number), 0)
                              )}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                }}
              />
              <Legend />
              {displayedAgentIds.map((agentId) => (
                <Line
                  key={agentId}
                  type="monotone"
                  dataKey={agentId}
                  name={agentId}
                  stroke={AGENT_COLORS[allAgentIds.indexOf(agentId) % AGENT_COLORS.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Summary Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
        {agentTimelines.map((timeline: AgentTimelineResponse, index) => {
          const totalCost = timeline.daily_metrics.reduce(
            (sum, metric) => sum + metric.total_cost_cents,
            0
          )
          const avgDailyCost = totalCost / timeline.daily_metrics.length

          return (
            <div
              key={timeline.agent_id}
              className="bg-white rounded-lg shadow p-6"
            >
              <div className="flex items-center gap-2 mb-4">
                <div
                  className="w-4 h-4 rounded-full"
                  style={{
                    backgroundColor: AGENT_COLORS[index % AGENT_COLORS.length],
                  }}
                />
                <h3 className="text-lg font-semibold text-gray-900">
                  {timeline.agent_id}
                </h3>
              </div>
              <dl className="space-y-2">
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-600">Total Cost:</dt>
                  <dd className="text-sm font-medium text-gray-900">
                    {formatCurrency(totalCost)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-600">Avg Daily Cost:</dt>
                  <dd className="text-sm font-medium text-gray-900">
                    {formatCurrency(avgDailyCost)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-600">Days:</dt>
                  <dd className="text-sm font-medium text-gray-900">
                    {timeline.daily_metrics.length}
                  </dd>
                </div>
              </dl>
              <Link
                to={`/simulations/${simId}/agents/${timeline.agent_id}`}
                className="mt-4 block text-center px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
              >
                View Details
              </Link>
            </div>
          )
        })}
      </div>
    </div>
  )
}
