import { useState, useEffect, useMemo, useCallback } from 'react';
import { listGamePrompts, getGamePrompt } from '../api';
import type { PromptListEntry, PromptDetail, PromptBlockDetail } from '../api';
import { getAgentColor } from '../utils';

interface Props {
  gameId: string;
  agentIds: string[];
}

// Colors for block categories in the token bar
const BLOCK_COLORS = [
  '#4A6FA5', '#7A6B98', '#3D7A55', '#B8854A', '#A06070',
  '#5B8C85', '#C4956A', '#6B7FA6', '#8B6F8E', '#5A8F5A',
  '#D4856A', '#4A8FA5', '#9A7B5A', '#6A9B8A', '#B07A7A',
  '#7A9B6A', '#A08B5A', '#5A7AA0', '#8A6A9A', '#6AA08A',
];

export function PromptExplorer({ gameId, agentIds }: Props) {
  const [promptList, setPromptList] = useState<PromptListEntry[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedDay, setSelectedDay] = useState<number>(0);
  const [selectedAgent, setSelectedAgent] = useState<string>(agentIds[0] ?? '');
  const [promptDetail, setPromptDetail] = useState<PromptDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [expandedBlocks, setExpandedBlocks] = useState<Set<string>>(new Set());
  const [prevPrompt, setPrevPrompt] = useState<PromptDetail | null>(null);
  const [copied, setCopied] = useState(false);

  // Load prompt list
  useEffect(() => {
    setLoading(true);
    setError(null);
    listGamePrompts(gameId)
      .then(list => {
        setPromptList(list);
        if (list.length > 0) {
          const days = [...new Set(list.map(p => p.day))].sort((a, b) => a - b);
          setSelectedDay(days[0]);
          const firstDayAgents = list.filter(p => p.day === days[0]).map(p => p.agent_id);
          if (firstDayAgents.length > 0 && !firstDayAgents.includes(selectedAgent)) {
            setSelectedAgent(firstDayAgents[0]);
          }
        }
      })
      .catch(() => setError('Failed to load prompt data'))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId]);

  // Available days and agents
  const availableDays = useMemo(() => {
    if (!promptList) return [];
    return [...new Set(promptList.map(p => p.day))].sort((a, b) => a - b);
  }, [promptList]);

  const availableAgents = useMemo(() => {
    if (!promptList) return [];
    return [...new Set(promptList.filter(p => p.day === selectedDay).map(p => p.agent_id))];
  }, [promptList, selectedDay]);

  // Load prompt detail when selection changes
  useEffect(() => {
    if (!promptList || promptList.length === 0) return;
    const exists = promptList.some(p => p.day === selectedDay && p.agent_id === selectedAgent);
    if (!exists) {
      setPromptDetail(null);
      return;
    }

    setDetailLoading(true);
    // Fetch previous round's prompt for "constant" detection
    const prevDay = availableDays[availableDays.indexOf(selectedDay) - 1];
    const fetches: Promise<unknown>[] = [getGamePrompt(gameId, selectedDay, selectedAgent)];
    if (prevDay !== undefined) {
      fetches.push(
        getGamePrompt(gameId, prevDay, selectedAgent).catch(() => null)
      );
    }

    Promise.all(fetches).then(([detail, prev]) => {
      setPromptDetail(detail as PromptDetail);
      setPrevPrompt((prev as PromptDetail) ?? null);
    }).catch(() => {
      setPromptDetail(null);
      setPrevPrompt(null);
    }).finally(() => setDetailLoading(false));
  }, [gameId, selectedDay, selectedAgent, promptList, availableDays]);

  // Check if block content is constant (same as previous round)
  const isConstant = useCallback((block: PromptBlockDetail): boolean => {
    if (!prevPrompt) return false;
    const prevBlock = prevPrompt.blocks.find(b => b.id === block.id);
    if (!prevBlock) return false;
    return prevBlock.content === block.content;
  }, [prevPrompt]);

  const toggleBlock = (blockId: string) => {
    setExpandedBlocks(prev => {
      const next = new Set(prev);
      next.has(blockId) ? next.delete(blockId) : next.add(blockId);
      return next;
    });
  };

  const expandAll = () => {
    if (promptDetail) {
      setExpandedBlocks(new Set(promptDetail.blocks.map(b => b.id)));
    }
  };

  const collapseAll = () => setExpandedBlocks(new Set());

  const copyFullPrompt = async () => {
    if (!promptDetail) return;
    const systemBlocks = promptDetail.blocks.filter(b => b.category === 'system' && b.enabled);
    const userBlocks = promptDetail.blocks.filter(b => b.category === 'user' && b.enabled);
    const text = [
      '=== SYSTEM PROMPT ===',
      ...systemBlocks.map(b => b.content),
      '',
      '=== USER PROMPT ===',
      ...userBlocks.map(b => b.content),
    ].join('\n\n');
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* ignore */ }
  };

  if (loading) {
    return (
      <div className="text-sm italic" style={{ color: 'var(--text-muted)' }}>
        Loading prompt data…
      </div>
    );
  }

  if (error || !promptList || promptList.length === 0) {
    return (
      <div className="rounded-xl p-6 text-center" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
        <div className="text-2xl mb-2">📭</div>
        <div className="text-sm" style={{ color: 'var(--text-muted)' }}>
          {error ?? 'No prompt data available for this experiment.'}
        </div>
        <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
          Prompt data is recorded during AI optimization rounds.
        </div>
      </div>
    );
  }

  const enabledBlocks = promptDetail?.blocks.filter(b => b.enabled) ?? [];

  return (
    <div className="space-y-4">
      {/* Token breakdown bar */}
      {promptDetail && enabledBlocks.length > 0 && (
        <div className="rounded-xl p-4" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
              Token Breakdown — {(promptDetail.total_tokens / 1000).toFixed(1)}k total
              {promptDetail.llm_response_tokens > 0 && (
                <span style={{ color: 'var(--text-muted)' }}> + {(promptDetail.llm_response_tokens / 1000).toFixed(1)}k response</span>
              )}
            </span>
            <div className="flex gap-1">
              <button onClick={expandAll} className="text-[10px] px-1.5 py-0.5 rounded" style={{ color: 'var(--text-muted)', background: 'var(--bg-secondary)' }}>Expand all</button>
              <button onClick={collapseAll} className="text-[10px] px-1.5 py-0.5 rounded" style={{ color: 'var(--text-muted)', background: 'var(--bg-secondary)' }}>Collapse all</button>
              <button onClick={copyFullPrompt} className="text-[10px] px-1.5 py-0.5 rounded" style={{ color: copied ? 'var(--color-success)' : 'var(--text-muted)', background: 'var(--bg-secondary)' }}>
                {copied ? '✓ Copied' : '📋 Copy'}
              </button>
            </div>
          </div>
          {/* Stacked bar */}
          <div className="flex rounded-md overflow-hidden h-5" style={{ background: 'var(--bg-secondary)' }}>
            {enabledBlocks.map((block, i) => {
              const pct = promptDetail.total_tokens > 0
                ? (block.token_estimate / promptDetail.total_tokens) * 100
                : 0;
              if (pct < 0.5) return null;
              return (
                <div
                  key={block.id}
                  className="relative group cursor-pointer transition-opacity hover:opacity-80"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: BLOCK_COLORS[i % BLOCK_COLORS.length],
                    minWidth: pct > 2 ? undefined : '2px',
                  }}
                  onClick={() => toggleBlock(block.id)}
                  title={`${block.name}: ~${(block.token_estimate / 1000).toFixed(1)}k tokens (${pct.toFixed(1)}%)`}
                >
                  {pct > 8 && (
                    <span className="absolute inset-0 flex items-center justify-center text-[9px] text-white font-medium truncate px-1">
                      {block.name.length > 12 ? block.id.replace(/^(sys_|usr_)/, '') : block.name}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
          {/* Legend */}
          <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2">
            {enabledBlocks.map((block, i) => (
              <span key={block.id} className="flex items-center gap-1 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                <span className="inline-block w-2 h-2 rounded-sm" style={{ backgroundColor: BLOCK_COLORS[i % BLOCK_COLORS.length] }} />
                {block.name} ({(block.token_estimate / 1000).toFixed(1)}k)
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Block accordion */}
      {detailLoading ? (
        <div className="text-sm italic" style={{ color: 'var(--text-muted)' }}>Loading prompt…</div>
      ) : promptDetail ? (
        <div className="space-y-1">
          {promptDetail.blocks.filter(b => b.enabled).map((block, i) => {
            const expanded = expandedBlocks.has(block.id);
            const constant = isConstant(block);
            return (
              <div key={block.id} className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--border-color)', background: 'var(--bg-card)' }}>
                <button
                  onClick={() => toggleBlock(block.id)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-left transition-colors"
                  style={{ background: expanded ? 'var(--bg-secondary)' : undefined }}
                >
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{expanded ? '▼' : '▶'}</span>
                  <span className="inline-block w-2 h-2 rounded-sm flex-shrink-0" style={{ backgroundColor: BLOCK_COLORS[i % BLOCK_COLORS.length] }} />
                  <span className="text-sm font-medium flex-1" style={{ color: 'var(--text-primary)' }}>{block.name}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                    block.source === 'static'
                      ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                      : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
                  }`}>
                    {block.source}
                  </span>
                  {constant && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300">
                      constant
                    </span>
                  )}
                  <span className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
                    ~{block.token_estimate >= 1000 ? `${(block.token_estimate / 1000).toFixed(1)}k` : block.token_estimate}
                  </span>
                </button>
                {expanded && (
                  <div className="px-3 pb-3 pt-1" style={{ borderTop: '1px solid var(--border-color)' }}>
                    <pre className="text-xs leading-relaxed whitespace-pre-wrap font-mono overflow-x-auto max-h-96 overflow-y-auto p-2 rounded" style={{ color: 'var(--text-secondary)', background: 'var(--bg-inset, var(--bg-secondary))' }}>
                      {block.content}
                    </pre>
                    {block.truncated && block.content_length && (
                      <div className="text-[10px] mt-1 italic" style={{ color: 'var(--text-muted)' }}>
                        Content truncated — full block is {(block.content_length / 1000).toFixed(1)}k chars
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Select a round and agent to view prompt data.
        </div>
      )}

      {/* LLM Response section */}
      {promptDetail?.llm_response && (
        <div className="rounded-xl p-4" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
          <h4 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
            🤖 LLM Response
            <span className="text-[10px] font-normal ml-2" style={{ color: 'var(--text-muted)' }}>
              ~{(promptDetail.llm_response_tokens / 1000).toFixed(1)}k tokens
            </span>
          </h4>
          <pre className="text-xs leading-relaxed whitespace-pre-wrap font-mono max-h-64 overflow-y-auto p-2 rounded" style={{ color: 'var(--text-secondary)', background: 'var(--bg-inset, var(--bg-secondary))' }}>
            {promptDetail.llm_response}
          </pre>
        </div>
      )}

      {/* Navigation bar — round selector + agent tabs */}
      <div className="rounded-xl p-3 sticky bottom-0 z-10" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', boxShadow: '0 -2px 8px rgba(0,0,0,0.15)' }}>
        <div className="flex items-center gap-3 flex-wrap">
          {/* Round selector */}
          <div className="flex items-center gap-1">
            <span className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Round:</span>
            <div className="flex gap-0.5">
              {availableDays.map(day => (
                <button
                  key={day}
                  onClick={() => {
                    setSelectedDay(day);
                    // Ensure selected agent exists for this day
                    const dayAgents = promptList!.filter(p => p.day === day).map(p => p.agent_id);
                    if (!dayAgents.includes(selectedAgent) && dayAgents.length > 0) {
                      setSelectedAgent(dayAgents[0]);
                    }
                  }}
                  className="w-7 h-7 rounded text-xs font-mono transition-all"
                  style={selectedDay === day
                    ? { background: 'var(--btn-primary-bg, var(--accent-primary))', color: '#fff' }
                    : { background: 'var(--bg-secondary)', color: 'var(--text-muted)' }
                  }
                >
                  {day + 1}
                </button>
              ))}
            </div>
          </div>
          {/* Agent tabs */}
          <div className="flex items-center gap-1">
            <span className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Agent:</span>
            {availableAgents.map((aid, i) => (
              <button
                key={aid}
                onClick={() => setSelectedAgent(aid)}
                className="px-2.5 py-1 rounded-md text-xs font-mono transition-all"
                style={selectedAgent === aid
                  ? { backgroundColor: getAgentColor(aid, i) + '20', color: getAgentColor(aid, i), border: `1px solid ${getAgentColor(aid, i)}40` }
                  : { color: 'var(--text-muted)', border: '1px solid transparent' }
                }
              >
                {aid}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
