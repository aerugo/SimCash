// Penalty can be a flat amount (cents) or a rate (bps of transaction amount)
export type PenaltyMode =
  | { mode: 'fixed'; amount: number }
  | { mode: 'rate'; bps_per_event: number };

// Parse raw penalty value from YAML/API: bare number → fixed, object → pass through
export function parsePenaltyMode(v: unknown): PenaltyMode {
  if (typeof v === 'number') return { mode: 'fixed', amount: v };
  if (v && typeof v === 'object' && 'mode' in v) {
    const obj = v as Record<string, unknown>;
    if (obj.mode === 'rate') return { mode: 'rate', bps_per_event: Number(obj.bps_per_event) || 0 };
    return { mode: 'fixed', amount: Number(obj.amount) || 0 };
  }
  return { mode: 'fixed', amount: 0 };
}

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
  simulated_ai: boolean;
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

export type TabId = 'home' | 'dashboard' | 'events' | 'agents' | 'config' | 'replay' | 'analysis' | 'library' | 'game' | 'docs' | 'scenarios' | 'policies' | 'create' | 'editor';

// Top-level navigation sections
export type SectionId = 'play' | 'library' | 'create' | 'simulation' | 'game' | 'docs';

export interface NavSection {
  id: SectionId;
  label: string;
  icon: string;
  defaultTab: TabId;
  tabs: { id: TabId; label: string }[];
  requiresSim?: boolean;
  requiresGame?: boolean;
}

// ---- Scenario Event Types ----

export type EventType =
  | 'DirectTransfer'
  | 'GlobalArrivalRateChange'
  | 'AgentArrivalRateChange'
  | 'DeadlineWindowChange'
  | 'CollateralAdjustment';

export const EVENT_TYPES: EventType[] = [
  'DirectTransfer',
  'GlobalArrivalRateChange',
  'AgentArrivalRateChange',
  'DeadlineWindowChange',
  'CollateralAdjustment',
];

export interface ScenarioEvent {
  id: string;
  type: EventType;
  trigger:
    | { type: 'OneTime'; tick: number }
    | { type: 'Repeating'; start_tick: number; interval: number };
  params: Record<string, unknown>;
}

export interface EventTimelineBuilderProps {
  events: ScenarioEvent[];
  agentIds: string[];
  totalTicks: number;
  onChange: (events: ScenarioEvent[]) => void;
}

// ---- Multi-Day Game Types ----

export interface PolicyJson {
  version?: string;
  policy_id?: string;
  parameters?: { initial_liquidity_fraction?: number; [key: string]: unknown };
  payment_tree?: Record<string, unknown>;
  bank_tree?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface GameState {
  game_id: string;
  current_round: number;
  rounds: number;
  current_day: number;
  total_days: number;
  is_complete: boolean;
  use_llm: boolean;
  constraint_preset?: string;
  optimization_schedule?: string;
  scenario_num_days?: number;
  agent_ids: string[];
  current_policies: Record<string, PolicyJson>;
  days: DayResult[];
  cost_history: Record<string, number[]>;
  fraction_history: Record<string, number[]>;
  reasoning_history: Record<string, GameOptimizationResult[]>;
  scenario_id?: string;
  scenario_name?: string;
  starting_policy_ids?: Record<string, string>;
  optimization_model?: string;
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
  optimized?: boolean;
  optimization_failed?: boolean;
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
  fallback_reason?: string;
  bootstrap?: BootstrapResult;
  rejection_reason?: string;
  new_policy?: PolicyJson;
  old_policy?: PolicyJson;
  rejected_policy?: PolicyJson;
  rejected_fraction?: number;
  day_num?: number;
  failed?: boolean;
  failure_reason?: string;
  reasoning_summary?: string;
  /** Full raw LLM response text (reasoning + policy JSON). */
  raw_response?: string;
  /** Model's internal thinking/reasoning (if exposed by provider). */
  thinking?: string;
  /** Token usage breakdown. */
  usage?: {
    input_tokens: number;
    output_tokens: number;
    thinking_tokens: number;
    total_tokens: number;
  };
  /** LLM call latency in seconds. */
  latency_seconds?: number;
  /** Model ID used for this optimization. */
  model?: string;
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
    eod_penalty_per_transaction?: number;
    eod_penalty?: unknown;
    deadline_penalty: unknown;
    [key: string]: unknown;
  };
}

