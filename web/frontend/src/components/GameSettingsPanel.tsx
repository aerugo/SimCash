import { useState, useEffect, useCallback } from 'react';
import type { LibraryPolicy } from '../types';
import { getPolicyLibrary } from '../api';
import { InfoTip } from './Tooltip';

export interface GameSettings {
  maxDays: number;
  numEvalSamples: number;
  optimizationInterval: number;
  constraintPreset: 'simple' | 'standard' | 'full';
  useLlm: boolean;
  mockReasoning: boolean;
  agentPolicies: Record<string, { policyId: string; fraction: number }>;
  /** Cached policy JSON strings keyed by policy ID (populated by the panel) */
  policyDetails: Record<string, string>;
}

export const DEFAULT_GAME_SETTINGS: GameSettings = {
  maxDays: 10,
  numEvalSamples: 1,
  optimizationInterval: 1,
  constraintPreset: 'full',
  useLlm: true,
  mockReasoning: true,
  agentPolicies: {},
  policyDetails: {},
};

interface Props {
  agentIds: string[];
  settings?: GameSettings;
  onChange: (settings: GameSettings) => void;
  /** If true, wrap in a collapsible section. Default: false */
  collapsible?: boolean;
  /** Default open state when collapsible. Default: false */
  defaultOpen?: boolean;
}

