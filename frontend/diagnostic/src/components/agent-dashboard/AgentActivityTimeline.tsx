import { formatCurrency } from '@/utils/currency'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  TooltipProps,
} from 'recharts'

export interface DailyMetric {
  day: number
  opening_balance: number // in cents
  closing_balance: number // in cents
  min_balance: number // in cents
  max_balance: number // in cents
  transactions_sent: number
  transactions_received: number
  total_cost_cents: number // in cents
}

export interface AgentActivityTimelineProps {
  dailyMetrics: DailyMetric[]
}

// Custom tooltip to format currency values
function CustomTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload || !payload.length) {
    return null
  }

  return (
    <div className="bg-white p-4 border border-gray-200 rounded-lg shadow-lg">
      <p className="font-medium text-gray-900 mb-2">Day {label}</p>
      {payload.map((entry, index) => {
        const value = entry.value as number
        const isCurrency = entry.dataKey?.toString().includes('balance') ||
                          entry.dataKey?.toString().includes('cost')

        return (
          <div key={index} className="flex items-center gap-2 text-sm">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-gray-600">{entry.name}:</span>
            <span className="font-medium text-gray-900">
              {isCurrency ? formatCurrency(value) : value}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export function AgentActivityTimeline({ dailyMetrics }: AgentActivityTimelineProps) {
  if (dailyMetrics.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Daily Activity Timeline</h2>
        <div className="py-12 text-center">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
          <p className="mt-2 text-sm text-gray-600">No activity data available</p>
          <p className="text-xs text-gray-500 mt-1">Daily metrics will appear here</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-gray-900">Daily Activity Timeline</h2>
        <p className="text-sm text-gray-600 mt-1">
          Balance, transactions, and cost metrics over time
        </p>
      </div>

      {/* Balance Chart */}
      <div className="mb-8">
        <h3 className="text-md font-medium text-gray-900 mb-4">Balance Trends</h3>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={dailyMetrics} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="day"
              label={{ value: 'Day', position: 'insideBottom', offset: -5 }}
              stroke="#6b7280"
            />
            <YAxis
              label={{ value: 'Balance ($)', angle: -90, position: 'insideLeft' }}
              tickFormatter={(value) => `$${(value / 100).toLocaleString()}`}
              stroke="#6b7280"
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Line
              type="monotone"
              dataKey="closing_balance"
              name="Closing Balance"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
            />
            <Line
              type="monotone"
              dataKey="min_balance"
              name="Min Balance"
              stroke="#ef4444"
              strokeWidth={2}
              dot={{ r: 3 }}
              strokeDasharray="5 5"
            />
            <Line
              type="monotone"
              dataKey="max_balance"
              name="Max Balance"
              stroke="#10b981"
              strokeWidth={2}
              dot={{ r: 3 }}
              strokeDasharray="5 5"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Transaction Volume Chart */}
      <div className="mb-8">
        <h3 className="text-md font-medium text-gray-900 mb-4">Transaction Volume</h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={dailyMetrics} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="day"
              label={{ value: 'Day', position: 'insideBottom', offset: -5 }}
              stroke="#6b7280"
            />
            <YAxis
              label={{ value: 'Count', angle: -90, position: 'insideLeft' }}
              stroke="#6b7280"
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Line
              type="monotone"
              dataKey="transactions_sent"
              name="Sent"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={{ r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="transactions_received"
              name="Received"
              stroke="#8b5cf6"
              strokeWidth={2}
              dot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Cost Chart */}
      <div>
        <h3 className="text-md font-medium text-gray-900 mb-4">Daily Costs</h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={dailyMetrics} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="day"
              label={{ value: 'Day', position: 'insideBottom', offset: -5 }}
              stroke="#6b7280"
            />
            <YAxis
              label={{ value: 'Cost ($)', angle: -90, position: 'insideLeft' }}
              tickFormatter={(value) => `$${(value / 100).toLocaleString()}`}
              stroke="#6b7280"
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Line
              type="monotone"
              dataKey="total_cost_cents"
              name="Total Cost"
              stroke="#dc2626"
              strokeWidth={2}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
