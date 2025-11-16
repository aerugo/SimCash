import { apiFetch } from './client'
import type {
  SimulationListResponse,
  SimulationMetadata,
  AgentListResponse,
  EventListResponse,
  AgentTimelineResponse,
  TransactionLifecycleResponse,
} from '../types/api'

/**
 * Fetch list of all simulations (active + database-persisted)
 */
export async function fetchSimulations(): Promise<SimulationListResponse> {
  return apiFetch<SimulationListResponse>('/simulations')
}

/**
 * Fetch simulation metadata (config + summary)
 */
export async function fetchSimulationMetadata(simId: string): Promise<SimulationMetadata> {
  return apiFetch<SimulationMetadata>(`/simulations/${simId}`)
}

/**
 * Fetch agent list for a simulation
 */
export async function fetchAgents(simId: string): Promise<AgentListResponse> {
  return apiFetch<AgentListResponse>(`/simulations/${simId}/agents`)
}

/**
 * Fetch paginated events for a simulation
 */
export async function fetchEvents(
  simId: string,
  params?: {
    tick?: number
    tick_min?: number
    tick_max?: number
    day?: number
    agent_id?: string
    tx_id?: string
    event_type?: string
    limit?: number
    offset?: number
    sort?: string
  }
): Promise<EventListResponse> {
  const searchParams = new URLSearchParams()

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value))
      }
    })
  }

  const query = searchParams.toString()
  const url = `/simulations/${simId}/events${query ? `?${query}` : ''}`

  return apiFetch<EventListResponse>(url)
}

/**
 * Fetch agent timeline (daily metrics + collateral events)
 */
export async function fetchAgentTimeline(
  simId: string,
  agentId: string
): Promise<AgentTimelineResponse> {
  return apiFetch<AgentTimelineResponse>(`/simulations/${simId}/agents/${agentId}/timeline`)
}

/**
 * Fetch transaction lifecycle
 */
export async function fetchTransactionLifecycle(
  simId: string,
  txId: string
): Promise<TransactionLifecycleResponse> {
  return apiFetch<TransactionLifecycleResponse>(
    `/simulations/${simId}/transactions/${txId}/lifecycle`
  )
}

/**
 * Fetch cost timeline data for all agents
 * This fetches timelines for all agents and aggregates the cost data
 */
export async function fetchCostTimeline(simId: string) {
  // First, fetch all agents
  const agentListResponse = await fetchAgents(simId)

  // Then fetch timeline for each agent
  const agentTimelines = await Promise.all(
    agentListResponse.agents.map(agent =>
      fetchAgentTimeline(simId, agent.agent_id)
    )
  )

  return agentTimelines
}
