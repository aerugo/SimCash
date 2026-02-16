import { useEffect, useState, useCallback } from 'react';
import type { SimulationState, TickResult } from '../types';
import { getReplayInfo, getReplayTick } from '../api';
import { BalanceChart } from '../components/BalanceChart';
import { AgentCards } from '../components/AgentCards';
import { PaymentFlow } from '../components/PaymentFlow';

export function ReplayView({ simId, state }: { simId: string; state: SimulationState }) {
  const [totalTicks, setTotalTicks] = useState(0);
  const [currentTick, setCurrentTick] = useState(0);
  const [tickData, setTickData] = useState<TickResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getReplayInfo(simId).then(info => {
      setTotalTicks(info.total_recorded_ticks);
    });
  }, [simId]);

  const loadTick = useCallback(async (tick: number) => {
    if (tick < 0 || tick >= totalTicks) return;
    setLoading(true);
    try {
      const data = await getReplayTick(simId, tick);
      setTickData(data);
      setCurrentTick(tick);
    } finally {
      setLoading(false);
    }
  }, [simId, totalTicks]);

  useEffect(() => {
    if (totalTicks > 0) loadTick(0);
  }, [totalTicks, loadTick]);

  if (!state.is_complete) {
    return (
      <div className="text-center py-20">
        <div className="text-4xl mb-4">🔄</div>
        <h2 className="text-xl font-bold mb-2">Simulation Not Complete</h2>
        <p className="text-slate-400">Complete the simulation first to use replay mode.</p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">🔄 Replay Mode</h2>

      {/* Scrubber */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 mb-6">
        <div className="flex items-center gap-4">
          <button
            onClick={() => loadTick(Math.max(0, currentTick - 1))}
            disabled={currentTick <= 0 || loading}
            className="px-3 py-1 rounded bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-sm"
          >
            ◀
          </button>

          <div className="flex-1">
            <input
              type="range"
              min={0}
              max={Math.max(0, totalTicks - 1)}
              value={currentTick}
              onChange={e => loadTick(Number(e.target.value))}
              className="w-full accent-sky-400"
            />
          </div>

          <button
            onClick={() => loadTick(Math.min(totalTicks - 1, currentTick + 1))}
            disabled={currentTick >= totalTicks - 1 || loading}
            className="px-3 py-1 rounded bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-sm"
          >
            ▶
          </button>

          <span className="text-sm font-mono text-slate-400 w-24 text-center">
            Tick {currentTick}/{totalTicks - 1}
          </span>
        </div>
      </div>

      {tickData && (
        <div className="space-y-6">
          <AgentCards agents={tickData.agents} />

          {tickData.balance_history && Object.keys(tickData.balance_history).length > 0 && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
              <h3 className="text-sm font-semibold text-slate-300 mb-4">Balances (up to tick {currentTick})</h3>
              <BalanceChart history={tickData.balance_history} />
            </div>
          )}

          <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Tick {currentTick} Activity</h3>
            <PaymentFlow events={tickData.events} currentTick={currentTick} />
          </div>
        </div>
      )}
    </div>
  );
}
