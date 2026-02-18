import type { PolicyJson } from '../types';

/**
 * Compare two policy JSON trees and show what changed.
 * Designed for the "full" constraint preset where the LLM optimizes
 * decision trees, not just the liquidity fraction.
 */

interface PolicyDiffViewProps {
  oldPolicy?: PolicyJson;
  newPolicy?: PolicyJson;
  compact?: boolean;
}

interface DiffEntry {
  path: string;
  label: string;
  oldValue: string;
  newValue: string;
  type: 'changed' | 'added' | 'removed';
}

function flattenTree(tree: Record<string, unknown>, prefix = ''): Record<string, string> {
  const result: Record<string, string> = {};
  if (!tree || typeof tree !== 'object') return result;

  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      Object.assign(result, flattenTree(value as Record<string, unknown>, path));
    } else {
      result[path] = JSON.stringify(value);
    }
  }
  return result;
}

function computeDiffs(oldPolicy?: PolicyJson, newPolicy?: PolicyJson): DiffEntry[] {
  if (!oldPolicy || !newPolicy) return [];

  const diffs: DiffEntry[] = [];

  // Compare parameters
  const oldParams = oldPolicy.parameters || {};
  const newParams = newPolicy.parameters || {};
  for (const key of new Set([...Object.keys(oldParams), ...Object.keys(newParams)])) {
    const oldVal = JSON.stringify(oldParams[key]);
    const newVal = JSON.stringify(newParams[key]);
    if (oldVal !== newVal) {
      diffs.push({
        path: `parameters.${key}`,
        label: key.replace(/_/g, ' '),
        oldValue: oldParams[key] != null ? String(oldParams[key]) : '—',
        newValue: newParams[key] != null ? String(newParams[key]) : '—',
        type: oldParams[key] == null ? 'added' : newParams[key] == null ? 'removed' : 'changed',
      });
    }
  }

  // Compare payment_tree
  const oldPayTree = flattenTree(oldPolicy.payment_tree as Record<string, unknown> || {});
  const newPayTree = flattenTree(newPolicy.payment_tree as Record<string, unknown> || {});
  const payTreeChanged = JSON.stringify(oldPolicy.payment_tree) !== JSON.stringify(newPolicy.payment_tree);
  if (payTreeChanged) {
    // Summarize tree changes
    const oldActions = extractActions(oldPolicy.payment_tree as Record<string, unknown>);
    const newActions = extractActions(newPolicy.payment_tree as Record<string, unknown>);
    const oldConditions = extractConditions(oldPolicy.payment_tree as Record<string, unknown>);
    const newConditions = extractConditions(newPolicy.payment_tree as Record<string, unknown>);

    if (oldActions.join(',') !== newActions.join(',')) {
      diffs.push({
        path: 'payment_tree.actions',
        label: 'Payment actions',
        oldValue: oldActions.join(' → ') || 'Release',
        newValue: newActions.join(' → ') || 'Release',
        type: 'changed',
      });
    }
    if (oldConditions.join(',') !== newConditions.join(',')) {
      diffs.push({
        path: 'payment_tree.conditions',
        label: 'Payment conditions',
        oldValue: oldConditions.join(', ') || 'none',
        newValue: newConditions.join(', ') || 'none',
        type: 'changed',
      });
    }
    // If structure changed but not captured above
    if (diffs.filter(d => d.path.startsWith('payment_tree')).length === 0) {
      const oldDepth = treeDepth(oldPolicy.payment_tree as Record<string, unknown>);
      const newDepth = treeDepth(newPolicy.payment_tree as Record<string, unknown>);
      diffs.push({
        path: 'payment_tree',
        label: 'Payment tree structure',
        oldValue: `depth ${oldDepth}, ${Object.keys(oldPayTree).length} nodes`,
        newValue: `depth ${newDepth}, ${Object.keys(newPayTree).length} nodes`,
        type: 'changed',
      });
    }
  }

  // Compare bank_tree
  const bankTreeChanged = JSON.stringify(oldPolicy.bank_tree) !== JSON.stringify(newPolicy.bank_tree);
  if (bankTreeChanged) {
    const oldActions = extractActions(oldPolicy.bank_tree as Record<string, unknown>);
    const newActions = extractActions(newPolicy.bank_tree as Record<string, unknown>);

    diffs.push({
      path: 'bank_tree',
      label: 'Bank-level actions',
      oldValue: oldActions.join(' → ') || 'NoAction',
      newValue: newActions.join(' → ') || 'NoAction',
      type: 'changed',
    });
  }

  return diffs;
}

