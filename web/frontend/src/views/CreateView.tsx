import { useState } from 'react';
import type { GameSetupConfig } from '../types';
import { ScenarioEditorView } from './ScenarioEditorView';
import { PolicyEditorView } from './PolicyEditorView';

interface Props {
  onGameLaunch: (config: GameSetupConfig) => void;
}

export function CreateView({ onGameLaunch }: Props) {
  const [mode, setMode] = useState<'scenario' | 'policy'>('scenario');

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

      {mode === 'scenario' && <ScenarioEditorView onGameLaunch={onGameLaunch} />}
      {mode === 'policy' && <PolicyEditorView onGameLaunch={onGameLaunch} />}
    </div>
  );
}
