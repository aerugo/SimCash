import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { LibraryPolicy, LibraryPolicyDetail } from '../types';
import { getPolicyLibrary, getPolicyLibraryDetail, listCustomPolicies, deleteCustomPolicy, saveCustomPolicyApi, type CustomPolicy } from '../api';
import { useAuthInfo } from '../AuthInfoContext';
import { PolicyVisualization } from '../components/PolicyVisualization';

const COMPLEXITY_COLORS: Record<string, string> = {
  simple: 'text-green-400 bg-green-400/10 border-green-400/30',
  moderate: 'text-amber-400 bg-amber-400/10 border-amber-400/30',
  complex: 'text-red-400 bg-red-400/10 border-red-400/30',
};

const ACTION_COLORS: Record<string, string> = {
  Release: 'bg-green-500/20 text-green-300',
  Hold: 'bg-red-500/20 text-red-300',
  Split: 'bg-purple-500/20 text-purple-300',
  Delay: 'bg-amber-500/20 text-amber-300',
  NoAction: 'bg-slate-500/20 text-slate-400',
};

interface Props {
  onSelectPolicy?: (policyId: string, policyJson: Record<string, unknown>) => void;
}

export function PolicyLibraryView({ onSelectPolicy }: Props = {}) {
  const { policyId: urlPolicyId } = useParams<{ policyId: string }>();
  const navigate = useNavigate();
  const { isGuest } = useAuthInfo();
  const [copying, setCopying] = useState(false);
  const [customPolicies, setCustomPolicies] = useState<CustomPolicy[]>([]);
  const [showMyPolicies, setShowMyPolicies] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [policies, setPolicies] = useState<LibraryPolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPolicy, setSelectedPolicy] = useState<LibraryPolicyDetail | null>(null);
  const [, setDetailLoading] = useState(false);
  const [filterComplexity, setFilterComplexity] = useState<string | null>(null);
  const [compareMode, setCompareMode] = useState(false);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [compareDetails, setCompareDetails] = useState<LibraryPolicyDetail[]>([]);
  const [compareLoading, setCompareLoading] = useState(false);
  const [showArchived, setShowArchived] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getPolicyLibrary(showArchived),
      listCustomPolicies().catch(() => [] as CustomPolicy[]),
    ])
      .then(([p, cp]) => { setPolicies(p); setCustomPolicies(cp); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [showArchived]);

  const handleDeleteCustom = async (id: string) => {
    try {
      await deleteCustomPolicy(id);
      setCustomPolicies(prev => prev.filter(p => p.id !== id));
      setDeleteConfirm(null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const handleCopyPolicy = async () => {
    if (!selectedPolicy) return;
    setCopying(true);
    try {
      const saved = await saveCustomPolicyApi({
        name: `Copy of ${selectedPolicy.name}`,
        description: selectedPolicy.description,
        json_string: JSON.stringify(selectedPolicy.raw),
      });
      navigate(`/create?editPolicy=${saved.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCopying(false);
    }
  };

  // Auto-open policy from URL param
  useEffect(() => {
    if (urlPolicyId && !selectedPolicy && policies.length > 0) {
      handleSelect(urlPolicyId);
    }
  }, [urlPolicyId, policies.length]);

  const filtered = filterComplexity
    ? policies.filter(p => p.complexity === filterComplexity)
    : policies;

  const handleSelect = async (id: string) => {
    setDetailLoading(true);
    try {
      const detail = await getPolicyLibraryDetail(id);
      setSelectedPolicy(detail);
      if (!urlPolicyId || urlPolicyId !== id) {
        navigate(`/library/policies/${id}`, { replace: true });
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDetailLoading(false);
    }
  };

  const toggleCompare = (id: string) => {
    setCompareIds(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id);
      if (prev.length >= 2) return [prev[1], id];
      return [...prev, id];
    });
  };

  // Load compare details when 2 selected
  useEffect(() => {
    if (compareIds.length !== 2) { setCompareDetails([]); return; }
    let cancelled = false;
    setCompareLoading(true);
    Promise.all(compareIds.map(id => getPolicyLibraryDetail(id)))
      .then(details => { if (!cancelled) setCompareDetails(details); })
      .catch(e => { if (!cancelled) setError((e as Error).message); })
      .finally(() => { if (!cancelled) setCompareLoading(false); });
    return () => { cancelled = true; };
  }, [compareIds]);

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

  // Compare view
  if (compareMode && compareDetails.length === 2) {
    return (
      <div>
        <button
          onClick={() => { setCompareMode(false); setCompareIds([]); setCompareDetails([]); }}
          className="mb-4 text-sm text-slate-400 hover:text-slate-200 flex items-center gap-1"
        >
          ← Back to Policies
        </button>
        <h2 className="text-xl font-bold text-slate-100 mb-4">🔍 Policy Comparison</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {compareDetails.map(pol => (
            <div key={pol.id} className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
              <h3 className="text-lg font-bold text-slate-100 mb-1">{pol.name}</h3>
              <div className="flex items-center gap-2 mb-3">
                <span className={`text-xs px-2 py-0.5 rounded border ${COMPLEXITY_COLORS[pol.complexity]}`}>
                  {pol.complexity}
                </span>
                <span className="text-xs text-slate-500">v{pol.version}</span>
                <span className="text-xs text-slate-500">{pol.total_nodes} nodes</span>
              </div>
              <p className="text-xs text-slate-400 mb-3">{pol.description}</p>

              {/* Key parameter */}
              <div className="bg-slate-900/50 rounded-lg p-3 mb-3">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">initial_liquidity_fraction</span>
                  <span className="font-mono text-sky-300 font-bold">
                    {pol.parameters.initial_liquidity_fraction !== undefined
                      ? String(pol.parameters.initial_liquidity_fraction)
                      : '—'}
                  </span>
                </div>
                {Object.entries(pol.parameters)
                  .filter(([k]) => k !== 'initial_liquidity_fraction')
                  .map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs mt-1">
                      <span className="text-slate-500">{k}</span>
                      <span className="text-slate-300 font-mono">{String(v)}</span>
                    </div>
                  ))}
              </div>

              {/* Actions */}
              <div className="flex flex-wrap gap-1 mb-3">
                {pol.actions_used.map(action => (
                  <span key={action} className={`text-[10px] px-1.5 py-0.5 rounded ${ACTION_COLORS[action] || 'bg-slate-700 text-slate-400'}`}>
                    {action}
                  </span>
                ))}
              </div>

              {/* Decision tree */}
              <div>
                <h4 className="text-xs font-semibold text-slate-400 mb-2">Decision Tree</h4>
                <PolicyVisualization policy={pol.raw} compact />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Detail view
  if (selectedPolicy) {
    return (
      <div>
        <button
          onClick={() => { setSelectedPolicy(null); navigate('/library/policies'); }}
          className="mb-4 text-sm text-slate-400 hover:text-slate-200 flex items-center gap-1"
        >
          ← Back to Policies
        </button>

        <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-xl font-bold text-slate-100 mb-1">{selectedPolicy.name}</h2>
              <div className="flex items-center gap-2">
                <span className={`text-xs px-2 py-0.5 rounded border ${COMPLEXITY_COLORS[selectedPolicy.complexity]}`}>
                  {selectedPolicy.complexity}
                </span>
                <span className="text-xs text-slate-500">v{selectedPolicy.version}</span>
                <span className="text-xs text-slate-500">{selectedPolicy.total_nodes} nodes</span>
              </div>
            </div>
          </div>

          <p className="text-sm text-slate-300 mb-4">{selectedPolicy.description}</p>

          {/* Trees used */}
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-slate-400 mb-2">Decision Trees</h3>
            <div className="flex gap-2">
              {['payment_tree', 'bank_tree', 'strategic_collateral_tree', 'end_of_tick_collateral_tree'].map(tree => (
                <span
                  key={tree}
                  className={`text-xs px-2 py-1 rounded ${
                    selectedPolicy.trees_used.includes(tree)
                      ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                      : 'bg-slate-800 text-slate-600 border border-slate-700'
                  }`}
                >
                  {tree.replace('_tree', '').replace('_', ' ')}
                </span>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-slate-400 mb-2">Actions Used</h3>
            <div className="flex flex-wrap gap-1.5">
              {selectedPolicy.actions_used.map(action => (
                <span key={action} className={`text-xs px-2 py-0.5 rounded ${ACTION_COLORS[action] || 'bg-slate-700 text-slate-300'}`}>
                  {action}
                </span>
              ))}
            </div>
          </div>

          {/* Parameters */}
          {Object.keys(selectedPolicy.parameters).length > 0 && (
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-slate-400 mb-2">Parameters</h3>
              <div className="bg-slate-900/50 rounded-lg p-3 grid grid-cols-2 gap-2 text-xs">
                {Object.entries(selectedPolicy.parameters).map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-slate-500">{k}</span>
                    <span className="text-slate-300 font-mono">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Context Fields */}
          {selectedPolicy.context_fields_used.length > 0 && (
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-slate-400 mb-2">Context Fields Referenced</h3>
              <div className="flex flex-wrap gap-1.5">
                {selectedPolicy.context_fields_used.map(field => (
                  <span key={field} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-400 font-mono">
                    {field}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Decision Tree Visualization */}
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-slate-400 mb-2">Decision Tree Visualization</h3>
            <PolicyVisualization policy={selectedPolicy.raw} compact />
          </div>

          {/* Raw JSON */}
          <details className="mb-4">
            <summary className="text-sm text-slate-400 cursor-pointer hover:text-slate-200">
              View Raw JSON
            </summary>
            <pre className="mt-2 bg-slate-900 rounded-lg p-4 text-xs text-slate-300 overflow-auto max-h-96 font-mono">
              {JSON.stringify(selectedPolicy.raw, null, 2)}
            </pre>
          </details>

          {/* Action buttons */}
          <div className="flex gap-3">
            {onSelectPolicy && (
              <button
                onClick={() => onSelectPolicy(selectedPolicy.id, selectedPolicy.raw)}
                className="flex-1 py-3 rounded-lg bg-sky-600 hover:bg-sky-500 text-sm font-semibold transition-colors"
              >
                ✅ Use This Policy
              </button>
            )}
            {!isGuest && (
              <button
                onClick={handleCopyPolicy}
                disabled={copying}
                className={`${onSelectPolicy ? '' : 'flex-1 '}px-4 py-3 rounded-lg text-sm font-medium transition-colors disabled:opacity-50`}
                style={{ border: '1px solid var(--border-color)', color: 'var(--text-secondary)', backgroundColor: 'var(--bg-inset)' }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgb(14 165 233 / 0.5)'; e.currentTarget.style.color = 'rgb(56 189 248)'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border-color)'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
              >
                {copying ? '📋 Copying…' : '📋 Copy & Edit'}
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // List view
  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-100 mb-1">🧠 Policy Library</h2>
        <p className="text-sm text-slate-400">
          {policies.length} built-in policies — from simple FIFO to sophisticated adaptive strategies.
        </p>
      </div>

      {/* My Policies tab */}
      {customPolicies.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          <button
            onClick={() => setShowMyPolicies(false)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              !showMyPolicies ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            🧠 Library
          </button>
          <button
            onClick={() => setShowMyPolicies(true)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              showMyPolicies ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            📝 My Policies ({customPolicies.length})
          </button>
        </div>
      )}

      {/* My Policies grid */}
      {showMyPolicies && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {customPolicies.map(cp => (
            <div
              key={cp.id}
              className="rounded-xl border p-5 text-left transition-colors group"
              style={{ backgroundColor: 'var(--card-bg)', borderColor: 'var(--border-color)' }}
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
                  📝 {cp.name}
                </h3>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => navigate(`/create?editPolicy=${cp.id}`)}
                    className="p-1 rounded hover:bg-sky-500/20 text-slate-400 hover:text-sky-300 transition-colors"
                    title="Edit"
                  >✏️</button>
                  <button
                    onClick={() => setDeleteConfirm(cp.id)}
                    className="p-1 rounded hover:bg-red-500/20 text-slate-400 hover:text-red-300 transition-colors"
                    title="Delete"
                  >🗑️</button>
                </div>
              </div>
              <p className="text-xs mb-3 line-clamp-2" style={{ color: 'var(--text-secondary)' }}>
                {cp.description || 'No description'}
              </p>
              <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ backgroundColor: 'var(--bg-inset)', color: 'var(--text-secondary)' }}>
                Custom
              </span>

              {deleteConfirm === cp.id && (
                <div className="mt-3 p-2 rounded-lg border" style={{ backgroundColor: 'var(--bg-inset)', borderColor: 'var(--border-color)' }}>
                  <p className="text-xs mb-2" style={{ color: 'var(--text-primary)' }}>Delete this policy?</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDeleteCustom(cp.id)}
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

      {!showMyPolicies && <>
      {/* Compare mode toggle + status */}
      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={() => { setCompareMode(!compareMode); if (compareMode) { setCompareIds([]); setCompareDetails([]); } }}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            compareMode ? 'bg-violet-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700'
          }`}
        >
          {compareMode ? '✕ Exit Compare' : '🔍 Compare'}
        </button>
        {compareMode && (
          <>
            <span className="text-xs text-slate-500">
              {compareIds.length}/2 selected
            </span>
            {compareIds.length === 2 && (
              <button
                onClick={() => {/* compareDetails will load automatically */}}
                disabled={compareLoading}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-sky-600 hover:bg-sky-500 text-white disabled:opacity-40"
              >
                {compareLoading ? 'Loading…' : '→ View Comparison'}
              </button>
            )}
          </>
        )}
      </div>

      {/* Complexity filter */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setFilterComplexity(null)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            filterComplexity === null ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
          }`}
        >
          All ({policies.length})
        </button>
        {['simple', 'moderate', 'complex'].map(c => (
          <button
            key={c}
            onClick={() => setFilterComplexity(c)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filterComplexity === c ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            {c} ({policies.filter(p => p.complexity === c).length})
          </button>
        ))}
      </div>

      {/* Policy cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map(policy => (
          <div
            key={policy.id}
            className={`bg-slate-800/50 rounded-xl border p-5 text-left transition-colors group relative ${
              compareMode && compareIds.includes(policy.id)
                ? 'border-violet-500/70'
                : 'border-slate-700 hover:border-sky-500/50'
            } ${policy.visible === false ? 'opacity-50' : ''}`}
          >
            {compareMode && (
              <button
                onClick={() => toggleCompare(policy.id)}
                className={`absolute top-3 right-3 w-5 h-5 rounded border text-xs flex items-center justify-center transition-colors ${
                  compareIds.includes(policy.id)
                    ? 'bg-violet-600 border-violet-500 text-white'
                    : 'bg-slate-900 border-slate-600 text-slate-500 hover:border-slate-400'
                }`}
              >
                {compareIds.includes(policy.id) ? '✓' : ''}
              </button>
            )}
            <button
              onClick={() => !compareMode && handleSelect(policy.id)}
              className="w-full text-left"
              disabled={compareMode}
            >
            <div className="flex items-start justify-between mb-2">
              <h3 className="font-semibold text-slate-100 group-hover:text-sky-300 transition-colors text-sm">
                {policy.name}
              </h3>
              <div className="flex items-center gap-1">
                {policy.visible === false && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-600/50 text-slate-400 border border-slate-600">
                    Archived
                  </span>
                )}
                <span className={`text-[10px] px-1.5 py-0.5 rounded border ${COMPLEXITY_COLORS[policy.complexity]}`}>
                  {policy.complexity}
                </span>
              </div>
            </div>

            <p className="text-xs text-slate-400 mb-3 line-clamp-2">{policy.description}</p>

            {/* Actions */}
            <div className="flex flex-wrap gap-1 mb-3">
              {policy.actions_used.slice(0, 4).map(action => (
                <span key={action} className={`text-[10px] px-1.5 py-0.5 rounded ${ACTION_COLORS[action] || 'bg-slate-700 text-slate-400'}`}>
                  {action}
                </span>
              ))}
            </div>

            {/* Stats */}
            <div className="flex gap-3 text-[10px] text-slate-500">
              <span>{policy.total_nodes} nodes</span>
              <span>·</span>
              <span>{policy.trees_used.length} tree{policy.trees_used.length !== 1 ? 's' : ''}</span>
              <span>·</span>
              <span>v{policy.version}</span>
            </div>
          </button>
          </div>
        ))}
      </div>

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
        <span className="text-xs text-slate-400">Show archived policies</span>
      </div>
      </>}
    </div>
  );
}
