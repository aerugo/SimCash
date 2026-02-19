import { useState, useMemo, useCallback } from 'react';
import { InfoTip } from './Tooltip';
import * as jsYaml from 'js-yaml';

// ── Types ───────────────────────────────────────────────────────────

interface AgentFormData {
  id: string;
  opening_balance: number;
  liquidity_pool: number;
  arrival_config: {
    rate_per_tick: number;
    amount_distribution: {
      type: string;
      mean?: number;
      std_dev?: number;
      min?: number;
      max?: number;
      rate?: number;
    };
    counterparty_weights: Record<string, number>;
    deadline_range: [number, number];
  };
}

interface ScenarioFormData {
  simulation: {
    ticks_per_day: number;
    num_days: number;
    rng_seed: number;
  };
  agents: AgentFormData[];
  cost_rates: {
    liquidity_cost_per_tick_bps: number;
    delay_cost_per_tick_per_cent: number;
    deadline_penalty: number;
    eod_penalty_per_transaction: number;
  };
  lsm_config?: {
    enable_bilateral: boolean;
    enable_cycles: boolean;
  };
  scenario_events?: unknown[];
}

interface Props {
  yaml: string;
  onYamlChange: (yaml: string) => void;
}

const distributionHelp: Record<string, string> = {
  LogNormal: 'Heavy-tailed: most payments are small, but occasional large ones occur. Realistic for interbank flows. Params: mean & std dev of the underlying log-normal.',
  Normal: 'Bell curve centered on the mean. Symmetric — equal chance of above/below average.',
  Uniform: 'Flat — every amount between min and max is equally likely. No clustering. Good for stress-testing edge cases.',
  Exponential: 'Many small payments, exponentially fewer large ones. Memoryless — the rate (λ) is 1/mean. More extreme skew than LogNormal.',
};

// ── Helpers ─────────────────────────────────────────────────────────

function parseYamlToForm(yamlStr: string): ScenarioFormData | null {
  try {
    const doc = jsYaml.load(yamlStr) as Record<string, unknown> | null;
    if (!doc) return null;
    const sim = (doc.simulation as Record<string, number>) ?? {};
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const agents = (doc.agents as any[]) ?? [];
    const costs = (doc.cost_rates as Record<string, number>) ?? {};
    const lsm = doc.lsm_config as { enable_bilateral?: boolean; enable_cycles?: boolean } | undefined;
    const events = doc.scenario_events as unknown[] | undefined;

    return {
      simulation: {
        ticks_per_day: sim.ticks_per_day ?? 12,
        num_days: sim.num_days ?? 1,
        rng_seed: sim.rng_seed ?? 42,
      },
      agents: agents.map(a => ({
        id: a.id ?? 'BANK_X',
        opening_balance: a.opening_balance ?? 0,
        liquidity_pool: a.liquidity_pool ?? 1000000,
        arrival_config: {
          rate_per_tick: a.arrival_config?.rate_per_tick ?? 2.0,
          amount_distribution: {
            type: a.arrival_config?.amount_distribution?.type ?? 'LogNormal',
            mean: a.arrival_config?.amount_distribution?.mean ?? 10000,
            std_dev: a.arrival_config?.amount_distribution?.std_dev ?? 5000,
          },
          counterparty_weights: a.arrival_config?.counterparty_weights ?? {},
          deadline_range: a.arrival_config?.deadline_range ?? a.deadline_range ?? [3, 8],
        },
      })),
      cost_rates: {
        liquidity_cost_per_tick_bps: costs.liquidity_cost_per_tick_bps ?? 83,
        delay_cost_per_tick_per_cent: costs.delay_cost_per_tick_per_cent ?? 0.2,
        deadline_penalty: costs.deadline_penalty ?? 50000,
        eod_penalty_per_transaction: costs.eod_penalty_per_transaction ?? 100000,
      },
      ...(lsm ? { lsm_config: { enable_bilateral: lsm.enable_bilateral ?? false, enable_cycles: lsm.enable_cycles ?? false } } : {}),
      ...(events ? { scenario_events: events } : {}),
    };
  } catch {
    return null;
  }
}

