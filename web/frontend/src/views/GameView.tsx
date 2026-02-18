import { useState, useEffect, useCallback } from 'react';
import type { GameState, GameOptimizationResult } from '../types';
import { useGameWebSocket } from '../hooks/useGameWebSocket';
import { getGameDayReplay, downloadGameExport } from '../api';
import { PolicyEvolutionPanel } from '../components/PolicyEvolutionPanel';
import { PolicyVisualization } from '../components/PolicyVisualization';
import { InfoTip } from '../components/Tooltip';

const AGENT_COLORS = ['#38bdf8', '#a78bfa', '#34d399', '#fb923c', '#f472b6', '#facc15', '#94a3b8', '#e879f9'];

interface Props {
  gameId: string;
  gameState: GameState;
  onUpdate: (state: GameState) => void;
  onReset: () => void;
}

export function GameView({ gameId, gameState: initialState, onUpdate, onReset }: Props) {
  const { gameState: wsState, connected, connectionStatus, reconnectAttempt, phase, optimizingAgent, simulatingDay, streamingText, step, rerun, autoRun, stop } = useGameWebSocket(gameId, initialState);
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const [autoRunning, setAutoRunning] = useState(false);
  const [replayData, setReplayData] = useState<{
    dayNum: number;
    ticks: { tick: number; events: Record<string, unknown>[]; balances: Record<string, number> }[];
    currentTick: number;
  } | null>(null);
  const [replayPlaying, setReplayPlaying] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [speed, setSpeed] = useState<'fast' | 'normal' | 'slow'>('normal');

  const SPEED_MS: Record<typeof speed, number> = { fast: 0, normal: 3000, slow: 8000 };

  const gameState = wsState ?? initialState;

  // Sync state up to parent
  useEffect(() => {
    if (wsState) onUpdate(wsState);
  }, [wsState, onUpdate]);

  // Auto-select latest day when new days arrive
  useEffect(() => {
    if (gameState.days.length > 0) {
      setSelectedDay(gameState.days.length - 1);
    }
  }, [gameState.days.length]);

  const handleReplay = useCallback(async (dayNum: number) => {
    try {
      const data = await getGameDayReplay(gameId, dayNum);
      setReplayData({ dayNum, ticks: data.ticks, currentTick: 0 });
      setReplayPlaying(false);
    } catch (e) {
      console.error('Replay failed:', e);
    }
  }, [gameId]);

  // Auto-advance replay
  useEffect(() => {
    if (!replayPlaying || !replayData) return;
    if (replayData.currentTick >= replayData.ticks.length - 1) {
      setReplayPlaying(false);
      return;
    }
    const timer = setTimeout(() => {
      setReplayData(prev => prev ? { ...prev, currentTick: prev.currentTick + 1 } : null);
    }, 500);
    return () => clearTimeout(timer);
  }, [replayPlaying, replayData]);

  const handleAutoRun = () => {
    setAutoRunning(true);
    autoRun(SPEED_MS[speed]);
  };

  // Stop auto-run when game completes
  useEffect(() => {
    if (gameState.is_complete && autoRunning) setAutoRunning(false);
  }, [gameState.is_complete, autoRunning]);

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
          {connectionStatus === 'reconnecting' && (
            <span className="px-2 py-1 rounded bg-amber-500/20 text-amber-400 text-xs font-medium animate-pulse">
              🔄 Reconnecting{reconnectAttempt > 0 ? ` (${reconnectAttempt}/10)` : ''}…
            </span>
          )}
          {connectionStatus === 'disconnected' && (
            <span className="px-2 py-1 rounded bg-red-500/20 text-red-400 text-xs font-medium">⚠ Connection lost — please refresh</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={step}
            disabled={!connected || autoRunning || gameState.is_complete}
            className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-40 text-sm font-medium"
          >
            ▶ Next Day
          </button>
          <button
            onClick={() => rerun()}
            disabled={!connected || autoRunning || gameState.days.length === 0}
            title="Re-run the last day with the same seed (deterministic replay)"
            className="px-4 py-2 rounded-lg bg-amber-700 hover:bg-amber-600 disabled:opacity-40 text-sm font-medium"
          >
            🔄 Re-run Day
          </button>
          <button
            onClick={autoRunning ? stop : handleAutoRun}
            disabled={!connected || gameState.is_complete}
            className={`px-4 py-2 rounded-lg text-sm font-medium ${
              autoRunning
                ? 'bg-red-600 hover:bg-red-500'
                : 'bg-violet-600 hover:bg-violet-500 disabled:opacity-40'
            }`}
          >
            {autoRunning ? '⏹ Stop' : '⏩ Auto-run'}
          </button>
          {/* Speed control */}
          <div className="flex items-center bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
            {([['fast', '⏩'], ['normal', '▶️'], ['slow', '🐢']] as const).map(([s, icon]) => (
              <button
                key={s}
                onClick={() => {
                  setSpeed(s);
                  if (autoRunning) autoRun(SPEED_MS[s]);
                }}
                className={`px-2.5 py-2 text-xs font-medium transition-all ${
                  speed === s
                    ? 'bg-sky-600 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-700'
                }`}
                title={`${s.charAt(0).toUpperCase() + s.slice(1)} speed${s === 'fast' ? ' (no delay)' : s === 'normal' ? ' (3s pause)' : ' (8s pause)'}`}
              >
                {icon}
              </button>
            ))}
          </div>
          <div className="relative">
            <button
              onClick={() => setExportOpen(!exportOpen)}
              disabled={gameState.days.length === 0}
              className="px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-600 disabled:opacity-40 text-sm font-medium"
            >
              📥 Export ▾
            </button>
            {exportOpen && (
              <div className="absolute right-0 mt-1 w-36 bg-slate-800 border border-slate-600 rounded-lg shadow-xl z-50 overflow-hidden">
                <button
                  onClick={() => { setExportOpen(false); downloadGameExport(gameId, 'csv'); }}
                  className="w-full px-4 py-2 text-left text-sm hover:bg-slate-700 text-slate-200"
                >
                  📊 CSV
                </button>
                <button
                  onClick={() => { setExportOpen(false); downloadGameExport(gameId, 'json'); }}
                  className="w-full px-4 py-2 text-left text-sm hover:bg-slate-700 text-slate-200"
                >
                  📋 JSON
                </button>
              </div>
            )}
          </div>
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

      {autoRunning && phase === 'idle' && !gameState.is_complete && speed !== 'fast' && (
        <div className="bg-slate-700/30 border border-slate-600/30 rounded-xl p-3 text-center">
          <span className="text-sm text-slate-400">
            ⏳ Pausing between days... ({speed === 'normal' ? '3s' : '8s'})
          </span>
        </div>
      )}

      {phase === 'simulating' && (
        <div className="bg-sky-500/10 border border-sky-500/30 rounded-xl p-3 text-center animate-pulse">
          <span className="text-sm">⚙️ Simulating Day {(simulatingDay ?? 0) + 1}...</span>
        </div>
      )}
      {phase === 'optimizing' && optimizingAgent && (
        <div className="bg-violet-500/10 border border-violet-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm font-medium">🧠 Optimizing {optimizingAgent}</span>
            <span className="inline-block w-2 h-2 rounded-full bg-violet-400 animate-pulse" />
          </div>
          {streamingText[optimizingAgent] ? (
            <div className="max-h-48 overflow-y-auto">
              <pre className="text-xs text-slate-400 whitespace-pre-wrap font-mono leading-relaxed">
                {streamingText[optimizingAgent]}
                <span className="inline-block w-1.5 h-3.5 bg-violet-400 animate-pulse ml-0.5 align-text-bottom" />
              </pre>
            </div>
          ) : (
            <div className="text-xs text-slate-500 animate-pulse">Waiting for response...</div>
          )}
        </div>
      )}

      {/* Completion summary */}
      {gameState.is_complete && gameState.days.length > 0 && (() => {
        const firstDay = gameState.days[0];
        const lastDay = gameState.days[gameState.days.length - 1];
        const firstTotal = firstDay.total_cost;
        const lastTotal = lastDay.total_cost;
        const reduction = firstTotal > 0 ? ((firstTotal - lastTotal) / firstTotal * 100) : 0;
        return (
          <div className="bg-gradient-to-r from-green-500/10 to-emerald-500/10 border border-green-500/30 rounded-xl p-5">
            <h3 className="text-lg font-semibold text-green-400 mb-3">🏁 Game Complete — {gameState.max_days} Days</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-xs text-slate-500">Day 1 Cost</div>
                <div className="font-mono text-sm">{firstTotal.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Final Cost</div>
                <div className="font-mono text-sm">{lastTotal.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Cost Reduction<InfoTip text="Percentage decrease in total system cost from Day 1 to the final day" /></div>
                <div className={`font-mono text-sm ${reduction > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {reduction > 0 ? '↓' : '↑'} {Math.abs(reduction).toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Final Fractions<InfoTip text="Each bank's liquidity commitment as a fraction of their pool (0 = none, 1 = all)" /></div>
                <div className="font-mono text-xs text-slate-300">
                  {gameState.agent_ids.map(aid => {
                    const f = gameState.current_policies[aid]?.initial_liquidity_fraction ?? 1;
                    return `${aid.replace('BANK_', '')}: ${f.toFixed(3)}`;
                  }).join(' · ')}
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Empty state guidance */}
      {gameState.days.length === 0 && (
        <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6 text-center">
          <div className="text-3xl mb-3">🏦</div>
          <h3 className="text-lg font-semibold mb-2">Ready to Start</h3>
          <p className="text-sm text-slate-400 max-w-lg mx-auto">
            Click <strong>▶ Next Day</strong> to simulate the first trading day. Each day, banks process payments using their current liquidity policy.
            After each day, the AI optimizer analyzes costs and proposes improved policies — watching for the sweet spot between
            holding too much liquidity (wasted capital) and too little (missed deadlines).
          </p>
          <p className="text-xs text-slate-500 mt-3">
            {(() => {
              const fracs = Object.entries(gameState.current_policies).map(([aid, p]) => ({ aid, f: p.initial_liquidity_fraction }));
              const allSame = fracs.length > 0 && fracs.every(x => x.f === fracs[0].f);
              if (allSame) {
                return <>All agents start with <span className="font-mono text-slate-400">fraction = {fracs[0].f.toFixed(3)}</span> (commit {(fracs[0].f * 100).toFixed(0)}% of their pool). The optimizer will learn to reduce this over multiple days.</>;
              }
              return <>Agents start with custom fractions: {fracs.map((x, i) => <span key={x.aid}>{i > 0 && ', '}<span className="font-mono text-slate-400">{x.aid}={x.f.toFixed(2)}</span></span>)}. The optimizer will refine these over multiple days.</>;
            })()}
          </p>
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
                {gameState.days.map((d, i) => (
                  <button
                    key={i}
                    onClick={() => setSelectedDay(i)}
                    title={d.optimized ? `Day ${i + 1} — optimized` : `Day ${i + 1}`}
                    className={`w-8 h-8 rounded text-xs font-mono transition-all relative ${
                      selectedDay === i || (selectedDay === null && i === gameState.days.length - 1)
                        ? 'bg-sky-500 text-white'
                        : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                    }`}
                  >
                    {i + 1}
                    {d.optimized && <span className="absolute -top-1 -right-1 text-[8px]">🧠</span>}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Replay controls */}
          {day && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-slate-300">🔁 Tick Replay</h3>
                {!replayData || replayData.dayNum !== (selectedDay ?? gameState.days.length - 1) ? (
                  <button
                    onClick={() => handleReplay(selectedDay ?? gameState.days.length - 1)}
                    className="px-3 py-1 rounded bg-slate-700 hover:bg-slate-600 text-xs"
                  >
                    Load Day {(selectedDay ?? gameState.days.length - 1) + 1} Replay
                  </button>
                ) : (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setReplayData(prev => prev ? { ...prev, currentTick: Math.max(0, prev.currentTick - 1) } : null)}
                      disabled={!replayData || replayData.currentTick <= 0}
                      className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-xs"
                    >◀</button>
                    <button
                      onClick={() => setReplayPlaying(!replayPlaying)}
                      className="px-2 py-1 rounded bg-sky-600 hover:bg-sky-500 text-xs"
                    >{replayPlaying ? '⏸' : '▶'}</button>
                    <button
                      onClick={() => setReplayData(prev => prev ? { ...prev, currentTick: Math.min(prev.ticks.length - 1, prev.currentTick + 1) } : null)}
                      disabled={!replayData || replayData.currentTick >= replayData.ticks.length - 1}
                      className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-xs"
                    >▶</button>
                    <span className="text-xs font-mono text-slate-400">
                      Tick {replayData.currentTick + 1}/{replayData.ticks.length}
                    </span>
                  </div>
                )}
              </div>
              {replayData && replayData.dayNum === (selectedDay ?? gameState.days.length - 1) && (
                <div>
                  {/* Tick progress bar */}
                  <div className="w-full bg-slate-900 rounded-full h-1.5 mb-3">
                    <div
                      className="bg-sky-500 h-1.5 rounded-full transition-all"
                      style={{ width: `${((replayData.currentTick + 1) / replayData.ticks.length) * 100}%` }}
                    />
                  </div>
                  {/* Balances at this tick */}
                  <div className="grid grid-cols-2 gap-2 mb-2">
                    {gameState.agent_ids.map((aid, i) => (
                      <div key={aid} className="bg-slate-900/50 rounded p-2">
                        <span className="font-mono text-[10px]" style={{ color: AGENT_COLORS[i % AGENT_COLORS.length] }}>{aid}</span>
                        <div className="font-mono text-xs text-slate-300">
                          ${((replayData.ticks[replayData.currentTick]?.balances[aid] ?? 0) / 100).toLocaleString()}
                        </div>
                      </div>
                    ))}
                  </div>
                  {/* Events at this tick */}
                  <div className="max-h-24 overflow-y-auto text-[10px] font-mono text-slate-500 space-y-0.5">
                    {(replayData.ticks[replayData.currentTick]?.events ?? []).map((e, i) => (
                      <div key={i} className="flex gap-1">
                        <span className="text-sky-400">{String(e.event_type ?? '')}</span>
                        {'sender_id' in e && 'receiver_id' in e && <span>{String(e.sender_id)}→{String(e.receiver_id)}</span>}
                        {'agent_id' in e && !('sender_id' in e) && <span>{String(e.agent_id)}</span>}
                        {'amount' in e && <span className="text-emerald-400">${(Number(e.amount) / 100).toLocaleString()}</span>}
                      </div>
                    ))}
                    {(replayData.ticks[replayData.currentTick]?.events ?? []).length === 0 && (
                      <span className="text-slate-600">No events this tick</span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Day costs */}
          {day && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">
                Day {day.day + 1} Results{' '}
                <span className="text-xs text-slate-500 font-normal ml-1">seed={day.seed}</span>
              </h3>
              {/* Settlement Rate Banner */}
              {(() => {
                // Count arrivals and settlements per agent and aggregate
                const agentArrivals: Record<string, number> = {};
                const agentSettled: Record<string, number> = {};
                let totalArrivals = 0;
                let totalSettled = 0;
                for (const e of day.events) {
                  const t = String(e.event_type ?? '');
                  if (t === 'Arrival') {
                    const sender = String((e as Record<string, unknown>).sender_id ?? '');
                    if (sender) {
                      agentArrivals[sender] = (agentArrivals[sender] ?? 0) + 1;
                    }
                    totalArrivals++;
                  } else if (t === 'RtgsImmediateSettlement' || t === 'CycleSettlement' || t === 'BilateralOffset') {
                    const sender = String((e as Record<string, unknown>).sender_id ?? '');
                    if (sender) {
                      agentSettled[sender] = (agentSettled[sender] ?? 0) + 1;
                    }
                    totalSettled++;
                  }
                }
                const aggRate = totalArrivals > 0 ? (totalSettled / totalArrivals * 100) : 0;
                return (
                  <div className="bg-slate-900/50 rounded-lg p-3 mb-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-semibold text-slate-400">
                        Settlement Rate<InfoTip text="Percentage of payments that settled successfully during the day. Higher is better — unsettled payments incur delay costs and deadline penalties." />
                      </span>
                      <span className={`font-mono text-lg font-bold ${aggRate >= 90 ? 'text-green-400' : aggRate >= 70 ? 'text-amber-400' : 'text-red-400'}`}>
                        {aggRate.toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex gap-3 text-[10px] text-slate-500">
                      <span>{totalSettled}/{totalArrivals} payments settled</span>
                      {gameState.agent_ids.map((aid, i) => {
                        const arr = agentArrivals[aid] ?? 0;
                        const stl = agentSettled[aid] ?? 0;
                        const rate = arr > 0 ? (stl / arr * 100) : 0;
                        return (
                          <span key={aid}>
                            <span style={{ color: AGENT_COLORS[i % AGENT_COLORS.length] }}>{aid.replace('BANK_', '')}</span>
                            : {rate.toFixed(1)}%
                          </span>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}
              <div className="space-y-3">
                {gameState.agent_ids.map((aid, i) => {
                  const costs = day.costs[aid];
                  const fraction = day.policies[aid]?.initial_liquidity_fraction ?? 1;
                  // Per-agent settlement rate
                  let agentArr = 0;
                  let agentStl = 0;
                  for (const e of day.events) {
                    const sender = String((e as Record<string, unknown>).sender_id ?? '');
                    if (sender !== aid) continue;
                    const t = String(e.event_type ?? '');
                    if (t === 'Arrival') agentArr++;
                    else if (t === 'RtgsImmediateSettlement' || t === 'CycleSettlement' || t === 'BilateralOffset') agentStl++;
                  }
                  const agentRate = agentArr > 0 ? (agentStl / agentArr * 100) : 0;
                  return (
                    <div key={aid} className="bg-slate-900/50 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-mono text-sm" style={{ color: AGENT_COLORS[i % AGENT_COLORS.length] }}>
                          {aid}
                        </span>
                        <div className="flex items-center gap-3">
                          <span className={`text-xs font-mono ${agentRate >= 90 ? 'text-green-400' : agentRate >= 70 ? 'text-amber-400' : 'text-red-400'}`}>
                            {agentRate.toFixed(1)}% settled
                          </span>
                          <span className="text-xs text-slate-400">
                            fraction={fraction.toFixed(3)}
                          </span>
                        </div>
                      </div>
                      {costs && (
                        <div className="grid grid-cols-4 gap-2 text-xs">
                          <div>
                            <div className="text-slate-500">Liquidity<InfoTip text="Cost of holding committed liquidity idle. Charged per tick based on committed amount × liquidity rate (bps)." /></div>
                            <div className="font-mono">{Math.round(costs.liquidity_cost).toLocaleString()}</div>
                          </div>
                          <div>
                            <div className="text-slate-500">Delay<InfoTip text="Cost of unsettled payments waiting in queue. Charged per tick based on payment amount × delay rate." /></div>
                            <div className="font-mono">{Math.round(costs.delay_cost).toLocaleString()}</div>
                          </div>
                          <div>
                            <div className="text-slate-500">Penalty<InfoTip text="Flat fee for each payment that missed its deadline or remained unsettled at end of day." /></div>
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

          {/* Policy Evolution */}
          {gameState.days.length > 0 && (
            <PolicyEvolutionPanel
              gameId={gameId}
              agentIds={gameState.agent_ids}
              currentDay={gameState.current_day}
            />
          )}

          {/* Day-specific reasoning */}
          {gameState.reasoning_history && Object.keys(gameState.reasoning_history).length > 0 && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">
                🧠 {selectedDay !== null && selectedDay < gameState.days.length - 1
                  ? `Day ${selectedDay + 1} Reasoning`
                  : 'Latest Reasoning'}
              </h3>
              <div className="space-y-3">
                {gameState.agent_ids.map((aid, i) => {
                  const history = gameState.reasoning_history[aid] ?? [];
                  const reasoningIndex = selectedDay ?? history.length - 1;
                  const latest = history[reasoningIndex];
                  if (!latest) return null;
                  const bs = latest.bootstrap;
                  return (
                    <div key={aid} className={`bg-slate-900/50 rounded-lg p-3 border-l-2 ${
                      latest.accepted ? 'border-green-500' : 'border-red-500'
                    }`}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-xs" style={{ color: AGENT_COLORS[i % AGENT_COLORS.length] }}>
                          {aid}
                        </span>
                        {latest.mock && <span className="text-[10px] text-slate-600 bg-slate-800 px-1 rounded" title="Using mock reasoning (no API call)">sim</span>}
                        {latest.accepted
                          ? <span className="text-green-400 text-[10px] font-medium">✓ ACCEPTED</span>
                          : <span className="text-red-400 text-[10px] font-medium">✗ REJECTED</span>
                        }
                        {latest.old_fraction != null && latest.new_fraction != null && (
                          <span className="text-[10px] text-slate-500 font-mono">
                            {latest.old_fraction.toFixed(3)} → {latest.new_fraction.toFixed(3)}
                          </span>
                        )}
                      </div>
                      {bs && (
                        <div className="flex gap-3 text-[10px] text-slate-500 mb-1 font-mono">
                          <span>Δ={bs.delta_sum.toLocaleString()}<InfoTip text="Cost change from previous day (negative = improvement)" /></span>
                          <span>CV={bs.cv.toFixed(2)}<InfoTip text="Coefficient of variation — measures consistency across bootstrap samples (lower = more reliable)" /></span>
                          <span>CI=[{bs.ci_lower.toLocaleString()},{bs.ci_upper.toLocaleString()}]<InfoTip text="95% confidence interval — true cost likely falls in this range" /></span>
                          <span>n={bs.num_samples}<InfoTip text="Number of bootstrap evaluation samples" /></span>
                        </div>
                      )}
                      {!latest.accepted && latest.rejection_reason && (
                        <div className="text-[10px] text-red-400/80 mb-1">
                          {latest.rejection_reason}
                        </div>
                      )}
                      <p className="text-xs text-slate-400 leading-relaxed">{latest.reasoning}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Policy history (all iterations) */}
          {gameState.reasoning_history && gameState.agent_ids.some(aid => (gameState.reasoning_history[aid] ?? []).length > 0) && (
            <PolicyHistoryPanel agentIds={gameState.agent_ids} reasoningHistory={gameState.reasoning_history} fractionHistory={gameState.fraction_history} />
          )}

          {/* Policies for selected day */}
          <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">
              📋 {selectedDay !== null && selectedDay < gameState.days.length - 1
                ? `Day ${selectedDay + 1} Policies`
                : 'Current Policies'}
            </h3>
            <div className="space-y-2">
              {gameState.agent_ids.map((aid, i) => {
                const dayPolicies = day?.policies?.[aid];
                const pol = dayPolicies ?? gameState.current_policies[aid];
                return (
                  <div key={aid} className="flex items-center justify-between bg-slate-900/50 rounded-lg px-3 py-2">
                    <span className="font-mono text-sm" style={{ color: AGENT_COLORS[i % AGENT_COLORS.length] }}>
                      {aid}
                    </span>
                    <span className="font-mono text-sm text-slate-300">
                      fraction = {(pol?.initial_liquidity_fraction ?? 1.0).toFixed(3)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Events for selected day — summary + collapsible detail */}
      {day && day.events.length > 0 && (
        <EventSummary day={day} />
      )}
    </div>
  );
}

const EVENT_TOOLTIPS: Record<string, string> = {
  Arrival: 'New payment obligations generated',
  RtgsSubmission: 'Payments submitted to the RTGS engine for settlement',
  RtgsImmediateSettlement: 'Payments settled immediately (sufficient funds)',
  PolicySubmit: 'Agent policy decisions executed',
  CostAccrual: 'Periodic cost calculations applied',
  QueuedRtgs: 'Payments queued due to insufficient funds',
  DeferredCreditApplied: 'Intraday credit facility used to cover shortfall',
  ScenarioEventExecuted: 'Scheduled scenario event triggered',
  BilateralOffset: 'Bilateral netting applied between two banks',
  CycleSettlement: 'Multilateral payment cycle detected and settled',
};

function EventSummary({ day }: { day: { day: number; events: Record<string, unknown>[] } }) {
  const [expanded, setExpanded] = useState(false);

  // Count events by type
  const counts: Record<string, number> = {};
  for (const e of day.events) {
    const t = String(e.event_type ?? 'unknown');
    counts[t] = (counts[t] ?? 0) + 1;
  }

  const summaryEntries = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-slate-300">
          Day {day.day + 1} Events ({day.events.length})
        </h3>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-slate-500 hover:text-slate-300"
        >
          {expanded ? '▲ Collapse' : '▼ Show details'}
        </button>
      </div>
      <div className="text-xs text-slate-500 flex flex-wrap gap-x-3 gap-y-1">
        {summaryEntries.map(([type, count], i) => (
          <span key={i}>{count} {type}{EVENT_TOOLTIPS[type] && <InfoTip text={EVENT_TOOLTIPS[type]} />}</span>
        ))}
      </div>
      {expanded && (
        <div className="mt-3 max-h-48 overflow-y-auto text-xs font-mono text-slate-400 space-y-0.5 border-t border-slate-700 pt-3">
          {day.events.slice(0, 200).map((e, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-slate-600 w-6">{String(e.tick)}</span>
              <span className="text-sky-400">{String(e.event_type)}</span>
              {'sender_id' in e && 'receiver_id' in e && <span>{String(e.sender_id)}→{String(e.receiver_id)}</span>}
              {'agent_id' in e && !('sender_id' in e) && <span>{String(e.agent_id)}</span>}
              {'amount' in e && <span className="text-emerald-400">${(Number(e.amount)/100).toLocaleString()}</span>}
            </div>
          ))}
          {day.events.length > 200 && (
            <div className="text-slate-600">... and {day.events.length - 200} more</div>
          )}
        </div>
      )}
    </div>
  );
}

function PolicyHistoryPanel({ agentIds, reasoningHistory, fractionHistory }: {
  agentIds: string[];
  reasoningHistory: Record<string, GameOptimizationResult[]>;
  fractionHistory: Record<string, number[]>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState(agentIds[0] ?? '');

  const history = reasoningHistory[selectedAgent] ?? [];
  const fractions = fractionHistory[selectedAgent] ?? [];

  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-300">📊 Policy History</h3>
        <div className="flex items-center gap-2">
          {agentIds.map((aid, i) => (
            <button
              key={aid}
              onClick={() => setSelectedAgent(aid)}
              className={`px-2 py-0.5 rounded text-xs font-mono transition-all ${
                selectedAgent === aid
                  ? 'text-white'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
              style={selectedAgent === aid ? { backgroundColor: AGENT_COLORS[i % AGENT_COLORS.length] + '40', color: AGENT_COLORS[i % AGENT_COLORS.length] } : {}}
            >
              {aid}
            </button>
          ))}
          <button onClick={() => setExpanded(!expanded)} className="text-xs text-slate-500 hover:text-slate-300 ml-2">
            {expanded ? '▲ collapse' : `▼ ${history.length} iterations`}
          </button>
        </div>
      </div>

      {/* Compact: just fraction steps */}
      {!expanded && (
        <div className="flex items-center gap-1 flex-wrap text-xs font-mono">
          {fractions.map((f, i) => (
            <span key={i} className="flex items-center gap-0.5">
              {i > 0 && <span className="text-slate-600">→</span>}
              <span className={`${i === fractions.length - 1 ? 'text-white font-bold' : 'text-slate-400'}`}>
                {f.toFixed(3)}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* Expanded: full iteration history */}
      {expanded && (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {history.map((r, i) => (
            <div key={i} className={`bg-slate-900/50 rounded p-2 border-l-2 ${
              r.accepted ? 'border-green-500' : 'border-red-500'
            }`}>
              <div className="flex items-center gap-2 text-[10px]">
                <span className="text-slate-500">Day {i + 1}</span>
                <span className={r.accepted ? 'text-green-400' : 'text-red-400'}>
                  {r.accepted ? '✓' : '✗'}
                </span>
                {r.old_fraction != null && (
                  <span className="font-mono text-slate-400">
                    {r.old_fraction.toFixed(3)} → {r.new_fraction?.toFixed(3) ?? r.old_fraction.toFixed(3)}
                  </span>
                )}
                {r.mock && <span className="text-slate-600 bg-slate-800 px-1 rounded" title="Mock reasoning">sim</span>}
                {r.bootstrap && (
                  <span className="text-slate-600">
                    Δ={r.bootstrap.delta_sum.toLocaleString()} CV={r.bootstrap.cv.toFixed(2)}
                  </span>
                )}
              </div>
              {r.rejection_reason && (
                <div className="text-[9px] text-red-400/70 mt-0.5">{r.rejection_reason}</div>
              )}
            </div>
          ))}
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
  const fmtDollar = (v: number) => `$${(v / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

  const w = 400;
  const h = 150;
  const pad = { t: 10, r: 10, b: 20, l: 55 };
  const plotW = w - pad.l - pad.r;
  const plotH = h - pad.t - pad.b;

  const toX = (i: number) => pad.l + (numTicks > 1 ? (i / (numTicks - 1)) * plotW : plotW / 2);
  const toY = (v: number) => pad.t + plotH - ((v - minVal) / range) * plotH;

  const midVal = (maxVal + minVal) / 2;

  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        {/* Grid lines */}
        <line x1={pad.l} y1={pad.t} x2={pad.l + plotW} y2={pad.t} stroke="#334155" strokeWidth={0.5} />
        <line x1={pad.l} y1={toY(midVal)} x2={pad.l + plotW} y2={toY(midVal)} stroke="#334155" strokeWidth={0.5} strokeDasharray="4,4" />
        <line x1={pad.l} y1={pad.t + plotH} x2={pad.l + plotW} y2={pad.t + plotH} stroke="#334155" strokeWidth={0.5} />
        {/* Y axis labels */}
        <text x={pad.l - 4} y={pad.t + 4} textAnchor="end" className="fill-slate-500 text-[7px]">{fmtDollar(maxVal)}</text>
        <text x={pad.l - 4} y={toY(midVal) + 3} textAnchor="end" className="fill-slate-500 text-[7px]">{fmtDollar(midVal)}</text>
        <text x={pad.l - 4} y={h - pad.b} textAnchor="end" className="fill-slate-500 text-[7px]">{fmtDollar(minVal)}</text>
        {/* X axis labels */}
        {numTicks <= 20 && Array.from({ length: numTicks }, (_, i) => (
          <text key={i} x={toX(i)} y={h - 4} textAnchor="middle" className="fill-slate-500 text-[6px]">{i + 1}</text>
        ))}
        {/* Lines */}
        {agentIds.map((aid, ci) => {
          const vals = balanceHistory[aid] ?? [];
          if (vals.length < 1) return null;
          const points = vals.map((v, i) => `${toX(i)},${toY(v)}`).join(' ');
          return <polyline key={aid} points={points} fill="none" stroke={AGENT_COLORS[ci % AGENT_COLORS.length]} strokeWidth={1.5} />;
        })}
      </svg>
      {/* Legend */}
      <div className="flex gap-3 justify-center mt-1">
        {agentIds.map((aid, ci) => (
          <span key={aid} className="text-[10px] flex items-center gap-1">
            <span className="inline-block w-2.5 h-0.5 rounded" style={{ backgroundColor: AGENT_COLORS[ci % AGENT_COLORS.length] }} />
            <span className="text-slate-500">{aid}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
