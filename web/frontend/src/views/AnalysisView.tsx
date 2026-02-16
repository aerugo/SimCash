import { useState } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import type { SimulationState, SimEvent } from '../types';
import { fmtCost, getAgentColor } from '../utils';
import { exportSimulation } from '../api';
import { toast } from '../components/Toast';

const COST_COLORS = ['#38bdf8', '#fbbf24', '#f87171'];

export function AnalysisView({ state, events, simId }: { state: SimulationState; events: SimEvent[]; simId: string }) {
  const [exporting, setExporting] = useState(false);

  if (!state.is_complete) {
    return (
      <div className="text-center py-20">
        <div className="text-4xl mb-4">📈</div>
        <h2 className="text-xl font-bold mb-2">Analysis Available After Completion</h2>
        <p className="text-slate-400">Run the simulation to completion to see analysis.</p>
      </div>
    );
  }

  const agents = Object.entries(state.agents);
  const totalSystemCost = agents.reduce((s, [, a]) => s + a.costs.total, 0);

  // Settlement tracking
  const settlements = events.filter(e => e.event_type === 'RtgsImmediateSettlement' || e.event_type === 'RtgsQueue2Settle');
  const arrivals = events.filter(e => e.event_type === 'Arrival');
  const overdue = events.filter(e => e.event_type === 'TransactionWentOverdue');

  const handleExport = async () => {
    setExporting(true);
    try {
      const data = await exportSimulation(simId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `simcash-${simId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast('Export downloaded', 'success');
    } catch {
      toast('Export failed', 'error');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold">📈 Post-Simulation Analysis</h2>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-sm font-medium"
        >
          📥 Export Full Data
        </button>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <MetricCard label="Total System Cost" value={fmtCost(totalSystemCost)} />
        <MetricCard label="Total Arrivals" value={String(arrivals.length)} />
        <MetricCard label="Total Settlements" value={String(settlements.length)} />
        <MetricCard label="Overdue" value={String(overdue.length)} color={overdue.length > 0 ? 'text-red-400' : 'text-green-400'} />
        <MetricCard label="Settlement Rate" value={arrivals.length > 0 ? `${Math.round(settlements.length / arrivals.length * 100)}%` : 'N/A'} />
      </div>

      {/* Cost Pie Charts per Agent */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
        {agents.map(([id, agent]) => {
          const data = [
            { name: 'Liquidity', value: agent.costs.liquidity_cost },
            { name: 'Delay', value: agent.costs.delay_cost },
            { name: 'Penalty', value: agent.costs.penalty_cost },
          ].filter(d => d.value > 0);

          if (data.length === 0) {
            return (
              <div key={id} className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
                <h3 className="text-sm font-semibold text-slate-300 mb-2">{id} Cost Breakdown</h3>
                <div className="text-sm text-slate-500 italic">No costs incurred</div>
              </div>
            );
          }

          return (
            <div key={id} className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
              <h3 className="text-sm font-semibold text-slate-300 mb-2">{id} — {fmtCost(agent.costs.total)}</h3>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={data} dataKey="value" cx="50%" cy="50%" outerRadius={60} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                    {data.map((_, i) => <Cell key={i} fill={COST_COLORS[i % COST_COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }} formatter={(v: number) => fmtCost(v)} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          );
        })}
      </div>

      {/* Payment Flow Table */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 mb-6">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Payment Flow Summary</h3>
        <div className="overflow-auto max-h-80">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-slate-500 border-b border-slate-700">
                <th className="text-left py-2 px-2">Tick</th>
                <th className="text-left py-2 px-2">Type</th>
                <th className="text-left py-2 px-2">From</th>
                <th className="text-left py-2 px-2">To</th>
                <th className="text-right py-2 px-2">Amount</th>
              </tr>
            </thead>
            <tbody>
              {[...arrivals, ...settlements].sort((a, b) => a.tick - b.tick).map((ev, i) => (
                <tr key={i} className="border-b border-slate-800 hover:bg-slate-700/30">
                  <td className="py-1.5 px-2 font-mono text-slate-400">{ev.tick}</td>
                  <td className="py-1.5 px-2">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${ev.event_type === 'Arrival' ? 'bg-sky-500/20 text-sky-300' : 'bg-emerald-500/20 text-emerald-300'}`}>
                      {ev.event_type === 'Arrival' ? 'Arrival' : 'Settled'}
                    </span>
                  </td>
                  <td className="py-1.5 px-2 font-mono">{(ev.sender_id || ev.sender) as string}</td>
                  <td className="py-1.5 px-2 font-mono">{(ev.receiver_id || ev.receiver) as string}</td>
                  <td className="py-1.5 px-2 font-mono text-right">${((ev.amount as number) / 100).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Agent comparison bar */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Agent Cost Comparison</h3>
        <div className="space-y-3">
          {agents.map(([id, agent], i) => {
            const pct = totalSystemCost > 0 ? (agent.costs.total / totalSystemCost) * 100 : 0;
            return (
              <div key={id} className="flex items-center gap-3">
                <span className="w-20 text-sm font-mono">{id}</span>
                <div className="flex-1 bg-slate-900 rounded-full h-4 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${pct}%`, backgroundColor: getAgentColor(id, i) }}
                  />
                </div>
                <span className="w-24 text-right text-sm font-mono text-slate-300">{fmtCost(agent.costs.total)}</span>
                <span className="w-12 text-right text-xs text-slate-500">{pct.toFixed(0)}%</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, color = 'text-slate-100' }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      <div className={`text-lg font-bold font-mono ${color}`}>{value}</div>
    </div>
  );
}
