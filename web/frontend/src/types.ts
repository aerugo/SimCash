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
  use_llm: boolean;
  mock_reasoning: boolean;
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

export interface AgentReasoning {
  tick: number;
  agent_id: string;
  phase: 'thinking' | 'decided';
  decision_type: 'liquidity_allocation' | 'payment_timing';
  decision: string;
  reasoning: string;
  reasoning_summary: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  error?: string;
  fallback?: boolean;
}

export type TabId = 'home' | 'dashboard' | 'events' | 'agents' | 'config' | 'replay' | 'analysis' | 'library' | 'game';

// ---- Multi-Day Game Types ----

export interface GameState {
  game_id: string;
  current_day: number;
  max_days: number;
  is_complete: boolean;
  use_llm: boolean;
  agent_ids: string[];
  current_policies: Record<string, { initial_liquidity_fraction: number }>;
  days: DayResult[];
  cost_history: Record<string, number[]>;
  fraction_history: Record<string, number[]>;
  reasoning_history: Record<string, GameOptimizationResult[]>;
}

export interface DayResult {
  day: number;
  seed: number;
  policies: Record<string, { initial_liquidity_fraction: number }>;
  costs: Record<string, CostBreakdown>;
  events: SimEvent[];
  balance_history: Record<string, number[]>;
  total_cost: number;
  per_agent_costs: Record<string, number>;
}

export interface BootstrapResult {
  delta_sum: number;
  mean_delta: number;
  cv: number;
  ci_lower: number;
  ci_upper: number;
  num_samples: number;
  old_mean_cost: number;
  new_mean_cost: number;
  rejection_reason: string;
}

export interface GameOptimizationResult {
  reasoning: string;
  old_fraction: number;
  new_fraction?: number;
  accepted: boolean;
  mock?: boolean;
  bootstrap?: BootstrapResult;
  rejection_reason?: string;
}

export interface ScenarioPackEntry {
  id: string;
  name: string;
  description: string;
  num_agents: number;
  ticks_per_day: number;
}

export interface GameScenario {
  id: string;
  name: string;
  description: string;
  num_agents: number;
  ticks_per_day: number;
  cost_rates: {
    liquidity_cost_per_tick_bps: number;
    delay_cost_per_tick_per_cent: number;
    eod_penalty_per_transaction: number;
    deadline_penalty: number;
    [key: string]: number;
  };
}

export interface GameSetupConfig {
  scenario_id: string;
  use_llm: boolean;
  mock_reasoning: boolean;
  max_days: number;
  num_eval_samples: number;
}
