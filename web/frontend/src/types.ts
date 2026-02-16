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

export interface PaymentEntry {
  sender: string;
  receiver: string;
  amount: number;
  tick: number;
  deadline: number;
}

export interface AgentSetup {
  id: string;
  agent_type: string;
  liquidity_pool: number;
  opening_balance: number;
  unsecured_cap: number;
}

export interface ScenarioConfig {
  preset?: string | null;
  ticks_per_day: number;
  num_days: number;
  rng_seed: number;
  agents: AgentSetup[] | null;
  liquidity_cost_per_tick_bps: number;
  delay_cost_per_tick_per_cent: number;
  eod_penalty_per_transaction: number;
  deadline_penalty: number;
  deferred_crediting: boolean;
  deadline_cap_at_eod: boolean;
  payment_schedule: PaymentEntry[] | null;
  enable_bilateral_lsm: boolean;
  enable_cycle_lsm: boolean;
}

export interface SavedScenario {
  id: string;
  name: string;
  description: string;
  config: ScenarioConfig;
}

export interface CompareResult {
  sim_id?: string;
  config?: Record<string, unknown>;
  final_state?: SimulationState;
  total_cost?: number;
  error?: string;
}

export type TabId = 'home' | 'dashboard' | 'events' | 'config' | 'replay' | 'analysis' | 'library';
