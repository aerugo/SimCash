import { useState, useEffect, useCallback, useMemo } from 'react';
import { getPromptBlocks, getPromptProfiles, createPromptProfile, deletePromptProfile } from '../api';
import type { PromptBlockInfo, PromptProfileSummary } from '../api';
import * as jsYaml from 'js-yaml';

export interface PromptProfileConfig {
  /** block_id → {enabled, options} overrides. Empty = all defaults. */
  blocks: Record<string, { enabled?: boolean; options?: Record<string, unknown> }>;
}

/* ── Smart Default Suggestions ── */

interface Suggestion {
  id: string;
  icon: string;
  title: string;
  description: string;
  severity: 'info' | 'warning';
  /** When user clicks Apply, these overrides are merged in */
  applyOverrides: Record<string, { enabled?: boolean; options?: Record<string, unknown> }>;
}

function analyzeScenario(yaml: string | undefined, blocks: PromptBlockInfo[], currentOverrides: Record<string, { enabled: boolean; options: Record<string, unknown> }>): Suggestion[] {
  if (!yaml) return [];
  let doc: Record<string, unknown>;
  try {
    doc = jsYaml.load(yaml) as Record<string, unknown>;
    if (!doc) return [];
  } catch {
    return [];
  }

  const suggestions: Suggestion[] = [];
  const sim = doc.simulation as Record<string, number> | undefined;
  const agents = doc.agents as Array<Record<string, unknown>> | undefined;
  const ticksPerDay = sim?.ticks_per_day ?? 12;
  const numDays = sim?.num_days ?? 1;

  // Current effective verbosity
  const traceVerbosity = currentOverrides['usr_simulation_trace']?.options?.verbosity;

  // 1. Deterministic scenario (no arrival_config on any agent)
  const isDeterministic = agents?.length
    ? agents.every(a => !a.arrival_config)
    : false;
  if (isDeterministic && traceVerbosity !== 'decisions_only') {
    suggestions.push({
      id: 'deterministic',
      icon: '🎯',
      title: 'Deterministic scenario detected',
      description: 'No arrival randomness — simulation traces are structurally identical across rounds. "decisions_only" verbosity saves tokens without losing information.',
      severity: 'info',
      applyOverrides: { usr_simulation_trace: { enabled: true, options: { verbosity: 'decisions_only' } } },
    });
  }

  // 2. Large tick count (>50 ticks/day)
  if (ticksPerDay > 50 && traceVerbosity !== 'decisions_only') {
    suggestions.push({
      id: 'large_ticks',
      icon: '📊',
      title: `High tick density (${ticksPerDay}/day)`,
      description: 'Simulation traces grow linearly with tick count. Consider "decisions_only" verbosity to keep prompts manageable.',
      severity: 'warning',
      applyOverrides: { usr_simulation_trace: { enabled: true, options: { verbosity: 'decisions_only' } } },
    });
  }

  // 3. Many rounds (max_days > 15)
  const maxDays = numDays;
  const historyFormat = currentOverrides['usr_iteration_history']?.options?.format;
  if (maxDays > 15 && historyFormat !== 'last_n') {
    suggestions.push({
      id: 'many_rounds',
      icon: '📚',
      title: `Long experiment (${maxDays} days)`,
      description: 'Full iteration history grows linearly and can dominate the prompt. Showing only the last 10 rounds is usually sufficient.',
      severity: 'info',
      applyOverrides: { usr_iteration_history: { enabled: true, options: { format: 'last_n', last_n: 10 } } },
    });
  }

  // 4. Total token estimate > 100k
  const totalTokens = blocks
    .filter(b => {
      const override = currentOverrides[b.id];
      return override ? override.enabled : b.enabled;
    })
    .reduce((sum, b) => sum + b.token_estimate, 0);
  if (totalTokens > 100000) {
    suggestions.push({
      id: 'token_warning',
      icon: '⚠️',
      title: `High token estimate (~${(totalTokens / 1000).toFixed(0)}k)`,
      description: 'Total prompt size exceeds 100k tokens. Consider disabling non-essential blocks or reducing trace verbosity.',
      severity: 'warning',
      applyOverrides: {},
    });
  }

  return suggestions;
}

interface Props {
  onChange: (config: PromptProfileConfig | null) => void;
  /** If true, wrap in a collapsible section */
  collapsible?: boolean;
  defaultOpen?: boolean;
  /** Raw scenario YAML for smart default analysis */
  scenarioYaml?: string;
}

