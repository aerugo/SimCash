/**
 * Event Card Components
 *
 * Type-specific event card components for rich event visualization.
 * Each component handles a specific event type with tailored UI.
 */

import React from 'react'
import type { EventRecord } from '@/types/api'
import type { BaseEventCardProps } from '@/types/events'
import {
  isArrivalEvent,
  isPolicyDecisionEvent,
  isSettlementEvent,
  isLsmBilateralEvent,
  isLsmCycleEvent,
  isCollateralEvent,
  isOverdueEvent,
} from '@/types/events'

import { ArrivalEventCard } from './ArrivalEventCard'
import { PolicyDecisionCard } from './PolicyDecisionCard'
import { SettlementCard } from './SettlementCard'
import { LsmCycleCard } from './LsmCycleCard'
import { CollateralEventCard } from './CollateralEventCard'
import { OverdueEventCard } from './OverdueEventCard'

// Export individual components
export {
  ArrivalEventCard,
  PolicyDecisionCard,
  SettlementCard,
  LsmCycleCard,
  CollateralEventCard,
  OverdueEventCard,
}

// Export LSM Cycle Visualizer
export { LsmCycleVisualizer, type LsmCycle, type LsmCycleVisualizerProps } from './LsmCycleVisualizer'

/**
 * Generic fallback card for events without specific implementations
 */
function GenericEventCard({ event, simId, isSelected = false }: BaseEventCardProps) {
  const { tick, event_type, tx_id, details, agent_id, day } = event

  return (
    <div
      className={`bg-white border rounded-lg p-6 transition-all ${
        isSelected
          ? 'border-blue-500 border-2 shadow-lg'
          : 'border-gray-200 hover:shadow-md'
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          {/* Header */}
          <div className="flex items-center gap-3 mb-3">
            <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
              {event_type}
            </span>
            <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
              Tick {tick}
            </span>
            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-50 text-gray-700">
              Day {day}
            </span>
          </div>

          {/* Agent */}
          {agent_id && (
            <div className="mb-2 text-sm">
              <span className="text-gray-600">Agent: </span>
              <span className="font-medium text-gray-900">{agent_id}</span>
            </div>
          )}

          {/* Transaction */}
          {tx_id && (
            <div className="mb-2 text-sm">
              <span className="text-gray-600">Transaction: </span>
              <span className="font-medium text-gray-900">{tx_id}</span>
            </div>
          )}

          {/* Details */}
          {Object.keys(details).length > 0 && (
            <details className="mt-2 text-sm text-gray-600">
              <summary className="cursor-pointer hover:text-gray-900">Event Details</summary>
              <pre className="mt-2 p-2 bg-gray-50 rounded text-xs overflow-x-auto">
                {JSON.stringify(details, null, 2)}
              </pre>
            </details>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * Factory function to render the appropriate event card based on event type
 */
export function EventCardFactory({ event, simId, isSelected = false }: BaseEventCardProps) {
  // Select appropriate card based on event type
  if (isArrivalEvent(event)) {
    return <ArrivalEventCard event={event} simId={simId} isSelected={isSelected} />
  }

  if (isPolicyDecisionEvent(event)) {
    return <PolicyDecisionCard event={event} simId={simId} isSelected={isSelected} />
  }

  if (isSettlementEvent(event)) {
    return <SettlementCard event={event} simId={simId} isSelected={isSelected} />
  }

  if (isLsmCycleEvent(event)) {
    return <LsmCycleCard event={event} simId={simId} isSelected={isSelected} />
  }

  if (isCollateralEvent(event)) {
    return <CollateralEventCard event={event} simId={simId} isSelected={isSelected} />
  }

  if (isOverdueEvent(event)) {
    return <OverdueEventCard event={event} simId={simId} isSelected={isSelected} />
  }

  // Fallback for events without specific implementations
  return <GenericEventCard event={event} simId={simId} isSelected={isSelected} />
}
