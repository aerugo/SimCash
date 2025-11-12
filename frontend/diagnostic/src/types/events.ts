/**
 * Event Detail Type Definitions
 *
 * These types define the shape of the `details` field for each event type.
 * Based on the backend Event enum serialization.
 */

import type { EventRecord } from './api'

/**
 * Common base interface for event props
 */
export interface BaseEventCardProps {
  event: EventRecord
  simId: string
  isSelected?: boolean
}

/**
 * Arrival event details
 */
export interface ArrivalDetails {
  tx_id: string
  sender_id: string
  receiver_id: string
  amount: number
  priority: number
  deadline_tick: number
  is_divisible?: boolean
}

/**
 * Policy decision event details (Submit/Hold/Drop/Split)
 */
export interface PolicyDecisionDetails {
  tx_id: string
  sender_id: string
  receiver_id: string
  amount: number
  decision: 'Submit' | 'Hold' | 'Drop' | 'Split'
  reason?: string
  priority?: number
  deadline_tick?: number
}

/**
 * Settlement event details
 */
export interface SettlementDetails {
  tx_id: string
  sender_id: string
  receiver_id: string
  amount: number
  settlement_type: 'RTGS' | 'LSM'
  ticks_to_settle?: number
}

/**
 * LSM Bilateral Offset details
 */
export interface LsmBilateralDetails {
  tx_ids: string[]
  agent_a: string
  agent_b: string
  amount_a: number
  amount_b: number
  net_offset: number
}

/**
 * LSM Cycle Settlement details
 */
export interface LsmCycleDetails {
  tx_ids: string[]
  agents: string[]
  tx_amounts: number[]
  net_positions: number[]
  max_net_outflow: number
  max_net_outflow_agent: string
  total_value: number
  cycle_size: number
}

/**
 * Collateral event details (Post/Withdraw)
 */
export interface CollateralDetails {
  agent_id: string
  action: 'Post' | 'Withdraw'
  amount: number
  reason: string
  new_total: number
}

/**
 * Overdue event details
 */
export interface OverdueDetails {
  tx_id: string
  sender_id: string
  receiver_id: string
  amount: number
  remaining_amount: number
  deadline_tick: number
  deadline_penalty_cost: number
}

/**
 * Queued RTGS event details
 */
export interface QueuedRtgsDetails {
  tx_id: string
  sender_id: string
  receiver_id: string
  amount: number
  reason: string
}

/**
 * Type guards for event details
 */
export function isArrivalEvent(event: EventRecord): event is EventRecord & { details: ArrivalDetails } {
  return event.event_type === 'Arrival'
}

export function isPolicyDecisionEvent(event: EventRecord): boolean {
  return ['PolicySubmit', 'PolicyHold', 'PolicyDrop', 'PolicySplit'].includes(event.event_type)
}

export function isSettlementEvent(event: EventRecord): event is EventRecord & { details: SettlementDetails } {
  return event.event_type === 'Settlement'
}

export function isLsmBilateralEvent(event: EventRecord): event is EventRecord & { details: LsmBilateralDetails } {
  return event.event_type === 'LsmBilateralOffset'
}

export function isLsmCycleEvent(event: EventRecord): event is EventRecord & { details: LsmCycleDetails } {
  return event.event_type === 'LsmCycleSettlement'
}

export function isCollateralEvent(event: EventRecord): event is EventRecord & { details: CollateralDetails } {
  return ['CollateralPost', 'CollateralWithdraw'].includes(event.event_type)
}

export function isOverdueEvent(event: EventRecord): boolean {
  return ['TransactionWentOverdue', 'OverdueTransactionSettled'].includes(event.event_type)
}

export function isQueuedRtgsEvent(event: EventRecord): event is EventRecord & { details: QueuedRtgsDetails } {
  return event.event_type === 'QueuedRtgs'
}

/**
 * Priority level classification
 */
export type PriorityLevel = 'low' | 'medium' | 'high'

export function getPriorityLevel(priority: number): PriorityLevel {
  if (priority >= 8) return 'high'
  if (priority >= 5) return 'medium'
  return 'low'
}

export function getPriorityColor(level: PriorityLevel): string {
  switch (level) {
    case 'high':
      return 'bg-red-100 text-red-800 border-red-200'
    case 'medium':
      return 'bg-yellow-100 text-yellow-800 border-yellow-200'
    case 'low':
      return 'bg-green-100 text-green-800 border-green-200'
  }
}
