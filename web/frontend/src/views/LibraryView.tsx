import { useEffect, useState } from 'react';
import type { SavedScenario, ScenarioConfig } from '../types';
import { listScenarios, saveScenario, deleteScenario } from '../api';
import { toast } from '../components/Toast';

interface Props {
  onLaunch: (config: ScenarioConfig) => void;
}

export function LibraryView({ onLaunch }: Props) {
  const [scenarios, setScenarios] = useState<SavedScenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');

  const refresh = () => {
    setLoading(true);
    listScenarios().then(setScenarios).finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    await saveScenario({
      name: newName,
      description: newDesc,
      config: {
        preset: null,
        ticks_per_day: 3,
        num_days: 1,
        rng_seed: 42,
        agents: [
          { id: 'BANK_A', agent_type: 'ai', liquidity_pool: 100_000, opening_balance: 0, unsecured_cap: 0 },
          { id: 'BANK_B', agent_type: 'ai', liquidity_pool: 100_000, opening_balance: 0, unsecured_cap: 0 },
        ],
        liquidity_cost_per_tick_bps: 333,
        delay_cost_per_tick_per_cent: 0.2,
        eod_penalty_per_transaction: 100_000,
        deadline_penalty: 50_000,
        deferred_crediting: true,
        deadline_cap_at_eod: true,
        payment_schedule: [],
        enable_bilateral_lsm: false,
        enable_cycle_lsm: false,
        use_llm: false,
        mock_reasoning: true,
      },
    });
    toast(`Scenario "${newName}" created`, 'success');
    setShowCreate(false);
    setNewName('');
    setNewDesc('');
    refresh();
  };

  const handleDelete = async (id: string, name: string) => {
    await deleteScenario(id);
    toast(`Deleted "${name}"`, 'info');
    refresh();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold">🎮 Scenario Library</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-sm font-medium"
        >
          + New Scenario
        </button>
      </div>

      {showCreate && (
        <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 mb-6">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Create New Scenario</h3>
          <div className="space-y-3">
            <input
              placeholder="Scenario Name"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-sky-500"
            />
            <input
              placeholder="Description"
              value={newDesc}
              onChange={e => setNewDesc(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-sky-500"
            />
            <div className="flex gap-2">
              <button onClick={handleCreate} className="px-4 py-2 rounded-lg bg-green-600 hover:bg-green-500 text-sm font-medium">Save</button>
              <button onClick={() => setShowCreate(false)} className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-sm font-medium">Cancel</button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-slate-500">Loading...</div>
      ) : scenarios.length === 0 ? (
        <div className="text-center py-20 text-slate-500">
          <div className="text-4xl mb-4">📁</div>
          <p>No saved scenarios yet. Create one to get started!</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {scenarios.map(s => (
            <div key={s.id} className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-semibold text-slate-100">{s.name}</h3>
                <span className="text-xs text-slate-500 font-mono">{s.id}</span>
              </div>
              {s.description && <p className="text-sm text-slate-400 mb-3">{s.description}</p>}
              <div className="flex gap-2 text-xs text-slate-500 mb-3">
                <span>{s.config.ticks_per_day} ticks/day</span>
                <span>·</span>
                <span>{s.config.agents?.length || 0} banks</span>
                <span>·</span>
                <span>{s.config.payment_schedule?.length || 0} payments</span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => onLaunch(s.config)}
                  className="px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-xs font-medium"
                >
                  🚀 Launch
                </button>
                <button
                  onClick={() => handleDelete(s.id, s.name)}
                  className="px-3 py-1.5 rounded-lg bg-red-600/20 hover:bg-red-600/40 text-red-300 text-xs font-medium"
                >
                  🗑 Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
