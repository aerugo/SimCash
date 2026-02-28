import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  LineChart, Line, ResponsiveContainer,
} from 'recharts';

// Hardcoded from actual experiment data (r1 runs) — will be replaced by API later

const costComparisonData = [
  { scenario: '2b_3t', baseline: 99900, flash: 13660, pro: 75886 },
  { scenario: '3b_6t', baseline: 74700, flash: 18017, pro: 19678 },
  { scenario: '4b_8t', baseline: 132800, flash: 59123, pro: 41233 },
  { scenario: 'castro', baseline: 99600, flash: 39393, pro: 108910 },
  { scenario: 'large_net', baseline: 182875980, flash: 192578912, pro: 202038573 },
  { scenario: 'lehman', baseline: 199111725, flash: 233402769, pro: 252529888 },
];

// Simple scenarios only (costs in thousands)
const simpleCostData = costComparisonData.slice(0, 4).map(d => ({
  scenario: d.scenario,
  Baseline: Math.round(d.baseline / 1000),
  Flash: Math.round(d.flash / 1000),
  Pro: Math.round(d.pro / 1000),
}));

// Complex scenarios (costs in millions)
const complexCostData = costComparisonData.slice(4).map(d => ({
  scenario: d.scenario,
  Baseline: Math.round(d.baseline / 1_000_000),
  Flash: Math.round(d.flash / 1_000_000),
  Pro: Math.round(d.pro / 1_000_000),
}));

// Settlement rate degradation over days — lehman_month (25 days)
// Hardcoded from actual daily SR data
const settlementDegradationData = [
  { day: 1, baseline: 0.73, flash: 0.68, pro: 0.65 },
  { day: 5, baseline: 0.73, flash: 0.67, pro: 0.64 },
  { day: 10, baseline: 0.73, flash: 0.67, pro: 0.66 },
  { day: 15, baseline: 0.73, flash: 0.66, pro: 0.65 },
  { day: 20, baseline: 0.73, flash: 0.67, pro: 0.66 },
  { day: 25, baseline: 0.73, flash: 0.67, pro: 0.66 },
].map(d => ({
  day: d.day,
  Baseline: Math.round(d.baseline * 100),
  Flash: Math.round(d.flash * 100),
  Pro: Math.round(d.pro * 100),
}));

const COLORS = {
  Baseline: '#8884d8',
  Flash: '#82ca9d',
  Pro: '#ff7300',
};

export function CostComparisonChart() {
  return (
    <div style={{ width: '100%' }}>
      <h3>Simple Scenarios: Cost Comparison (thousands)</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={simpleCostData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="scenario" />
          <YAxis label={{ value: 'Cost (K)', angle: -90, position: 'insideLeft' }} />
          <Tooltip />
          <Legend />
          <Bar dataKey="Baseline" fill={COLORS.Baseline} />
          <Bar dataKey="Flash" fill={COLORS.Flash} />
          <Bar dataKey="Pro" fill={COLORS.Pro} />
        </BarChart>
      </ResponsiveContainer>

      <h3 style={{ marginTop: 32 }}>Complex Scenarios: Cost Comparison (millions)</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={complexCostData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="scenario" />
          <YAxis label={{ value: 'Cost (M)', angle: -90, position: 'insideLeft' }} />
          <Tooltip />
          <Legend />
          <Bar dataKey="Baseline" fill={COLORS.Baseline} />
          <Bar dataKey="Flash" fill={COLORS.Flash} />
          <Bar dataKey="Pro" fill={COLORS.Pro} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SettlementDegradationChart() {
  return (
    <div style={{ width: '100%' }}>
      <h3>Settlement Rate Over Time — Lehman Month</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={settlementDegradationData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="day" label={{ value: 'Day', position: 'insideBottom', offset: -5 }} />
          <YAxis
            domain={[50, 100]}
            label={{ value: 'Settlement Rate (%)', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="Baseline" stroke={COLORS.Baseline} strokeWidth={2} />
          <Line type="monotone" dataKey="Flash" stroke={COLORS.Flash} strokeWidth={2} />
          <Line type="monotone" dataKey="Pro" stroke={COLORS.Pro} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function PaperChart() {
  return (
    <div style={{ padding: 24 }}>
      <CostComparisonChart />
      <div style={{ marginTop: 48 }} />
      <SettlementDegradationChart />
    </div>
  );
}
