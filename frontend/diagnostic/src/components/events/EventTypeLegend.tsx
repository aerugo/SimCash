import { useState } from 'react'

interface EventTypeInfo {
  type: string
  category: 'transaction' | 'policy' | 'settlement' | 'lsm' | 'collateral' | 'cost' | 'system'
  color: string
  icon: string
  description: string
}

const EVENT_TYPES: EventTypeInfo[] = [
  // Transaction Events
  {
    type: 'Arrival',
    category: 'transaction',
    color: 'bg-blue-100 text-blue-800',
    icon: '📥',
    description: 'New transaction arrives at sender\'s queue',
  },

  // Policy Events
  {
    type: 'PolicySubmit',
    category: 'policy',
    color: 'bg-indigo-100 text-indigo-800',
    icon: '📤',
    description: 'Agent submits transaction to settlement queue',
  },
  {
    type: 'PolicyHold',
    category: 'policy',
    color: 'bg-yellow-100 text-yellow-800',
    icon: '⏸️',
    description: 'Agent holds transaction in queue (insufficient liquidity)',
  },
  {
    type: 'PolicyDrop',
    category: 'policy',
    color: 'bg-red-100 text-red-800',
    icon: '❌',
    description: 'Agent drops transaction (deadline passed or rejected)',
  },
  {
    type: 'PolicySplit',
    category: 'policy',
    color: 'bg-pink-100 text-pink-800',
    icon: '✂️',
    description: 'Agent splits large transaction into smaller parts',
  },

  // Settlement Events
  {
    type: 'Settlement',
    category: 'settlement',
    color: 'bg-green-100 text-green-800',
    icon: '✅',
    description: 'Transaction successfully settled via RTGS',
  },
  {
    type: 'QueuedRtgs',
    category: 'settlement',
    color: 'bg-orange-100 text-orange-800',
    icon: '⏳',
    description: 'Transaction queued in RTGS (awaiting liquidity)',
  },

  // LSM Events
  {
    type: 'LsmBilateralOffset',
    category: 'lsm',
    color: 'bg-purple-100 text-purple-800',
    icon: '🔄',
    description: 'Bilateral offset between two agents (liquidity saving)',
  },
  {
    type: 'LsmCycleSettlement',
    category: 'lsm',
    color: 'bg-purple-100 text-purple-800',
    icon: '⚙️',
    description: 'Multilateral cycle settlement (multiple agents)',
  },

  // Collateral Events
  {
    type: 'CollateralPost',
    category: 'collateral',
    color: 'bg-teal-100 text-teal-800',
    icon: '💰',
    description: 'Agent posts collateral for intraday credit',
  },
  {
    type: 'CollateralWithdraw',
    category: 'collateral',
    color: 'bg-teal-100 text-teal-800',
    icon: '💸',
    description: 'Agent withdraws collateral',
  },

  // Cost Events
  {
    type: 'CostAccrual',
    category: 'cost',
    color: 'bg-amber-100 text-amber-800',
    icon: '💵',
    description: 'Costs accrued for agent (delays, splits, overdrafts)',
  },

  // System Events
  {
    type: 'EndOfDay',
    category: 'system',
    color: 'bg-slate-100 text-slate-800',
    icon: '🌙',
    description: 'End of day processing and settlement',
  },
]

const CATEGORY_LABELS: Record<string, string> = {
  transaction: 'Transaction Lifecycle',
  policy: 'Policy Decisions',
  settlement: 'Settlement Operations',
  lsm: 'Liquidity Saving Mechanism',
  collateral: 'Collateral Management',
  cost: 'Cost Tracking',
  system: 'System Events',
}

export function EventTypeLegend() {
  const [isOpen, setIsOpen] = useState(false)

  // Group events by category
  const eventsByCategory = EVENT_TYPES.reduce((acc, event) => {
    if (!acc[event.category]) {
      acc[event.category] = []
    }
    acc[event.category]!.push(event)
    return acc
  }, {} as Record<string, EventTypeInfo[]>)

  return (
    <div className="mb-4">
      {/* Toggle button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors"
        aria-label="Toggle event type legend"
      >
        <span>ℹ️ Event Type Legend</span>
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Legend panel */}
      {isOpen && (
        <div className="mt-2 p-4 bg-white border border-gray-200 rounded-lg shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Event Types</h3>

          <div className="space-y-6">
            {Object.entries(eventsByCategory).map(([category, events]) => (
              <div key={category}>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">
                  {CATEGORY_LABELS[category]}
                </h4>
                <div className="space-y-2">
                  {events.map((event) => (
                    <div key={event.type} className="flex items-start gap-3">
                      {/* Icon and badge */}
                      <div className="flex items-center gap-2 min-w-[180px]">
                        <span className="text-lg" role="img" aria-label={event.type}>
                          {event.icon}
                        </span>
                        <span
                          className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${event.color}`}
                        >
                          {event.type}
                        </span>
                      </div>

                      {/* Description */}
                      <p className="text-sm text-gray-600 flex-1">{event.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Close button */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <button
              onClick={() => setIsOpen(false)}
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Close Legend
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
