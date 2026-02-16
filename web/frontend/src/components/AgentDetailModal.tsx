import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import type { AgentState, CostBreakdown } from '../types';
import { fmtDollars, fmtCost } from '../utils';

interface Props {
  agentId: string;
  agent: AgentState;
  balanceHistory?: number[];
  costHistory?: CostBreakdown[];
  onClose: () => void;
}

export function AgentDetailModal({ agentId, agent, balanceHistory, costHistory, onClose }: Props) {
  const balData = (balanceHistory ?? []).map((b, i) => ({ tick: i, balance: b / 100 }));
  const costData = (costHistory ?? []).map((c, i) => ({
    tick: i,
    liquidity: c.liquidity_cost,
    delay: c.delay_cost,
    penalty: c.penalty_cost,
    total: c.total,
  }));

  const tooltipStyle = {
    contentStyle: { background: '#1e293b', border: '1px solid #334155', borderRadius: '8px' },
    labelStyle: { color: '#94a3b8' },
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6 w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-sky-400">{agentId} — Detail View</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xl">✕</button>
        </div>

        {/* Current state */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatBox label="Balance" value={fmtDollars(agent.balance)} color={agent.balance >= 0 ? 'text-green-400' : 'text-red-400'} />
          <StatBox label="Available Liquidity" value={fmtDollars(agent.available_liquidity)} color="text-slate-200" />
          <StatBox label="Queue Size" value={String(agent.queue1_size)} color="text-amber-300" />
          <StatBox label="Total Cost" value={fmtCost(agent.costs.total)} color="text-slate-100" />
        </div>

        {/* Balance over time */}
        {balData.length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Balance Over Time</h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={balData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="tick" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} tickFormatter={(v: number) => `$${v}`} />
                <Tooltip {...tooltipStyle} formatter={((v: any) => [`$${Number(v??0).toFixed(2)}`, 'Balance']) as any} />
                <Line type="monotone" dataKey="balance" stroke="#38bdf8" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Cost breakdown over time */}
        {costData.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Cost Breakdown Over Time</h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={costData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="tick" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} tickFormatter={(v: number) => `$${v.toFixed(0)}`} />
                <Tooltip {...tooltipStyle} />
                <Legend />
                <Line type="monotone" dataKey="liquidity" stroke="#38bdf8" strokeWidth={2} name="Liquidity" />
                <Line type="monotone" dataKey="delay" stroke="#fbbf24" strokeWidth={2} name="Delay" />
                <Line type="monotone" dataKey="penalty" stroke="#f87171" strokeWidth={2} name="Penalty" />
                <Line type="monotone" dataKey="total" stroke="#94a3b8" strokeWidth={2} strokeDasharray="5 5" name="Total" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-slate-900/50 rounded-lg p-3">
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      <div className={`font-mono font-semibold ${color}`}>{value}</div>
    </div>
  );
}
