import { useState } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import type { CostBreakdown } from '../types';
import { getAgentColor } from '../utils';

export function CostChart({ history }: { history: Record<string, CostBreakdown[]> }) {
  const agents = Object.keys(history);
  const [view, setView] = useState<'line' | 'bar'>('line');

  if (agents.length === 0) return null;

  const tooltipStyle = {
    contentStyle: { background: '#1e293b', border: '1px solid #334155', borderRadius: '8px' },
    labelStyle: { color: '#94a3b8' },
  };

  if (view === 'bar') {
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
      <div>
        <div className="flex justify-end mb-2">
          <ViewToggle view={view} onChange={setView} />
        </div>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="agent" stroke="#64748b" tick={{ fontSize: 12 }} />
            <YAxis stroke="#64748b" tick={{ fontSize: 12 }} tickFormatter={(v: number) => `$${v.toFixed(0)}`} />
            <Tooltip {...tooltipStyle} />
            <Legend />
            <Bar dataKey="Liquidity" fill="#38bdf8" radius={[4, 4, 0, 0]} />
            <Bar dataKey="Delay" fill="#fbbf24" radius={[4, 4, 0, 0]} />
            <Bar dataKey="Penalties" fill="#f87171" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Line chart: total cost over time per agent
  const maxLen = Math.max(...agents.map(a => history[a].length));
  const data = Array.from({ length: maxLen }, (_, i) => {
    const point: Record<string, number> = { tick: i };
    for (const agent of agents) {
      point[agent] = history[agent]?.[i]?.total ?? 0;
    }
    return point;
  });

  return (
    <div>
      <div className="flex justify-end mb-2">
        <ViewToggle view={view} onChange={setView} />
      </div>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="tick" stroke="#64748b" tick={{ fontSize: 12 }} />
          <YAxis stroke="#64748b" tick={{ fontSize: 12 }} tickFormatter={(v: number) => `$${v.toFixed(0)}`} />
          <Tooltip {...tooltipStyle} labelFormatter={(l) => `Tick ${l}`} formatter={(v: number, n: string) => [`$${v.toFixed(2)}`, n]} />
          <Legend />
          {agents.map((agent, i) => (
            <Line key={agent} type="monotone" dataKey={agent} stroke={getAgentColor(agent, i)} strokeWidth={2} dot={{ r: 3 }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function ViewToggle({ view, onChange }: { view: 'line' | 'bar'; onChange: (v: 'line' | 'bar') => void }) {
  return (
    <div className="flex gap-1 bg-slate-700 rounded-lg p-0.5">
      <button
        onClick={() => onChange('line')}
        className={`px-2 py-1 text-xs rounded ${view === 'line' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-white'}`}
      >
        📈 Line
      </button>
      <button
        onClick={() => onChange('bar')}
        className={`px-2 py-1 text-xs rounded ${view === 'bar' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-white'}`}
      >
        📊 Bar
      </button>
    </div>
  );
}
