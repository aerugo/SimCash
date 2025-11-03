import { useState } from 'react'

export interface EventFilterParams {
  tick_min?: number
  tick_max?: number
  day?: number
  agent_id?: string
  tx_id?: string
  event_type?: string
  sort?: string
}

interface EventFiltersProps {
  onApplyFilters: (filters: EventFilterParams) => void
  onClearFilters: () => void
  availableAgents?: string[]
  initialFilters?: EventFilterParams
  filterInputRef?: React.RefObject<HTMLInputElement>
  isOpen?: boolean
  onToggle?: (open: boolean) => void
}

const EVENT_TYPES = [
  'Arrival',
  'PolicySubmit',
  'PolicyHold',
  'PolicyDrop',
  'PolicySplit',
  'Settlement',
  'QueuedRtgs',
  'LsmBilateralOffset',
  'LsmCycleSettlement',
  'CollateralPost',
  'CollateralWithdraw',
  'CostAccrual',
  'EndOfDay',
]

export function EventFilters({
  onApplyFilters,
  onClearFilters,
  availableAgents = [],
  initialFilters = {},
  filterInputRef,
  isOpen: isOpenProp,
  onToggle,
}: EventFiltersProps) {
  const [internalIsOpen, setInternalIsOpen] = useState(false)

  // Use controlled state if provided, otherwise use internal state
  const isOpen = isOpenProp !== undefined ? isOpenProp : internalIsOpen
  const setIsOpen = onToggle || setInternalIsOpen
  const [tickMin, setTickMin] = useState<string>(initialFilters.tick_min?.toString() || '')
  const [tickMax, setTickMax] = useState<string>(initialFilters.tick_max?.toString() || '')
  const [day, setDay] = useState<string>(initialFilters.day?.toString() || '')
  const [agentId, setAgentId] = useState<string>(initialFilters.agent_id || '')
  const [txId, setTxId] = useState<string>(initialFilters.tx_id || '')
  const [eventType, setEventType] = useState<string>(initialFilters.event_type || '')
  const [sort, setSort] = useState<string>(initialFilters.sort || 'tick_asc')

  const handleApply = () => {
    const filters: EventFilterParams = {}

    if (tickMin) filters.tick_min = parseInt(tickMin, 10)
    if (tickMax) filters.tick_max = parseInt(tickMax, 10)
    if (day) filters.day = parseInt(day, 10)
    if (agentId) filters.agent_id = agentId
    if (txId) filters.tx_id = txId
    if (eventType) filters.event_type = eventType
    if (sort && sort !== 'tick_asc') filters.sort = sort

    onApplyFilters(filters)
    setIsOpen(false)
  }

  const handleClear = () => {
    setTickMin('')
    setTickMax('')
    setDay('')
    setAgentId('')
    setTxId('')
    setEventType('')
    setSort('tick_asc')
    onClearFilters()
    setIsOpen(false)
  }

  const activeFilterCount = [
    tickMin,
    tickMax,
    day,
    agentId,
    txId,
    eventType,
    sort !== 'tick_asc' ? sort : null,
  ].filter(Boolean).length

  return (
    <div className="mb-6">
      {/* Toggle button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
      >
        <span className="font-medium">Filters</span>
        {activeFilterCount > 0 && (
          <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
            {activeFilterCount}
          </span>
        )}
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Filter panel */}
      {isOpen && (
        <div className="mt-4 p-6 bg-white border border-gray-200 rounded-lg shadow-sm">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Tick range */}
            <div>
              <label htmlFor="tick-min" className="block text-sm font-medium text-gray-700 mb-1">
                Min Tick
              </label>
              <input
                id="tick-min"
                ref={filterInputRef}
                type="number"
                min="0"
                value={tickMin}
                onChange={(e) => setTickMin(e.target.value)}
                placeholder="0"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label htmlFor="tick-max" className="block text-sm font-medium text-gray-700 mb-1">
                Max Tick
              </label>
              <input
                id="tick-max"
                type="number"
                min="0"
                value={tickMax}
                onChange={(e) => setTickMax(e.target.value)}
                placeholder="1000"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Day */}
            <div>
              <label htmlFor="day" className="block text-sm font-medium text-gray-700 mb-1">
                Day
              </label>
              <input
                id="day"
                type="number"
                min="0"
                value={day}
                onChange={(e) => setDay(e.target.value)}
                placeholder="Any"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Agent */}
            <div>
              <label htmlFor="agent" className="block text-sm font-medium text-gray-700 mb-1">
                Agent
              </label>
              <select
                id="agent"
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Agents</option>
                {availableAgents.map((agent) => (
                  <option key={agent} value={agent}>
                    {agent}
                  </option>
                ))}
              </select>
            </div>

            {/* Event Type */}
            <div>
              <label htmlFor="event-type" className="block text-sm font-medium text-gray-700 mb-1">
                Event Type
              </label>
              <select
                id="event-type"
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Types</option>
                {EVENT_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>

            {/* Transaction ID */}
            <div>
              <label htmlFor="tx-id" className="block text-sm font-medium text-gray-700 mb-1">
                Transaction ID
              </label>
              <input
                id="tx-id"
                type="text"
                value={txId}
                onChange={(e) => setTxId(e.target.value)}
                placeholder="tx-..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Sort */}
            <div>
              <label htmlFor="sort" className="block text-sm font-medium text-gray-700 mb-1">
                Sort Order
              </label>
              <select
                id="sort"
                value={sort}
                onChange={(e) => setSort(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="tick_asc">Tick Ascending</option>
                <option value="tick_desc">Tick Descending</option>
              </select>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex gap-3 mt-6">
            <button
              onClick={handleApply}
              className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors font-medium"
            >
              Apply Filters
            </button>
            <button
              onClick={handleClear}
              className="px-6 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors font-medium"
            >
              Clear All
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
