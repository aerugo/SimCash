import { useEffect, useState } from 'react';
import type { LibraryPolicy, LibraryPolicyDetail } from '../types';
import { getPolicyLibrary, getPolicyLibraryDetail } from '../api';
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

export function PolicyLibraryView({ onSelectPolicy }: Props) {
  const [policies, setPolicies] = useState<LibraryPolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPolicy, setSelectedPolicy] = useState<LibraryPolicyDetail | null>(null);
  const [, setDetailLoading] = useState(false);
  const [filterComplexity, setFilterComplexity] = useState<string | null>(null);

  useEffect(() => {
    getPolicyLibrary()
      .then(setPolicies)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = filterComplexity
    ? policies.filter(p => p.complexity === filterComplexity)
    : policies;

  const handleSelect = async (id: string) => {
    setDetailLoading(true);
    try {
      const detail = await getPolicyLibraryDetail(id);
      setSelectedPolicy(detail);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDetailLoading(false);
    }
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

  // Detail view
  if (selectedPolicy) {
    return (
      <div>
        <button
          onClick={() => setSelectedPolicy(null)}
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

          {/* Select button */}
          {onSelectPolicy && (
            <button
              onClick={() => onSelectPolicy(selectedPolicy.id, selectedPolicy.raw)}
              className="w-full py-3 rounded-lg bg-sky-600 hover:bg-sky-500 text-sm font-semibold transition-colors"
            >
              ✅ Use This Policy
            </button>
          )}
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
          <button
            key={policy.id}
            onClick={() => handleSelect(policy.id)}
            className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 text-left hover:border-sky-500/50 transition-colors group"
          >
            <div className="flex items-start justify-between mb-2">
              <h3 className="font-semibold text-slate-100 group-hover:text-sky-300 transition-colors text-sm">
                {policy.name}
              </h3>
              <span className={`text-[10px] px-1.5 py-0.5 rounded border ${COMPLEXITY_COLORS[policy.complexity]}`}>
                {policy.complexity}
              </span>
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
        ))}
      </div>
    </div>
  );
}
