import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { LibraryScenario, LibraryScenarioDetail, GameSetupConfig } from '../types';
import { getScenarioLibrary, getScenarioLibraryDetail, fetchCollections, type Collection, listCustomScenarios, deleteCustomScenario, type CustomScenario } from '../api';
import { useGameContext } from '../GameContext';
import { useAuthInfo } from '../AuthInfoContext';

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

  // Game launch config
  const [maxDays, setMaxDays] = useState(10);
  const [useLlm, setUseLlm] = useState(true);
  const [simulatedAi, setSimulatedAi] = useState(false);
  const [numEvalSamples, setNumEvalSamples] = useState(50);
  const [constraintPreset, setConstraintPreset] = useState<'simple' | 'full'>('full');
  const [optimizationInterval, setOptimizationInterval] = useState(1);
  const [optimizationSchedule, setOptimizationSchedule] = useState<'every_round' | 'every_scenario_day'>('every_round');

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getScenarioLibrary(showArchived),
      fetchCollections().catch(() => [] as Collection[]),
      isGuest ? Promise.resolve([]) : listCustomScenarios().catch(() => [] as CustomScenario[]),
    ])
      .then(([s, c, cs]) => { setScenarios(s); setCollections(c); setCustomScenarios(cs); })
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
    onLaunchGame({
      scenario_id: selectedScenario.id,
      inline_config: selectedScenario.raw_config,
      use_llm: useLlm,
      simulated_ai: simulatedAi,
      max_days: maxDays,
      num_eval_samples: numEvalSamples,
      optimization_interval: optimizationInterval,
      constraint_preset: constraintPreset,
      optimization_schedule: selectedScenario.num_days > 1 ? optimizationSchedule : undefined,
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

  // Detail view for a selected scenario
  if (selectedScenario) {
    return (
      <div>
        <button
          onClick={() => { setSelectedScenario(null); navigate('/library/scenarios'); }}
          className="mb-4 text-sm text-slate-400 hover:text-slate-200 flex items-center gap-1"
        >
          ← Back to Library
        </button>

        <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-2xl">{CATEGORY_ICONS[selectedScenario.category] || '🎯'}</span>
                <h2 className="text-xl font-bold text-slate-100">{selectedScenario.name}</h2>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded border ${DIFFICULTY_COLORS[selectedScenario.difficulty]}`}>
                {selectedScenario.difficulty}
              </span>
            </div>
            <span className="text-xs text-slate-500 font-mono">{selectedScenario.id}</span>
          </div>

          <p className="text-sm text-slate-300 mb-4 leading-relaxed">{selectedScenario.description}</p>

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
            <div className="bg-slate-900/50 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-sky-400">{selectedScenario.num_agents}</div>
              <div className="text-xs text-slate-500">Banks</div>
            </div>
            <div className="bg-slate-900/50 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-sky-400">{selectedScenario.ticks_per_day}</div>
              <div className="text-xs text-slate-500">Ticks/Day</div>
            </div>
            <div className="bg-slate-900/50 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-sky-400">{selectedScenario.num_days}</div>
              <div className="text-xs text-slate-500">Days</div>
            </div>
            <div className="bg-slate-900/50 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-sky-400">{selectedScenario.features_used.length}</div>
              <div className="text-xs text-slate-500">Features</div>
            </div>
          </div>

          {/* Features */}
          {selectedScenario.features_used.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-slate-400 mb-2">Engine Features</h3>
              <div className="flex flex-wrap gap-1.5">
                {selectedScenario.features_used.map(f => (
                  <span key={f} className="text-xs px-2 py-1 rounded bg-slate-700/50 text-slate-300 border border-slate-600">
                    {f.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Cost Config */}
          {Object.keys(selectedScenario.cost_config).length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-slate-400 mb-2">Cost Parameters</h3>
              <div className="bg-slate-900/50 rounded-lg p-3 grid grid-cols-2 gap-2 text-xs">
                {Object.entries(selectedScenario.cost_config).map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-slate-500">{k.replace(/_/g, ' ')}</span>
                    <span className="text-slate-300 font-mono">{typeof v === 'number' ? v.toLocaleString() : String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Launch Configuration */}
          <div className="border-t border-slate-700 pt-4 mt-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">🚀 Launch Configuration</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <div>
                <label className="text-xs text-slate-500 block mb-1">Max Days</label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={maxDays}
                  onChange={e => setMaxDays(Number(e.target.value))}
                  className="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded text-sm text-slate-200"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">Eval Samples</label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={numEvalSamples}
                  onChange={e => setNumEvalSamples(Number(e.target.value))}
                  className="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded text-sm text-slate-200"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">Optimization Interval</label>
                <select
                  value={optimizationInterval}
                  onChange={e => setOptimizationInterval(Number(e.target.value))}
                  className="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded text-sm text-slate-200"
                >
                  <option value={1}>Every round</option>
                  <option value={2}>Every 2 rounds</option>
                  <option value={3}>Every 3 rounds</option>
                  <option value={5}>Every 5 rounds</option>
                </select>
                <p className="text-[10px] text-slate-600 mt-1">Rounds between AI policy updates</p>
              </div>
              {selectedScenario.num_days > 1 && (
              <div>
                <label className="text-xs text-slate-500 block mb-1">Optimization Schedule</label>
                <select
                  value={optimizationSchedule}
                  onChange={e => setOptimizationSchedule(e.target.value as 'every_round' | 'every_scenario_day')}
                  className="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded text-sm text-slate-200"
                >
                  <option value="every_round">Every round</option>
                  <option value="every_scenario_day">Every scenario day</option>
                </select>
                <p className="text-[10px] text-slate-600 mt-1">Optimize between scenario days (continuous sim)</p>
              </div>
              )}
              <div>
                <label className="text-xs text-slate-500 block mb-1">AI Reasoning</label>
                <select
                  value={useLlm ? (simulatedAi ? 'mock' : 'real') : 'off'}
                  onChange={e => {
                    const v = e.target.value;
                    setUseLlm(v !== 'off');
                    setSimulatedAi(v === 'mock');
                  }}
                  className="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded text-sm text-slate-200"
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
                <label className="text-xs text-slate-500 block mb-1">LLM Strategy Depth</label>
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
                          : 'border-slate-700 bg-slate-900 hover:border-slate-600'
                      }`}
                    >
                      <div className="text-xs font-medium text-slate-200">{p.label}</div>
                      <div className="text-[10px] text-slate-500">{p.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {isGuest ? (
              <div className="text-center py-3 rounded-lg text-sm" style={{ backgroundColor: 'var(--bg-inset)', border: '1px solid var(--border-color)' }}>
                <p style={{ color: 'var(--text-secondary)' }}>Sign in to run experiments</p>
              </div>
            ) : (
              <button
                onClick={handleLaunch}
                disabled={!onLaunchGame}
                className="w-full py-3 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-sm font-semibold transition-colors"
              >
                🚀 Launch Simulation
              </button>
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
        <h2 className="text-xl font-bold text-slate-100 mb-1">📚 Scenario Library</h2>
        <p className="text-sm text-slate-400">
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
            <div
              key={cs.id}
              className="rounded-xl border p-5 text-left transition-colors group"
              style={{ backgroundColor: 'var(--card-bg)', borderColor: 'var(--border-color)' }}
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
                  📝 {cs.name}
                </h3>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => navigate(`/create?edit=${cs.id}`)}
                    className="p-1 rounded hover:bg-sky-500/20 text-slate-400 hover:text-sky-300 transition-colors"
                    title="Edit"
                  >✏️</button>
                  <button
                    onClick={() => setDeleteConfirm(cs.id)}
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
                      onClick={() => handleDeleteCustom(cs.id)}
                      className="px-2 py-1 rounded text-xs bg-red-600 hover:bg-red-500 text-white"
                    >Delete</button>
                    <button
                      onClick={() => setDeleteConfirm(null)}
                      className="px-2 py-1 rounded text-xs bg-slate-700 hover:bg-slate-600 text-slate-200"
                    >Cancel</button>
                  </div>
                </div>
              )}
            </div>
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
          className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors"
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
            className={`bg-slate-800/50 rounded-xl border border-slate-700 p-5 text-left hover:border-sky-500/50 transition-colors group ${
              scenario.visible === false ? 'opacity-50' : ''
            }`}
          >
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-lg">{CATEGORY_ICONS[scenario.category] || '🎯'}</span>
                <h3 className="font-semibold text-slate-100 group-hover:text-sky-300 transition-colors text-sm">
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

            <p className="text-xs text-slate-400 mb-3 line-clamp-2">{scenario.description}</p>

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
            <div className="flex gap-3 text-[10px] text-slate-500">
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
        <span className="text-xs text-slate-400">Show archived scenarios</span>
      </div>
    </div>
  );
}