function extractActions(tree: Record<string, unknown> | undefined): string[] {
  if (!tree) return [];
  const actions: string[] = [];
  if (tree.action) actions.push(String(tree.action));
  if (tree.true_branch) actions.push(...extractActions(tree.true_branch as Record<string, unknown>));
  if (tree.false_branch) actions.push(...extractActions(tree.false_branch as Record<string, unknown>));
  return actions;
}

function extractConditions(tree: Record<string, unknown> | undefined): string[] {
  if (!tree) return [];
  const conditions: string[] = [];
  if (tree.field && tree.operator) {
    conditions.push(`${tree.field} ${tree.operator} ${tree.value ?? ''}`);
  }
  if (tree.condition && typeof tree.condition === 'object') {
    conditions.push(...extractConditions(tree.condition as Record<string, unknown>));
  }
  if (tree.true_branch) conditions.push(...extractConditions(tree.true_branch as Record<string, unknown>));
  if (tree.false_branch) conditions.push(...extractConditions(tree.false_branch as Record<string, unknown>));
  return conditions;
}

function treeDepth(tree: Record<string, unknown> | undefined): number {
  if (!tree) return 0;
  const trueD = tree.true_branch ? treeDepth(tree.true_branch as Record<string, unknown>) : 0;
  const falseD = tree.false_branch ? treeDepth(tree.false_branch as Record<string, unknown>) : 0;
  return 1 + Math.max(trueD, falseD);
}

export function PolicyDiffView({ oldPolicy, newPolicy, compact }: PolicyDiffViewProps) {
  const diffs = computeDiffs(oldPolicy, newPolicy);

  if (diffs.length === 0) {
    return <span className="text-slate-500 text-xs italic">No policy changes</span>;
  }

  if (compact) {
    return (
      <span className="text-xs">
        {diffs.map((d, i) => (
          <span key={d.path}>
            {i > 0 && ' · '}
            <span className="text-slate-400">{d.label}:</span>{' '}
            <span className="text-red-400 line-through">{d.oldValue}</span>{' → '}
            <span className="text-green-400">{d.newValue}</span>
          </span>
        ))}
      </span>
    );
  }

  return (
    <div className="space-y-1 text-xs">
      {diffs.map((d) => (
        <div key={d.path} className="flex items-start gap-2">
          <span className={`shrink-0 w-1.5 h-1.5 rounded-full mt-1.5 ${
            d.type === 'changed' ? 'bg-amber-400' :
            d.type === 'added' ? 'bg-green-400' : 'bg-red-400'
          }`} />
          <div>
            <span className="text-slate-300 font-medium">{d.label}</span>
            <div className="text-slate-500">
              <span className="text-red-400/70">{d.oldValue}</span>
              <span className="text-slate-600 mx-1">→</span>
              <span className="text-green-400/70">{d.newValue}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Summary line for the policy change (e.g., "3 changes: fraction, payment actions, bank actions") */
export function PolicyChangeSummary({ oldPolicy, newPolicy }: { oldPolicy?: PolicyJson; newPolicy?: PolicyJson }) {
  const diffs = computeDiffs(oldPolicy, newPolicy);
  if (diffs.length === 0) return <span className="text-slate-500">No changes</span>;

  return (
    <span className="text-xs text-slate-400">
      {diffs.length} change{diffs.length !== 1 ? 's' : ''}: {diffs.map(d => d.label).join(', ')}
    </span>
  );
}
