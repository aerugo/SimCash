import { useState, useEffect, useCallback } from 'react';
import { getPromptBlocks, getPromptProfiles, createPromptProfile, deletePromptProfile } from '../api';
import type { PromptBlockInfo, PromptProfileSummary } from '../api';

export interface PromptProfileConfig {
  /** block_id → {enabled, options} overrides. Empty = all defaults. */
  blocks: Record<string, { enabled?: boolean; options?: Record<string, unknown> }>;
}

interface Props {
  onChange: (config: PromptProfileConfig | null) => void;
  /** If true, wrap in a collapsible section */
  collapsible?: boolean;
  defaultOpen?: boolean;
}

export function PromptAnatomyPanel({ onChange, collapsible = true, defaultOpen = false }: Props) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [blocks, setBlocks] = useState<PromptBlockInfo[]>([]);
  const [profiles, setProfiles] = useState<PromptProfileSummary[]>([]);
  const [overrides, setOverrides] = useState<Record<string, { enabled: boolean; options: Record<string, unknown> }>>({});
  const [expandedOptions, setExpandedOptions] = useState<Set<string>>(new Set());
  const [selectedProfileId, setSelectedProfileId] = useState<string>('');
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [loading, setLoading] = useState(false);

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
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                  block.source === 'static'
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                    : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
                }`}>
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
