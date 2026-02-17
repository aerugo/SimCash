import { useState, useEffect } from 'react';
import type { AgentReasoning } from '../types';

interface Props {
  reasoning: Record<string, AgentReasoning[]>;
  compact?: boolean;
  onNavigateToAgents?: () => void;
}

function TypewriterText({ text, speed = 15 }: { text: string; speed?: number }) {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);

  useEffect(() => {
    setDisplayed('');
    setDone(false);
    let i = 0;
    const interval = setInterval(() => {
      i++;
      if (i >= text.length) {
        setDisplayed(text);
        setDone(true);
        clearInterval(interval);
      } else {
        setDisplayed(text.slice(0, i));
      }
    }, speed);
    return () => clearInterval(interval);
  }, [text, speed]);

  return (
    <span>
      {displayed}
      {!done && <span className="animate-pulse text-sky-400">▌</span>}
    </span>
  );
}

function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-2 text-sky-400">
      <div className="flex gap-1">
        <div className="w-2 h-2 rounded-full bg-sky-400 animate-bounce" style={{ animationDelay: '0ms' }} />
        <div className="w-2 h-2 rounded-full bg-sky-400 animate-bounce" style={{ animationDelay: '150ms' }} />
        <div className="w-2 h-2 rounded-full bg-sky-400 animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
      <span className="text-sm font-medium">Thinking...</span>
    </div>
  );
}

function ReasoningCard({ trace, isLatest }: { trace: AgentReasoning; isLatest: boolean }) {
  const [expanded, setExpanded] = useState(isLatest);
  const isThinking = trace.phase === 'thinking';
  const isLiquidity = trace.decision_type === 'liquidity_allocation';

  const borderColor = isThinking ? 'border-sky-500/50' : 'border-emerald-500/50';
  const glowColor = isThinking ? 'shadow-sky-500/10' : 'shadow-emerald-500/10';

  return (
    <div
      className={`rounded-xl border ${borderColor} bg-slate-800/80 shadow-lg ${glowColor} transition-all duration-300 overflow-hidden`}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">{isLiquidity ? '💰' : '⏱'}</span>
          <div className="text-left">
            <div className="text-xs text-slate-500">
              Tick {trace.tick} · {isLiquidity ? 'Liquidity Allocation' : 'Payment Timing'}
            </div>
            {!isThinking && (
              <div className="text-sm font-medium text-slate-200">{trace.decision}</div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isThinking ? (
            <span className="px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-400 text-xs font-medium">
              thinking
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-medium">
              decided
            </span>
          )}
          <span className={`text-slate-500 transition-transform ${expanded ? 'rotate-180' : ''}`}>▾</span>
        </div>
      </button>

      {/* Body */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-slate-700/50">
          {isThinking ? (
            <div className="pt-3">
              <ThinkingIndicator />
            </div>
          ) : (
            <>
              {/* Summary */}
              <div className="pt-3">
                <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
                  <span>🧠</span> Reasoning Summary
                </div>
                <div className="text-sm text-slate-300 leading-relaxed">
                  {isLatest ? (
                    <TypewriterText text={trace.reasoning_summary} speed={10} />
                  ) : (
                    trace.reasoning_summary
                  )}
                </div>
              </div>

              {/* Decision */}
              <div>
                <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
                  <span>📊</span> Decision
                </div>
                <div className="inline-block px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm font-medium">
                  {trace.decision}
                </div>
              </div>

              {/* Full reasoning (collapsible) */}
              <details className="group">
                <summary className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer hover:text-slate-400">
                  <span>💭</span> Full Rationale
                  <span className="group-open:rotate-180 transition-transform">▾</span>
                </summary>
                <div className="mt-2 text-xs text-slate-400 leading-relaxed bg-slate-900/50 rounded-lg p-3 font-mono">
                  {trace.reasoning}
                </div>
              </details>

              {/* Token usage */}
              {(trace.prompt_tokens || trace.completion_tokens) && (
                <div className="flex gap-3 text-[10px] text-slate-600">
                  {trace.prompt_tokens && <span>↑ {trace.prompt_tokens} tokens</span>}
                  {trace.completion_tokens && <span>↓ {trace.completion_tokens} tokens</span>}
                  {trace.fallback && <span className="text-amber-500">⚠ fallback</span>}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function AgentReasoningPanel({ reasoning, compact, onNavigateToAgents }: Props) {
  const agentIds = Object.keys(reasoning);

  if (agentIds.length === 0) {
    return (
      <div className="text-center text-slate-500 py-8">
        <div className="text-3xl mb-2">🧠</div>
        <div className="text-sm">No reasoning data yet. Enable AI reasoning and step through ticks.</div>
      </div>
    );
  }

  if (compact) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-300">🧠 Agent Reasoning</h3>
          {onNavigateToAgents && (
            <button
              onClick={onNavigateToAgents}
              className="text-xs text-sky-400 hover:text-sky-300 transition-colors"
            >
              See full reasoning →
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {agentIds.map(aid => {
            const traces = reasoning[aid];
            const latest = traces[traces.length - 1];
            if (!latest) return null;
            return (
              <div
                key={aid}
                className="rounded-lg border border-slate-700 bg-slate-800/50 p-3"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-slate-200">{aid}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    latest.phase === 'thinking'
                      ? 'bg-sky-500/20 text-sky-400'
                      : 'bg-emerald-500/20 text-emerald-400'
                  }`}>
                    {latest.phase === 'thinking' ? '🔄 thinking' : '✅ decided'}
                  </span>
                </div>
                {latest.phase === 'thinking' ? (
                  <ThinkingIndicator />
                ) : (
                  <>
                    <div className="text-xs text-emerald-300 font-medium mb-1">{latest.decision}</div>
                    <div className="text-xs text-slate-400 line-clamp-2">{latest.reasoning_summary}</div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // Full view — timeline grouped by agent
  return (
    <div className="space-y-6">
      {agentIds.map(aid => {
        const traces = reasoning[aid];
        return (
          <div key={aid}>
            <h3 className="text-lg font-bold text-slate-200 mb-3 flex items-center gap-2">
              <span className="w-8 h-8 rounded-full bg-gradient-to-br from-sky-500 to-violet-500 flex items-center justify-center text-sm font-bold">
                {aid.replace('BANK_', '')}
              </span>
              {aid}
              <span className="text-xs text-slate-500 font-normal">· {traces.length} decisions</span>
            </h3>
            <div className="space-y-2 pl-4 border-l-2 border-slate-700">
              {traces.map((trace, i) => (
                <ReasoningCard
                  key={`${aid}-${trace.tick}`}
                  trace={trace}
                  isLatest={i === traces.length - 1}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
