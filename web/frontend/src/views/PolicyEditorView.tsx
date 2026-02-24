import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { authFetch, API_ORIGIN, getCustomPolicy, updateCustomPolicy as updateCustomPolicyApi } from '../api';
import type { GameSetupConfig } from '../types';
import { CodeEditor } from '../components/CodeEditor';

const BASE = `${API_ORIGIN}/api`;

interface ValidationSummary {
  trees_present: string[];
  actions_used: string[];
  fields_used: string[];
  node_count: number;
  parameters: Record<string, unknown>;
  policy_id: string;
  version: string;
}

interface ValidationResult {
  valid: boolean;
  errors: string[];
  summary: ValidationSummary | null;
}

interface LibraryPolicy {
  policy_id: string;
  name: string;
  description: string;
}

// ---- Templates ----

const TEMPLATES: Record<string, { label: string; json: object }> = {
  release_all: {
    label: 'Release All (FIFO)',
    json: {
      version: '2.0',
      policy_id: 'custom_release_all',
      parameters: { initial_liquidity_fraction: 1.0 },
      payment_tree: { type: 'action', node_id: 'root', action: 'Release' },
      bank_tree: { type: 'action', node_id: 'bank', action: 'NoAction' },
    },
  },
  balance_hold: {
    label: 'Balance-Aware Hold',
    json: {
      version: '2.0',
      policy_id: 'custom_balance_hold',
      parameters: { initial_liquidity_fraction: 0.5, hold_threshold: 50000 },
      payment_tree: {
        type: 'condition', node_id: 'check_balance',
        condition: { op: '>=', left: { field: 'balance' }, right: { param: 'hold_threshold' } },
        on_true: { type: 'action', node_id: 'release', action: 'Release' },
        on_false: {
          type: 'condition', node_id: 'check_urgent',
          condition: { op: '<=', left: { field: 'ticks_to_deadline' }, right: { value: 2 } },
          on_true: { type: 'action', node_id: 'release_urgent', action: 'Release' },
          on_false: { type: 'action', node_id: 'hold', action: 'Hold' },
        },
      },
      bank_tree: { type: 'action', node_id: 'bank', action: 'NoAction' },
    },
  },
  deadline_driven: {
    label: 'Deadline-Driven',
    json: {
      version: '2.0',
      policy_id: 'custom_deadline_driven',
      parameters: { initial_liquidity_fraction: 0.6, urgent_threshold: 3 },
      payment_tree: {
        type: 'condition', node_id: 'check_deadline',
        condition: { op: '<=', left: { field: 'ticks_to_deadline' }, right: { param: 'urgent_threshold' } },
        on_true: { type: 'action', node_id: 'release_urgent', action: 'Release' },
        on_false: { type: 'action', node_id: 'hold', action: 'Hold' },
      },
      bank_tree: { type: 'action', node_id: 'bank', action: 'NoAction' },
    },
  },
  smart_splitter: {
    label: 'Smart Splitter',
    json: {
      version: '2.0',
      policy_id: 'custom_smart_splitter',
      parameters: { initial_liquidity_fraction: 0.5, split_threshold: 100000 },
      payment_tree: {
        type: 'condition', node_id: 'check_amount',
        condition: { op: '>=', left: { field: 'amount' }, right: { param: 'split_threshold' } },
        on_true: { type: 'action', node_id: 'split', action: 'Split' },
        on_false: { type: 'action', node_id: 'release', action: 'Release' },
      },
      bank_tree: { type: 'action', node_id: 'bank', action: 'NoAction' },
    },
  },
};

interface SavedPolicy {
  id: string;
  name: string;
  json_string: string;
}

