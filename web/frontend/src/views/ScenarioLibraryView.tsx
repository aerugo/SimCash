import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { LibraryScenario, LibraryScenarioDetail, GameSetupConfig } from '../types';
import { getScenarioLibrary, getScenarioLibraryDetail, fetchCollections, type Collection, listCustomScenarios, deleteCustomScenario, saveCustomScenario, type CustomScenario, fetchModels, type ModelOption } from '../api';
import { useGameContext } from '../GameContext';
import { useAuthInfo } from '../AuthInfoContext';
import yaml from 'js-yaml';

const CATEGORY_ICONS: Record<string, string> = {
  'Paper Experiments': '📄',
  'Crisis & Stress': '🔥',
  'LSM Exploration': '⚙️',
  'General': '🎯',
  'Testing': '🧪',
};

const DIFFICULTY_COLORS: Record<string, string> = {
  beginner: 'text-green-400 bg-green-400/10 border-green-400/30',
  intermediate: 'text-amber-400 bg-amber-400/10 border-amber-400/30',
  advanced: 'text-red-400 bg-red-400/10 border-red-400/30',
};

const TAG_COLORS: Record<string, string> = {
  crisis: 'bg-red-500/20 text-red-300',
  lsm: 'bg-purple-500/20 text-purple-300',
  stochastic: 'bg-blue-500/20 text-blue-300',
  deterministic: 'bg-teal-500/20 text-teal-300',
  'multi-day': 'bg-amber-500/20 text-amber-300',
  priority: 'bg-orange-500/20 text-orange-300',
  'custom-events': 'bg-pink-500/20 text-pink-300',
  paper: 'bg-sky-500/20 text-sky-300',
};

