export interface AgentState {
  balance: number;
  available_liquidity: number;
  queue1_size: number;
  posted_collateral: number;
  costs: CostBreakdown;
}

export interface CostBreakdown {
  liquidity_cost: number;
  delay_cost: number;
  penalty_cost: number;
  total: number;
}

export interface SimulationState {
  sim_id: string;
  current_tick: number;
  current_day: number;
  total_ticks: number;
  is_complete: boolean;
  agents: Record<string, AgentState>;
  balance_history: Record<string, number[]>;
  cost_history: Record<string, CostBreakdown[]>;
}

export interface TickResult {
  tick: number;
  num_arrivals: number;
  num_settlements: number;
  agents: Record<string, AgentState>;
  events: SimEvent[];
  is_complete: boolean;
  balance_history: Record<string, number[]>;
  cost_history: Record<string, CostBreakdown[]>;
}

export interface SimEvent {
  event_type: string;
  tick: number;
  [key: string]: unknown;
}

export interface Preset {
  id: string;
  name: string;
  description: string;
  ticks_per_day: number;
  num_agents: number;
}

export interface CreateSimResponse {
  sim_id: string;
  config: Record<string, unknown>;
}