export function PromptAnatomyPanel({ onChange, collapsible = true, defaultOpen = false, scenarioYaml }: Props) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [blocks, setBlocks] = useState<PromptBlockInfo[]>([]);
  const [profiles, setProfiles] = useState<PromptProfileSummary[]>([]);
  const [overrides, setOverrides] = useState<Record<string, { enabled: boolean; options: Record<string, unknown> }>>({});
  const [expandedOptions, setExpandedOptions] = useState<Set<string>>(new Set());
  const [selectedProfileId, setSelectedProfileId] = useState<string>('');
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [loading, setLoading] = useState(false);
  const [dismissedSuggestions, setDismissedSuggestions] = useState<Set<string>>(new Set());

  useEffect(() => {
    setLoading(true);
    Promise.all([getPromptBlocks(), getPromptProfiles()])
      .then(([b, p]) => { setBlocks(b); setProfiles(p); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Emit changes to parent
  const emitChanges = useCallback((newOverrides: typeof overrides) => {
    const hasOverrides = Object.keys(newOverrides).length > 0;
    if (!hasOverrides) {
      onChange(null);
    } else {
      onChange({ blocks: newOverrides });
    }
  }, [onChange]);

  const toggleBlock = (blockId: string, currentEnabled: boolean) => {
    const next = { ...overrides };
    const existing = next[blockId] || { enabled: currentEnabled, options: {} };
    existing.enabled = !currentEnabled;
    next[blockId] = existing;
    setOverrides(next);
    emitChanges(next);
  };

  const setOption = (blockId: string, key: string, value: unknown) => {
    const next = { ...overrides };
    const existing = next[blockId] || { enabled: true, options: {} };
    existing.options = { ...existing.options, [key]: value };
    next[blockId] = existing;
    setOverrides(next);
    emitChanges(next);
  };

  const loadProfile = (profileId: string) => {
    setSelectedProfileId(profileId);
    if (!profileId) {
      setOverrides({});
      emitChanges({});
      return;
    }
    const profile = profiles.find(p => p.id === profileId);
    if (profile) {
      const newOverrides: typeof overrides = {};
      for (const [blockId, cfg] of Object.entries(profile.blocks)) {
        newOverrides[blockId] = {
          enabled: cfg.enabled ?? true,
          options: (cfg.options ?? {}) as Record<string, unknown>,
        };
      }
      setOverrides(newOverrides);
      emitChanges(newOverrides);
    }
  };

  const handleSaveProfile = async () => {
    if (!saveName.trim()) return;
    try {
      const saved = await createPromptProfile(saveName.trim(), '', overrides);
      setProfiles(prev => [...prev, saved]);
      setSelectedProfileId(saved.id);
      setSaveDialogOpen(false);
      setSaveName('');
    } catch { /* ignore */ }
  };

  const handleDeleteProfile = async (id: string) => {
    try {
      await deletePromptProfile(id);
      setProfiles(prev => prev.filter(p => p.id !== id));
      if (selectedProfileId === id) {
        setSelectedProfileId('');
        setOverrides({});
        emitChanges({});
      }
    } catch { /* ignore */ }
  };

  const getBlockEnabled = (block: PromptBlockInfo): boolean => {
    const override = overrides[block.id];
    return override ? override.enabled : block.enabled;
  };

  const getBlockOption = (blockId: string, key: string, defaultVal: unknown): unknown => {
    return overrides[blockId]?.options?.[key] ?? defaultVal;
  };

  const totalTokens = blocks
    .filter(b => getBlockEnabled(b))
    .reduce((sum, b) => sum + b.token_estimate, 0);

  const suggestions = useMemo(
    () => analyzeScenario(scenarioYaml, blocks, overrides),
    [scenarioYaml, blocks, overrides]
  );

  const visibleSuggestions = suggestions.filter(s => !dismissedSuggestions.has(s.id));

  const applySuggestion = (suggestion: Suggestion) => {
    const next = { ...overrides };
    for (const [blockId, cfg] of Object.entries(suggestion.applyOverrides)) {
      const existing = next[blockId] || { enabled: true, options: {} };
      if (cfg.enabled !== undefined) existing.enabled = cfg.enabled;
      if (cfg.options) existing.options = { ...existing.options, ...cfg.options };
      next[blockId] = existing;
    }
    setOverrides(next);
    emitChanges(next);
    setDismissedSuggestions(prev => new Set([...prev, suggestion.id]));
  };

  const dismissSuggestion = (id: string) => {
    setDismissedSuggestions(prev => new Set([...prev, id]));
  };

  const systemBlocks = blocks.filter(b => b.category === 'system');
  const userBlocks = blocks.filter(b => b.category === 'user');

  const content = (
    <div className="space-y-4">
      {loading ? (
        <div className="text-sm text-[var(--text-muted)] italic">Loading blocks…</div>
      ) : (
        <>
          {/* Profile selector */}
          <div className="flex items-center gap-2">
            <select
              value={selectedProfileId}
              onChange={e => loadProfile(e.target.value)}
              className="flex-1 px-3 py-1.5 rounded-lg text-sm bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-color)]"
            >
              <option value="">Default (all blocks enabled)</option>
              {profiles.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <button
              onClick={() => setSaveDialogOpen(true)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--bg-secondary)] text-[var(--text-secondary)] border border-[var(--border-color)] hover:bg-[var(--bg-tertiary)] transition-colors"
              title="Save current config as profile"
            >
              💾 Save
            </button>
            {selectedProfileId && (
              <button
                onClick={() => handleDeleteProfile(selectedProfileId)}
                className="px-2 py-1.5 rounded-lg text-xs text-red-400 hover:bg-red-500/10 transition-colors"
                title="Delete profile"
              >
                🗑️
              </button>
            )}
          </div>

          {/* Save dialog */}
          {saveDialogOpen && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-[var(--bg-tertiary)] border border-[var(--border-color)]">
              <input
                type="text"
                value={saveName}
                onChange={e => setSaveName(e.target.value)}
                placeholder="Profile name…"
                className="flex-1 px-3 py-1.5 rounded text-sm bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-color)]"
                onKeyDown={e => e.key === 'Enter' && handleSaveProfile()}
                autoFocus
              />
              <button onClick={handleSaveProfile} className="px-3 py-1.5 rounded text-xs font-medium bg-[var(--accent-primary)] text-white">Save</button>
              <button onClick={() => setSaveDialogOpen(false)} className="px-2 py-1.5 rounded text-xs text-[var(--text-muted)]">Cancel</button>
            </div>
          )}

          {/* Smart suggestions */}
          {visibleSuggestions.length > 0 && (
            <div className="space-y-2">
              {visibleSuggestions.map(s => (
                <div
                  key={s.id}
                  className="flex items-start gap-3 p-3 rounded-lg border text-sm"
                  style={s.severity === 'warning'
                    ? { backgroundColor: 'var(--alert-warning-bg, #fffbeb)', borderColor: 'var(--alert-warning-border, #fde68a)' }
                    : { backgroundColor: 'var(--alert-info-bg, #eff6ff)', borderColor: 'var(--alert-info-border, #bfdbfe)' }
                  }
                >
                  <span className="text-lg flex-shrink-0">{s.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-xs"
                      style={{ color: s.severity === 'warning' ? 'var(--alert-warning-title, #92400e)' : 'var(--alert-info-title, #1e40af)' }}
                    >{s.title}</div>
                    <div className="text-[11px] mt-0.5"
                      style={{ color: s.severity === 'warning' ? 'var(--alert-warning-text, #a16207)' : 'var(--alert-info-text, #1d4ed8)' }}
                    >{s.description}</div>
                  </div>
                  <div className="flex gap-1 flex-shrink-0">
                    {Object.keys(s.applyOverrides).length > 0 && (
                      <button
                        onClick={() => applySuggestion(s)}
                        className="px-2 py-1 rounded text-[10px] font-medium transition-colors"
                      style={s.severity === 'warning'
                        ? { backgroundColor: 'var(--alert-warning-btn-bg, #fde68a)', color: 'var(--alert-warning-btn-text, #92400e)' }
                        : { backgroundColor: 'var(--alert-info-btn-bg, #bfdbfe)', color: 'var(--alert-info-btn-text, #1e40af)' }
                      }
                      >
                        Apply
                      </button>
                    )}
                    <button
                      onClick={() => dismissSuggestion(s.id)}
                      className="px-2 py-1 rounded text-[10px] text-[var(--text-muted)] hover:bg-[var(--bg-tertiary)] transition-colors"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Block groups */}
          <BlockGroup title="System Prompt" blocks={systemBlocks} getEnabled={getBlockEnabled} onToggle={toggleBlock} expandedOptions={expandedOptions} setExpandedOptions={setExpandedOptions} getOption={getBlockOption} setOption={setOption} />
          <BlockGroup title="User Prompt" blocks={userBlocks} getEnabled={getBlockEnabled} onToggle={toggleBlock} expandedOptions={expandedOptions} setExpandedOptions={setExpandedOptions} getOption={getBlockOption} setOption={setOption} />

          {/* Token estimate */}
          <div className="text-right text-xs text-[var(--text-muted)]">
            Estimated total: ~{(totalTokens / 1000).toFixed(1)}k tokens
          </div>
        </>
      )}
    </div>
  );

  if (!collapsible) return content;

  return (
    <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-primary)] overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[var(--bg-secondary)] transition-colors"
      >
        <span className="text-sm font-semibold text-[var(--text-primary)]">🧩 Prompt Configuration</span>
        <span className="text-xs text-[var(--text-muted)]">
          {isOpen ? '▼' : '▶'} ~{(totalTokens / 1000).toFixed(1)}k tokens
        </span>
      </button>
      {isOpen && <div className="px-4 pb-4">{content}</div>}
    </div>
  );
}


function BlockGroup({
  title, blocks, getEnabled, onToggle, expandedOptions, setExpandedOptions, getOption, setOption,
}: {
  title: string;
  blocks: PromptBlockInfo[];
  getEnabled: (b: PromptBlockInfo) => boolean;
  onToggle: (id: string, current: boolean) => void;
  expandedOptions: Set<string>;
  setExpandedOptions: (s: Set<string>) => void;
  getOption: (blockId: string, key: string, defaultVal: unknown) => unknown;
  setOption: (blockId: string, key: string, value: unknown) => void;
}) {
  if (!blocks.length) return null;

  return (
    <div>
      <div className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-2">{title}</div>
      <div className="space-y-1">
        {blocks.map(block => {
          const enabled = getEnabled(block);
          const hasOptions = block.available_options && Object.keys(block.available_options).length > 0;
          const optionsExpanded = expandedOptions.has(block.id);

          return (
            <div key={block.id} className={`rounded-lg border transition-colors ${enabled ? 'border-[var(--border-color)] bg-[var(--bg-secondary)]' : 'border-transparent bg-[var(--bg-tertiary)] opacity-60'}`}>
              <div className="flex items-center gap-2 px-3 py-2">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={() => onToggle(block.id, enabled)}
                  className="rounded accent-[var(--accent-primary)]"
                />
                <span className={`text-sm flex-1 ${enabled ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)] line-through'}`}>
                  {block.name}
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                  style={block.source === 'static'
                    ? { backgroundColor: 'var(--badge-static-bg, #dbeafe)', color: 'var(--badge-static-text, #1d4ed8)' }
                    : { backgroundColor: 'var(--badge-dynamic-bg, #fef3c7)', color: 'var(--badge-dynamic-text, #92400e)' }
                  }>
                  {block.source}
                </span>
                <span className="text-[10px] text-[var(--text-muted)]">
                  ~{block.token_estimate >= 1000 ? `${(block.token_estimate / 1000).toFixed(1)}k` : block.token_estimate}
                </span>
                {hasOptions && enabled && (
                  <button
                    onClick={() => {
                      const next = new Set(expandedOptions);
                      optionsExpanded ? next.delete(block.id) : next.add(block.id);
                      setExpandedOptions(next);
                    }}
                    className="text-xs hover:bg-[var(--bg-tertiary)] rounded p-1 transition-colors"
                    title="Block options"
                  >
                    ⚙️
                  </button>
                )}
              </div>

              {/* Block description */}
              <div className="px-3 pb-1 text-[10px] text-[var(--text-muted)]">{block.description}</div>

              {/* Options panel */}
              {hasOptions && optionsExpanded && enabled && block.available_options && (
                <div className="px-3 pb-3 pt-1 border-t border-[var(--border-color)] mt-1">
                  {Object.entries(block.available_options).map(([key, opt]) => (
                    <div key={key} className="flex items-center gap-2 mt-1">
                      <label className="text-xs text-[var(--text-secondary)] min-w-[60px]">{key}:</label>
                      {opt.type === 'enum' && opt.values ? (
                        <select
                          value={String(getOption(block.id, key, opt.default))}
                          onChange={e => setOption(block.id, key, e.target.value)}
                          className="text-xs px-2 py-1 rounded bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border-color)]"
                        >
                          {opt.values.map(v => <option key={v} value={v}>{v}</option>)}
                        </select>
                      ) : opt.type === 'int' ? (
                        <input
                          type="number"
                          value={Number(getOption(block.id, key, opt.default))}
                          onChange={e => setOption(block.id, key, parseInt(e.target.value) || opt.default)}
                          className="text-xs px-2 py-1 rounded bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border-color)] w-20"
                        />
                      ) : null}
                      {opt.description && <span className="text-[10px] text-[var(--text-muted)]">{opt.description}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