function formToYaml(data: ScenarioFormData): string {
  // Build a clean object preserving key order
  const doc: Record<string, unknown> = {
    simulation: data.simulation,
    agents: data.agents.map(a => ({
      id: a.id,
      opening_balance: a.opening_balance,
      liquidity_pool: a.liquidity_pool,
      arrival_config: {
        rate_per_tick: a.arrival_config.rate_per_tick,
        amount_distribution: a.arrival_config.amount_distribution,
        counterparty_weights: a.arrival_config.counterparty_weights,
        deadline_range: a.arrival_config.deadline_range,
      },
    })),
  };
  if (data.scenario_events && data.scenario_events.length > 0) {
    doc.scenario_events = data.scenario_events;
  }
  if (data.lsm_config) {
    doc.lsm_config = data.lsm_config;
  }
  doc.cost_rates = data.cost_rates;
  return jsYaml.dump(doc, { lineWidth: -1, noRefs: true, flowLevel: -1 });
}

// ── Shared input styles ─────────────────────────────────────────────

const inputCls = 'w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-sky-500';
const labelCls = 'text-xs text-slate-400 block mb-1';
const sectionCls = 'bg-slate-800/60 border border-slate-700 rounded-xl p-4 space-y-3';
const sectionTitle = 'text-sm font-semibold text-slate-300 mb-2';

// ── Component ───────────────────────────────────────────────────────

