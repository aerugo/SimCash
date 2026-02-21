import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { GameSetupConfig } from '../types';
import { ScenarioEditorView } from './ScenarioEditorView';
import { PolicyEditorView } from './PolicyEditorView';
import { useGameContext } from '../GameContext';

export function CreateView() {
  const { handleGameLaunch, scenarioEditorState, setScenarioEditorState: onScenarioEditorStateChange, policyEditorJsonText, setPolicyEditorJsonText: onPolicyEditorJsonTextChange } = useGameContext();
  const navigate = useNavigate();
  const onGameLaunch = async (config: GameSetupConfig) => {
    const gid = await handleGameLaunch(config);
    if (gid) navigate(`/experiment/${gid}`);
  };
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState<'scenario' | 'policy'>('scenario');

  // Auto-switch to policy tab if editPolicy param is present
  useEffect(() => {
    if (searchParams.get('editPolicy')) {
      setMode('policy');
    }
  }, [searchParams]);

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <h2 className="text-xl font-bold text-slate-100">✏️ Create</h2>
        <div className="flex gap-1 bg-slate-800 rounded-lg p-1">
          <button
            onClick={() => setMode('scenario')}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              mode === 'scenario' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            🎬 Scenario
          </button>
          <button
            onClick={() => setMode('policy')}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              mode === 'policy' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            🧠 Policy
          </button>
        </div>
      </div>

      {mode === 'scenario' && <ScenarioEditorView initialState={scenarioEditorState} onStateChange={onScenarioEditorStateChange} />}
      {mode === 'policy' && <PolicyEditorView onGameLaunch={onGameLaunch} initialJsonText={policyEditorJsonText} onJsonTextChange={onPolicyEditorJsonTextChange} />}
    </div>
  );
}
