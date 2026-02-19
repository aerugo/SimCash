import { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import type { GameOptimizationResult, PolicyJson } from '../types';

// ── Markdown components (compact, reasoning-optimized) ──────────────

const mdComponents: Components = {
  h1: ({ children }) => <h3 className="text-sm font-semibold text-slate-200 mt-3 mb-1">{children}</h3>,
  h2: ({ children }) => <h3 className="text-sm font-semibold text-slate-200 mt-3 mb-1">{children}</h3>,
  h3: ({ children }) => <h4 className="text-xs font-semibold text-slate-300 mt-2 mb-1">{children}</h4>,
  p: ({ children }) => <p className="text-xs text-slate-300 leading-relaxed mb-2">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-4 space-y-0.5 mb-2 text-xs text-slate-300">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-4 space-y-0.5 mb-2 text-xs text-slate-300">{children}</ol>,
  li: ({ children }) => <li className="text-xs text-slate-300">{children}</li>,
  strong: ({ children }) => <strong className="text-slate-200 font-semibold">{children}</strong>,
  em: ({ children }) => <em className="text-slate-400">{children}</em>,
  code: ({ className, children }) => {
    const isBlock = className?.includes('language-') || String(children).includes('\n');
    if (isBlock) {
      return (
        <pre className="bg-slate-900 border border-slate-700 rounded p-2 text-[10px] font-mono text-slate-300 overflow-x-auto my-2 whitespace-pre">
          <code>{children}</code>
        </pre>
      );
    }
    return <code className="text-sky-400 bg-slate-800 px-1 py-0.5 rounded text-[10px]">{children}</code>;
  },
  blockquote: ({ children }) => (
    <div className="border-l-2 border-slate-600 pl-3 my-2 text-xs text-slate-400">{children}</div>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="text-[10px] text-slate-300 border-collapse w-full">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="text-left text-slate-400 font-medium border-b border-slate-700 pb-1 pr-3">{children}</th>,
  td: ({ children }) => <td className="border-b border-slate-800 py-0.5 pr-3 text-slate-300">{children}</td>,
};

// ── Split LLM response into analysis + JSON ─────────────────────────

interface ParsedResponse {
  analysis: string;
  policyJson: string | null;
}

function splitResponse(raw: string): ParsedResponse {
  // Try to find JSON block in fenced code block
  const fenceMatch = raw.match(/```(?:json)?\s*\n(\{[\s\S]*?\})\s*\n```/);
  if (fenceMatch) {
    const jsonStart = raw.indexOf(fenceMatch[0]);
    return {
      analysis: raw.slice(0, jsonStart).trim(),
      policyJson: fenceMatch[1],
    };
  }

  // Try to find a bare JSON block starting with {"version" or {"policy_id"
  const jsonPattern = /\n(\{"(?:version|policy_id|parameters)"\s*:[\s\S]*\})\s*$/;
  const bareMatch = raw.match(jsonPattern);
  if (bareMatch) {
    const jsonStart = raw.lastIndexOf(bareMatch[1]);
    return {
      analysis: raw.slice(0, jsonStart).trim(),
      policyJson: bareMatch[1],
    };
  }

  return { analysis: raw, policyJson: null };
}

// ── Format JSON for display ─────────────────────────────────────────

function formatJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

// ── Policy diff summary ─────────────────────────────────────────────

function policyDiffSummary(oldP?: PolicyJson, newP?: PolicyJson): string[] {
  if (!oldP || !newP) return [];
  const changes: string[] = [];

  const oldFrac = oldP.parameters?.initial_liquidity_fraction;
  const newFrac = newP.parameters?.initial_liquidity_fraction;
  if (oldFrac != null && newFrac != null && oldFrac !== newFrac) {
    const delta = ((newFrac - oldFrac) * 100).toFixed(1);
    changes.push(`Liquidity: ${(oldFrac * 100).toFixed(1)}% → ${(newFrac * 100).toFixed(1)}% (${Number(delta) > 0 ? '+' : ''}${delta}pp)`);
  }

  // Tree structure changes
  const oldPayTree = JSON.stringify(oldP.payment_tree ?? {});
  const newPayTree = JSON.stringify(newP.payment_tree ?? {});
  if (oldPayTree !== newPayTree) changes.push('Payment tree modified');

  const oldBankTree = JSON.stringify(oldP.bank_tree ?? {});
  const newBankTree = JSON.stringify(newP.bank_tree ?? {});
  if (oldBankTree !== newBankTree) changes.push('Bank tree modified');

  return changes;
}

// ── Main component ──────────────────────────────────────────────────

interface ReasoningExplorerProps {
  result: GameOptimizationResult;
  /** Which section to expand by default (null = collapsed) */
  defaultExpanded?: 'analysis' | 'policy' | 'thinking' | null;
  /** Compact mode — less padding, for use inside iteration lists */
  compact?: boolean;
}

type Section = 'analysis' | 'policy' | 'thinking';

export function ReasoningExplorer({ result, defaultExpanded = null, compact = false }: ReasoningExplorerProps) {
  const [expanded, setExpanded] = useState<Section | null>(defaultExpanded);

  const hasRaw = !!result.raw_response;
  const hasThinking = !!result.thinking;
  const parsed = useMemo(() => hasRaw ? splitResponse(result.raw_response!) : null, [result.raw_response, hasRaw]);
  const hasPolicyJson = !!(parsed?.policyJson || result.new_policy);
  const diffSummary = useMemo(() => policyDiffSummary(result.old_policy, result.new_policy), [result.old_policy, result.new_policy]);

  // Nothing to show
  if (!hasRaw && !hasThinking) return null;

  const toggle = (section: Section) => setExpanded(expanded === section ? null : section);

  const pad = compact ? 'p-2' : 'p-3';

  return (
    <div className={`mt-2 space-y-1.5`}>
      {/* Change summary chips */}
      {diffSummary.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {diffSummary.map((s, i) => (
            <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
              {s}
            </span>
          ))}
        </div>
      )}

      {/* Section toggle buttons */}
      <div className="flex gap-1.5 flex-wrap">
        {hasRaw && parsed?.analysis && (
          <SectionButton
            active={expanded === 'analysis'}
            onClick={() => toggle('analysis')}
            icon="📝"
            label="Analysis"
            color="sky"
          />
        )}
        {hasPolicyJson && (
          <SectionButton
            active={expanded === 'policy'}
            onClick={() => toggle('policy')}
            icon="🧬"
            label="Policy"
            color="emerald"
          />
        )}
        {hasThinking && (
          <SectionButton
            active={expanded === 'thinking'}
            onClick={() => toggle('thinking')}
            icon="🧠"
            label="Thinking"
            color="violet"
          />
        )}
      </div>

      {/* Analysis section — markdown rendered */}
      {expanded === 'analysis' && parsed?.analysis && (
        <div className={`bg-slate-950/50 border border-slate-600/30 rounded-lg ${pad} max-h-80 overflow-y-auto`}>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
            {parsed.analysis}
          </ReactMarkdown>
        </div>
      )}

      {/* Policy JSON section */}
      {expanded === 'policy' && (
        <div className={`bg-slate-950/50 border border-emerald-500/20 rounded-lg ${pad} max-h-64 overflow-y-auto`}>
          <div className="text-[10px] text-emerald-400/60 mb-1 font-medium">Proposed Policy JSON</div>
          <pre className="text-[10px] text-emerald-200/80 whitespace-pre-wrap font-mono leading-relaxed">
            {parsed?.policyJson
              ? formatJson(parsed.policyJson)
              : result.new_policy
                ? JSON.stringify(result.new_policy, null, 2)
                : 'No policy data'}
          </pre>
        </div>
      )}

      {/* Thinking section */}
      {expanded === 'thinking' && result.thinking && (
        <div className={`bg-violet-950/30 border border-violet-500/20 rounded-lg ${pad} max-h-64 overflow-y-auto`}>
          <div className="text-[10px] text-violet-400/60 mb-1 font-medium">Internal Reasoning</div>
          <pre className="text-[10px] text-violet-200/80 whitespace-pre-wrap font-mono leading-relaxed">
            {result.thinking}
          </pre>
        </div>
      )}
    </div>
  );
}

// ── Section toggle button ───────────────────────────────────────────

function SectionButton({ active, onClick, icon, label, color }: {
  active: boolean;
  onClick: () => void;
  icon: string;
  label: string;
  color: 'sky' | 'emerald' | 'violet';
}) {
  const colors = {
    sky: active
      ? 'bg-sky-500/20 text-sky-300 border-sky-500/30'
      : 'bg-slate-800 text-slate-500 hover:text-slate-400 border-slate-700',
    emerald: active
      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
      : 'bg-slate-800 text-slate-500 hover:text-slate-400 border-slate-700',
    violet: active
      ? 'bg-violet-500/20 text-violet-300 border-violet-500/30'
      : 'bg-slate-800 text-slate-500 hover:text-slate-400 border-slate-700',
  };

  return (
    <button
      onClick={onClick}
      className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${colors[color]}`}
    >
      {icon} {active ? 'Hide' : ''} {label}
    </button>
  );
}
