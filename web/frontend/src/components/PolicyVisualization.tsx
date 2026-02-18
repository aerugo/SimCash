import { useState } from 'react';
import { PolicyTreeView } from './PolicyTreeView';

interface PolicyVisualizationProps {
  policy: Record<string, unknown>;
  className?: string;
  compact?: boolean;
}

const TREE_KEYS = ['payment_tree', 'bank_tree', 'strategic_collateral_tree', 'end_of_tick_collateral_tree'] as const;
const TREE_LABELS: Record<string, string> = {
  payment_tree: '💳 Payment Tree',
  bank_tree: '🏦 Bank Tree',
  strategic_collateral_tree: '🛡️ Strategic Collateral',
  end_of_tick_collateral_tree: '⏱️ End-of-Tick Collateral',
};

export function PolicyVisualization({ policy, className = '', compact = false }: PolicyVisualizationProps) {
  const availableTrees = TREE_KEYS.filter(k => policy[k] && typeof policy[k] === 'object');
  const [activeTree, setActiveTree] = useState<string>(availableTrees[0] || 'payment_tree');

  if (availableTrees.length === 0) {
    return (
      <div className={`text-slate-500 text-sm py-4 text-center ${className}`}>
        No decision trees found in policy
      </div>
    );
  }

  const params = policy.parameters as Record<string, unknown> | undefined;

  return (
    <div className={className}>
      {!compact && (
        <div className="mb-3">
          {policy.policy_id && (
            <div className="text-xs text-slate-500 font-mono mb-1">{String(policy.policy_id)}</div>
          )}
          {params?.initial_liquidity_fraction != null && (
            <div className="text-xs text-slate-400">
              Initial liquidity: <span className="text-sky-300 font-mono">{String(params.initial_liquidity_fraction)}</span>
            </div>
          )}
        </div>
      )}

      {/* Tree tabs */}
      {availableTrees.length > 1 && (
        <div className="flex gap-1 mb-3 overflow-x-auto">
          {availableTrees.map(key => (
            <button
              key={key}
              onClick={() => setActiveTree(key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                activeTree === key
                  ? 'bg-sky-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {TREE_LABELS[key] || key}
            </button>
          ))}
        </div>
      )}

      <PolicyTreeView
        tree={policy[activeTree] as Record<string, unknown>}
        title={availableTrees.length === 1 ? TREE_LABELS[activeTree] : undefined}
      />
    </div>
  );
}
