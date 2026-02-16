import type { SimulationState } from '../types';
import { fmtDollars, fmtCost } from '../utils';

export function SimulationSummary({ state }: { state: SimulationState }) {
  if (!state.is_complete) return null;

  const agents = Object.entries(state.agents);
  const totalCost = agents.reduce((sum, [, a]) => sum + a.costs.total, 0);
  const totalLiquidity = agents.reduce((sum, [, a]) => sum + a.costs.liquidity_cost, 0);
  const totalDelay = agents.reduce((sum, [, a]) => sum + a.costs.delay_cost, 0);
  const totalPenalty = agents.reduce((sum, [, a]) => sum + a.costs.penalty_cost, 0);
  const lowestCostAgent = agents.reduce((best, curr) => curr[1].costs.total < best[1].costs.total ? curr : best);

  return (
    <div className="bg-gradient-to-br from-green-900/30 to-emerald-900/20 rounded-xl border border-green-700/50 p-6">
      <h3 className="text-lg font-bold text-green-400 mb-4">🏁 Simulation Complete</h3>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className="bg-slate-900/50 rounded-lg p-3">
          <div className="text-xs text-slate-500">Total Ticks</div>
          <div className="text-xl font-bold text-slate-100">{state.total_ticks}</div>
        </div>
        <div className="bg-slate-900/50 rounded-lg p-3">
          <div className="text-xs text-slate-500">System Cost</div>
          <div className="text-xl font-bold text-amber-300">{fmtCost(totalCost)}</div>
        </div>
        <div className="bg-slate-900/50 rounded-lg p-3">
          <div className="text-xs text-slate-500">Best Performer</div>
          <div className="text-xl font-bold text-green-400">{lowestCostAgent[0]}</div>
          <div className="text-xs text-slate-500">{fmtCost(lowestCostAgent[1].costs.total)}</div>
        </div>
        <div className="bg-slate-900/50 rounded-lg p-3">
          <div className="text-xs text-slate-500">Agents</div>
          <div className="text-xl font-bold text-slate-100">{agents.length}</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 text-sm">
        <div className="text-center">
          <div className="text-blue-300 font-mono font-semibold">{fmtCost(totalLiquidity)}</div>
          <div className="text-xs text-slate-500">Liquidity Costs</div>
        </div>
        <div className="text-center">
          <div className="text-amber-300 font-mono font-semibold">{fmtCost(totalDelay)}</div>
          <div className="text-xs text-slate-500">Delay Costs</div>
        </div>
        <div className="text-center">
          <div className="text-red-300 font-mono font-semibold">{fmtCost(totalPenalty)}</div>
          <div className="text-xs text-slate-500">Penalties</div>
        </div>
      </div>
    </div>
  );
}