export interface GameSetupConfig {
  scenario_id?: string;
  scenario_name?: string;
  inline_config?: Record<string, unknown>;
  use_llm: boolean;
  simulated_ai: boolean;
  rounds: number;
  num_eval_samples: number;
  optimization_interval?: number;
  constraint_preset?: 'simple' | 'full';
  starting_policies?: Record<string, string>;  // agent_id → policy JSON string
  starting_policy_ids?: Record<string, string>;  // agent_id → policy library ID
  optimization_schedule?: 'every_round' | 'every_scenario_day';
  prompt_profile_id?: string;
  prompt_profile?: Record<string, { enabled?: boolean; options?: Record<string, unknown> }>;
  model_override?: string;
}

export interface ConstraintPresetInfo {
  id: string;
  name: string;
  description: string;
  complexity: string;
}

// ---- Scenario Library Types ----

export interface LibraryScenario {
  id: string;
  name: string;
  description: string;
  category: 'Paper Experiments' | 'Crisis & Stress' | 'LSM Exploration' | 'General' | 'Testing';
  tags: string[];
  num_agents: number;
  ticks_per_day: number;
  num_days: number;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  features_used: string[];
  cost_config: Record<string, number>;
  visible?: boolean;
  collections?: string[];
}

export interface LibraryScenarioDetail extends LibraryScenario {
  raw_config: Record<string, unknown>;
}

// ---- Policy Library Types ----

export interface LibraryPolicy {
  id: string;
  name: string;
  description: string;
  version: string;
  complexity: 'simple' | 'moderate' | 'complex';
  category: string;
  trees_used: string[];
  actions_used: string[];
  parameters: Record<string, unknown>;
  context_fields_used: string[];
  total_nodes: number;
  visible?: boolean;
}

export interface LibraryPolicyDetail extends LibraryPolicy {
  raw: Record<string, unknown>;
}

// ---- Policy Evolution Types ----

// ---- Payment Trace Types ----

export interface PaymentLifecycleEvent {
  tick: number;
  event_type: string;
  details: Record<string, unknown>;
}

export interface PaymentTrace {
  index: number;
  tx_id: string;
  sender: string | null;
  receiver: string | null;
  amount: number | null;
  arrival_tick: number | null;
  deadline_tick: number | null;
  settled_tick: number | null;
  settlement_type: string | null;
  status: 'settled' | 'delayed' | 'failed';
  lifecycle: PaymentLifecycleEvent[];
}

export interface PaymentTraceResponse {
  day: number;
  total_payments: number;
  payments: PaymentTrace[];
}

// ---- Policy Evolution Types ----

export interface PolicyHistoryResponse {
  agent_ids: string[];
  days: PolicyHistoryDay[];
  parameter_trajectories: Record<string, Record<string, number[]>>;
}

export interface PolicyHistoryDay {
  day: number;
  policies: Record<string, Record<string, unknown>>;
  costs: Record<string, number>;
  accepted: Record<string, boolean>;
  reasoning: Record<string, string>;
}

export interface PolicyDiffResponse {
  agent: string;
  day1: number;
  day2: number;
  parameter_changes: { param: string; old: unknown; new: unknown }[];
  tree_changes: Record<string, {
    added_nodes: Record<string, unknown>[];
    removed_nodes: Record<string, unknown>[];
    modified_nodes: Record<string, unknown>[];
  }>;
  summary: string;
}
