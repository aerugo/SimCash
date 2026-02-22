import { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import type { GameOptimizationResult, PolicyJson } from '../types';

// ── Markdown components — uses CSS variables for theme compat ────────

const mdComponents: Components = {
  h1: ({ children }) => <h3 className="text-sm font-semibold mt-3 mb-1.5" style={{ color: 'var(--text-primary)' }}>{children}</h3>,
  h2: ({ children }) => <h3 className="text-sm font-semibold mt-3 mb-1.5" style={{ color: 'var(--text-primary)' }}>{children}</h3>,
  h3: ({ children }) => <h4 className="text-xs font-semibold mt-2.5 mb-1" style={{ color: 'var(--text-secondary)' }}>{children}</h4>,
  p: ({ children }) => <p className="text-xs leading-relaxed mb-2" style={{ color: 'var(--text-secondary)' }}>{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-4 space-y-1 mb-2 text-xs" style={{ color: 'var(--text-secondary)' }}>{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-4 space-y-1 mb-2 text-xs" style={{ color: 'var(--text-secondary)' }}>{children}</ol>,
  li: ({ children }) => <li className="text-xs" style={{ color: 'var(--text-secondary)' }}>{children}</li>,
  strong: ({ children }) => <strong className="font-semibold" style={{ color: 'var(--text-primary)' }}>{children}</strong>,
  em: ({ children }) => <em style={{ color: 'var(--text-muted)' }}>{children}</em>,
  code: ({ className, children }) => {
    const isBlock = className?.includes('language-') || String(children).includes('\n');
    if (isBlock) {
      return (
        <pre className="rounded-md p-3 text-[11px] font-mono overflow-x-auto my-2 whitespace-pre leading-relaxed"
          style={{ background: 'var(--bg-inset)', border: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>
          <code>{children}</code>
        </pre>
      );
    }
    return (
      <code className="px-1.5 py-0.5 rounded text-[11px] font-mono"
        style={{ background: 'var(--bg-inset)', color: 'var(--text-accent)' }}>
        {children}
      </code>
    );
  },
  blockquote: ({ children }) => (
    <div className="border-l-2 pl-3 my-2 text-xs" style={{ borderColor: 'var(--border-color)', color: 'var(--text-muted)' }}>
      {children}
    </div>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="text-xs border-collapse w-full" style={{ color: 'var(--text-secondary)' }}>{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="text-left font-medium pb-1.5 pr-3 text-xs" style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border-color)' }}>{children}</th>,
  td: ({ children }) => <td className="py-1 pr-3 text-xs" style={{ color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-subtle)' }}>{children}</td>,
};

// ── Split LLM response into analysis + JSON ─────────────────────────

interface ParsedResponse {
  analysis: string;
  policyJson: string | null;
}

function splitResponse(raw: string): ParsedResponse {
  const fenceMatch = raw.match(/```(?:json)?\s*\n(\{[\s\S]*?\})\s*\n```/);
  if (fenceMatch) {
    const jsonStart = raw.indexOf(fenceMatch[0]);
    return {
      analysis: raw.slice(0, jsonStart).trim(),
      policyJson: fenceMatch[1],
    };
  }
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

function formatJson(raw: string): string {
  try { return JSON.stringify(JSON.parse(raw), null, 2); } catch { return raw; }
}

// ── Policy diff ─────────────────────────────────────────────────────

function policyDiffSummary(oldP?: PolicyJson, newP?: PolicyJson): string[] {
  if (!oldP || !newP) return [];
  const changes: string[] = [];
  const oldFrac = oldP.parameters?.initial_liquidity_fraction;
  const newFrac = newP.parameters?.initial_liquidity_fraction;
  if (oldFrac != null && newFrac != null && oldFrac !== newFrac) {
    changes.push(`Liquidity: ${(oldFrac * 100).toFixed(1)}% → ${(newFrac * 100).toFixed(1)}%`);
  }
  if (JSON.stringify(oldP.payment_tree ?? {}) !== JSON.stringify(newP.payment_tree ?? {})) changes.push('Payment tree modified');
  if (JSON.stringify(oldP.bank_tree ?? {}) !== JSON.stringify(newP.bank_tree ?? {})) changes.push('Bank tree modified');
  return changes;
}

// ── Main component ──────────────────────────────────────────────────

interface ReasoningExplorerProps {
  result: GameOptimizationResult;
  defaultExpanded?: 'analysis' | 'policy' | 'thinking' | null;
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

  // Show note for non-thinking models (no thinking content and no thinking tokens), but not for mock results
  const noThinkingAvailable = !hasThinking && (!result.usage?.thinking_tokens) && !result.mock;

  if (!hasRaw && !hasThinking && !noThinkingAvailable) return null;

  const toggle = (section: Section) => setExpanded(expanded === section ? null : section);

  return (
    <div className={`mt-2 space-y-2`}>
      {/* Note for models that don't expose thinking */}
      {noThinkingAvailable && !hasRaw && (
        <p className="text-xs italic" style={{ color: 'var(--text-muted)' }}>
          This model does not expose chain-of-thought reasoning tokens.
        </p>
      )}

      {/* Change summary chips */}
      {diffSummary.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {diffSummary.map((s, i) => (
            <span key={i} className="text-xs px-2 py-0.5 rounded-full font-medium"
              style={{ background: 'var(--bg-inset)', color: 'var(--text-accent)', border: '1px solid var(--border-color)' }}>
              {s}
            </span>
          ))}
        </div>
      )}

      {/* Section toggle buttons */}
      <div className="flex gap-2 flex-wrap">
        {hasRaw && parsed?.analysis && (
          <ToggleButton active={expanded === 'analysis'} onClick={() => toggle('analysis')} label={expanded === 'analysis' ? 'Hide Analysis' : 'Analysis'} />
        )}
        {hasPolicyJson && (
          <ToggleButton active={expanded === 'policy'} onClick={() => toggle('policy')} label={expanded === 'policy' ? 'Hide Policy JSON' : 'Policy JSON'} />
        )}
        {hasThinking && (
          <ToggleButton active={expanded === 'thinking'} onClick={() => toggle('thinking')} label={expanded === 'thinking' ? 'Hide Thinking' : 'Thinking'} />
        )}
        {noThinkingAvailable && hasRaw && (
          <span className="text-xs italic self-center" style={{ color: 'var(--text-muted)' }}>
            This model does not expose chain-of-thought reasoning tokens.
          </span>
        )}
      </div>

      {/* Analysis — markdown rendered */}
      {expanded === 'analysis' && parsed?.analysis && (
        <div className={`rounded-lg ${compact ? 'p-3' : 'p-4'} max-h-96 overflow-y-auto`}
          style={{ background: 'var(--bg-inset)', border: '1px solid var(--border-color)' }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
            {parsed.analysis}
          </ReactMarkdown>
        </div>
      )}

      {/* Policy JSON */}
      {expanded === 'policy' && (
        <div className={`rounded-lg ${compact ? 'p-3' : 'p-4'} max-h-80 overflow-y-auto`}
          style={{ background: 'var(--bg-inset)', border: '1px solid var(--border-color)' }}>
          <div className="text-[11px] font-medium mb-2" style={{ color: 'var(--text-muted)' }}>Proposed Policy</div>
          <pre className="text-[11px] whitespace-pre-wrap font-mono leading-relaxed"
            style={{ color: 'var(--text-secondary)' }}>
            {parsed?.policyJson
              ? formatJson(parsed.policyJson)
              : result.new_policy
                ? JSON.stringify(result.new_policy, null, 2)
                : 'No policy data'}
          </pre>
        </div>
      )}

      {/* Thinking */}
      {expanded === 'thinking' && result.thinking && (
        <div className={`rounded-lg ${compact ? 'p-3' : 'p-4'} max-h-80 overflow-y-auto`}
          style={{ background: 'var(--bg-inset)', border: '1px solid var(--border-color)' }}>
          <div className="text-[11px] font-medium mb-2" style={{ color: 'var(--text-muted)' }}>Internal Reasoning</div>
          <pre className="text-[11px] whitespace-pre-wrap font-mono leading-relaxed"
            style={{ color: 'var(--text-secondary)' }}>
            {result.thinking}
          </pre>
        </div>
      )}
    </div>
  );
}

// ── Clean toggle button ─────────────────────────────────────────────

function ToggleButton({ active, onClick, label }: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className="text-xs px-3 py-1 rounded-md font-medium transition-all"
      style={{
        background: active ? 'var(--btn-primary-bg)' : 'var(--bg-inset)',
        color: active ? '#fff' : 'var(--text-muted)',
        border: `1px solid ${active ? 'var(--btn-primary-bg)' : 'var(--border-color)'}`,
      }}
    >
      {label}
    </button>
  );
}
