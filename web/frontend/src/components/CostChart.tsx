import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import type { CostBreakdown } from '../types';

export function CostChart({ history }: { history: Record<string, CostBreakdown[]> }) {
  const agents = Object.keys(history);
  if (agents.length === 0) return null;

  // Show final accumulated costs per agent
  const data = agents.map(agent => {
    const costs = history[agent];
    const latest = costs[costs.length - 1] ?? { liquidity_cost: 0, delay_cost: 0, penalty_cost: 0, total: 0 };
    return {
      agent,
      Liquidity: latest.liquidity_cost,
      Delay: latest.delay_cost,
      Penalties: latest.penalty_cost,
    };
  });

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="agent" stroke="#64748b" tick={{ fontSize: 12 }} />
        <YAxis stroke="#64748b" tick={{ fontSize: 12 }} tickFormatter={(v: number) => `$${v.toFixed(0)}`} />
        <Tooltip
          contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
          labelStyle={{ color: '#94a3b8' }}
        />
        <Legend />
        <Bar dataKey="Liquidity" fill="#38bdf8" radius={[4, 4, 0, 0]} />
        <Bar dataKey="Delay" fill="#fbbf24" radius={[4, 4, 0, 0]} />
        <Bar dataKey="Penalties" fill="#f87171" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
