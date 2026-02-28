/**
 * PaperChart — recharts-based charts for Q1 2026 campaign paper.
 * Fetches data from /api/docs/chart-data/{chartId} endpoint.
 */
import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  LineChart, Line, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { API_ORIGIN } from '../api';

const API_BASE = `${API_ORIGIN}/api`;

const COLORS: Record<string, string> = {
  baseline: '#94a3b8',
  flash: '#3b82f6',
  pro: '#ef4444',
  glm: '#f59e0b',
};

const MODEL_LABELS: Record<string, string> = {
  baseline: 'Baseline (FIFO)',
  flash: 'Flash',
  pro: 'Pro',
  glm: 'GLM',
};

const formatCost = (v: number) => {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}k`;
  return `${v}`;
};

interface ChartData {
  type: string;
  data: Record<string, unknown>[];
  keys?: string[];
  baseline_sr?: number;
  label?: string;
}

function useChartData(chartId: string) {
  const [data, setData] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/docs/chart-data/${chartId}`)
      .then(r => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [chartId]);

  return { data, loading, error };
}

function ChartLoading() {
  return (
    <div className="flex items-center justify-center h-64 text-slate-500 text-sm">
      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-sky-400 mr-3" />
      Loading chart data...
    </div>
  );
}

function ChartError({ msg }: { msg: string }) {
  return (
    <div className="flex items-center justify-center h-32 text-red-400 text-sm border border-red-500/20 rounded-lg bg-red-500/5">
      Failed to load chart: {msg}
    </div>
  );
}

export function CostComparisonChart() {
  const { data, loading, error } = useChartData('cost-comparison');
  if (loading) return <ChartLoading />;
  if (error || !data) return <ChartError msg={error || 'No data'} />;

  const keys = data.keys || ['baseline', 'flash', 'pro'];

  return (
    <div style={{ width: '100%', marginBottom: 32 }}>
      <h4 className="text-center text-sm font-medium text-slate-300 mb-2">
        Simple Scenarios: Final Cost by Model (lower = better)
      </h4>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data.data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="scenario" tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <YAxis tickFormatter={formatCost} tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <Tooltip
            formatter={(v: number, name: string) => [formatCost(v), MODEL_LABELS[name] || name]}
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
            labelStyle={{ color: '#e2e8f0' }}
          />
          <Legend formatter={(v: string) => MODEL_LABELS[v] || v} />
          {keys.map(k => (
            <Bar key={k} dataKey={k} fill={COLORS[k] || '#6b7280'} radius={[2, 2, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ComplexCostDeltaChart() {
  const { data, loading, error } = useChartData('complex-cost-delta');
  if (loading) return <ChartLoading />;
  if (error || !data) return <ChartError msg={error || 'No data'} />;

  const keys = data.keys || ['flash', 'pro'];

  return (
    <div style={{ width: '100%', marginBottom: 32 }}>
      <h4 className="text-center text-sm font-medium text-slate-300 mb-2">
        Complex Scenarios: Cost Change vs Baseline (positive = LLM worse)
      </h4>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data.data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="scenario" tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <YAxis
            tickFormatter={(v: number) => `${v > 0 ? '+' : ''}${v}%`}
            domain={['auto', 'auto']}
            tick={{ fill: '#94a3b8', fontSize: 12 }}
          />
          <Tooltip
            formatter={(v: number, name: string) => [`${v > 0 ? '+' : ''}${v}%`, MODEL_LABELS[name] || name]}
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
            labelStyle={{ color: '#e2e8f0' }}
          />
          <Legend formatter={(v: string) => MODEL_LABELS[v] || v} />
          <ReferenceLine y={0} stroke="#475569" strokeDasharray="3 3" />
          {keys.map(k => (
            <Bar key={k} dataKey={k} fill={COLORS[k] || '#6b7280'} radius={[2, 2, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SettlementDegradationChart() {
  const { data, loading, error } = useChartData('settlement-degradation');
  if (loading) return <ChartLoading />;
  if (error || !data) return <ChartError msg={error || 'No data'} />;

  const baselineSR = data.baseline_sr || 77;
  const chartData = (data.data as { day: number; sr: number }[]).map(d => ({
    ...d,
    baseline: baselineSR,
  }));

  return (
    <div style={{ width: '100%', marginBottom: 32 }}>
      <h4 className="text-center text-sm font-medium text-slate-300 mb-2">
        {data.label || 'Cumulative Settlement Rate Over Time'}
      </h4>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 25 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="day"
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            label={{ value: 'Day', position: 'insideBottom', offset: -15, fill: '#94a3b8' }}
          />
          <YAxis
            domain={[60, 105]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fill: '#94a3b8', fontSize: 12 }}
          />
          <Tooltip
            formatter={(v: number, name: string) => [`${v.toFixed(1)}%`, name === 'sr' ? 'Flash (optimized)' : `Baseline (${baselineSR}%)`]}
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
            labelStyle={{ color: '#e2e8f0' }}
            labelFormatter={(v) => `Day ${v}`}
          />
          <Legend formatter={(v: string) => v === 'sr' ? 'Flash (optimized)' : `Baseline (${baselineSR}%)`} />
          <Line type="monotone" dataKey="sr" stroke={COLORS.flash} strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="baseline" stroke={COLORS.baseline} strokeWidth={2} strokeDasharray="5 5" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
