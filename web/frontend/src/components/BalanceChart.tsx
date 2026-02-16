import { useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { getAgentColor } from '../utils';

export function BalanceChart({ history }: { history: Record<string, number[]> }) {
  const agents = Object.keys(history);
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  if (agents.length === 0) return null;

  const maxLen = Math.max(...agents.map(a => history[a].length));
  const data = Array.from({ length: maxLen }, (_, i) => {
    const point: Record<string, number> = { tick: i };
    for (const agent of agents) {
      point[agent] = (history[agent]?.[i] ?? 0) / 100;
    }
    return point;
  });

  const toggleAgent = (agent: string) => {
    setHidden(prev => {
      const next = new Set(prev);
      if (next.has(agent)) next.delete(agent);
      else next.add(agent);
      return next;
    });
  };

  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data}>
        <defs>
          {agents.map((agent, i) => (
            <linearGradient key={agent} id={`grad-${agent}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={getAgentColor(agent, i)} stopOpacity={0.3} />
              <stop offset="95%" stopColor={getAgentColor(agent, i)} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="tick" stroke="#64748b" tick={{ fontSize: 12 }} label={{ value: 'Tick', position: 'insideBottom', offset: -5, fill: '#64748b' }} />
        <YAxis stroke="#64748b" tick={{ fontSize: 12 }} tickFormatter={(v: number) => `$${v.toLocaleString()}`} />
        <Tooltip
          contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
          labelStyle={{ color: '#94a3b8' }}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter={((value: any, name: any) => [`$${Number(value ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`, name ?? '']) as any}
          labelFormatter={(label) => `Tick ${label}`}
        />
        <Legend onClick={(e) => { if (e.dataKey) toggleAgent(String(e.dataKey)); }} wrapperStyle={{ cursor: 'pointer' }} />
        {agents.map((agent, i) => (
          <Area
            key={agent}
            type="monotone"
            dataKey={agent}
            stroke={getAgentColor(agent, i)}
            fill={`url(#grad-${agent})`}
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 6 }}
            hide={hidden.has(agent)}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}
