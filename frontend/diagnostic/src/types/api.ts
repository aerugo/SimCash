/**
 * API Type Definitions for Payment Simulator Diagnostic Client
 *
 * These types mirror the backend API response schemas.
 * All money values are in integer cents to avoid floating point errors.
 */

export interface Simulation {
  simulation_id: string;
  // Active simulation fields
  current_tick?: number;
  current_day?: number;
  // Database simulation fields
  config_file?: string;
  config_hash?: string;
  rng_seed?: number;
  ticks_per_day?: number;
  num_days?: number;
  num_agents?: number;
  status?: "pending" | "running" | "completed" | "failed";
  started_at?: string; // ISO 8601 datetime
  completed_at?: string; // ISO 8601 datetime
}

export interface SimulationListResponse {
  simulations: Simulation[];
}

export interface SimulationMetadata {
  simulation_id: string;
  created_at: string;
  config: SimulationConfig;
  summary: SimulationSummary;
}

export interface SimulationConfig {
  ticks_per_day: number;
  num_days: number;
  rng_seed: number;
  agents: AgentConfig[];
  lsm_config?: Record<string, unknown>;
  // Database simulations may have additional fields
  config_file?: string;
  config_hash?: string;
  num_agents?: number;
}

export interface AgentConfig {
  id: string;
  opening_balance: number;
  credit_limit: number;
  policy: {
    type: string;
    [key: string]: unknown;
  };
}

export interface SimulationSummary {
  total_ticks: number;
  total_transactions: number;
  settlement_rate: number;
  total_cost_cents: number;
  duration_seconds: number | null;
  ticks_per_second: number | null;
}

export interface AgentSummary {
  agent_id: string;
  total_sent: number;
  total_received: number;
  total_settled: number;
  total_dropped: number;
  total_cost_cents: number;
  avg_balance_cents: number;
  peak_overdraft_cents: number;
  credit_limit_cents: number;
}

export interface AgentListResponse {
  agents: AgentSummary[];
}

export interface EventRecord {
  event_id: string;
  simulation_id: string;
  tick: number;
  day: number;
  event_type: string;
  event_timestamp: string;
  details: Record<string, any>;
  agent_id?: string;
  tx_id?: string;
  created_at: string;
}

export interface EventListResponse {
  events: EventRecord[];
  total: number;
  limit: number;
  offset: number;
  filters?: {
    tick?: number;
    tick_min?: number;
    tick_max?: number;
    day?: number;
    agent_id?: string;
    tx_id?: string;
    event_type?: string;
    sort?: string;
  };
}

export interface DailyAgentMetric {
  day: number;
  opening_balance: number;
  closing_balance: number;
  min_balance: number;
  max_balance: number;
  transactions_sent: number;
  transactions_received: number;
  total_cost_cents: number;
}

export interface CollateralEvent {
  tick: number;
  event_type: string;
  amount_cents: number;
}

export interface AgentTimelineResponse {
  agent_id: string;
  total_sent: number;
  total_received: number;
  total_settled: number;
  total_dropped: number;
  total_cost_cents: number;
  avg_balance_cents: number;
  peak_overdraft_cents: number;
  credit_limit_cents: number;
  daily_metrics: DailyAgentMetric[];
  collateral_events: CollateralEvent[];
}

export interface TransactionDetail {
  tx_id: string;
  sender_id: string;
  receiver_id: string;
  amount: number;
  priority: number;
  arrival_tick: number;
  deadline_tick: number;
  settlement_tick: number | null;
  status: string;
  delay_cost: number;
  amount_settled: number;
}

export interface TransactionEvent {
  tick: number;
  event_type: string;
  details: Record<string, unknown>;
}

export interface RelatedTransaction {
  tx_id: string;
  relationship: string;
  split_index?: number;
}

export interface TransactionLifecycleResponse {
  transaction: TransactionDetail;
  events: TransactionEvent[];
  related_transactions: RelatedTransaction[];
}

export interface AgentCostBreakdown {
  liquidity_cost: number;
  collateral_cost: number;
  delay_cost: number;
  split_friction_cost: number;
  deadline_penalty: number;
  total_cost: number;
}

export interface CostResponse {
  simulation_id: string;
  tick: number;
  day: number;
  agents: Record<string, AgentCostBreakdown>;
  total_system_cost: number;
}