export function ScenarioLibraryView() {
  const { handleGameLaunch } = useGameContext();
  const navigate = useNavigate();
  const { isGuest } = useAuthInfo();
  const { scenarioId: urlScenarioId } = useParams<{ scenarioId: string }>();
  const onLaunchGame = async (config: GameSetupConfig) => {
    const gid = await handleGameLaunch(config);
    if (gid) navigate(`/experiment/${gid}`);
  };
  const [scenarios, setScenarios] = useState<LibraryScenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedScenario, setSelectedScenario] = useState<LibraryScenarioDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [customScenarios, setCustomScenarios] = useState<CustomScenario[]>([]);
  const [showMyScenarios, setShowMyScenarios] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [copying, setCopying] = useState(false);
  const [selectedCustom, setSelectedCustom] = useState<CustomScenario | null>(null);

  // Game launch config
  const [rounds, setRounds] = useState(1);
  const [useLlm, setUseLlm] = useState(true);
  const [simulatedAi, setSimulatedAi] = useState(false);
  const [numEvalSamples, setNumEvalSamples] = useState(50);
  const [constraintPreset, setConstraintPreset] = useState<'simple' | 'full'>('full');
  const [optimizationInterval, setOptimizationInterval] = useState(1);
  const [optimizationSchedule, setOptimizationSchedule] = useState<'every_round' | 'every_scenario_day'>('every_scenario_day');
  const [availableModels, setAvailableModels] = useState<ModelOption[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');  // empty = server default
  const [startingFraction, setStartingFraction] = useState(0.5);

  const buildStartingPolicies = (agentIds: string[]): Record<string, string> => {
    const policies: Record<string, string> = {};
    for (const aid of agentIds) {
      policies[aid] = JSON.stringify({
        version: "2.0",
        policy_id: "default_fifo",
        parameters: { initial_liquidity_fraction: startingFraction },
        bank_tree: { type: "action", node_id: "bank_root", action: "NoAction" },
        payment_tree: { type: "action", node_id: "pay_root", action: "Release" },
      });
    }
    return policies;
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getScenarioLibrary(showArchived),
      fetchCollections().catch(() => [] as Collection[]),
      isGuest ? Promise.resolve([]) : listCustomScenarios().catch(() => [] as CustomScenario[]),
      isGuest ? Promise.resolve([]) : fetchModels().catch(() => [] as ModelOption[]),
    ])
      .then(([s, c, cs, m]) => {
        setScenarios(s);
        setCollections(c);
        setCustomScenarios(cs);
        setAvailableModels(m as ModelOption[]);
        const active = (m as ModelOption[]).find(x => x.active);
        if (active && !selectedModel) setSelectedModel(active.id);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [showArchived, isGuest]);

  const handleDeleteCustom = async (id: string) => {
    try {
      await deleteCustomScenario(id);
      setCustomScenarios(prev => prev.filter(s => s.id !== id));
      setDeleteConfirm(null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const handleCopyScenario = async () => {
    if (!selectedScenario) return;
    setCopying(true);
    try {
      const saved = await saveCustomScenario({
        name: `Copy of ${selectedScenario.name}`,
        description: selectedScenario.description,
        yaml_string: yaml.dump(selectedScenario.raw_config),
      });
      navigate(`/create?edit=${saved.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCopying(false);
    }
  };

  // Auto-open scenario from URL param
  useEffect(() => {
    if (urlScenarioId && !selectedScenario && !detailLoading && scenarios.length > 0) {
      handleSelectScenario(urlScenarioId);
    }
  }, [urlScenarioId, scenarios.length]);

  const categories = [...new Set(scenarios.map(s => s.category))];
  const activeCollection = collections.find(c => c.id === selectedCollection);
  const searchLower = searchQuery.toLowerCase();
  const filtered = scenarios.filter(s => {
    if (selectedCollection && activeCollection) {
      const inCollection = activeCollection.scenario_ids.includes(s.id) || s.collections?.includes(selectedCollection);
      if (!inCollection) return false;
    }
    if (selectedCategory && s.category !== selectedCategory) return false;
    if (searchLower) {
      return (
        s.name.toLowerCase().includes(searchLower) ||
        s.description.toLowerCase().includes(searchLower) ||
        s.tags.some(t => t.toLowerCase().includes(searchLower)) ||
        String(s.num_agents).includes(searchLower)
      );
    }
    return true;
  });

  const handleSelectScenario = async (id: string) => {
    setDetailLoading(true);
    try {
      const detail = await getScenarioLibraryDetail(id);
      setSelectedScenario(detail);
      // Update URL without full navigation
      if (!urlScenarioId || urlScenarioId !== id) {
        navigate(`/library/scenarios/${id}`, { replace: true });
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleLaunch = () => {
    if (!selectedScenario || !onLaunchGame) return;
    const libAgentIds: string[] = Array.isArray((selectedScenario.raw_config as any)?.agents)
      ? (selectedScenario.raw_config as any).agents.map((a: any) => a.id).filter(Boolean)
      : [];
    onLaunchGame({
      scenario_id: selectedScenario.id,
      scenario_name: selectedScenario.name,
      inline_config: selectedScenario.raw_config,
      use_llm: useLlm,
      simulated_ai: simulatedAi,
      rounds: rounds,
      num_eval_samples: numEvalSamples,
      optimization_interval: optimizationInterval,
      constraint_preset: constraintPreset,
      optimization_schedule: selectedScenario.num_days > 1 ? optimizationSchedule : undefined,
      starting_policies: libAgentIds.length > 0 ? buildStartingPolicies(libAgentIds) : undefined,
      model_override: selectedModel || undefined,
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-20">
        <div className="text-4xl mb-4">⚠️</div>
        <p className="text-red-400">{error}</p>
      </div>
    );
  }

  // Loading state for detail fetch
  if (detailLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-500" />
        <span className="ml-3 text-sm text-slate-400">Loading scenario details…</span>
      </div>
    );
  }

  // Detail view for a selected custom scenario
  if (selectedCustom) {
    let parsedConfig: Record<string, unknown> | null = null;
    try { parsedConfig = yaml.load(selectedCustom.yaml_string) as Record<string, unknown>; } catch { /* */ }
    const numAgents = parsedConfig && Array.isArray((parsedConfig as any)?.agents) ? (parsedConfig as any).agents.length : '?';
    const customNumDays: number = (parsedConfig as any)?.simulation?.num_days ?? 1;
    const customAgentIds: string[] = parsedConfig && Array.isArray((parsedConfig as any)?.agents)
      ? (parsedConfig as any).agents.map((a: any) => a.id).filter(Boolean)
      : [];
    const handleCustomLaunch = () => {
      if (!parsedConfig) return;
      onLaunchGame({
        scenario_id: `custom:${selectedCustom.id}`,
        scenario_name: selectedCustom.name,
        inline_config: parsedConfig,
        use_llm: useLlm,
        simulated_ai: simulatedAi,
        rounds: rounds,
        num_eval_samples: numEvalSamples,
        optimization_interval: optimizationInterval,
        optimization_schedule: customNumDays > 1 ? optimizationSchedule : undefined,
        constraint_preset: constraintPreset,
        starting_policies: customAgentIds.length > 0 ? buildStartingPolicies(customAgentIds) : undefined,
        model_override: selectedModel || undefined,
      });
    };
    return (
      <div>
        <button
          onClick={() => setSelectedCustom(null)}
          className="mb-4 text-sm flex items-center gap-1"
          style={{ color: 'var(--text-secondary)' }}
        >
          ← Back to My Scenarios
        </button>

        <div className="rounded-xl p-6" style={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)' }}>
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-2xl">📝</span>
                <h2 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{selectedCustom.name}</h2>
              </div>
              <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-300 border border-slate-600">Custom</span>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => navigate(`/create?edit=${selectedCustom.id}`)}
                className="p-1.5 rounded hover:bg-sky-500/20 text-slate-400 hover:text-sky-300 transition-colors text-sm"
                title="Edit"
              >✏️ Edit</button>
            </div>
          </div>

          <p className="text-sm mb-4 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            {selectedCustom.description || 'No description'}
          </p>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
            <div className="rounded-lg p-3 text-center" style={{ backgroundColor: 'var(--bg-inset)' }}>
              <div className="text-lg font-bold text-sky-400">{numAgents}</div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Banks</div>
            </div>
            <div className="rounded-lg p-3 text-center" style={{ backgroundColor: 'var(--bg-inset)' }}>
              <div className="text-lg font-bold text-sky-400">Custom</div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Source</div>
            </div>
          </div>

          {/* Launch Configuration */}
          <div className="pt-4 mt-4" style={{ borderTop: '1px solid var(--border-color)' }}>
            <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>🚀 Launch Configuration</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <div>
                <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>Rounds</label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={rounds}
                  onChange={e => setRounds(Number(e.target.value))}
                  className="w-full px-3 py-1.5 rounded text-sm"
                  style={{ backgroundColor: 'var(--input-bg, var(--card-bg))', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
                />
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>Eval Samples</label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={numEvalSamples}
                  onChange={e => setNumEvalSamples(Number(e.target.value))}
                  className="w-full px-3 py-1.5 rounded text-sm"
                  style={{ backgroundColor: 'var(--input-bg, var(--card-bg))', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
                />
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>
                  {customNumDays > 1 ? 'Optimize When' : 'Optimize Every'}
                </label>
                <select
                  value={customNumDays > 1 && optimizationSchedule === 'every_scenario_day' ? 'every_scenario_day' : String(optimizationInterval)}
                  onChange={e => {
                    const v = e.target.value;
                    if (v === 'every_scenario_day') {
                      setOptimizationSchedule('every_scenario_day');
                      setOptimizationInterval(1);
                    } else {
                      setOptimizationSchedule('every_round');
                      setOptimizationInterval(Number(v));
                    }
                  }}
                  className="w-full px-3 py-1.5 rounded text-sm"
                  style={{ backgroundColor: 'var(--input-bg, var(--card-bg))', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
                >
                  {customNumDays > 1 && (
                    <option value="every_scenario_day">Between each day ({customNumDays}× per round)</option>
                  )}
                  <option value={1}>Every round{customNumDays > 1 ? ` (all ${customNumDays} days)` : ''}</option>
                  <option value={2}>Every 2 rounds</option>
                  <option value={3}>Every 3 rounds</option>
                  <option value={5}>Every 5 rounds</option>
                </select>
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>AI Reasoning</label>
                <select
                  value={useLlm ? (simulatedAi ? 'mock' : 'real') : 'off'}
                  onChange={e => {
                    const v = e.target.value;
                    setUseLlm(v !== 'off');
                    setSimulatedAi(v === 'mock');
                  }}
                  className="w-full px-3 py-1.5 rounded text-sm"
                  style={{ backgroundColor: 'var(--input-bg, var(--card-bg))', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
                >
                  <option value="off">Off (FIFO)</option>
                  <option value="mock">Simulated AI (no API cost)</option>
                  <option value="real" disabled={isGuest}>Live AI (Vertex AI){isGuest ? ' — sign in required' : ''}</option>
                </select>
              </div>
            </div>
            {useLlm && (
              <div className="mb-4">
                <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>LLM Strategy Depth</label>
                <div className="grid grid-cols-2 gap-2">
                  {([
                    { id: 'simple' as const, label: 'Simple', desc: 'initial_liquidity_fraction only' },
                    { id: 'full' as const, label: 'Full', desc: 'Complete decision trees' },
                  ]).map(p => (
                    <button
                      key={p.id}
                      onClick={() => setConstraintPreset(p.id)}
                      className={`p-2 rounded-lg text-left border transition-colors ${
                        constraintPreset === p.id
                          ? 'border-sky-500 bg-sky-500/10'
                          : 'hover:border-sky-500/30'
                      }`}
                      style={constraintPreset !== p.id ? { borderColor: 'var(--border-color)', backgroundColor: 'var(--bg-inset)' } : undefined}
                    >
                      <div className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{p.label}</div>
                      <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{p.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {useLlm && !simulatedAi && availableModels.length > 0 && (
              <div className="mb-4">
                <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>Optimization Model</label>
                <select
                  value={selectedModel}
                  onChange={e => setSelectedModel(e.target.value)}
                  className="w-full px-3 py-1.5 rounded text-sm"
                  style={{ backgroundColor: 'var(--input-bg, var(--card-bg))', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
                >
                  {availableModels.map(m => (
                    <option key={m.id} value={m.id}>{m.label}{m.active ? ' (default)' : ''}</option>
                  ))}
                </select>
              </div>
            )}
            {/* Starting Liquidity Fraction */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs" style={{ color: 'var(--text-muted)' }}>Starting Liquidity Fraction</label>
                <span className="text-xs font-mono" style={{ color: 'var(--text-primary)' }}>{Math.round(startingFraction * 100)}% of pool</span>
              </div>
              <input
                type="range"
                min={0.05}
                max={1.0}
                step={0.05}
                value={startingFraction}
                onChange={e => setStartingFraction(Number(e.target.value))}
                className="w-full accent-sky-500"
                style={{ height: '6px' }}
              />
              <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
                How much of their liquidity pool each bank commits at the start of each business day. Liquidity is returned at end-of-day and reallocated fresh each morning — the AI optimizer can change this fraction between days.
              </p>
            </div>
            <button
              onClick={handleCustomLaunch}
              disabled={!parsedConfig}
              className="w-full py-3 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-sm font-semibold transition-colors"
            >
              🚀 Launch Simulation
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Detail view for a selected scenario
  if (selectedScenario) {
    return (
      <div>
        <button
          onClick={() => { setSelectedScenario(null); navigate('/library/scenarios'); }}
          className="mb-4 text-sm flex items-center gap-1"
          style={{ color: 'var(--text-secondary)' }}
        >
          ← Back to Library
        </button>

        <div className="rounded-xl p-6" style={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)' }}>
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-2xl">{CATEGORY_ICONS[selectedScenario.category] || '🎯'}</span>
                <h2 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{selectedScenario.name}</h2>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded border ${DIFFICULTY_COLORS[selectedScenario.difficulty]}`}>
                {selectedScenario.difficulty}
              </span>
            </div>
            <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>{selectedScenario.id}</span>
          </div>

          <p className="text-sm mb-4 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{selectedScenario.description}</p>

          {/* Tags */}
          <div className="flex flex-wrap gap-1.5 mb-4">
            {selectedScenario.tags.map(tag => (
              <span key={tag} className={`text-xs px-2 py-0.5 rounded ${TAG_COLORS[tag] || 'bg-slate-700 text-slate-300'}`}>
                {tag}
              </span>
            ))}
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <div className="rounded-lg p-3 text-center" style={{ backgroundColor: 'var(--bg-inset)' }}>
              <div className="text-lg font-bold text-sky-400">{selectedScenario.num_agents}</div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Banks</div>
            </div>
            <div className="rounded-lg p-3 text-center" style={{ backgroundColor: 'var(--bg-inset)' }}>
              <div className="text-lg font-bold text-sky-400">{selectedScenario.ticks_per_day}</div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Ticks/Day</div>
            </div>
            <div className="rounded-lg p-3 text-center" style={{ backgroundColor: 'var(--bg-inset)' }}>
              <div className="text-lg font-bold text-sky-400">{selectedScenario.num_days}</div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Days</div>
            </div>
            <div className="rounded-lg p-3 text-center" style={{ backgroundColor: 'var(--bg-inset)' }}>
              <div className="text-lg font-bold text-sky-400">{selectedScenario.features_used.length}</div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Features</div>
            </div>
          </div>

          {/* Features */}
          {selectedScenario.features_used.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-secondary)' }}>Engine Features</h3>
              <div className="flex flex-wrap gap-1.5">
                {selectedScenario.features_used.map(f => (
                  <span key={f} className="text-xs px-2 py-1 rounded" style={{ backgroundColor: 'var(--bg-inset)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)' }}>
                    {f.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Cost Config */}
          {Object.keys(selectedScenario.cost_config).length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-secondary)' }}>Cost Parameters</h3>
              <div className="rounded-lg p-3 grid grid-cols-2 gap-2 text-xs" style={{ backgroundColor: 'var(--bg-inset)' }}>
                {Object.entries(selectedScenario.cost_config).map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span style={{ color: 'var(--text-muted)' }}>{k.replace(/_/g, ' ')}</span>
                    <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>{typeof v === 'number' ? v.toLocaleString() : String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Launch Configuration */}
          <div className="pt-4 mt-4" style={{ borderTop: '1px solid var(--border-color)' }}>
            <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>🚀 Launch Configuration</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <div>
                <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>Rounds</label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={rounds}
                  onChange={e => setRounds(Number(e.target.value))}
                  className="w-full px-3 py-1.5 rounded text-sm"
                  style={{ backgroundColor: 'var(--input-bg, var(--card-bg))', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
                />
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>Eval Samples</label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={numEvalSamples}
                  onChange={e => setNumEvalSamples(Number(e.target.value))}
                  className="w-full px-3 py-1.5 rounded text-sm"
                  style={{ backgroundColor: 'var(--input-bg, var(--card-bg))', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
                />
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>
                  {selectedScenario.num_days > 1 ? 'Optimize When' : 'Optimize Every'}
                </label>
                <select
                  value={selectedScenario.num_days > 1 && optimizationSchedule === 'every_scenario_day' ? 'every_scenario_day' : String(optimizationInterval)}
                  onChange={e => {
                    const v = e.target.value;
                    if (v === 'every_scenario_day') {
                      setOptimizationSchedule('every_scenario_day');
                      setOptimizationInterval(1);
                    } else {
                      setOptimizationSchedule('every_round');
                      setOptimizationInterval(Number(v));
                    }
                  }}
                  className="w-full px-3 py-1.5 rounded text-sm"
                  style={{ backgroundColor: 'var(--input-bg, var(--card-bg))', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
                >
                  {selectedScenario.num_days > 1 && (
                    <option value="every_scenario_day">Between each day ({selectedScenario.num_days}× per round)</option>
                  )}
                  <option value={1}>After every round{selectedScenario.num_days > 1 ? ` (all ${selectedScenario.num_days} days)` : ''}</option>
                  <option value={2}>Every 2 rounds</option>
                  <option value={3}>Every 3 rounds</option>
                  <option value={5}>Every 5 rounds</option>
                  <option value={10}>Every 10 rounds</option>
                </select>
                <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
                  {selectedScenario.num_days > 1 && optimizationSchedule === 'every_scenario_day'
                    ? `AI optimizes policy between each of the ${selectedScenario.num_days} simulated days`
                    : 'Rounds between AI policy updates'}
                </p>
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>AI Reasoning</label>
                <select
                  value={useLlm ? (simulatedAi ? 'mock' : 'real') : 'off'}
                  onChange={e => {
                    const v = e.target.value;
                    setUseLlm(v !== 'off');
                    setSimulatedAi(v === 'mock');
                  }}
                  className="w-full px-3 py-1.5 rounded text-sm"
                  style={{ backgroundColor: 'var(--input-bg, var(--card-bg))', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
                >
                  <option value="off">Off (FIFO)</option>
                  <option value="mock">Simulated AI (no API cost)</option>
                  <option value="real" disabled={isGuest}>Live AI (Vertex AI){isGuest ? ' — sign in required' : ''}</option>
                </select>
              </div>
            </div>
            {/* Advanced: Constraint Preset */}
            {useLlm && (
              <div className="mb-4">
                <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>LLM Strategy Depth</label>
                <div className="grid grid-cols-2 gap-2">
                  {([
                    { id: 'simple' as const, label: 'Simple', desc: 'initial_liquidity_fraction only' },
                    { id: 'full' as const, label: 'Full', desc: 'Complete decision trees' },
                  ]).map(p => (
                    <button
                      key={p.id}
                      onClick={() => setConstraintPreset(p.id)}
                      className={`p-2 rounded-lg text-left border transition-colors ${
                        constraintPreset === p.id
                          ? 'border-sky-500 bg-sky-500/10'
                          : 'hover:border-sky-500/30'
                      }`}
                      style={constraintPreset !== p.id ? { borderColor: 'var(--border-color)', backgroundColor: 'var(--bg-inset)' } : undefined}
                    >
                      <div className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{p.label}</div>
                      <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{p.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {useLlm && !simulatedAi && availableModels.length > 0 && (
              <div className="mb-4">
                <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>Optimization Model</label>
                <select
                  value={selectedModel}
                  onChange={e => setSelectedModel(e.target.value)}
                  className="w-full px-3 py-1.5 rounded text-sm"
                  style={{ backgroundColor: 'var(--input-bg, var(--card-bg))', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
                >
                  {availableModels.map(m => (
                    <option key={m.id} value={m.id}>{m.label}{m.active ? ' (default)' : ''}</option>
                  ))}
                </select>
              </div>
            )}
            {/* Starting Liquidity Fraction */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs" style={{ color: 'var(--text-muted)' }}>Starting Liquidity Fraction</label>
                <span className="text-xs font-mono" style={{ color: 'var(--text-primary)' }}>{Math.round(startingFraction * 100)}% of pool</span>
              </div>
              <input
                type="range"
                min={0.05}
                max={1.0}
                step={0.05}
                value={startingFraction}
                onChange={e => setStartingFraction(Number(e.target.value))}
                className="w-full accent-sky-500"
                style={{ height: '6px' }}
              />
              <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
                How much of their liquidity pool each bank commits at the start of each business day. Liquidity is returned at end-of-day and reallocated fresh each morning — the AI optimizer can change this fraction between days.
              </p>
            </div>
            {isGuest ? (
              <div className="text-center py-3 rounded-lg text-sm" style={{ backgroundColor: 'var(--bg-inset)', border: '1px solid var(--border-color)' }}>
                <p style={{ color: 'var(--text-secondary)' }}>Sign in to run experiments</p>
              </div>
            ) : (
              <div className="flex gap-3">
                <button
                  onClick={handleLaunch}
                  disabled={!onLaunchGame}
                  className="flex-1 py-3 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-sm font-semibold transition-colors"
                >
                  🚀 Launch Simulation
                </button>
                <button
                  onClick={handleCopyScenario}
                  disabled={copying}
                  className="px-4 py-3 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                  style={{ border: '1px solid var(--border-color)', color: 'var(--text-secondary)', backgroundColor: 'var(--bg-inset)' }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgb(14 165 233 / 0.5)'; e.currentTarget.style.color = 'rgb(56 189 248)'; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border-color)'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
                >
                  {copying ? '📋 Copying…' : '📋 Copy & Edit'}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Library list view
  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-bold mb-1" style={{ color: 'var(--text-primary)' }}>📚 Scenario Library</h2>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Explore {scenarios.length} scenarios — from paper experiments to crisis stress tests.
        </p>
      </div>

      {/* My Scenarios tab */}
      {!isGuest && customScenarios.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          <button
            onClick={() => setShowMyScenarios(false)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              !showMyScenarios ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            📚 Library
          </button>
          <button
            onClick={() => setShowMyScenarios(true)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              showMyScenarios ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            📝 My Scenarios ({customScenarios.length})
          </button>
        </div>
      )}

      {/* My Scenarios grid */}
      {showMyScenarios && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {customScenarios.map(cs => (
            <button
              key={cs.id}
              onClick={() => setSelectedCustom(cs)}
              className="rounded-xl border p-5 text-left hover:border-sky-500/50 transition-colors group"
              style={{ backgroundColor: 'var(--card-bg)', borderColor: 'var(--border-color)' }}
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
                  📝 {cs.name}
                </h3>
                <div className="flex items-center gap-1">
                  <button
                    onClick={(e) => { e.stopPropagation(); navigate(`/create?edit=${cs.id}`); }}
                    className="p-1 rounded hover:bg-sky-500/20 text-slate-400 hover:text-sky-300 transition-colors"
                    title="Edit"
                  >✏️</button>
                  <button
                    onClick={(e) => { e.stopPropagation(); setDeleteConfirm(cs.id); }}
                    className="p-1 rounded hover:bg-red-500/20 text-slate-400 hover:text-red-300 transition-colors"
                    title="Delete"
                  >🗑️</button>
                </div>
              </div>
              <p className="text-xs mb-3 line-clamp-2" style={{ color: 'var(--text-secondary)' }}>
                {cs.description || 'No description'}
              </p>
              <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ backgroundColor: 'var(--bg-inset)', color: 'var(--text-secondary)' }}>
                Custom
              </span>

              {/* Delete confirmation */}
              {deleteConfirm === cs.id && (
                <div className="mt-3 p-2 rounded-lg border" style={{ backgroundColor: 'var(--bg-inset)', borderColor: 'var(--border-color)' }}>
                  <p className="text-xs mb-2" style={{ color: 'var(--text-primary)' }}>Delete this scenario?</p>
                  <div className="flex gap-2">
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeleteCustom(cs.id); }}
                      className="px-2 py-1 rounded text-xs bg-red-600 hover:bg-red-500 text-white"
                    >Delete</button>
                    <button
                      onClick={(e) => { e.stopPropagation(); setDeleteConfirm(null); }}
                      className="px-2 py-1 rounded text-xs bg-slate-700 hover:bg-slate-600 text-slate-200"
                    >Cancel</button>
                  </div>
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Collections */}
      {!showMyScenarios && collections.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          <button
            onClick={() => setSelectedCollection(null)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              selectedCollection === null ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            All
          </button>
          {collections.map(col => (
            <button
              key={col.id}
              onClick={() => setSelectedCollection(col.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                selectedCollection === col.id
                  ? 'bg-sky-600 text-white'
                  : col.name === 'Paper Experiments'
                    ? 'bg-slate-800 text-slate-300 hover:text-slate-100 border border-sky-500/30'
                    : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {col.icon} {col.name} ({col.scenario_count})
            </button>
          ))}
        </div>
      )}

      {/* Search */}
      {!showMyScenarios && <div className="mb-4">
        <input
          type="text"
          placeholder="Search scenarios by name, description, tags, or agent count…"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="w-full px-4 py-2.5 rounded-lg text-sm focus:outline-none focus:border-sky-500 transition-colors"
          style={{ backgroundColor: 'var(--input-bg, var(--card-bg))', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
        />
      </div>}

      {/* Category filter */}
      {!showMyScenarios && <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => setSelectedCategory(null)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            selectedCategory === null ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
          }`}
        >
          All ({scenarios.length})
        </button>
        {categories.map(cat => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              selectedCategory === cat ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            {CATEGORY_ICONS[cat] || '📁'} {cat} ({scenarios.filter(s => s.category === cat).length})
          </button>
        ))}
      </div>}

      {/* Scenario cards */}
      {!showMyScenarios &&
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map(scenario => (
          <button
            key={scenario.id}
            onClick={() => handleSelectScenario(scenario.id)}
            className={`rounded-xl p-5 text-left hover:border-sky-500/50 transition-colors group ${
              scenario.visible === false ? 'opacity-50' : ''
            }`}
            style={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)' }}
          >
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-lg">{CATEGORY_ICONS[scenario.category] || '🎯'}</span>
                <h3 className="font-semibold group-hover:text-sky-300 transition-colors text-sm" style={{ color: 'var(--text-primary)' }}>
                  {scenario.name}
                </h3>
              </div>
              <div className="flex items-center gap-1">
                {scenario.visible === false && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-600/50 text-slate-400 border border-slate-600">
                    Archived
                  </span>
                )}
                <span className={`text-[10px] px-1.5 py-0.5 rounded border ${DIFFICULTY_COLORS[scenario.difficulty]}`}>
                  {scenario.difficulty}
                </span>
              </div>
            </div>

            <p className="text-xs mb-3 line-clamp-2" style={{ color: 'var(--text-secondary)' }}>{scenario.description}</p>

            {/* Tags */}
            <div className="flex flex-wrap gap-1 mb-3">
              {scenario.tags.slice(0, 4).map(tag => (
                <span key={tag} className={`text-[10px] px-1.5 py-0.5 rounded ${TAG_COLORS[tag] || 'bg-slate-700 text-slate-400'}`}>
                  {tag}
                </span>
              ))}
              {scenario.tags.length > 4 && (
                <span className="text-[10px] text-slate-500">+{scenario.tags.length - 4}</span>
              )}
            </div>

            {/* Stats row */}
            <div className="flex gap-3 text-[10px]" style={{ color: 'var(--text-muted)' }}>
              <span>{scenario.num_agents} banks</span>
              <span>·</span>
              <span>{scenario.ticks_per_day} ticks/day</span>
              {scenario.num_days > 1 && (
                <>
                  <span>·</span>
                  <span>{scenario.num_days} days</span>
                </>
              )}
            </div>
          </button>
        ))}
      </div>}

      {/* Show archived toggle */}
      <div className="mt-6 flex items-center gap-3">
        <button
          onClick={() => setShowArchived(!showArchived)}
          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
            showArchived ? 'bg-sky-600' : 'bg-slate-700'
          }`}
        >
          <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
            showArchived ? 'translate-x-4.5' : 'translate-x-0.5'
          }`} />
        </button>
        <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Show archived scenarios</span>
      </div>
    </div>
  );
}
