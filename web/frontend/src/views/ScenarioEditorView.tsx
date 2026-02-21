import { useState, useCallback, useMemo, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { GameSetupConfig, ScenarioEvent } from '../types';
import { authFetch, API_ORIGIN, getCustomScenario, updateCustomScenario, saveCustomScenario as saveCustomScenarioApi } from '../api';
import { EventTimelineBuilder, eventsToYaml, yamlToEvents } from '../components/EventTimelineBuilder';
import { ScenarioForm } from '../components/ScenarioForm';
import { GameSettingsPanel, gameSettingsToConfig, DEFAULT_GAME_SETTINGS } from '../components/GameSettingsPanel';
import type { GameSettings } from '../components/GameSettingsPanel';
import { PromptAnatomyPanel } from '../components/PromptAnatomyPanel';
import type { PromptProfileConfig } from '../components/PromptAnatomyPanel';
import { CodeEditor } from '../components/CodeEditor';
import * as jsYaml from 'js-yaml';

const BLANK_TEMPLATE = `simulation:
  ticks_per_day: 12
  num_days: 1
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 0
    liquidity_pool: 1000000
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10000
        std_dev: 5000
      counterparty_weights:
        BANK_B: 1.0
      deadline_range: [3, 8]
  - id: BANK_B
    opening_balance: 0
    liquidity_pool: 1000000
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10000
        std_dev: 5000
      counterparty_weights:
        BANK_A: 1.0
      deadline_range: [3, 8]

cost_rates:
  delay_cost_per_tick_per_cent: 0.2
  eod_penalty_per_transaction: 100000
  deadline_penalty: 50000
  liquidity_cost_per_tick_bps: 83
`;

const SIMPLE_2BANK_TEMPLATE = `simulation:
  ticks_per_day: 3
  num_days: 1
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 0
    liquidity_pool: 100000
    arrival_config:
      rate_per_tick: 1.0
      amount_distribution:
        type: LogNormal
        mean: 5000
        std_dev: 2000
      counterparty_weights:
        BANK_B: 1.0
      deadline_range: [1, 3]
  - id: BANK_B
    opening_balance: 0
    liquidity_pool: 100000
    arrival_config:
      rate_per_tick: 1.0
      amount_distribution:
        type: LogNormal
        mean: 5000
        std_dev: 2000
      counterparty_weights:
        BANK_A: 1.0
      deadline_range: [1, 3]

cost_rates:
  delay_cost_per_tick_per_cent: 0.2
  eod_penalty_per_transaction: 100000
  deadline_penalty: 50000
  liquidity_cost_per_tick_bps: 333
`;

const CRISIS_TEMPLATE = `simulation:
  ticks_per_day: 12
  num_days: 3
  rng_seed: 99

agents:
  - id: BANK_A
    opening_balance: 0
    liquidity_pool: 2000000
    arrival_config:
      rate_per_tick: 3.0
      amount_distribution:
        type: LogNormal
        mean: 15000
        std_dev: 8000
      counterparty_weights:
        BANK_B: 0.6
        BANK_C: 0.4
      deadline_range: [2, 6]
  - id: BANK_B
    opening_balance: 0
    liquidity_pool: 1500000
    arrival_config:
      rate_per_tick: 2.5
      amount_distribution:
        type: LogNormal
        mean: 12000
        std_dev: 6000
      counterparty_weights:
        BANK_A: 0.7
        BANK_C: 0.3
      deadline_range: [2, 6]
  - id: BANK_C
    opening_balance: 0
    liquidity_pool: 1000000
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10000
        std_dev: 5000
      counterparty_weights:
        BANK_A: 0.5
        BANK_B: 0.5
      deadline_range: [3, 8]

scenario_events:
  - type: DirectTransfer
    from_agent: BANK_A
    to_agent: BANK_C
    amount: 500000
    schedule:
      type: OneTime
      tick: 12
  - type: DirectTransfer
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 300000
    schedule:
      type: OneTime
      tick: 24

cost_rates:
  delay_cost_per_tick_per_cent: 0.3
  eod_penalty_per_transaction: 150000
  deadline_penalty: 75000
  liquidity_cost_per_tick_bps: 100
`;

const LSM_TEMPLATE = `simulation:
  ticks_per_day: 8
  num_days: 1
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 0
    liquidity_pool: 500000
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10000
        std_dev: 5000
      counterparty_weights:
        BANK_B: 0.5
        BANK_C: 0.5
      deadline_range: [2, 6]
  - id: BANK_B
    opening_balance: 0
    liquidity_pool: 500000
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10000
        std_dev: 5000
      counterparty_weights:
        BANK_A: 0.5
        BANK_C: 0.5
      deadline_range: [2, 6]
  - id: BANK_C
    opening_balance: 0
    liquidity_pool: 500000
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10000
        std_dev: 5000
      counterparty_weights:
        BANK_A: 0.5
        BANK_B: 0.5
      deadline_range: [2, 6]

lsm_config:
  enable_bilateral: true
  enable_cycles: true

cost_rates:
  delay_cost_per_tick_per_cent: 0.2
  eod_penalty_per_transaction: 100000
  deadline_penalty: 50000
  liquidity_cost_per_tick_bps: 83
`;

const TEMPLATES: { label: string; value: string }[] = [
  { label: 'Blank (2-Bank)', value: BLANK_TEMPLATE },
  { label: 'Simple 2-Bank', value: SIMPLE_2BANK_TEMPLATE },
  { label: 'Crisis (3-phase)', value: CRISIS_TEMPLATE },
  { label: 'LSM Test', value: LSM_TEMPLATE },
];

interface ValidationSummary {
  num_agents: number;
  agent_ids: string[];
  ticks_per_day: number;
  num_days: number;
  total_ticks: number;
  features: string[];
  cost_config: Record<string, number>;
}

export interface ScenarioEditorState {
  yaml: string;
  name: string;
  description: string;
}

interface Props {
  onGameLaunch?: (config: GameSetupConfig) => void;
  initialState?: ScenarioEditorState;
  onStateChange?: (state: ScenarioEditorState) => void;
}

export function ScenarioEditorView({ onGameLaunch, initialState, onStateChange }: Props) {
  const [searchParams] = useSearchParams();
  const editId = searchParams.get('edit');
  const [isEditing, setIsEditing] = useState(false);
  const [saveToast, setSaveToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [yaml, setYamlRaw] = useState(initialState?.yaml ?? BLANK_TEMPLATE);
  const [validating, setValidating] = useState(false);
  const [valid, setValid] = useState<boolean | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [summary, setSummary] = useState<ValidationSummary | null>(null);
  const [saving, setSaving] = useState(false);
  const [scenarioName, setScenarioNameRaw] = useState(initialState?.name ?? 'My Scenario');
  const [scenarioDesc, setScenarioDescRaw] = useState(initialState?.description ?? '');
  const [editorMode, setEditorMode] = useState<'form' | 'yaml'>('form');
  const [modeSwitchError, setModeSwitchError] = useState<string | null>(null);
  const [gameSettings, setGameSettings] = useState<GameSettings>(DEFAULT_GAME_SETTINGS);
  const [promptProfileConfig, setPromptProfileConfig] = useState<PromptProfileConfig | null>(null);

  // Load scenario for editing
  useEffect(() => {
    if (editId) {
      getCustomScenario(editId).then(s => {
        setYamlRaw(s.yaml_string);
        setScenarioNameRaw(s.name);
        setScenarioDescRaw(s.description);
        setIsEditing(true);
      }).catch(() => {
        setErrors(['Failed to load scenario for editing']);
        setValid(false);
      });
    }
  }, [editId]);

  const setYaml = useCallback((v: string) => {
    setYamlRaw(v);
    onStateChange?.({ yaml: v, name: scenarioName, description: scenarioDesc });
  }, [onStateChange, scenarioName, scenarioDesc]);

  const setScenarioName = useCallback((v: string) => {
    setScenarioNameRaw(v);
    onStateChange?.({ yaml, name: v, description: scenarioDesc });
  }, [onStateChange, yaml, scenarioDesc]);

  const setScenarioDesc = useCallback((v: string) => {
    setScenarioDescRaw(v);
    onStateChange?.({ yaml, name: scenarioName, description: v });
  }, [onStateChange, yaml, scenarioName]);

  // Parse YAML to extract agent IDs, total ticks, and events for the timeline builder
  const parsedYaml = useMemo(() => {
    try {
      const doc = jsYaml.load(yaml) as Record<string, unknown> | null;
      if (!doc) return null;
      const sim = doc.simulation as Record<string, number> | undefined;
      const agents = doc.agents as { id: string }[] | undefined;
      const agentIds = agents?.map(a => a.id) ?? [];
      const ticksPerDay = sim?.ticks_per_day ?? 12;
      const numDays = sim?.num_days ?? 1;
      const totalTicks = ticksPerDay * numDays;
      const rawEvents = doc.scenario_events as unknown[] | undefined;
      const events = rawEvents ? yamlToEvents(rawEvents) : [];
      return { agentIds, totalTicks, events };
    } catch {
      return null;
    }
  }, [yaml]);

  const handleEventsChange = useCallback((newEvents: ScenarioEvent[]) => {
    try {
      const doc = jsYaml.load(yaml) as Record<string, unknown> | null;
      if (!doc) return;
      // Remove old scenario_events
      delete doc.scenario_events;
      // Serialize without events, then append event YAML block
      let base = jsYaml.dump(doc, { lineWidth: -1, noRefs: true }).trimEnd();
      const evYaml = eventsToYaml(newEvents);
      if (evYaml) {
        base += '\n\n' + evYaml + '\n';
      } else {
        base += '\n';
      }
      setYaml(base);
      setValid(null);
    } catch {
      // if YAML is broken, don't modify
    }
  }, [yaml, setYaml]);

  const validate = useCallback(async () => {
    setValidating(true);
    setValid(null);
    setErrors([]);
    setWarnings([]);
    setSummary(null);
    try {
      const res = await authFetch(`${API_ORIGIN}/api/scenarios/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ yaml_string: yaml }),
      });
      const data = await res.json();
      setValid(data.valid);
      if (data.valid) {
        setSummary(data.summary);
        setWarnings(data.warnings || []);
      } else {
        setErrors(data.errors || ['Unknown error']);
      }
    } catch (e) {
      setErrors([String(e)]);
      setValid(false);
    } finally {
      setValidating(false);
    }
  }, [yaml]);

  const saveAndLaunch = useCallback(async () => {
    setSaving(true);
    try {
      // Save custom scenario
      const saveRes = await authFetch(`${API_ORIGIN}/api/scenarios/custom`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: scenarioName, description: scenarioDesc, yaml_string: yaml }),
      });
      if (!saveRes.ok) {
        const err = await saveRes.json();
        setErrors([err.detail || 'Save failed']);
        setValid(false);
        return;
      }
      const saved = await saveRes.json();

      // Launch game with inline config + game settings
      if (onGameLaunch) {
        onGameLaunch({
          inline_config: saved.config,
          ...gameSettingsToConfig(gameSettings),
          ...(promptProfileConfig ? { prompt_profile: promptProfileConfig.blocks } : {}),
        });
      }
    } catch (e) {
      setErrors([String(e)]);
    } finally {
      setSaving(false);
    }
  }, [yaml, scenarioName, scenarioDesc, onGameLaunch]);

  const handleSaveOnly = useCallback(async () => {
    setSaving(true);
    try {
      if (isEditing && editId) {
        await updateCustomScenario(editId, { name: scenarioName, description: scenarioDesc, yaml_string: yaml });
        setSaveToast({ message: '✅ Updated!', type: 'success' });
      } else {
        await saveCustomScenarioApi({ name: scenarioName, description: scenarioDesc, yaml_string: yaml });
        setSaveToast({ message: '✅ Saved!', type: 'success' });
      }
    } catch (e) {
      setSaveToast({ message: `❌ ${e}`, type: 'error' });
    } finally {
      setSaving(false);
      setTimeout(() => setSaveToast(null), 3000);
    }
  }, [yaml, scenarioName, scenarioDesc, isEditing, editId]);

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-bold mb-1">✏️ Scenario Editor</h2>
        <p className="text-slate-400 text-sm">Write YAML scenarios with live validation. Start from a template or build from scratch.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Editor panel */}
        <div className="lg:col-span-2 space-y-4">
          {/* Template selector + name */}
          <div className="flex gap-3 items-end flex-wrap">
            <div>
              <label className="text-xs text-slate-500 block mb-1">Start from template</label>
              <select
                onChange={e => { setYaml(e.target.value); setValid(null); setSummary(null); setErrors([]); }}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200"
                defaultValue=""
              >
                <option value="" disabled>Choose template…</option>
                {TEMPLATES.map(t => (
                  <option key={t.label} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="text-xs text-slate-500 block mb-1">Scenario name</label>
              <input
                value={scenarioName}
                onChange={e => setScenarioName(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200"
              />
            </div>
          </div>

          <div>
            <label className="text-xs text-slate-500 block mb-1">Description (optional)</label>
            <input
              value={scenarioDesc}
              onChange={e => setScenarioDesc(e.target.value)}
              placeholder="What does this scenario test?"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200"
            />
          </div>

          {/* Mode toggle */}
          <div className="flex items-center gap-1 bg-slate-800 border border-slate-700 rounded-lg p-1 w-fit">
            <button
              onClick={() => {
                if (editorMode === 'yaml') {
                  // Try to parse YAML before switching to form
                  try {
                    jsYaml.load(yaml);
                    setModeSwitchError(null);
                    setEditorMode('form');
                  } catch (e) {
                    setModeSwitchError(`Invalid YAML: ${e instanceof Error ? e.message : String(e)}`);
                  }
                }
              }}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors ${editorMode === 'form' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}
            >
              📋 Form
            </button>
            <button
              onClick={() => { setEditorMode('yaml'); setModeSwitchError(null); }}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors ${editorMode === 'yaml' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}
            >
              📝 YAML
            </button>
          </div>

          {modeSwitchError && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-300">
              ⚠️ {modeSwitchError}
            </div>
          )}

          {/* Editor area */}
          {editorMode === 'yaml' ? (
            <CodeEditor
              value={yaml}
              onChange={(v) => { setYaml(v); setValid(null); }}
              language="yaml"
              height="500px"
            />
          ) : (
            <div>
              <ScenarioForm yaml={yaml} onYamlChange={(v) => { setYaml(v); setValid(null); }} />
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-3 flex-wrap items-center">
            <button
              onClick={validate}
              disabled={validating}
              className="px-5 py-2.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-sm font-medium disabled:opacity-50 transition-colors"
            >
              {validating ? '⏳ Validating…' : '✅ Validate'}
            </button>
            <button
              onClick={handleSaveOnly}
              disabled={saving || valid !== true}
              className="px-5 py-2.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-sm font-medium disabled:opacity-50 transition-colors"
            >
              {saving ? '⏳ Saving…' : isEditing ? '💾 Update' : '💾 Save'}
            </button>
            <button
              onClick={saveAndLaunch}
              disabled={saving || valid !== true}
              className="px-5 py-2.5 rounded-lg bg-gradient-to-r from-violet-500 to-pink-500 hover:from-violet-400 hover:to-pink-400 text-sm font-medium disabled:opacity-50 transition-all"
            >
              {saving ? '⏳ Launching…' : '🚀 Save & Launch'}
            </button>
            {saveToast && (
              <span className={`px-3 py-2 rounded-lg text-sm font-medium ${saveToast.type === 'success' ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300'}`}>
                {saveToast.message}
              </span>
            )}
          </div>

          {/* Game Settings Panel */}
          <GameSettingsPanel
            agentIds={parsedYaml?.agentIds ?? []}
            settings={gameSettings}
            onChange={setGameSettings}
            collapsible
            defaultOpen={false}
          />

          {/* Prompt Configuration Panel */}
          <PromptAnatomyPanel
            onChange={setPromptProfileConfig}
            collapsible
            defaultOpen={false}
            scenarioYaml={yaml}
          />

          {/* Event Timeline Builder */}
          {parsedYaml && (
            <EventTimelineBuilder
              events={parsedYaml.events}
              agentIds={parsedYaml.agentIds}
              totalTicks={parsedYaml.totalTicks}
              onChange={handleEventsChange}
            />
          )}
        </div>

        {/* Preview panel */}
        <div className="space-y-4">
          {/* Validation result */}
          {valid === true && (
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-emerald-400 text-lg">✓</span>
                <span className="text-emerald-300 font-semibold text-sm">Valid Scenario</span>
              </div>
              {warnings.length > 0 && (
                <div className="mt-2 space-y-1">
                  {warnings.map((w, i) => (
                    <p key={i} className="text-xs text-amber-300">⚠️ {w}</p>
                  ))}
                </div>
              )}
            </div>
          )}
          {valid === false && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-red-400 text-lg">✗</span>
                <span className="text-red-300 font-semibold text-sm">Validation Errors</span>
              </div>
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {errors.map((err, i) => (
                  <p key={i} className="text-xs text-red-300/80 font-mono break-all">{err}</p>
                ))}
              </div>
            </div>
          )}

          {/* Summary */}
          {summary && (
            <>
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
                <h3 className="text-sm font-semibold text-slate-300 mb-3">📊 Summary</h3>
                <div className="grid grid-cols-2 gap-3">
                  <Stat label="Agents" value={summary.num_agents} />
                  <Stat label="Ticks/Day" value={summary.ticks_per_day} />
                  <Stat label="Days" value={summary.num_days} />
                  <Stat label="Total Ticks" value={summary.total_ticks} />
                </div>
                <div className="mt-3 text-xs text-slate-400">
                  <span className="font-medium">Banks:</span> {summary.agent_ids.join(', ')}
                </div>
              </div>

              {/* Features */}
              {summary.features.length > 0 && (
                <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
                  <h3 className="text-sm font-semibold text-slate-300 mb-2">🏷️ Features</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {summary.features.map(f => (
                      <span key={f} className="px-2 py-0.5 bg-violet-500/20 text-violet-300 rounded-full text-xs">{f}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Cost config */}
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
                <h3 className="text-sm font-semibold text-slate-300 mb-3">💰 Cost Parameters</h3>
                <div className="space-y-2 text-xs">
                  <CostRow label="Liquidity (bps/tick)" value={summary.cost_config.liquidity_cost_per_tick_bps} />
                  <CostRow label="Delay (per ¢/tick)" value={summary.cost_config.delay_cost_per_tick_per_cent} />
                  <CostRow label="EOD Penalty" value={`$${(summary.cost_config.eod_penalty_per_transaction / 100).toLocaleString()}`} />
                  <CostRow label="Deadline Penalty" value={`$${(summary.cost_config.deadline_penalty / 100).toLocaleString()}`} />
                </div>
              </div>
            </>
          )}

          {!summary && valid === null && (
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 text-center">
              <p className="text-slate-500 text-sm">Click <strong>Validate</strong> to see scenario summary</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-lg font-bold text-slate-200">{value}</div>
    </div>
  );
}

function CostRow({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-400">{label}</span>
      <span className="text-slate-200 font-mono">{value}</span>
    </div>
  );
}
