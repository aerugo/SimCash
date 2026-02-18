import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import type { ScenarioConfig, AgentSetup, PaymentEntry, GameScenario, GameSetupConfig } from '../types';
import { getGameScenarios } from '../api';
import { HowItWorks } from '../components/HowItWorks';
import { GameSettingsPanel, gameSettingsToConfig, DEFAULT_GAME_SETTINGS } from '../components/GameSettingsPanel';
import type { GameSettings } from '../components/GameSettingsPanel';
import { useGameContext } from '../GameContext';

const DEFAULT_CONFIG: ScenarioConfig = {
  preset: null,
  ticks_per_day: 3,
  num_days: 1,
  rng_seed: 42,
  agents: [
    { id: 'BANK_A', agent_type: 'ai', liquidity_pool: 100_000, opening_balance: 0, unsecured_cap: 0 },
    { id: 'BANK_B', agent_type: 'ai', liquidity_pool: 100_000, opening_balance: 0, unsecured_cap: 0 },
  ],
  liquidity_cost_per_tick_bps: 333,
  delay_cost_per_tick_per_cent: 0.2,
  eod_penalty_per_transaction: 100_000,
  deadline_penalty: 50_000,
  deferred_crediting: true,
  deadline_cap_at_eod: true,
  payment_schedule: [],
  enable_bilateral_lsm: false,
  enable_cycle_lsm: false,
  use_llm: false,
  mock_reasoning: true,
};

