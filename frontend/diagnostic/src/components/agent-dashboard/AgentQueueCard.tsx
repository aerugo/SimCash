import { formatCurrency } from '@/utils/currency'

export interface QueueTransaction {
  tx_id: string
  receiver_id: string
  amount: number // in cents
  priority: number
  deadline_tick: number
}

export interface AgentQueueCardProps {
  queue1Transactions: QueueTransaction[]
  queue2Transactions: QueueTransaction[]
  currentTick: number
}

interface QueueSectionProps {
  title: string
  transactions: QueueTransaction[]
  currentTick: number
  queueNumber: 1 | 2
}

function QueueSection({ title, transactions, currentTick, queueNumber }: QueueSectionProps) {
  const totalValue = transactions.reduce((sum, tx) => sum + tx.amount, 0)
  const count = transactions.length
  const countText = count === 1 ? '1 transaction' : `${count} transactions`

  return (
    <div className="bg-white rounded-lg shadow p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          <p className="text-sm text-gray-600 mt-1">{countText}</p>
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-600">Total Value</div>
          <div className="text-lg font-bold text-gray-900">{formatCurrency(totalValue)}</div>
        </div>
      </div>

      {/* Transactions List */}
      {transactions.length === 0 ? (
        <div className="py-8 text-center">
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
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <p className="mt-2 text-sm text-gray-600">Queue is empty</p>
          <p className="text-xs text-gray-500 mt-1">No transactions pending</p>
        </div>
      ) : (
        <div className="space-y-3">
          {transactions.map((tx) => {
            const ticksUntilDeadline = tx.deadline_tick - currentTick
            const isUrgent = ticksUntilDeadline <= 20
            const isHighPriority = tx.priority >= 8

            return (
              <div
                key={tx.tx_id}
                className={`p-4 rounded-lg border transition-all ${
                  isUrgent
                    ? 'border-red-300 bg-red-50'
                    : isHighPriority
                      ? 'border-orange-200 bg-orange-50'
                      : 'border-gray-200 bg-gray-50 hover:bg-gray-100'
                }`}
              >
                {/* Transaction Header */}
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1 min-w-0">
                    <div className="font-mono text-sm font-medium text-gray-900 truncate">
                      {tx.tx_id}
                    </div>
                    <div className="text-xs text-gray-600 mt-1">
                      To: <span className="font-medium">{tx.receiver_id}</span>
                    </div>
                  </div>
                  <div
                    className={`ml-3 inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                      isHighPriority
                        ? 'bg-red-100 text-red-800'
                        : tx.priority >= 5
                          ? 'bg-orange-100 text-orange-800'
                          : 'bg-blue-100 text-blue-800'
                    }`}
                  >
                    P{tx.priority}
                  </div>
                </div>

                {/* Transaction Details */}
                <div className="grid grid-cols-2 gap-3 mt-3">
                  <div>
                    <div className="text-xs text-gray-600">Amount</div>
                    <div className="text-sm font-semibold text-gray-900">
                      {formatCurrency(tx.amount)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-600">Deadline</div>
                    <div
                      className={`text-sm font-medium ${
                        isUrgent ? 'text-red-700' : 'text-gray-900'
                      }`}
                    >
                      {ticksUntilDeadline} ticks
                    </div>
                  </div>
                </div>

                {/* Urgency Warning */}
                {isUrgent && (
                  <div className="mt-3 flex items-center gap-2 text-xs text-red-700">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                        clipRule="evenodd"
                      />
                    </svg>
                    <span className="font-medium">Urgent - deadline approaching</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function AgentQueueCard({
  queue1Transactions,
  queue2Transactions,
  currentTick,
}: AgentQueueCardProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <QueueSection
        title="Queue 1 (Internal)"
        transactions={queue1Transactions}
        currentTick={currentTick}
        queueNumber={1}
      />
      <QueueSection
        title="Queue 2 (RTGS)"
        transactions={queue2Transactions}
        currentTick={currentTick}
        queueNumber={2}
      />
    </div>
  )
}
