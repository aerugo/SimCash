import { useState, useEffect, useCallback } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';
import type { PolicyHistoryResponse, PolicyDiffResponse } from '../types';
import { getPolicyHistory, getPolicyDiff } from '../api';
import { PolicyVisualization } from './PolicyVisualization';

const AGENT_COLORS = ['#38bdf8', '#a78bfa', '#34d399', '#fb923c', '#f472b6', '#facc15'];

interface Props {
  gameId: string;
  agentIds: string[];
  currentDay: number;
}

export function PolicyEvolutionPanel({ gameId, agentIds, currentDay }: Props) {
  const [history, setHistory] = useState<PolicyHistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const [diffData, setDiffData] = useState<PolicyDiffResponse | null>(null);
  const [diffAgent, setDiffAgent] = useState(agentIds[0] ?? '');
  const [diffDays, setDiffDays] = useState<[number, number] | null>(null);
  const [showDiffModal, setShowDiffModal] = useState(false);

  const fetchHistory = useCallback(async () => {
    if (currentDay === 0) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getPolicyHistory(gameId);
      setHistory(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [gameId, currentDay]);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  const handleDiff = async (day1: number, day2: number, agent: string) => {
    try {
      const data = await getPolicyDiff(gameId, day1, day2, agent);
      setDiffData(data);
      setDiffDays([day1, day2]);
      setDiffAgent(agent);
      setShowDiffModal(true);
    } catch (e) {
      console.error('Diff failed:', e);
    }
  };

  if (currentDay === 0) return null;
  if (loading) return <div className="text-xs text-slate-500 animate-pulse">Loading policy evolution...</div>;
  if (error) return <div className="text-xs text-red-400">Error: {error}</div>;
  if (!history || history.days.length === 0) return null;

  // Build chart data for parameter trajectories
  const chartData = history.days.map((d, i) => {
    const point: Record<string, unknown> = { day: i + 1 };
    for (const aid of agentIds) {
      const frac = history.parameter_trajectories[aid]?.initial_liquidity_fraction?.[i];
      point[aid] = frac ?? null;
      point[`${aid}_accepted`] = d.accepted[aid] ?? true;
    }
    return point;
  });

  return (
    <div className="space-y-4">
      {/* Parameter Trajectory Chart */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
        <h3 className="text-sm font-semibold text-slate-300 mb-3">📊 Policy Parameter Evolution</h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="day" stroke="#64748b" tick={{ fontSize: 11 }} label={{ value: 'Day', position: 'insideBottom', offset: -5, fill: '#64748b', fontSize: 11 }} />
            <YAxis stroke="#64748b" tick={{ fontSize: 11 }} domain={[0, 1]} label={{ value: 'Fraction', angle: -90, position: 'insideLeft', fill: '#64748b', fontSize: 11 }} />
            <Tooltip
              contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: 12 }}
              labelStyle={{ color: '#94a3b8' }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {agentIds.map((aid, i) => (
              <Line
                key={aid}
                type="monotone"
                dataKey={aid}
                stroke={AGENT_COLORS[i % AGENT_COLORS.length]}
                strokeWidth={2}
                dot={(props: Record<string, unknown>) => {
                  const cx = props.cx as number | undefined;
                  const cy = props.cy as number | undefined;
                  const payload = props.payload as Record<string, unknown> | undefined;
                  if (cx == null || cy == null || !payload) return <circle r={0} />;
                  const accepted = payload[`${aid}_accepted`];
                  return (
                    <circle
                      key={`${aid}-${String(payload.day)}`}
                      cx={cx}
                      cy={cy}
                      r={4}
                      fill={accepted ? '#22c55e' : '#ef4444'}
                      stroke={AGENT_COLORS[i % AGENT_COLORS.length]}
                      strokeWidth={1.5}
                    />
                  );
                }}
                activeDot={{ r: 6 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
        <div className="flex items-center gap-4 mt-2 text-[10px] text-slate-500 justify-center">
          <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full bg-green-500" /> Accepted</span>
          <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full bg-red-500" /> Rejected</span>
        </div>
      </div>

      {/* Policy Timeline */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
        <h3 className="text-sm font-semibold text-slate-300 mb-3">🕐 Policy Timeline</h3>
        <div className="flex items-center gap-1 overflow-x-auto pb-2">
          {history.days.map((d, i) => {
            const isSelected = selectedDay === i;
            return (
              <div key={i} className="flex items-center">
                <button
                  onClick={() => setSelectedDay(isSelected ? null : i)}
                  className={`flex-shrink-0 w-10 h-10 rounded-lg text-xs font-mono flex items-center justify-center transition-all border ${
                    isSelected
                      ? 'bg-sky-500/20 border-sky-500 text-sky-400'
                      : 'bg-slate-900/50 border-slate-700 text-slate-400 hover:border-slate-500'
                  }`}
                >
                  D{d.day + 1}
                </button>
                {i < history.days.length - 1 && (
                  <button
                    onClick={() => handleDiff(i, i + 1, diffAgent)}
                    className="flex-shrink-0 mx-0.5 text-slate-600 hover:text-sky-400 text-[10px] transition-colors"
                    title={`Diff Day ${d.day + 1} → Day ${d.day + 2}`}
                  >
                    →
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* Expanded day details */}
        {selectedDay !== null && history.days[selectedDay] && (
          <div className="mt-3 border-t border-slate-700 pt-3 space-y-2">
            <div className="text-xs font-semibold text-slate-400">Day {selectedDay + 1} Policies</div>
            {agentIds.map((aid, i) => {
              const d = history.days[selectedDay];
              const policy = d.policies[aid];
              const params = (policy as Record<string, unknown>)?.parameters as Record<string, number> | undefined;
              return (
                <div key={aid} className={`bg-slate-900/50 rounded-lg p-2 border-l-2 ${
                  d.accepted[aid] ? 'border-green-500' : 'border-red-500'
                }`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-xs" style={{ color: AGENT_COLORS[i % AGENT_COLORS.length] }}>{aid}</span>
                    <span className={`text-[10px] ${d.accepted[aid] ? 'text-green-400' : 'text-red-400'}`}>
                      {d.accepted[aid] ? '✓' : '✗'}
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      cost={d.costs[aid]?.toLocaleString()}
                    </span>
                  </div>
                  {params && (
                    <div className="text-[10px] text-slate-500 font-mono">
                      {Object.entries(params).map(([k, v]) => (
                        <span key={k} className="mr-3">{k}={typeof v === 'number' ? v.toFixed(3) : String(v)}</span>
                      ))}
                    </div>
                  )}
                  {d.reasoning[aid] && (
                    <p className="text-[10px] text-slate-500 mt-1 leading-relaxed">{d.reasoning[aid]}</p>
                  )}
                  {policy && typeof (policy as Record<string, unknown>).payment_tree === 'object' && (
                    <details className="mt-2">
                      <summary className="text-[10px] text-slate-500 cursor-pointer hover:text-slate-300">
                        View Decision Trees
                      </summary>
                      <PolicyVisualization
                        policy={policy as Record<string, unknown>}
                        compact
                        className="mt-2"
                      />
                    </details>
                  )}
                </div>
              );
            })}
            {/* Diff buttons for selected day */}
            {selectedDay > 0 && (
              <div className="flex gap-2 mt-2">
                <select
                  value={diffAgent}
                  onChange={(e) => setDiffAgent(e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300"
                >
                  {agentIds.map(aid => <option key={aid} value={aid}>{aid}</option>)}
                </select>
                <button
                  onClick={() => handleDiff(selectedDay - 1, selectedDay, diffAgent)}
                  className="px-3 py-1 rounded bg-slate-700 hover:bg-slate-600 text-xs text-slate-300"
                >
                  Compare with Day {selectedDay}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Diff Modal */}
      {showDiffModal && diffData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setShowDiffModal(false)}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-200">
                Policy Diff: {diffData.agent} — Day {(diffDays?.[0] ?? 0) + 1} → Day {(diffDays?.[1] ?? 0) + 1}
              </h3>
              <button onClick={() => setShowDiffModal(false)} className="text-slate-500 hover:text-slate-300 text-lg">×</button>
            </div>

            {/* Summary */}
            <p className="text-xs text-slate-400 mb-4 leading-relaxed">{diffData.summary}</p>

            {/* Parameter changes */}
            {diffData.parameter_changes.length > 0 && (
              <div className="mb-4">
                <h4 className="text-xs font-semibold text-slate-400 mb-2">Parameter Changes</h4>
                <div className="space-y-1">
                  {diffData.parameter_changes.map((pc, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs font-mono bg-slate-900/50 rounded px-2 py-1">
                      <span className="text-slate-400">{pc.param}</span>
                      <span className="text-red-400">{String(pc.old)}</span>
                      <span className="text-slate-600">→</span>
                      <span className="text-green-400">{String(pc.new)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tree changes */}
            {Object.entries(diffData.tree_changes).map(([treeName, tc]) => {
              const hasChanges = tc.added_nodes.length > 0 || tc.removed_nodes.length > 0 || tc.modified_nodes.length > 0;
              if (!hasChanges) return null;
              return (
                <div key={treeName} className="mb-3">
                  <h4 className="text-xs font-semibold text-slate-400 mb-1">{treeName}</h4>
                  {tc.added_nodes.length > 0 && (
                    <div className="text-[10px] text-green-400 mb-1">+ {tc.added_nodes.length} node(s) added</div>
                  )}
                  {tc.removed_nodes.length > 0 && (
                    <div className="text-[10px] text-red-400 mb-1">- {tc.removed_nodes.length} node(s) removed</div>
                  )}
                  {tc.modified_nodes.length > 0 && (
                    <div className="text-[10px] text-yellow-400 mb-1">~ {tc.modified_nodes.length} node(s) modified</div>
                  )}
                </div>
              );
            })}

            {diffData.parameter_changes.length === 0 &&
              Object.values(diffData.tree_changes).every(tc => tc.added_nodes.length === 0 && tc.removed_nodes.length === 0 && tc.modified_nodes.length === 0) && (
              <div className="text-xs text-slate-500 text-center py-4">No changes between these days.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