export function HomeView() {
  const { presets, handleLaunch: onLaunch, handleGameLaunch } = useGameContext();
  const navigate = useNavigate();
  const onGameLaunch = async (config: GameSetupConfig) => {
    const gid = await handleGameLaunch(config);
    if (gid) navigate(`/experiment/${gid}`);
  };
  const [mode, setMode] = useState<'preset' | 'custom' | 'game'>('game');
  const [selectedPreset, setSelectedPreset] = useState('exp3');
  const [config, setConfig] = useState<ScenarioConfig>({ ...DEFAULT_CONFIG });
  const [gameScenarios, setGameScenarios] = useState<GameScenario[]>([]);
  const [selectedScenario, setSelectedScenario] = useState('2bank_12tick');
  const [gameSettings, setGameSettings] = useState<GameSettings>(DEFAULT_GAME_SETTINGS);

  useEffect(() => {
    getGameScenarios().then(setGameScenarios).catch(() => {});
  }, []);

  // Derive agent IDs from selected scenario
  const selectedScenarioData = gameScenarios.find(s => s.id === selectedScenario);
  const agentIds = selectedScenarioData
    ? Array.from({ length: selectedScenarioData.num_agents }, (_, i) => `BANK_${String.fromCharCode(65 + i)}`)
    : [];

  // Reset agent policies when scenario changes
  useEffect(() => {
    setGameSettings(prev => ({ ...prev, agentPolicies: {} }));
  }, [selectedScenario]);

  const handleLaunch = () => {
    if (mode === 'preset') {
      if (config.use_llm) {
        // Pass LLM config with preset
        onLaunch({ ...DEFAULT_CONFIG, preset: selectedPreset, use_llm: config.use_llm, mock_reasoning: config.mock_reasoning });
      } else {
        onLaunch(selectedPreset);
      }
    } else {
      onLaunch(config);
    }
  };

  const updateAgent = (idx: number, updates: Partial<AgentSetup>) => {
    const agents = [...(config.agents || [])];
    agents[idx] = { ...agents[idx], ...updates };
    setConfig({ ...config, agents });
  };

  const addAgent = () => {
    const agents = [...(config.agents || [])];
    const letters = 'ABCDEFGH';
    const id = `BANK_${letters[agents.length] || agents.length}`;
    agents.push({ id, agent_type: 'ai', liquidity_pool: 100_000, opening_balance: 0, unsecured_cap: 0 });
    setConfig({ ...config, agents });
  };

  const removeAgent = (idx: number) => {
    const agents = [...(config.agents || [])];
    agents.splice(idx, 1);
    setConfig({ ...config, agents });
  };

  const addPayment = () => {
    const agents = config.agents || [];
    const schedule = [...(config.payment_schedule || [])];
    schedule.push({
      sender: agents[0]?.id || 'BANK_A',
      receiver: agents[1]?.id || 'BANK_B',
      amount: 50_000,
      tick: 0,
      deadline: 2,
    });
    setConfig({ ...config, payment_schedule: schedule });
  };

  const updatePayment = (idx: number, updates: Partial<PaymentEntry>) => {
    const schedule = [...(config.payment_schedule || [])];
    schedule[idx] = { ...schedule[idx], ...updates };
    setConfig({ ...config, payment_schedule: schedule });
  };

  const removePayment = (idx: number) => {
    const schedule = [...(config.payment_schedule || [])];
    schedule.splice(idx, 1);
    setConfig({ ...config, payment_schedule: schedule });
  };

  const randomize = () => {
    const numBanks = 2 + Math.floor(Math.random() * 3);
    const letters = 'ABCDEFGH';
    const agents: AgentSetup[] = Array.from({ length: numBanks }, (_, i) => ({
      id: `BANK_${letters[i]}`,
      agent_type: 'ai',
      liquidity_pool: Math.round((50_000 + Math.random() * 150_000) / 100) * 100,
      opening_balance: 0,
      unsecured_cap: 0,
    }));

    const ticks = [2, 3, 5, 8, 12][Math.floor(Math.random() * 5)];
    const payments: PaymentEntry[] = [];
    for (let t = 0; t < ticks; t++) {
      if (Math.random() > 0.5) {
        const from = Math.floor(Math.random() * numBanks);
        let to = Math.floor(Math.random() * numBanks);
        if (to === from) to = (to + 1) % numBanks;
        payments.push({
          sender: agents[from].id,
          receiver: agents[to].id,
          amount: Math.round((10_000 + Math.random() * 100_000) / 100) * 100,
          tick: t,
          deadline: t + 1 + Math.floor(Math.random() * 3),
        });
      }
    }

    setConfig({
      ...config,
      ticks_per_day: ticks,
      rng_seed: Math.floor(Math.random() * 10000),
      agents,
      payment_schedule: payments,
      liquidity_cost_per_tick_bps: Math.round(100 + Math.random() * 500),
      delay_cost_per_tick_per_cent: Math.round(Math.random() * 5 * 10) / 10,
    });
  };

  const exportConfig = () => {
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'scenario.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  const importConfig = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      const text = await file.text();
      try {
        setConfig(JSON.parse(text));
        setMode('custom');
      } catch { /* ignore */ }
    };
    input.click();
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold mb-1">Payment System Simulator</h2>
        <p className="text-lg text-violet-300/90 italic mb-3">Can AI agents learn to coordinate in payment systems?</p>
        <p className="text-slate-400 max-w-2xl mx-auto">
          Banks in real-time gross settlement systems face a fundamental tension:
          holding liquidity is expensive, but delaying payments is worse — and if every bank waits
          for incoming funds before releasing outgoing ones, the whole system gridlocks.
          Here, AI agents independently build decision-tree policies to navigate this coordination problem,
          and we watch whether they find equilibrium.
        </p>
        <p className="text-xs text-slate-500 mt-2">
          Extends the methodology of BIS Working Paper 1310 (Castro et al., 2025)
        </p>
      </div>

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Link
          to="/library/scenarios"
          className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 text-left hover:border-sky-500/50 transition-colors group"
        >
          <div className="text-2xl mb-2">📚</div>
          <h3 className="font-semibold text-slate-100 group-hover:text-sky-300 transition-colors mb-1">Explore Scenarios</h3>
          <p className="text-xs text-slate-400">Browse crisis simulations, LSM tests, paper experiments, and more</p>
        </Link>
        <Link
          to="/library/policies"
          className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 text-left hover:border-violet-500/50 transition-colors group"
        >
          <div className="text-2xl mb-2">🧠</div>
          <h3 className="font-semibold text-slate-100 group-hover:text-violet-300 transition-colors mb-1">Policy Library</h3>
          <p className="text-xs text-slate-400">30+ built-in strategies — from simple FIFO to adaptive decision trees</p>
        </Link>
        <Link
          to="/create"
          className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 text-left hover:border-amber-500/50 transition-colors group"
        >
          <div className="text-2xl mb-2">✏️</div>
          <h3 className="font-semibold text-slate-100 group-hover:text-amber-300 transition-colors mb-1">Build Your Own</h3>
          <p className="text-xs text-slate-400">Write custom YAML scenarios with live validation and launch them</p>
        </Link>
        <Link
          to="/docs"
          className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 text-left hover:border-emerald-500/50 transition-colors group"
        >
          <div className="text-2xl mb-2">📖</div>
          <h3 className="font-semibold text-slate-100 group-hover:text-emerald-300 transition-colors mb-1">Documentation</h3>
          <p className="text-xs text-slate-400">Learn about RTGS, LSM, game theory, and the SimCash engine</p>
        </Link>
      </div>

      <HowItWorks defaultOpen={true} />

      {/* Mode toggle */}
      <div className="flex gap-2 mb-6 justify-center">
        <button
          onClick={() => setMode('game')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            mode === 'game' ? 'bg-violet-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
          }`}
        >
          {'Multi-Round Experiment'}
        </button>
        <button
          onClick={() => setMode('preset')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            mode === 'preset' ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
          }`}
        >
          📋 Presets
        </button>
        <button
          onClick={() => setMode('custom')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            mode === 'custom' ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
          }`}
        >
          🛠 Custom Builder
        </button>
      </div>

      {mode === 'game' ? (
        <div className="space-y-6 mb-8">
          {/* Quick Start Card */}
          <div className="bg-gradient-to-r from-violet-500/10 to-pink-500/10 border border-violet-500/30 rounded-xl p-6 text-center">
            <h3 className="text-lg font-semibold text-white mb-2">{'Quick Experiment'}</h3>
            <p className="text-sm text-slate-300 max-w-lg mx-auto mb-4">
              Run a demo experiment in one click with simulated AI responses — results appear instantly.
              Real experiments use an LLM for optimization, where each round waits for the AI to analyze
              results and propose an improved policy (typically 10–40 seconds per optimization).
            </p>
            <button
              onClick={() => {
                onGameLaunch?.({
                  scenario_id: '2bank_12tick',
                  use_llm: true,
                  mock_reasoning: true,
                  max_days: 5,
                  num_eval_samples: 1,
                  optimization_interval: 1,
                  constraint_preset: 'full',
                });
              }}
              className="px-8 py-4 rounded-xl bg-gradient-to-r from-violet-500 to-pink-500 font-bold text-lg text-white hover:from-violet-400 hover:to-pink-400 transition-all shadow-lg shadow-violet-500/25 cursor-pointer"
            >
              ▶ Launch Experiment
            </button>
            <p className="text-xs text-slate-500 mt-3">2 Banks · Simulated AI · 5 rounds · No API cost</p>
          </div>

          {/* Scenario Pack */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-300">Choose Scenario</h3>
            {gameScenarios.map(s => (
              <button
                key={s.id}
                onClick={() => setSelectedScenario(s.id)}
                className={`w-full text-left p-4 rounded-xl border transition-all ${
                  selectedScenario === s.id
                    ? 'border-violet-500 bg-violet-500/10'
                    : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-semibold flex items-center gap-2">
                      {s.name}
                      {s.id === '2bank_12tick' && (
                        <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">★ Recommended</span>
                      )}
                    </div>
                    <div className="text-sm text-slate-400 mt-1">{s.description}</div>
                  </div>
                  <div className="text-xs text-slate-500 flex gap-3">
                    <span>{s.ticks_per_day} ticks</span>
                    <span>{s.num_agents} banks</span>
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Game Settings */}
          <GameSettingsPanel
            agentIds={agentIds}
            settings={gameSettings}
            onChange={setGameSettings}
          />

          <button
            onClick={() => {
              onGameLaunch?.({
                scenario_id: selectedScenario,
                ...gameSettingsToConfig(gameSettings),
              });
            }}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-violet-500 to-pink-500 font-semibold text-white hover:from-violet-400 hover:to-pink-400 transition-all shadow-lg shadow-violet-500/20"
          >
            {'Start Experiment'}
          </button>
        </div>
      ) : mode === 'preset' ? (
        <div className="space-y-3 mb-8">
          {presets.map(p => (
            <button
              key={p.id}
              onClick={() => setSelectedPreset(p.id)}
              className={`w-full text-left p-4 rounded-xl border transition-all ${
                selectedPreset === p.id
                  ? 'border-sky-500 bg-sky-500/10'
                  : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
              }`}
            >
              <div className="flex justify-between items-start">
                <div>
                  <div className="font-semibold">{p.name}</div>
                  <div className="text-sm text-slate-400 mt-1">{p.description}</div>
                </div>
                <div className="text-xs text-slate-500 flex gap-3">
                  <span>{p.ticks_per_day} ticks</span>
                  <span>{p.num_agents} banks</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="space-y-6 mb-8">
          {/* Simulation params */}
          <Section title="Simulation Parameters">
            <div className="grid grid-cols-3 gap-4">
              <NumberInput label="Ticks per Day" value={config.ticks_per_day} onChange={v => setConfig({ ...config, ticks_per_day: v })} min={1} max={50} />
              <NumberInput label="Days" value={config.num_days} onChange={v => setConfig({ ...config, num_days: v })} min={1} max={5} />
              <NumberInput label="RNG Seed" value={config.rng_seed} onChange={v => setConfig({ ...config, rng_seed: v })} min={0} max={99999} />
            </div>
          </Section>

          {/* Cost rates */}
          <Section title="Cost Parameters">
            <div className="grid grid-cols-2 gap-4">
              <SliderInput
                label="Liquidity Cost (bps/tick)"
                value={config.liquidity_cost_per_tick_bps}
                onChange={v => setConfig({ ...config, liquidity_cost_per_tick_bps: v })}
                min={0} max={1000} step={10}
              />
              <SliderInput
                label="Delay Cost (per cent/tick)"
                value={config.delay_cost_per_tick_per_cent}
                onChange={v => setConfig({ ...config, delay_cost_per_tick_per_cent: v })}
                min={0} max={5} step={0.1}
              />
              <NumberInput
                label="EOD Penalty ($)"
                value={config.eod_penalty_per_transaction / 100}
                onChange={v => setConfig({ ...config, eod_penalty_per_transaction: v * 100 })}
                min={0} max={50000}
              />
              <NumberInput
                label="Deadline Penalty ($)"
                value={config.deadline_penalty / 100}
                onChange={v => setConfig({ ...config, deadline_penalty: v * 100 })}
                min={0} max={50000}
              />
            </div>
            <p className="text-xs text-slate-500 mt-2">
              Constraint: r_c (liquidity) &lt; r_d (delay) &lt; r_b (penalty). Current: {config.liquidity_cost_per_tick_bps} bps &lt; {config.delay_cost_per_tick_per_cent}/cent/tick
            </p>
          </Section>

          {/* Toggles */}
          <Section title="Features">
            <div className="flex gap-6 flex-wrap">
              <Toggle label="Deferred Crediting" value={config.deferred_crediting} onChange={v => setConfig({ ...config, deferred_crediting: v })} />
              <Toggle label="Deadline Cap at EOD" value={config.deadline_cap_at_eod} onChange={v => setConfig({ ...config, deadline_cap_at_eod: v })} />
              <Toggle label="Bilateral LSM" value={config.enable_bilateral_lsm} onChange={v => setConfig({ ...config, enable_bilateral_lsm: v })} />
              <Toggle label="Cycle LSM" value={config.enable_cycle_lsm} onChange={v => setConfig({ ...config, enable_cycle_lsm: v })} />
            </div>
          </Section>

          {/* Banks */}
          <Section title={`Banks (${config.agents?.length || 0})`}>
            <div className="space-y-3">
              {(config.agents || []).map((agent, i) => (
                <div key={i} className="flex items-center gap-3 bg-slate-900/50 rounded-lg p-3">
                  <input
                    value={agent.id}
                    onChange={e => updateAgent(i, { id: e.target.value })}
                    className="w-24 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-sm font-mono text-slate-200"
                  />
                  <div className="flex-1">
                    <label className="text-xs text-slate-500">Liquidity Pool ($)</label>
                    <input
                      type="number"
                      value={agent.liquidity_pool / 100}
                      onChange={e => updateAgent(i, { liquidity_pool: Number(e.target.value) * 100 })}
                      className="w-full px-2 py-1 bg-slate-800 border border-slate-700 rounded text-sm font-mono text-slate-200"
                    />
                  </div>
                  {(config.agents?.length || 0) > 2 && (
                    <button onClick={() => removeAgent(i)} className="text-red-400 hover:text-red-300 text-sm">✕</button>
                  )}
                </div>
              ))}
              {(config.agents?.length || 0) < 8 && (
                <button onClick={addAgent} className="text-sm text-sky-400 hover:text-sky-300">+ Add Bank</button>
              )}
            </div>
          </Section>

          {/* Payment schedule */}
          <Section title={`Payment Schedule (${config.payment_schedule?.length || 0})`}>
            <div className="space-y-2">
              {(config.payment_schedule || []).map((p, i) => (
                <div key={i} className="flex items-center gap-2 bg-slate-900/50 rounded-lg p-2 text-sm">
                  <select value={p.sender} onChange={e => updatePayment(i, { sender: e.target.value })} className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs">
                    {(config.agents || []).map(a => <option key={a.id} value={a.id}>{a.id}</option>)}
                  </select>
                  <span className="text-slate-500">→</span>
                  <select value={p.receiver} onChange={e => updatePayment(i, { receiver: e.target.value })} className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs">
                    {(config.agents || []).map(a => <option key={a.id} value={a.id}>{a.id}</option>)}
                  </select>
                  <div>
                    <input type="number" value={p.amount / 100} onChange={e => updatePayment(i, { amount: Number(e.target.value) * 100 })} className="w-20 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs font-mono text-slate-200" />
                    <span className="text-xs text-slate-500 ml-1">$</span>
                  </div>
                  <div>
                    <span className="text-xs text-slate-500">t=</span>
                    <input type="number" value={p.tick} onChange={e => updatePayment(i, { tick: Number(e.target.value) })} className="w-12 px-1 py-1 bg-slate-800 border border-slate-700 rounded text-xs font-mono text-slate-200" />
                  </div>
                  <div>
                    <span className="text-xs text-slate-500">dl=</span>
                    <input type="number" value={p.deadline} onChange={e => updatePayment(i, { deadline: Number(e.target.value) })} className="w-12 px-1 py-1 bg-slate-800 border border-slate-700 rounded text-xs font-mono text-slate-200" />
                  </div>
                  <button onClick={() => removePayment(i)} className="text-red-400 hover:text-red-300 text-xs">✕</button>
                </div>
              ))}
              <button onClick={addPayment} className="text-sm text-sky-400 hover:text-sky-300">+ Add Payment</button>
            </div>
          </Section>

          {/* Actions */}
          <div className="flex gap-3">
            <button onClick={randomize} className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-sm font-medium">Randomize</button>
            <button onClick={exportConfig} className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-sm font-medium">📥 Export JSON</button>
            <button onClick={importConfig} className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-sm font-medium">📤 Import JSON</button>
          </div>

          {/* Start Game with custom config */}
          {onGameLaunch && (
            <button
              onClick={() => {
                // Convert ScenarioConfig to raw YAML-compatible dict for the engine
                const inlineConfig: Record<string, unknown> = {
                  simulation: {
                    ticks_per_day: config.ticks_per_day,
                    num_days: config.num_days,
                    rng_seed: config.rng_seed,
                  },
                  deferred_crediting: config.deferred_crediting,
                  deadline_cap_at_eod: config.deadline_cap_at_eod,
                  cost_rates: {
                    liquidity_cost_per_tick_bps: config.liquidity_cost_per_tick_bps,
                    delay_cost_per_tick_per_cent: config.delay_cost_per_tick_per_cent,
                    eod_penalty_per_transaction: config.eod_penalty_per_transaction,
                    deadline_penalty: config.deadline_penalty,
                  },
                  lsm_config: {
                    enable_bilateral: config.enable_bilateral_lsm,
                    enable_cycles: config.enable_cycle_lsm,
                  },
                  agents: (config.agents || []).map(a => ({
                    id: a.id,
                    opening_balance: a.opening_balance,
                    unsecured_cap: a.unsecured_cap,
                    liquidity_pool: a.liquidity_pool,
                  })),
                  payment_schedule: config.payment_schedule || [],
                };
                onGameLaunch({
                  inline_config: inlineConfig,
                  use_llm: config.use_llm,
                  mock_reasoning: config.mock_reasoning,
                  max_days: 10,
                  num_eval_samples: 1,
                });
              }}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-violet-500 to-pink-500 font-semibold text-white hover:from-violet-400 hover:to-pink-400 transition-all shadow-lg shadow-violet-500/20"
            >
              {'Start Multi-Round Experiment'}
            </button>
          )}
        </div>
      )}

      {/* AI Reasoning + Launch — only for Presets and Custom Builder */}
      {mode !== 'game' && (
        <>
          <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 mb-6">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-300">🧠 AI Agent Reasoning (Gemini 2.5 Flash)</h3>
                <p className="text-xs text-slate-500 mt-1">Watch agents think through decisions in real-time</p>
              </div>
              <Toggle label="" value={config.use_llm} onChange={v => setConfig({ ...config, use_llm: v })} />
            </div>
            {config.use_llm && (
              <div className="flex items-center justify-between pt-3 border-t border-slate-700/50">
                <div>
                  <span className="text-xs text-slate-400">Simulated AI</span>
                  <span className="text-[10px] text-slate-600 ml-2">
                    {config.mock_reasoning ? 'Use simulated AI responses (no API cost)' : '⚠ Uses Vertex AI API'}
                  </span>
                </div>
                <Toggle label="" value={config.mock_reasoning} onChange={v => setConfig({ ...config, mock_reasoning: v })} />
              </div>
            )}
          </div>

          <button
            onClick={handleLaunch}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-sky-500 to-violet-500 font-semibold text-white hover:from-sky-400 hover:to-violet-400 transition-all shadow-lg shadow-sky-500/20"
          >
            Launch Simulation
          </button>
        </>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
      <h3 className="text-sm font-semibold text-slate-300 mb-4">{title}</h3>
      {children}
    </div>
  );
}

function NumberInput({ label, value, onChange, min, max }: { label: string; value: number; onChange: (v: number) => void; min?: number; max?: number }) {
  return (
    <div>
      <label className="text-xs text-slate-500 block mb-1">{label}</label>
      <input
        type="number"
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        min={min}
        max={max}
        className="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm font-mono text-slate-200 focus:outline-none focus:border-sky-500"
      />
    </div>
  );
}

function SliderInput({ label, value, onChange, min, max, step }: { label: string; value: number; onChange: (v: number) => void; min: number; max: number; step?: number }) {
  return (
    <div>
      <label className="text-xs text-slate-500 flex justify-between mb-1">
        <span>{label}</span>
        <span className="font-mono text-slate-300">{value}</span>
      </label>
      <input
        type="range"
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        min={min}
        max={max}
        step={step}
        className="w-full accent-sky-400"
      />
    </div>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <div
        onClick={() => onChange(!value)}
        className={`w-9 h-5 rounded-full transition-colors relative ${value ? 'bg-sky-500' : 'bg-slate-600'}`}
      >
        <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${value ? 'left-4.5' : 'left-0.5'}`} />
      </div>
      <span className="text-sm text-slate-300">{label}</span>
    </label>
  );
}
