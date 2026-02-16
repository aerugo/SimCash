import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const COLORS = ['#38bdf8', '#a78bfa', '#4ade80', '#fbbf24'];

export function BalanceChart({ history }: { history: Record<string, number[]> }) {
  const agents = Object.keys(history);
  if (agents.length === 0) return null;

  const maxLen = Math.max(...agents.map(a => history[a].length));
  const data = Array.from({ length: maxLen }, (_, i) => {
    const point: Record<string, number> = { tick: i };
    for (const agent of agents) {
      point[agent] = (history[agent]?.[i] ?? 0) / 100; // cents to dollars
    }
    return point;
  });

  return (
    <ResponsiveContainer width="100%" height={250}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="tick" stroke="#64748b" tick={{ fontSize: 12 }} label={{ value: 'Tick', position: 'insideBottom', offset: -5, fill: '#64748b' }} />
        <YAxis stroke="#64748b" tick={{ fontSize: 12 }} tickFormatter={(v: number) => `$${v.toLocaleString()}`} />
        <Tooltip
          contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
          labelStyle={{ color: '#94a3b8' }}
          formatter={(value: number) => [`$${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`, '']}
        />
        <Legend />
        {agents.map((agent, i) => (
          <Line
            key={agent}
            type="monotone"
            dataKey={agent}
            stroke={COLORS[i % COLORS.length]}
            strokeWidth={2}
            dot={{ r: 4 }}
            activeDot={{ r: 6 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