export function ScenarioForm({ yaml, onYamlChange }: Props) {
  const data = useMemo(() => parseYamlToForm(yaml), [yaml]);
  const [parseError] = useState<string | null>(null);

  const update = useCallback((mutate: (d: ScenarioFormData) => void) => {
    if (!data) return;
    // Deep clone
    const copy: ScenarioFormData = JSON.parse(JSON.stringify(data));
    mutate(copy);
    onYamlChange(formToYaml(copy));
  }, [data, onYamlChange]);

  if (!data) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-sm text-red-300">
        {parseError || 'Cannot parse YAML into form. Switch to YAML mode to fix.'}
      </div>
    );
  }

  const agentIds = data.agents.map(a => a.id);

  return (
    <div className="space-y-4">
      {/* Simulation */}
      <div className={sectionCls}>
        <h3 className={sectionTitle}>⚙️ Simulation</h3>
        <div className="grid grid-cols-3 gap-3">
          <NumberField label="Ticks per Day" value={data.simulation.ticks_per_day} onChange={v => update(d => { d.simulation.ticks_per_day = v; })} />
          <NumberField label="Number of Days" value={data.simulation.num_days} onChange={v => update(d => { d.simulation.num_days = v; })} />
          <NumberField label="RNG Seed" value={data.simulation.rng_seed} onChange={v => update(d => { d.simulation.rng_seed = v; })} />
        </div>
      </div>

      {/* Cost Rates */}
      <div className={sectionCls}>
        <h3 className={sectionTitle}>💰 Cost Rates</h3>
        <div className="grid grid-cols-2 gap-3">
          <NumberField label="Liquidity Cost (bps/tick)" value={data.cost_rates.liquidity_cost_per_tick_bps} onChange={v => update(d => { d.cost_rates.liquidity_cost_per_tick_bps = v; })} tooltip="Basis points charged per tick on committed liquidity. Higher = more expensive to hold cash ready." />
          <NumberField label="Delay Cost (per ¢/tick)" value={data.cost_rates.delay_cost_per_tick_per_cent} onChange={v => update(d => { d.cost_rates.delay_cost_per_tick_per_cent = v; })} step={0.01} tooltip="Cost per cent of unsettled payment per tick. Penalizes slow settlement." />
          <NumberField label="Deadline Penalty" value={data.cost_rates.deadline_penalty} onChange={v => update(d => { d.cost_rates.deadline_penalty = v; })} tooltip="Flat fee charged when a payment misses its deadline (in cents)." />
          <NumberField label="EOD Penalty / Txn" value={data.cost_rates.eod_penalty_per_transaction} onChange={v => update(d => { d.cost_rates.eod_penalty_per_transaction = v; })} tooltip="Flat fee per payment still unsettled at end of day (in cents)." />
        </div>
      </div>

      {/* LSM Config */}
      <div className={sectionCls}>
        <div className="flex items-center justify-between">
          <h3 className={sectionTitle + ' mb-0'}>🔄 LSM Config</h3>
          <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
            <input
              type="checkbox"
              checked={!!data.lsm_config}
              onChange={e => {
                if (e.target.checked) {
                  update(d => { d.lsm_config = { enable_bilateral: false, enable_cycles: false }; });
                } else {
                  update(d => { delete d.lsm_config; });
                }
              }}
              className="accent-sky-500"
            />
            Enable
          </label>
        </div>
        {data.lsm_config && (
          <div className="flex gap-6 mt-2">
            <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
              <input type="checkbox" checked={data.lsm_config.enable_bilateral} onChange={e => update(d => { d.lsm_config!.enable_bilateral = e.target.checked; })} className="accent-sky-500" />
              Bilateral<InfoTip text="Bilateral offsetting: nets payments between pairs of banks (A owes B, B owes A → only the difference settles)" />
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
              <input type="checkbox" checked={data.lsm_config.enable_cycles} onChange={e => update(d => { d.lsm_config!.enable_cycles = e.target.checked; })} className="accent-sky-500" />
              Cycles<InfoTip text="Cycle detection: finds circular payment chains (A→B→C→A) and settles them simultaneously" />
            </label>
          </div>
        )}
      </div>

      {/* Agents */}
      <div className={sectionCls}>
        <div className="flex items-center justify-between">
          <h3 className={sectionTitle + ' mb-0'}>🏦 Agents ({data.agents.length})</h3>
          <button
            onClick={() => update(d => {
              const nextId = `BANK_${String.fromCharCode(65 + d.agents.length)}`;
              const otherIds = d.agents.map(a => a.id);
              const weights: Record<string, number> = {};
              otherIds.forEach(id => { weights[id] = 1.0; });
              d.agents.push({
                id: nextId,
                opening_balance: 0,
                liquidity_pool: 1000000,
                arrival_config: {
                  rate_per_tick: 2.0,
                  amount_distribution: { type: 'LogNormal', mean: 10000, std_dev: 5000 },
                  counterparty_weights: weights,
                  deadline_range: [3, 8],
                },
              });
              // Add this new agent to other agents' weights
              d.agents.forEach((a, i) => {
                if (i < d.agents.length - 1) {
                  a.arrival_config.counterparty_weights[nextId] = 1.0;
                }
              });
            })}
            className="px-3 py-1 text-xs bg-sky-600 hover:bg-sky-500 rounded-lg transition-colors"
          >
            + Add Agent
          </button>
        </div>
        <div className="space-y-3 mt-2">
          {data.agents.map((agent, idx) => (
            <AgentCard
              key={idx}
              agent={agent}
              index={idx}
              allAgentIds={agentIds}
              canRemove={data.agents.length > 2}
              onChange={(mutate) => update(d => { mutate(d.agents[idx]); })}
              onRemove={() => update(d => {
                const removedId = d.agents[idx].id;
                d.agents.splice(idx, 1);
                // Remove from other agents' weights
                d.agents.forEach(a => { delete a.arrival_config.counterparty_weights[removedId]; });
              })}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Agent Card ──────────────────────────────────────────────────────

function AgentCard({ agent, index, allAgentIds, canRemove, onChange, onRemove }: {
  agent: AgentFormData;
  index: number;
  allAgentIds: string[];
  canRemove: boolean;
  onChange: (mutate: (a: AgentFormData) => void) => void;
  onRemove: () => void;
}) {
  const [expanded, setExpanded] = useState(index < 2);
  const otherIds = allAgentIds.filter(id => id !== agent.id);

  return (
    <div className="bg-slate-900/60 border border-slate-700 rounded-lg p-3">
      <div className="flex items-center justify-between">
        <button onClick={() => setExpanded(!expanded)} className="flex items-center gap-2 text-sm font-medium text-slate-200 hover:text-sky-400 transition-colors">
          <span className="text-xs">{expanded ? '▼' : '▶'}</span>
          {agent.id}
        </button>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Pool: {agent.liquidity_pool.toLocaleString()}</span>
          {canRemove && (
            <button onClick={onRemove} className="text-xs text-red-400 hover:text-red-300 px-1">✕</button>
          )}
        </div>
      </div>

      {expanded && (
        <div className="mt-3 space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className={labelCls}>Agent ID</label>
              <input value={agent.id} onChange={e => onChange(a => { a.id = e.target.value; })} className={inputCls} />
            </div>
            <NumberField label="Opening Balance" value={agent.opening_balance} onChange={v => onChange(a => { a.opening_balance = v; })} />
            <NumberField label="Liquidity Pool" value={agent.liquidity_pool} onChange={v => onChange(a => { a.liquidity_pool = v; })} />
          </div>

          {/* Arrival config */}
          <div className="bg-slate-800/40 rounded-lg p-3 space-y-2">
            <div className="text-xs font-medium text-slate-400">Arrival Config</div>
            <div className="grid grid-cols-4 gap-3">
              <NumberField label="Rate/Tick" value={agent.arrival_config.rate_per_tick} onChange={v => onChange(a => { a.arrival_config.rate_per_tick = v; })} step={0.1} />
              <div>
                <label className={labelCls}>Distribution <InfoTip text={distributionHelp[agent.arrival_config.amount_distribution.type] ?? ''} /></label>
                <select value={agent.arrival_config.amount_distribution.type} onChange={e => onChange(a => {
                  const t = e.target.value;
                  if (t === 'Uniform') a.arrival_config.amount_distribution = { type: 'Uniform', min: 1000, max: 20000 };
                  else if (t === 'Normal') a.arrival_config.amount_distribution = { type: 'Normal', mean: 10000, std_dev: 5000 };
                  else if (t === 'Exponential') a.arrival_config.amount_distribution = { type: 'Exponential', rate: 0.0001 };
                  else a.arrival_config.amount_distribution = { type: 'LogNormal', mean: 10000, std_dev: 5000 };
                })} className={inputCls}>
                  <option value="LogNormal">LogNormal</option>
                  <option value="Normal">Normal</option>
                  <option value="Uniform">Uniform</option>
                  <option value="Exponential">Exponential</option>
                </select>
              </div>
              {(agent.arrival_config.amount_distribution.type === 'LogNormal' || agent.arrival_config.amount_distribution.type === 'Normal') && <>
                <NumberField label="Mean" value={agent.arrival_config.amount_distribution.mean ?? 10000} onChange={v => onChange(a => { a.arrival_config.amount_distribution.mean = v; })} />
                <NumberField label="Std Dev" value={agent.arrival_config.amount_distribution.std_dev ?? 5000} onChange={v => onChange(a => { a.arrival_config.amount_distribution.std_dev = v; })} />
              </>}
              {agent.arrival_config.amount_distribution.type === 'Uniform' && <>
                <NumberField label="Min" value={agent.arrival_config.amount_distribution.min ?? 1000} onChange={v => onChange(a => { a.arrival_config.amount_distribution.min = v; })} />
                <NumberField label="Max" value={agent.arrival_config.amount_distribution.max ?? 20000} onChange={v => onChange(a => { a.arrival_config.amount_distribution.max = v; })} />
              </>}
              {agent.arrival_config.amount_distribution.type === 'Exponential' && <>
                <NumberField label="Rate (λ)" value={agent.arrival_config.amount_distribution.rate ?? 0.0001} onChange={v => onChange(a => { a.arrival_config.amount_distribution.rate = v; })} step={0.0001} />
              </>}
            </div>
          </div>

          {/* Deadline range */}
          <div className="grid grid-cols-2 gap-3">
            <NumberField label="Deadline Min" value={agent.arrival_config.deadline_range[0]} onChange={v => onChange(a => { a.arrival_config.deadline_range[0] = v; })} />
            <NumberField label="Deadline Max" value={agent.arrival_config.deadline_range[1]} onChange={v => onChange(a => { a.arrival_config.deadline_range[1] = v; })} />
          </div>

          {/* Counterparty weights */}
          <div className="bg-slate-800/40 rounded-lg p-3 space-y-2">
            <div className="text-xs font-medium text-slate-400">Counterparty Weights</div>
            {otherIds.length === 0 && <div className="text-xs text-slate-500">No other agents</div>}
            <div className="grid grid-cols-2 gap-2">
              {otherIds.map(otherId => (
                <div key={otherId} className="flex items-center gap-2">
                  <span className="text-xs text-slate-400 min-w-[60px]">{otherId}</span>
                  <input
                    type="number"
                    step={0.1}
                    value={agent.arrival_config.counterparty_weights[otherId] ?? 0}
                    onChange={e => onChange(a => { a.arrival_config.counterparty_weights[otherId] = parseFloat(e.target.value) || 0; })}
                    className={inputCls + ' flex-1'}
                  />
                </div>
              ))}
              {/* Show weights for IDs not in allAgentIds (manual YAML entries) */}
              {Object.keys(agent.arrival_config.counterparty_weights)
                .filter(k => !otherIds.includes(k))
                .map(k => (
                  <div key={k} className="flex items-center gap-2">
                    <span className="text-xs text-slate-500 min-w-[60px]">{k}</span>
                    <input
                      type="number"
                      step={0.1}
                      value={agent.arrival_config.counterparty_weights[k] ?? 0}
                      onChange={e => onChange(a => { a.arrival_config.counterparty_weights[k] = parseFloat(e.target.value) || 0; })}
                      className={inputCls + ' flex-1'}
                    />
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Reusable number field ───────────────────────────────────────────

function NumberField({ label, value, onChange, step, tooltip }: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
  tooltip?: string;
}) {
  return (
    <div>
      <label className={labelCls}>{label}{tooltip && <InfoTip text={tooltip} />}</label>
      <input
        type="number"
        step={step}
        value={value}
        onChange={e => onChange(parseFloat(e.target.value) || 0)}
        className={inputCls}
      />
    </div>
  );
}
