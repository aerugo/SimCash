import { useQuery } from '@tanstack/react-query'
import {
  fetchSimulations,
  fetchSimulationMetadata,
  fetchAgents,
  fetchEvents,
  fetchAgentTimeline,
  fetchTransactionLifecycle,
} from '../api/simulations'

/**
 * Fetch list of all simulations
 */
export function useSimulations() {
  return useQuery({
    queryKey: ['simulations'],
    queryFn: fetchSimulations,
  })
}

/**
 * Fetch simulation metadata
 */
export function useSimulation(simId: string) {
  return useQuery({
    queryKey: ['simulation', simId],
    queryFn: () => fetchSimulationMetadata(simId),
    enabled: !!simId,
  })
}

/**
 * Fetch agents for a simulation
 */
export function useAgents(simId: string) {
  return useQuery({
    queryKey: ['agents', simId],
    queryFn: () => fetchAgents(simId),
    enabled: !!simId,
  })
}

/**
 * Fetch events for a simulation
 */
export function useEvents(
  simId: string,
  params?: {
    tick?: number
    tick_min?: number
    tick_max?: number
    agent_id?: string
    event_type?: string
    limit?: number
    offset?: number
  }
) {
  return useQuery({
    queryKey: ['events', simId, params],
    queryFn: () => fetchEvents(simId, params),
    enabled: !!simId,
  })
}

/**
 * Fetch agent timeline
 */
export function useAgentTimeline(simId: string, agentId: string) {
  return useQuery({
    queryKey: ['agentTimeline', simId, agentId],
    queryFn: () => fetchAgentTimeline(simId, agentId),
    enabled: !!simId && !!agentId,
  })
}

/**
 * Fetch transaction lifecycle
 */
export function useTransactionLifecycle(simId: string, txId: string) {
  return useQuery({
    queryKey: ['transactionLifecycle', simId, txId],
    queryFn: () => fetchTransactionLifecycle(simId, txId),
    enabled: !!simId && !!txId,
  })
}