export function GameSettingsPanel({ agentIds, settings: settingsProp, onChange, collapsible = false, defaultOpen = false }: Props) {
  const s = settingsProp ?? DEFAULT_GAME_SETTINGS;
  const [policyLibrary, setPolicyLibrary] = useState<LibraryPolicy[]>([]);
  const [startingPoliciesOpen, setStartingPoliciesOpen] = useState(false);
  const [isOpen, setIsOpen] = useState(defaultOpen);

  useEffect(() => {
    getPolicyLibrary().then((policies) => {
      setPolicyLibrary(policies);
      const details: Record<string, string> = {};
      Promise.all(policies.map(async (p) => {
        try {
          const res = await fetch(`/api/policies/library/${p.id}`);
          const data = await res.json();
          if (data.raw) details[p.id] = JSON.stringify(data.raw);
        } catch { /* ignore */ }
      })).then(() => onChange({ ...s, policyDetails: details }));
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const update = useCallback((partial: Partial<GameSettings>) => {
    onChange({ ...s, ...partial });
  }, [s, onChange]);

  const setAgentPolicy = useCallback((aid: string, policy: { policyId: string; fraction: number }) => {
    onChange({ ...s, agentPolicies: { ...s.agentPolicies, [aid]: policy } });
  }, [s, onChange]);

  const setAllAgentPolicies = useCallback((policyId: string) => {
    const libPolicy = policyLibrary.find(p => p.id === policyId);
    const frac = policyId === 'default' ? 1.0
      : (libPolicy?.parameters as Record<string, number>)?.initial_liquidity_fraction ?? 0.5;
    const updated: Record<string, { policyId: string; fraction: number }> = {};
    agentIds.forEach(aid => { updated[aid] = { policyId, fraction: frac }; });
    onChange({ ...s, agentPolicies: updated });
  }, [s, onChange, agentIds, policyLibrary]);

  const content = (
    <div className="space-y-4">
      <div>
        <label className="text-xs text-slate-500 flex justify-between mb-1">
          <span>Max Days</span>
          <span className="font-mono text-slate-300">{s.maxDays}</span>
        </label>
        <input
          type="range" value={s.maxDays} onChange={e => update({ maxDays: Number(e.target.value) })}
          min={1} max={50} className="w-full accent-violet-400"
        />
      </div>
      <div>
        <label className="text-xs text-slate-500 flex justify-between mb-1">
          <span>Evaluation Samples</span>
          <span className="font-mono text-slate-300">{s.numEvalSamples}</span>
        </label>
        <input
          type="range" value={s.numEvalSamples} onChange={e => update({ numEvalSamples: Number(e.target.value) })}
          min={1} max={50} className="w-full accent-violet-400"
        />
        <p className="text-[10px] text-slate-600 mt-1">
          {s.numEvalSamples === 1 ? '1 = fast exploration · 10+ = statistically robust' : s.numEvalSamples >= 50 ? 'Paper-faithful — 50 bootstrap samples' : `${s.numEvalSamples} samples · 10+ = statistically robust`}
        </p>
      </div>
      <div>
        <label className="text-xs text-slate-500 flex justify-between mb-1">
          <span>Optimization Interval</span>
          <span className="font-mono text-slate-300">
            {s.optimizationInterval === 1 ? 'Every day' : `Every ${s.optimizationInterval} days`}
          </span>
        </label>
        <select
          value={s.optimizationInterval}
          onChange={e => update({ optimizationInterval: Number(e.target.value) })}
          className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm text-slate-200"
        >
          <option value={1}>Every day (1)</option>
          <option value={2}>Every 2 days</option>
          <option value={3}>Every 3 days</option>
          <option value={5}>Every 5 days</option>
          <option value={10}>Every 10 days</option>
        </select>
        <p className="text-[10px] text-slate-600 mt-1">
          How often the AI re-evaluates its strategy. More days between optimizations = more data per evaluation, slower adaptation.
        </p>
      </div>
      {s.useLlm && (
        <div>
          <label className="text-xs text-slate-500 flex justify-between mb-1">
            <span>Policy Complexity<InfoTip text="Simple: Agent optimizes only the liquidity fraction (single number). Standard: Agent optimizes fraction + payment timing decisions. Full: Agent designs complete decision trees with conditions, splitting, priorities." /></span>
            <span className="font-mono text-slate-300">
              {s.constraintPreset === 'simple' ? 'Simple' : s.constraintPreset === 'standard' ? 'Standard' : 'Full'}
            </span>
          </label>
          <select
            value={s.constraintPreset}
            onChange={e => update({ constraintPreset: e.target.value as 'simple' | 'standard' | 'full' })}
            className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm text-slate-200"
          >
            <option value="simple">Simple</option>
            <option value="standard">Standard</option>
            <option value="full">Full</option>
          </select>
          <p className="text-[10px] text-slate-600 mt-1">
            {s.constraintPreset === 'simple' ? 'AI adjusts liquidity fraction only' :
             s.constraintPreset === 'standard' ? 'AI also decides payment timing (Release/Hold)' :
             'AI has complete freedom — all actions, conditions, and parameters'}
          </p>
        </div>
      )}
      <div className="flex gap-6 flex-wrap">
        <Toggle label="Enable AI Optimization" value={s.useLlm} onChange={v => update({ useLlm: v })} />
        {s.useLlm && (
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-500">{s.mockReasoning ? 'Algorithmic' : 'LLM-Powered'}</span>
              <Toggle label="" value={!s.mockReasoning} onChange={v => update({ mockReasoning: !v })} />
            </div>
            <p className="text-[10px] text-slate-500">
              {s.mockReasoning ? '(fast, deterministic)' : '(Gemini, richer reasoning)'}
            </p>
            <p className="text-[10px] text-slate-600">
              Algorithmic mode uses rule-based optimization. LLM mode uses a language model to reason about strategy.
            </p>
          </div>
        )}
      </div>

      {/* Starting Policies */}
      {agentIds.length > 0 && (
        <div className="bg-slate-800/50 rounded-xl border border-slate-700">
          <button
            onClick={() => setStartingPoliciesOpen(!startingPoliciesOpen)}
            className="w-full flex items-center justify-between p-4 text-left"
          >
            <span className="text-sm font-semibold text-slate-300">
              {startingPoliciesOpen ? '▼' : '▶'} Starting Policies <span className="text-slate-500 font-normal">(optional)</span>
            </span>
            {Object.values(s.agentPolicies).some(v => v.policyId !== 'default') && (
              <span className="text-xs text-violet-400">Custom policies set</span>
            )}
          </button>
          {startingPoliciesOpen && (
            <div className="px-4 pb-4 space-y-3">
              {agentIds.map(aid => {
                const ap = s.agentPolicies[aid] || { policyId: 'default', fraction: 1.0 };
                return (
                  <div key={aid} className="space-y-1">
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-mono text-slate-300 w-20">{aid}</span>
                      <select
                        value={ap.policyId}
                        onChange={e => {
                          const pid = e.target.value;
                          const libPolicy = policyLibrary.find(p => p.id === pid);
                          const frac = pid === 'default' ? 1.0
                            : (libPolicy?.parameters as Record<string, number>)?.initial_liquidity_fraction ?? 0.5;
                          setAgentPolicy(aid, { policyId: pid, fraction: frac });
                        }}
                        className="flex-1 bg-slate-700 border border-slate-600 rounded px-2 py-1.5 text-sm text-slate-200"
                      >
                        <option value="default">Default (FIFO)</option>
                        {policyLibrary.map(p => {
                          const frac = (p.parameters as Record<string, number>)?.initial_liquidity_fraction;
                          return (
                            <option key={p.id} value={p.id}>
                              {p.name} (frac={frac != null ? frac.toFixed(2) : '?'})
                            </option>
                          );
                        })}
                      </select>
                    </div>
                    <div className="flex items-center gap-2 ml-[92px]">
                      <span className="text-xs text-slate-500 w-16">Fraction:</span>
                      <input
                        type="range"
                        min="0" max="1" step="0.05"
                        value={ap.fraction}
                        onChange={e => setAgentPolicy(aid, { ...ap, fraction: parseFloat(e.target.value) })}
                        className="flex-1 h-1.5 accent-violet-500"
                      />
                      <span className="text-xs font-mono text-violet-400 w-10 text-right">{ap.fraction.toFixed(2)}</span>
                    </div>
                  </div>
                );
              })}
              {agentIds.length > 1 && (
                <div className="flex items-center gap-3 pt-2 border-t border-slate-700/50">
                  <span className="text-xs text-slate-500 w-20">Apply to all:</span>
                  <select
                    value=""
                    onChange={e => { if (e.target.value) setAllAgentPolicies(e.target.value); }}
                    className="flex-1 bg-slate-700 border border-slate-600 rounded px-2 py-1.5 text-sm text-slate-200"
                  >
                    <option value="">— select —</option>
                    <option value="default">Default (FIFO)</option>
                    {policyLibrary.map(p => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );

  if (collapsible) {
    return (
      <div className="bg-slate-800/50 rounded-xl border border-slate-700">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full flex items-center justify-between p-4 text-left"
        >
          <span className="text-sm font-semibold text-slate-300">
            {isOpen ? '▼' : '▶'} Game Settings
          </span>
        </button>
        {isOpen && <div className="px-4 pb-4">{content}</div>}
      </div>
    );
  }

  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
      <h3 className="text-sm font-semibold text-slate-300 mb-4">Game Settings</h3>
      {content}
    </div>
  );
}

/** Build starting_policies from GameSettings for the launch payload */
export function buildStartingPoliciesPayload(settings: GameSettings): Record<string, string> | undefined {
  const result: Record<string, string> = {};
  for (const [aid, ap] of Object.entries(settings.agentPolicies)) {
    if (ap.policyId && ap.policyId !== 'default' && settings.policyDetails[ap.policyId]) {
      const policyObj = JSON.parse(settings.policyDetails[ap.policyId]);
      if (!policyObj.parameters) policyObj.parameters = {};
      policyObj.parameters.initial_liquidity_fraction = ap.fraction;
      result[aid] = JSON.stringify(policyObj);
    }
  }
  return Object.keys(result).length > 0 ? result : undefined;
}

/** Convert GameSettings to the GameSetupConfig fields needed for launch */
export function gameSettingsToConfig(settings: GameSettings): {
  use_llm: boolean;
  mock_reasoning: boolean;
  max_days: number;
  num_eval_samples: number;
  optimization_interval: number;
  constraint_preset: 'simple' | 'standard' | 'full';
  starting_policies?: Record<string, string>;
} {
  return {
    use_llm: settings.useLlm,
    mock_reasoning: settings.mockReasoning,
    max_days: settings.maxDays,
    num_eval_samples: settings.numEvalSamples,
    optimization_interval: settings.optimizationInterval,
    constraint_preset: settings.constraintPreset,
    starting_policies: buildStartingPoliciesPayload(settings),
  };
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <div
        onClick={() => onChange(!value)}
        className={`w-9 h-5 rounded-full transition-colors relative ${value ? 'bg-sky-500' : 'bg-slate-600'}`}
      >
        <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${value ? 'left-4.5' : 'left-0.5'}`} />
      </div>
      <span className="text-sm text-slate-300">{label}</span>
    </label>
  );
}