async function validatePolicy(jsonString: string): Promise<ValidationResult> {
  const res = await authFetch(`${BASE}/policies/editor/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ json_string: jsonString }),
  });
  return res.json();
}

async function fetchPolicyLibrary(): Promise<LibraryPolicy[]> {
  try {
    const res = await authFetch(`${BASE}/policies/library`);
    const data = await res.json();
    return data.policies || [];
  } catch {
    return [];
  }
}

async function fetchPolicyDetail(policyId: string): Promise<string | null> {
  try {
    const res = await authFetch(`${BASE}/policies/library/${policyId}`);
    const data = await res.json();
    return JSON.stringify(data.raw_json || data, null, 2);
  } catch {
    return null;
  }
}

async function fetchCustomPolicies(): Promise<SavedPolicy[]> {
  try {
    const res = await authFetch(`${BASE}/policies/custom`);
    const data = await res.json();
    return data.policies || [];
  } catch {
    return [];
  }
}

async function saveCustomPolicy(jsonString: string, name: string, description: string = ''): Promise<{ ok: boolean; error?: string; policy?: SavedPolicy }> {
  try {
    const res = await authFetch(`${BASE}/policies/custom`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ json_string: jsonString, name, description }),
    });
    if (!res.ok) {
      const data = await res.json();
      return { ok: false, error: data.detail || 'Save failed' };
    }
    const policy = await res.json();
    return { ok: true, policy };
  } catch (e) {
    return { ok: false, error: `${e}` };
  }
}

interface PolicyEditorProps {
  onGameLaunch?: (config: GameSetupConfig) => void;
  initialJsonText?: string;
  onJsonTextChange?: (text: string) => void;
}

export function PolicyEditorView({ onGameLaunch, initialJsonText, onJsonTextChange }: PolicyEditorProps) {
  const [searchParams] = useSearchParams();
  const editPolicyId = searchParams.get('editPolicy');
  const [isEditing, setIsEditing] = useState(false);
  const [policyName, setPolicyName] = useState('');
  const [policyDesc, setPolicyDesc] = useState('');
  const [jsonText, setJsonTextRaw] = useState(() => initialJsonText ?? JSON.stringify(TEMPLATES.release_all.json, null, 2));

  const setJsonText = useCallback((v: string) => {
    setJsonTextRaw(v);
    onJsonTextChange?.(v);
  }, [onJsonTextChange]);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [libraryPolicies, setLibraryPolicies] = useState<LibraryPolicy[]>([]);
  const [savedPolicies, setSavedPolicies] = useState<SavedPolicy[]>([]);
  const [saveToast, setSaveToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    fetchPolicyLibrary().then(setLibraryPolicies);
    fetchCustomPolicies().then(setSavedPolicies);
  }, []);

  // Load policy for editing
  useEffect(() => {
    if (editPolicyId) {
      getCustomPolicy(editPolicyId).then(p => {
        setJsonTextRaw(p.json_string);
        setPolicyName(p.name);
        setPolicyDesc(p.description);
        setIsEditing(true);
      }).catch(() => {
        setResult({ valid: false, errors: ['Failed to load policy for editing'], summary: null });
      });
    }
  }, [editPolicyId]);

  const handleValidate = useCallback(async () => {
    setLoading(true);
    try {
      const r = await validatePolicy(jsonText);
      setResult(r);
    } catch (e) {
      setResult({ valid: false, errors: [`Request failed: ${e}`], summary: null });
    }
    setLoading(false);
  }, [jsonText]);

  const handleTemplate = useCallback((key: string) => {
    const t = TEMPLATES[key];
    if (t) {
      const text = JSON.stringify(t.json, null, 2);
      setJsonText(text);
      setResult(null);
    }
  }, [setJsonText]);

  const handleLoadLibrary = useCallback(async (policyId: string) => {
    if (!policyId) return;
    const detail = await fetchPolicyDetail(policyId);
    if (detail) {
      setJsonText(detail);
      setResult(null);
    }
  }, [setJsonText]);

  const handleSave = useCallback(async () => {
    try {
      if (isEditing && editPolicyId) {
        const name = policyName || JSON.parse(jsonText).policy_id || `custom_${Date.now()}`;
        await updateCustomPolicyApi(editPolicyId, { name, description: policyDesc, json_string: jsonText });
        setSaveToast({ message: '✅ Updated!', type: 'success' });
      } else {
        const parsed = JSON.parse(jsonText);
        const name = policyName || parsed.policy_id || `custom_${Date.now()}`;
        const res = await saveCustomPolicy(jsonText, name, policyDesc);
        if (res.ok) {
          setSaveToast({ message: '✅ Saved!', type: 'success' });
          fetchCustomPolicies().then(setSavedPolicies);
        } else {
          setSaveToast({ message: `❌ ${res.error}`, type: 'error' });
          setTimeout(() => setSaveToast(null), 3000);
          return;
        }
      }
      fetchCustomPolicies().then(setSavedPolicies);
    } catch {
      setSaveToast({ message: '❌ Invalid JSON', type: 'error' });
    }
    setTimeout(() => setSaveToast(null), 3000);
  }, [jsonText, isEditing, editPolicyId, policyName, policyDesc]);

  const handleTestPolicy = useCallback(() => {
    if (!onGameLaunch) return;
    try {
      const parsed = JSON.parse(jsonText);
      // Create a quick 1-day game with this policy
      onGameLaunch({
        scenario_id: 'gridlock_risk',
        rounds: 1,
        use_llm: false,
        simulated_ai: true,
        num_eval_samples: 1,
        inline_config: {
          simulation: { ticks_per_day: 12, num_days: 1 },
          agents: [
            { name: 'Agent_A', policy: { type: 'InlineJson', json_string: JSON.stringify(parsed) } },
            { name: 'Agent_B', policy: { type: 'InlineJson', json_string: JSON.stringify(parsed) } },
          ],
        },
      });
    } catch {
      setResult({ valid: false, errors: ['Cannot test: invalid JSON'], summary: null });
    }
  }, [jsonText, onGameLaunch]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-100">🛠️ Policy Editor</h2>
          <p className="text-sm text-slate-400 mt-1">Create and validate policy decision trees</p>
        </div>
      </div>

      {/* Controls row */}
      <div className="flex flex-wrap gap-3">
        <select
          onChange={e => handleTemplate(e.target.value)}
          defaultValue=""
          className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-sky-500 focus:outline-none"
        >
          <option value="" disabled>Start from template…</option>
          {Object.entries(TEMPLATES).map(([key, t]) => (
            <option key={key} value={key}>{t.label}</option>
          ))}
        </select>

        {libraryPolicies.length > 0 && (
          <select
            onChange={e => handleLoadLibrary(e.target.value)}
            defaultValue=""
            className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-sky-500 focus:outline-none"
          >
            <option value="" disabled>Load from library…</option>
            {libraryPolicies.map(p => (
              <option key={p.policy_id} value={p.policy_id}>{p.name || p.policy_id}</option>
            ))}
          </select>
        )}

        {savedPolicies.length > 0 && (
          <select
            onChange={e => {
              const p = savedPolicies.find(sp => sp.id === e.target.value);
              if (p) { setJsonText(p.json_string); setResult(null); }
            }}
            defaultValue=""
            className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-sky-500 focus:outline-none"
          >
            <option value="" disabled>Load saved…</option>
            {savedPolicies.map(p => (
              <option key={p.id} value={p.id}>{p.name || p.id}</option>
            ))}
          </select>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Editor */}
        <div className="lg:col-span-2 space-y-3">
          <CodeEditor
            value={jsonText}
            onChange={(v) => { setJsonText(v); setResult(null); }}
            language="json"
            height="500px"
          />
          <div className="flex gap-3">
            <button
              onClick={handleValidate}
              disabled={loading}
              className="px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              {loading ? '⏳ Validating…' : '✅ Validate'}
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm font-medium transition-colors"
            >
              {isEditing ? '💾 Update' : '💾 Save'}
            </button>
            {saveToast && (
              <span className={`px-3 py-2 rounded-lg text-sm font-medium ${saveToast.type === 'success' ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300'}`}>
                {saveToast.message}
              </span>
            )}
            {onGameLaunch && (
              <button
                onClick={handleTestPolicy}
                className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-sm font-medium transition-colors"
              >
                🧪 Test Policy
              </button>
            )}
          </div>
        </div>

        {/* Results panel */}
        <div className="space-y-4">
          {result && (
            <div className={`rounded-lg border p-4 ${result.valid ? 'border-green-600 bg-green-900/20' : 'border-red-600 bg-red-900/20'}`}>
              <div className="flex items-center gap-2 mb-2">
                {result.valid ? (
                  <span className="text-green-400 text-lg">✅ Valid</span>
                ) : (
                  <span className="text-red-400 text-lg">❌ Invalid</span>
                )}
              </div>
              {!result.valid && result.errors.length > 0 && (
                <ul className="space-y-1">
                  {result.errors.map((err, i) => (
                    <li key={i} className="text-sm text-red-300 font-mono">• {err}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {result?.summary && (
            <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4 space-y-3">
              <h3 className="text-sm font-semibold text-slate-300">Summary</h3>
              <div className="space-y-2 text-sm">
                <div>
                  <span className="text-slate-400">Policy ID:</span>{' '}
                  <span className="text-slate-200 font-mono">{result.summary.policy_id}</span>
                </div>
                <div>
                  <span className="text-slate-400">Version:</span>{' '}
                  <span className="text-slate-200">{result.summary.version}</span>
                </div>
                <div>
                  <span className="text-slate-400">Trees:</span>{' '}
                  <span className="text-slate-200">{result.summary.trees_present.join(', ')}</span>
                </div>
                <div>
                  <span className="text-slate-400">Actions:</span>{' '}
                  <div className="flex flex-wrap gap-1 mt-1">
                    {result.summary.actions_used.map(a => (
                      <span key={a} className="px-2 py-0.5 bg-sky-900/50 text-sky-300 rounded text-xs font-mono">{a}</span>
                    ))}
                  </div>
                </div>
                {result.summary.fields_used.length > 0 && (
                  <div>
                    <span className="text-slate-400">Context fields:</span>{' '}
                    <div className="flex flex-wrap gap-1 mt-1">
                      {result.summary.fields_used.map(f => (
                        <span key={f} className="px-2 py-0.5 bg-violet-900/50 text-violet-300 rounded text-xs font-mono">{f}</span>
                      ))}
                    </div>
                  </div>
                )}
                <div>
                  <span className="text-slate-400">Node count:</span>{' '}
                  <span className="text-slate-200">{result.summary.node_count}</span>
                </div>
                <div>
                  <span className="text-slate-400">Parameters:</span>
                  <pre className="mt-1 text-xs text-slate-300 bg-slate-900 rounded p-2 overflow-x-auto">
                    {JSON.stringify(result.summary.parameters, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          )}

          {!result && (
            <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4 text-sm text-slate-500">
              Click <strong>Validate</strong> to check your policy JSON
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
