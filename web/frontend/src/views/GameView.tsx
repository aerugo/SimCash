import { useState, useCallback } from 'react';
import type { GameState } from '../types';
import { stepGame, autoRunGame } from '../api';

const AGENT_COLORS = ['#38bdf8', '#a78bfa', '#34d399', '#fb923c', '#f472b6', '#facc15', '#94a3b8', '#e879f9'];

interface Props {
  gameId: string;
  gameState: GameState;
  onUpdate: (state: GameState) => void;
  onReset: () => void;
}

export function GameView({ gameId, gameState, onUpdate, onReset }: Props) {
  const [loading, setLoading] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const [autoRunning, setAutoRunning] = useState(false);

  const handleStep = useCallback(async () => {
    setLoading(true);
    setOptimizing(false);
    try {
      const res = await stepGame(gameId);
      if (res.reasoning && Object.keys(res.reasoning).length > 0) {
        setOptimizing(true);
        setTimeout(() => setOptimizing(false), 500);
      }
      onUpdate(res.game);
      setSelectedDay(res.game.current_day - 1);
    } catch (e) {
      console.error('Step failed:', e);
    } finally {
      setLoading(false);
    }
  }, [gameId, onUpdate]);

  const handleAutoRun = useCallback(async () => {
    setAutoRunning(true);
    try {
      const res = await autoRunGame(gameId);
      onUpdate(res.game);
      setSelectedDay(res.game.current_day - 1);
    } catch (e) {
      console.error('Auto-run failed:', e);
    } finally {
      setAutoRunning(false);
    }
  }, [gameId, onUpdate]);

  const day = selectedDay !== null && selectedDay < gameState.days.length
    ? gameState.days[selectedDay] : gameState.days[gameState.days.length - 1] ?? null;

  return (
    <div className="space-y-6">
      {/* Top Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-2xl font-bold">🎮 Policy Game</h2>
          <span className="text-lg font-mono text-sky-400">
            Day {gameState.current_day}/{gameState.max_days}
          </span>
          {gameState.is_complete && (
            <span className="px-2 py-1 rounded bg-green-500/20 text-green-400 text-xs font-medium">COMPLETE</span>
          )}
          {gameState.use_llm && (
            <span className="px-2 py-1 rounded bg-violet-500/20 text-violet-400 text-xs font-medium">🧠 AI Optimization</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleStep}
            disabled={loading || autoRunning || gameState.is_complete}
            className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-40 text-sm font-medium"
          >
            {loading ? '⏳ Running...' : '▶ Next Day'}
          </button>
          <button
            onClick={handleAutoRun}
            disabled={loading || autoRunning || gameState.is_complete}
            className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-sm font-medium"
          >
            {autoRunning ? '⏳ Running all...' : '⏩ Auto-run'}
          </button>
          <button
            onClick={onReset}
            className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-sm font-medium"
          >
            🔄 New Game
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-slate-800 rounded-full h-2">
        <div
          className="bg-gradient-to-r from-sky-500 to-violet-500 h-2 rounded-full transition-all"
          style={{ width: `${(gameState.current_day / gameState.max_days) * 100}%` }}
        />
      </div>

      {optimizing && (
        <div className="bg-violet-500/10 border border-violet-500/30 rounded-xl p-4 text-center animate-pulse">
          <span className="text-lg">🧠 Optimizing policies...</span>
        </div>
      )}

      {/* Main layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Current day details */}
        <div className="space-y-4">
          {/* Day selector */}
          {gameState.days.length > 0 && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">Day Timeline</h3>
              <div className="flex gap-1 flex-wrap">
                {gameState.days.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setSelectedDay(i)}
                    className={`w-8 h-8 rounded text-xs font-mono transition-all ${
                      selectedDay === i || (selectedDay === null && i === gameState.days.length - 1)
                        ? 'bg-sky-500 text-white'
                        : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                    }`}
                  >
                    {i + 1}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Day costs */}
          {day && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">
                Day {day.day + 1} Results
                <span className="text-xs text-slate-500 ml-2">seed={day.seed}</span>
              </h3>
              <div className="space-y-3">
                {gameState.agent_ids.map((aid, i) => {
                  const costs = day.costs[aid];
                  const fraction = day.policies[aid]?.initial_liquidity_fraction ?? 1;
                  return (
                    <div key={aid} className="bg-slate-900/50 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-mono text-sm" style={{ color: AGENT_COLORS[i % AGENT_COLORS.length] }}>
                          {aid}
                        </span>
                        <span className="text-xs text-slate-400">
                          fraction={fraction.toFixed(3)}
                        </span>
                      </div>
                      {costs && (
                        <div className="grid grid-cols-4 gap-2 text-xs">
                          <div>
                            <div className="text-slate-500">Liquidity</div>
                            <div className="font-mono">{Math.round(costs.liquidity_cost).toLocaleString()}</div>
                          </div>
                          <div>
                            <div className="text-slate-500">Delay</div>
                            <div className="font-mono">{Math.round(costs.delay_cost).toLocaleString()}</div>
                          </div>
                          <div>
                            <div className="text-slate-500">Penalty</div>
                            <div className="font-mono text-red-400">{Math.round(costs.penalty_cost).toLocaleString()}</div>
                          </div>
                          <div>
                            <div className="text-slate-500">Total</div>
                            <div className="font-mono font-bold">{Math.round(costs.total).toLocaleString()}</div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
                <div className="text-right text-sm font-mono text-slate-300">
                  System total: <span className="font-bold text-white">{day.total_cost.toLocaleString()}</span>
                </div>
              </div>
            </div>
          )}

          {/* Balance chart for selected day */}
          {day && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">Day {day.day + 1} Balances</h3>
              <MiniBalanceChart balanceHistory={day.balance_history} agentIds={gameState.agent_ids} />
            </div>
          )}
        </div>

        {/* Right: Policy evolution */}
        <div className="space-y-4">
          {/* Fraction evolution chart */}
          {gameState.days.length > 0 && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">📈 Liquidity Fraction Evolution</h3>
              <EvolutionChart
                data={gameState.fraction_history}
                agentIds={gameState.agent_ids}
                yLabel="Fraction"
                format={(v) => v.toFixed(3)}
              />
            </div>
          )}

          {/* Cost evolution chart */}
          {gameState.days.length > 0 && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">💰 Cost Evolution</h3>
              <EvolutionChart
                data={gameState.cost_history}
                agentIds={gameState.agent_ids}
                yLabel="Cost"
                format={(v) => Math.round(v).toLocaleString()}
              />
            </div>
          )}

          {/* Latest reasoning */}
          {gameState.reasoning_history && Object.keys(gameState.reasoning_history).length > 0 && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">🧠 Latest Reasoning</h3>
              <div className="space-y-3">
                {gameState.agent_ids.map((aid, i) => {
                  const history = gameState.reasoning_history[aid] ?? [];
                  const latest = history[history.length - 1];
                  if (!latest) return null;
                  return (
                    <div key={aid} className="bg-slate-900/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-xs" style={{ color: AGENT_COLORS[i % AGENT_COLORS.length] }}>
                          {aid}
                        </span>
                        {latest.mock && <span className="text-[10px] text-slate-600">mock</span>}
                        {latest.accepted && <span className="text-green-400 text-[10px]">✓ accepted</span>}
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed">{latest.reasoning}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Current policies */}
          <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">📋 Current Policies</h3>
            <div className="space-y-2">
              {gameState.agent_ids.map((aid, i) => {
                const pol = gameState.current_policies[aid];
                return (
                  <div key={aid} className="flex items-center justify-between bg-slate-900/50 rounded-lg px-3 py-2">
                    <span className="font-mono text-sm" style={{ color: AGENT_COLORS[i % AGENT_COLORS.length] }}>
                      {aid}
                    </span>
                    <span className="font-mono text-sm text-slate-300">
                      fraction = {pol?.initial_liquidity_fraction?.toFixed(3) ?? '1.000'}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Events for selected day */}
      {day && day.events.length > 0 && (
        <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">
            Day {day.day + 1} Events ({day.events.length})
          </h3>
          <div className="max-h-48 overflow-y-auto text-xs font-mono text-slate-400 space-y-0.5">
            {day.events.slice(0, 100).map((e, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-slate-600 w-6">{String(e.tick)}</span>
                <span className="text-sky-400">{String(e.event_type)}</span>
                {'sender_id' in e && <span>{String(e.sender_id)}→{String(e.receiver_id)}</span>}
                {'amount' in e && <span className="text-emerald-400">${(Number(e.amount)/100).toLocaleString()}</span>}
              </div>
            ))}
            {day.events.length > 100 && (
              <div className="text-slate-600">... and {day.events.length - 100} more</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Simple SVG line chart for evolution data
function EvolutionChart({ data, agentIds, format }: {
  data: Record<string, number[]>;
  agentIds: string[];
  yLabel?: string;
  format: (v: number) => string;
}) {
  const allValues = agentIds.flatMap(aid => data[aid] ?? []);
  if (allValues.length === 0) return <div className="text-xs text-slate-600">No data yet</div>;

  const minVal = Math.min(...allValues);
  const maxVal = Math.max(...allValues);
  const range = maxVal - minVal || 1;
  const numDays = Math.max(...agentIds.map(aid => (data[aid] ?? []).length));

  const w = 400;
  const h = 120;
  const pad = { t: 10, r: 10, b: 20, l: 50 };
  const plotW = w - pad.l - pad.r;
  const plotH = h - pad.t - pad.b;

  const toX = (i: number) => pad.l + (numDays > 1 ? (i / (numDays - 1)) * plotW : plotW / 2);
  const toY = (v: number) => pad.t + plotH - ((v - minVal) / range) * plotH;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
      {/* Y axis labels */}
      <text x={pad.l - 4} y={pad.t + 4} textAnchor="end" className="fill-slate-500 text-[8px]">{format(maxVal)}</text>
      <text x={pad.l - 4} y={h - pad.b} textAnchor="end" className="fill-slate-500 text-[8px]">{format(minVal)}</text>
      {/* X axis labels */}
      {Array.from({ length: numDays }, (_, i) => (
        <text key={i} x={toX(i)} y={h - 4} textAnchor="middle" className="fill-slate-500 text-[7px]">{i + 1}</text>
      ))}
      {/* Lines */}
      {agentIds.map((aid, ci) => {
        const vals = data[aid] ?? [];
        if (vals.length < 1) return null;
        const points = vals.map((v, i) => `${toX(i)},${toY(v)}`).join(' ');
        return (
          <g key={aid}>
            <polyline points={points} fill="none" stroke={AGENT_COLORS[ci % AGENT_COLORS.length]} strokeWidth={2} />
            {vals.map((v, i) => (
              <circle key={i} cx={toX(i)} cy={toY(v)} r={3} fill={AGENT_COLORS[ci % AGENT_COLORS.length]} />
            ))}
            <text x={toX(vals.length - 1) + 4} y={toY(vals[vals.length - 1]) + 3}
              className="text-[7px]" fill={AGENT_COLORS[ci % AGENT_COLORS.length]}>{aid}</text>
          </g>
        );
      })}
    </svg>
  );
}

function MiniBalanceChart({ balanceHistory, agentIds }: {
  balanceHistory: Record<string, number[]>;
  agentIds: string[];
}) {
  const allValues = agentIds.flatMap(aid => balanceHistory[aid] ?? []);
  if (allValues.length === 0) return <div className="text-xs text-slate-600">No data</div>;

  const minVal = Math.min(...allValues, 0);
  const maxVal = Math.max(...allValues);
  const range = maxVal - minVal || 1;
  const numTicks = Math.max(...agentIds.map(aid => (balanceHistory[aid] ?? []).length));

  const w = 400;
  const h = 80;
  const pad = { t: 5, r: 5, b: 5, l: 5 };
  const plotW = w - pad.l - pad.r;
  const plotH = h - pad.t - pad.b;

  const toX = (i: number) => pad.l + (numTicks > 1 ? (i / (numTicks - 1)) * plotW : plotW / 2);
  const toY = (v: number) => pad.t + plotH - ((v - minVal) / range) * plotH;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
      {agentIds.map((aid, ci) => {
        const vals = balanceHistory[aid] ?? [];
        if (vals.length < 1) return null;
        const points = vals.map((v, i) => `${toX(i)},${toY(v)}`).join(' ');
        return <polyline key={aid} points={points} fill="none" stroke={AGENT_COLORS[ci % AGENT_COLORS.length]} strokeWidth={1.5} />;
      })}
    </svg>
  );
}
