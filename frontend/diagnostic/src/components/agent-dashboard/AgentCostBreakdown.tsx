import { formatCurrency } from '@/utils/currency'

export interface AgentCostBreakdownProps {
  liquidity_cost: number // in cents
  delay_cost: number // in cents
  collateral_cost: number // in cents
  split_friction_cost: number // in cents
  deadline_penalty: number // in cents
}

interface CostCategory {
  name: string
  amount: number
  color: string
  bgColor: string
}

export function AgentCostBreakdown({
  liquidity_cost,
  delay_cost,
  collateral_cost,
  split_friction_cost,
  deadline_penalty,
}: AgentCostBreakdownProps) {
  // Calculate total cost
  const totalCost =
    liquidity_cost + delay_cost + collateral_cost + split_friction_cost + deadline_penalty

  // Define cost categories with colors
  const categories: CostCategory[] = [
    {
      name: 'Liquidity Cost',
      amount: liquidity_cost,
      color: 'bg-blue-500',
      bgColor: 'bg-blue-50',
    },
    {
      name: 'Delay Cost',
      amount: delay_cost,
      color: 'bg-yellow-500',
      bgColor: 'bg-yellow-50',
    },
    {
      name: 'Collateral Cost',
      amount: collateral_cost,
      color: 'bg-purple-500',
      bgColor: 'bg-purple-50',
    },
    {
      name: 'Split Friction Cost',
      amount: split_friction_cost,
      color: 'bg-orange-500',
      bgColor: 'bg-orange-50',
    },
    {
      name: 'Deadline Penalty',
      amount: deadline_penalty,
      color: 'bg-red-500',
      bgColor: 'bg-red-50',
    },
  ]

  // Sort by amount descending
  const sortedCategories = [...categories].sort((a, b) => b.amount - a.amount)

  // Find highest cost category
  const highestCost = sortedCategories[0]?.amount || 0

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-6">Cost Breakdown</h2>

      {/* Total Cost */}
      <div className="mb-6 p-4 bg-gray-50 rounded-lg">
        <div className="flex justify-between items-center">
          <span className="text-lg font-medium text-gray-700">Total Cost</span>
          <span className="text-2xl font-bold text-gray-900">{formatCurrency(totalCost)}</span>
        </div>
      </div>

      {/* Cost Categories */}
      <div className="grid grid-cols-1 gap-4">
        {sortedCategories.map((category) => {
          const percentage = totalCost > 0 ? Math.round((category.amount / totalCost) * 100) : 0
          const isHighest = category.amount === highestCost && highestCost > 0
          const barWidth = totalCost > 0 ? (category.amount / totalCost) * 100 : 0

          return (
            <div
              key={category.name}
              className={`p-4 rounded-lg border ${
                isHighest
                  ? 'border-gray-400 ring-2 ring-gray-200 font-bold'
                  : 'border-gray-200'
              } ${category.bgColor}`}
            >
              {/* Category Header */}
              <div className="flex justify-between items-start mb-3">
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-700 mb-1">{category.name}</div>
                  <div className="text-2xl font-semibold text-gray-900">
                    {formatCurrency(category.amount)}
                  </div>
                </div>
                {totalCost > 0 && (
                  <div className="ml-4">
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-white text-gray-700 border border-gray-200">
                      {percentage}%
                    </span>
                  </div>
                )}
              </div>

              {/* Visual Bar */}
              <div className="relative h-3 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`absolute h-full ${category.color} transition-all duration-300`}
                  style={{ width: `${barWidth}%` }}
                  role="progressbar"
                  aria-valuenow={category.amount}
                  aria-valuemin={0}
                  aria-valuemax={totalCost}
                  aria-label={`${category.name}: ${percentage}%`}
                />
              </div>
            </div>
          )
        })}
      </div>

      {/* No costs message */}
      {totalCost === 0 && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span className="text-sm font-medium text-green-800">
              No costs incurred - optimal performance!
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
