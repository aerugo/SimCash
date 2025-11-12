import { formatCurrency } from '@/utils/currency'

export interface AgentFinancialOverviewProps {
  balance: number // in cents
  credit_limit: number // in cents
  liquidity: number // balance + available credit, in cents
  headroom: number // unused credit, in cents
}

export function AgentFinancialOverview({
  balance,
  credit_limit,
  liquidity,
  headroom,
}: AgentFinancialOverviewProps) {
  // Calculate credit usage percentage
  const creditUsed = Math.max(0, -balance) // Overdraft amount
  const creditUsagePercent = credit_limit > 0 ? Math.round((creditUsed / credit_limit) * 100) : 0
  const isHighCreditUsage = creditUsagePercent >= 80

  // Determine balance color
  const balanceColor = balance >= 0 ? 'text-green-700' : 'text-red-700'

  // Liquidity percentage (of credit limit, if any)
  const liquidityPercent = credit_limit > 0 ? Math.min(100, Math.round((liquidity / (balance + credit_limit)) * 100)) : 100

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-6">Financial Overview</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Balance */}
        <div>
          <div className="text-sm font-medium text-gray-600 mb-2">Balance</div>
          <div className={`text-3xl font-bold ${balanceColor}`}>
            {formatCurrency(balance)}
          </div>
          <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full ${balance >= 0 ? 'bg-green-500' : 'bg-red-500'}`}
              style={{ width: `${Math.min(100, Math.abs((balance / (balance + credit_limit)) * 100))}%` }}
              role="progressbar"
              aria-valuenow={balance}
              aria-valuemin={-credit_limit}
              aria-valuemax={balance + credit_limit}
            />
          </div>
        </div>

        {/* Credit Limit */}
        <div>
          <div className="text-sm font-medium text-gray-600 mb-2">Credit Limit</div>
          <div className="text-3xl font-bold text-gray-900">
            {formatCurrency(credit_limit)}
          </div>
          {credit_limit > 0 && (
            <div className="mt-2 text-sm">
              <span
                className={`font-medium ${
                  isHighCreditUsage ? 'text-red-600' : 'text-gray-600'
                }`}
              >
                {creditUsagePercent}% used
              </span>
            </div>
          )}
        </div>

        {/* Liquidity */}
        <div>
          <div className="text-sm font-medium text-gray-600 mb-2">Liquidity</div>
          <div className="text-3xl font-bold text-blue-700">
            {formatCurrency(liquidity)}
          </div>
          <div className="mt-2 text-sm text-gray-600">
            Available for payments
          </div>
        </div>

        {/* Headroom */}
        <div>
          <div className="text-sm font-medium text-gray-600 mb-2">Headroom</div>
          <div className="text-3xl font-bold text-gray-900">
            {formatCurrency(headroom)}
          </div>
          <div className="mt-2 text-sm text-gray-600">
            Unused credit
          </div>
        </div>
      </div>

      {/* Liquidity Gauge Visualization */}
      <div className="mt-6 pt-6 border-t border-gray-200">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-600">Liquidity Status</span>
          <span className="text-sm font-semibold text-blue-700">
            {formatCurrency(liquidity)}
          </span>
        </div>
        <div className="relative h-4 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="absolute h-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-300"
            style={{ width: `${liquidityPercent}%` }}
            role="progressbar"
            aria-valuenow={liquidity}
            aria-valuemin={0}
            aria-valuemax={balance + credit_limit}
          />
        </div>
      </div>

      {/* Warning for high credit usage */}
      {isHighCreditUsage && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <span className="text-sm font-medium text-red-800">
              High credit utilization ({creditUsagePercent}%)
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
