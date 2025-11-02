import { useParams, Link } from 'react-router-dom'
import { useTransactionLifecycle } from '@/hooks/useSimulations'
import { formatCurrency } from '@/utils/currency'
import type { TransactionEvent, RelatedTransaction } from '@/types/api'

export function TransactionDetailPage() {
  const { simId, txId } = useParams<{ simId: string; txId: string }>()
  const { data, isLoading, error } = useTransactionLifecycle(simId!, txId!)

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="text-lg text-gray-600">Loading transaction details...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          <h2 className="font-bold mb-2">Error loading transaction</h2>
          <p>{error instanceof Error ? error.message : 'Unknown error occurred'}</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return null
  }

  const { transaction, events, related_transactions } = data

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header with breadcrumb */}
      <div className="mb-8">
        <Link
          to={`/simulations/${simId}/events`}
          className="text-blue-600 hover:text-blue-800 mb-4 inline-block"
        >
          ← Back to events
        </Link>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Transaction: {transaction.tx_id}
        </h1>
        <p className="text-gray-600">Simulation: {simId}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left column: Transaction details */}
        <div className="lg:col-span-2 space-y-8">
          {/* Transaction Header Card */}
          <section className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Details</h2>
              <StatusBadge status={transaction.status} />
            </div>

            <div className="space-y-4">
              {/* Sender → Receiver */}
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="text-sm text-gray-600 mb-1">From</div>
                  <div className="font-medium text-lg">{transaction.sender_id}</div>
                </div>
                <div className="text-gray-400 text-2xl">→</div>
                <div className="flex-1">
                  <div className="text-sm text-gray-600 mb-1">To</div>
                  <div className="font-medium text-lg">{transaction.receiver_id}</div>
                </div>
              </div>

              {/* Amount and Priority */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-sm text-gray-600 mb-1">Amount</div>
                  <div className="font-medium text-xl text-green-600">
                    {formatCurrency(transaction.amount)}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600 mb-1">Priority</div>
                  <div className="font-medium text-xl">{transaction.priority}</div>
                </div>
              </div>

              {/* Ticks */}
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <div className="text-sm text-gray-600 mb-1">Arrival</div>
                  <div className="font-medium">Tick {transaction.arrival_tick}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600 mb-1">Deadline</div>
                  <div className="font-medium">Tick {transaction.deadline_tick}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600 mb-1">Settlement</div>
                  <div className="font-medium">
                    {transaction.settlement_tick
                      ? `Tick ${transaction.settlement_tick}`
                      : 'Not settled'}
                  </div>
                </div>
              </div>

              {/* Settlement info */}
              <div className="grid grid-cols-2 gap-4 pt-4 border-t">
                <div>
                  <div className="text-sm text-gray-600 mb-1">Amount Settled</div>
                  <div className="font-medium">
                    {formatCurrency(transaction.amount_settled)}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600 mb-1">Delay Cost</div>
                  <div className="font-medium text-red-600">
                    {formatCurrency(transaction.delay_cost)}
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Event Timeline */}
          {events.length > 0 && (
            <section className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-6">
                Event Timeline
              </h2>
              <EventTimeline events={events} />
            </section>
          )}
        </div>

        {/* Right column: Related info */}
        <div className="space-y-8">
          {/* Cost Breakdown */}
          <section className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Cost Breakdown
            </h2>
            <dl className="space-y-3">
              <div className="flex justify-between">
                <dt className="text-gray-600">Delay Cost:</dt>
                <dd className="font-medium text-red-600">
                  {formatCurrency(transaction.delay_cost)}
                </dd>
              </div>
            </dl>
          </section>

          {/* Related Transactions */}
          {related_transactions.length > 0 && (
            <section className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Related Transactions
              </h2>
              <RelatedTransactionsList
                transactions={related_transactions}
                simId={simId!}
              />
            </section>
          )}
        </div>
      </div>
    </div>
  )
}

interface StatusBadgeProps {
  status: string
}

function StatusBadge({ status }: StatusBadgeProps) {
  const colorMap: Record<string, string> = {
    settled: 'bg-green-100 text-green-800',
    pending: 'bg-yellow-100 text-yellow-800',
    dropped: 'bg-red-100 text-red-800',
    split: 'bg-blue-100 text-blue-800',
    partially_settled: 'bg-orange-100 text-orange-800',
  }

  const colorClass = colorMap[status] || 'bg-gray-100 text-gray-800'

  return (
    <span
      role="status"
      className={`px-3 py-1 rounded-full text-sm font-semibold ${colorClass}`}
    >
      {status}
    </span>
  )
}

interface EventTimelineProps {
  events: TransactionEvent[]
}

function EventTimeline({ events }: EventTimelineProps) {
  return (
    <div className="relative">
      {/* Vertical line */}
      <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200" />

      {/* Events */}
      <div className="space-y-6">
        {events.map((event, index) => (
          <div key={index} className="relative pl-12">
            {/* Dot */}
            <div
              className={`absolute left-2.5 top-1.5 h-3 w-3 rounded-full border-2 border-white ${getEventColor(
                event.event_type
              )}`}
            />

            {/* Content */}
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-gray-900">
                  {event.event_type}
                </span>
                <span className="text-sm text-gray-500">Tick {event.tick}</span>
              </div>

              {Object.keys(event.details).length > 0 && (
                <div className="text-sm text-gray-600">
                  {Object.entries(event.details).map(([key, value]) => (
                    <div key={key}>
                      <span className="font-medium">{key}: </span>
                      {String(value)}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function getEventColor(eventType: string): string {
  switch (eventType) {
    case 'Arrival':
      return 'bg-blue-500'
    case 'Settlement':
      return 'bg-green-500'
    case 'Drop':
      return 'bg-red-500'
    case 'PolicyHold':
      return 'bg-yellow-500'
    case 'LSMAttempt':
      return 'bg-purple-500'
    default:
      return 'bg-gray-500'
  }
}

interface RelatedTransactionsListProps {
  transactions: RelatedTransaction[]
  simId: string
}

function RelatedTransactionsList({
  transactions,
  simId,
}: RelatedTransactionsListProps) {
  return (
    <ul className="space-y-2">
      {transactions.map((tx, index) => (
        <li
          key={index}
          className="flex items-center justify-between p-3 bg-gray-50 rounded hover:bg-gray-100 transition-colors"
        >
          <div>
            <Link
              to={`/simulations/${simId}/transactions/${tx.tx_id}`}
              className="text-blue-600 hover:text-blue-800 font-medium"
            >
              {tx.tx_id}
            </Link>
            <div className="text-xs text-gray-600">
              {tx.relationship}
              {tx.split_index !== undefined && ` (Part ${tx.split_index})`}
            </div>
          </div>
        </li>
      ))}
    </ul>
  )
}
