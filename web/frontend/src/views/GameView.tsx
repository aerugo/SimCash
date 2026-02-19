import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { GameOptimizationResult } from '../types';
import { useGameWebSocket } from '../hooks/useGameWebSocket';
import { getGameDayReplay, downloadGameExport } from '../api';
import { PolicyEvolutionPanel } from '../components/PolicyEvolutionPanel';
import { PolicyDiffView, PolicyChangeSummary } from '../components/PolicyDiffView';
import { ReasoningExplorer } from '../components/ReasoningExplorer';
import { InfoTip } from '../components/Tooltip';
import { PaymentTraceView } from '../components/PaymentTraceView';
import { useGameContext } from '../GameContext';
import { useTour } from '../hooks/useTour';
import { TourOverlay, TourCompletionNote } from '../components/TourOverlay';

const AGENT_COLORS = ['#38bdf8', '#a78bfa', '#34d399', '#fb923c', '#f472b6', '#facc15', '#94a3b8', '#e879f9'];

function extractTreeActions(tree: Record<string, unknown>): string[] {
  if (!tree) return [];
  const actions: string[] = [];
  if (tree.action) actions.push(String(tree.action));
  if (tree.true_branch) actions.push(...extractTreeActions(tree.true_branch as Record<string, unknown>));
  if (tree.false_branch) actions.push(...extractTreeActions(tree.false_branch as Record<string, unknown>));
  return [...new Set(actions)];
}

function useGameNotes(gameId: string) {
  const key = `simcash_notes_${gameId}`;
  const [notes, setNotes] = useState(() => {
    try { return localStorage.getItem(key) ?? ''; } catch { return ''; }
  });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const update = useCallback((text: string) => {
    setNotes(text);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      try { localStorage.setItem(key, text); } catch { /* ignore */ }
    }, 500);
  }, [key]);

  // Cleanup on unmount
  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  return { notes, update };
}

/* AgentResponseDetail replaced by ReasoningExplorer component */

export function GameView() {
  const params = useParams<{ gameId: string }>();
  const nav = useNavigate();
  const { gameId: contextGameId, gameState: contextGameState, setGameState: onUpdate, handleReset } = useGameContext();
  const gameId = params.gameId ?? contextGameId ?? '';
  const initialState = contextGameState;
  const onReset = () => { handleReset(); nav('/'); };

  if (!initialState) {
    return (
      <div className="text-center py-20">
        <div className="text-4xl mb-4">🔍</div>
        <h2 className="text-xl font-semibold mb-2">Experiment Not Found</h2>
        <p className="text-sm text-slate-400 mb-4">No active experiment for ID: {gameId}</p>
        <button onClick={() => nav('/')} className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-sm font-medium">← Back to Home</button>
      </div>
    );
  }
  const { gameState: wsState, connected, connectionStatus, reconnectAttempt, phase, optimizingAgent: _optimizingAgent, optimizingAgents, simulatingDay, streamingText, step, rerun, autoRun, stop } = useGameWebSocket(gameId, initialState);
  void _optimizingAgent; // kept for API compat
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const [autoRunning, setAutoRunning] = useState(false);
  const [replayData, setReplayData] = useState<{
    dayNum: number;
    ticks: { tick: number; events: Record<string, unknown>[]; balances: Record<string, number> }[];
    currentTick: number;
  } | null>(null);
  const [replayPlaying, setReplayPlaying] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [showPaymentTrace, setShowPaymentTrace] = useState(false);
  const [speed, setSpeed] = useState<'fast' | 'normal' | 'slow'>('normal');
  const [notesOpen, setNotesOpen] = useState(false);
  const { notes, update: updateNotes } = useGameNotes(gameId);

  const SPEED_MS: Record<typeof speed, number> = { fast: 0, normal: 3000, slow: 8000 };

  const gameState = wsState ?? initialState;

  const tour = useTour(gameState.days.length, autoRunning);

  // Sync state up to parent — use ref to avoid dependency on onUpdate
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;
  useEffect(() => {
    if (wsState) onUpdateRef.current(wsState);
  }, [wsState]);

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
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2" data-tour="top-bar">
          <h2 className="text-xl sm:text-2xl font-bold">{'Policy Experiment'}</h2>
          <span className="text-base sm:text-lg font-mono text-sky-400">
            {'Round'} {gameState.current_day}/{gameState.max_days}
          </span>
          {gameState.is_complete && (
            <span className="px-2 py-1 rounded bg-green-500/20 text-green-400 text-xs font-medium">COMPLETE</span>
          )}
          {gameState.use_llm && (
            <span className="px-2 py-1 rounded bg-violet-500/20 text-violet-400 text-xs font-medium">🧠 AI</span>
          )}
          {connectionStatus === 'reconnecting' && (
            <span className="px-2 py-1 rounded bg-amber-500/20 text-amber-400 text-xs font-medium animate-pulse">
              🔄 Reconnecting{reconnectAttempt > 0 ? ` (${reconnectAttempt}/10)` : ''}…
            </span>
          )}
          {connectionStatus === 'disconnected' && (
            <span className="px-2 py-1 rounded bg-red-500/20 text-red-400 text-xs font-medium">⚠ Disconnected</span>
          )}
        </div>
        {/* Action buttons — wrap on mobile */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={step}
            disabled={!connected || autoRunning || gameState.is_complete}
            className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-sm font-medium text-white"
            data-tour="next-btn"
          >
            ▶ Next
          </button>
          <button
            onClick={() => rerun()}
            disabled={!connected || autoRunning || gameState.days.length === 0}
            title="Re-run the last round with the same seed (deterministic replay)"
            className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-sm font-medium text-white"
            data-tour="rerun-btn"
          >
            🔄 Re-run
          </button>
          <span className="contents" data-tour="auto-btn">
          <button
            onClick={autoRunning ? stop : handleAutoRun}
            disabled={!connected || gameState.is_complete}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium text-white ${
              autoRunning
                ? 'bg-red-600 hover:bg-red-500'
                : 'bg-slate-700 hover:bg-slate-600 disabled:opacity-40'
            }`}
          >
            {autoRunning ? '⏹ Stop' : '⏩ Auto'}
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
                className={`px-2 py-1.5 text-xs font-medium transition-all ${
                  speed === s
                    ? 'bg-slate-600 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-700'
                }`}
                title={`${s.charAt(0).toUpperCase() + s.slice(1)} speed`}
              >
                {icon}
              </button>
            ))}
          </div>
          </span>
          <div className="relative" data-tour="export-btn">
            <button
              onClick={() => setExportOpen(!exportOpen)}
              disabled={gameState.days.length === 0}
              className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-sm font-medium text-white"
            >
              📥 Export
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
                  onClick={async () => {
                    setExportOpen(false);
                    const { authFetch, getGameExportUrl } = await import('../api');
                    const res = await authFetch(getGameExportUrl(gameId, 'json'));
                    if (!res.ok) return;
                    const data = await res.json();
                    if (notes) data.researcher_notes = notes;
                    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = `game_${gameId}.json`; a.click();
                    URL.revokeObjectURL(url);
                  }}
                  className="w-full px-4 py-2 text-left text-sm hover:bg-slate-700 text-slate-200"
                >
                  📋 JSON
                </button>
              </div>
            )}
          </div>
          <button
            onClick={onReset}
            className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-sm font-medium"
          >
            New
          </button>
        </div>
      </div>

      {/* LLM error banner */}
      {(() => {
        const allResults = Object.values(gameState.reasoning_history ?? {}).flat();
        const fallbacks = allResults.filter(r => r.fallback_reason);
        if (fallbacks.length === 0) return null;
        const reason = fallbacks[0].fallback_reason || '';
        const short = reason.length > 120 ? reason.slice(0, 120) + '…' : reason;
        return (
          <div className="bg-amber-900/30 border border-amber-700 rounded-lg px-4 py-2 text-sm text-amber-300">
            ⚠️ <strong>LLM calls are failing</strong> — falling back to simulated AI. {short}
          </div>
        );
      })()}

      {/* Progress bar */}
      <div className="w-full bg-slate-800 rounded-full h-2" data-tour="progress-bar">
        <div
          className="bg-gradient-to-r from-sky-500 to-violet-500 h-2 rounded-full transition-all"
          style={{ width: `${(gameState.current_day / gameState.max_days) * 100}%` }}
        />
      </div>

      {autoRunning && phase === 'idle' && !gameState.is_complete && speed !== 'fast' && (
        <div className="bg-slate-700/30 border border-slate-600/30 rounded-xl p-3 text-center">
          <span className="text-sm text-slate-400">
            ⏳ Pausing between rounds... ({speed === 'normal' ? '3s' : '8s'})
          </span>
        </div>
      )}

      {phase === 'simulating' && (
        <div className="bg-sky-500/10 border border-sky-500/30 rounded-xl p-3 text-center animate-pulse">
          <span className="text-sm">⚙️ {'Simulating Round'} {(simulatingDay ?? 0) + 1}...</span>
        </div>
      )}
      {phase === 'optimizing' && optimizingAgents.size > 0 && (
        <div className="bg-violet-500/10 border border-violet-500/30 rounded-xl p-4 space-y-3">
          {[...optimizingAgents].map(aid => (
            <div key={aid}>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium">🧠 Optimizing {aid}</span>
                <span className="inline-block w-2 h-2 rounded-full bg-violet-400 animate-pulse" />
              </div>
              {streamingText[aid] ? (
                <div className="max-h-32 overflow-y-auto">
                  <pre className="text-xs text-slate-400 whitespace-pre-wrap font-mono leading-relaxed">
                    {streamingText[aid]}
                    <span className="inline-block w-1.5 h-3.5 bg-violet-400 animate-pulse ml-0.5 align-text-bottom" />
                  </pre>
                </div>
              ) : (
                <div className="text-xs text-slate-500 animate-pulse">Waiting for response...</div>
              )}
            </div>
          ))}
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
            <h3 className="text-lg font-semibold text-green-400 mb-3">Experiment Complete — {gameState.max_days} Rounds</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-xs text-slate-500">Round 1 Cost</div>
                <div className="font-mono text-sm">{firstTotal.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Final Cost</div>
                <div className="font-mono text-sm">{lastTotal.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Cost Reduction<InfoTip text="Percentage decrease in total system cost from Round 1 to the final round" /></div>
                <div className={`font-mono text-sm ${reduction > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {reduction > 0 ? '↓' : '↑'} {Math.abs(reduction).toFixed(1)}%
                </div>
              </div>
              <div>
                {gameState.constraint_preset === 'full' ? (
                  <>
                    <div className="text-xs text-slate-500">Final Policies<InfoTip text="Optimized decision trees for each bank" /></div>
                    <div className="text-xs text-slate-300 space-y-1">
                      {gameState.agent_ids.map(aid => {
                        const p = gameState.current_policies[aid];
                        const actions = p?.payment_tree ? extractTreeActions(p.payment_tree as Record<string, unknown>) : ['Release'];
                        const frac = (p?.parameters?.initial_liquidity_fraction as number) ?? 1;
                        return <div key={aid} className="font-mono">{aid.replace('BANK_', '')}: frac={frac.toFixed(3)}, actions=[{actions.join(',')}]</div>;
                      })}
                    </div>
                  </>
                ) : (
                  <>
                    <div className="text-xs text-slate-500">Final Fractions<InfoTip text="Each bank's liquidity commitment as a fraction of their pool (0 = none, 1 = all)" /></div>
                    <div className="font-mono text-xs text-slate-300">
                      {gameState.agent_ids.map(aid => {
                        const f = gameState.current_policies[aid]?.parameters?.initial_liquidity_fraction ?? 1;
                        return `${aid.replace('BANK_', '')}: ${(f as number).toFixed(3)}`;
                      }).join(' · ')}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        );
      })()}

      {/* Empty state guidance */}
      {gameState.days.length === 0 && (
        <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6 text-center" data-tour="empty-state">
          
          <h3 className="text-lg font-semibold mb-2">Ready to Start</h3>
          <p className="text-sm text-slate-400 max-w-lg mx-auto">
            Click <strong>▶ Next Day</strong> to simulate the first round. Each round, banks process payments using their current liquidity policy.
            After each round, the AI optimizer analyzes costs and proposes improved policies — watching for the sweet spot between
            holding too much liquidity (wasted capital) and too little (missed deadlines).
          </p>
          <p className="text-xs text-slate-500 mt-3">
            {(() => {
              const fracs = Object.entries(gameState.current_policies).map(([aid, p]) => ({ aid, f: (p.parameters?.initial_liquidity_fraction as number) ?? 1 }));
              const allSame = fracs.length > 0 && fracs.every(x => x.f === fracs[0].f);
              if (gameState.constraint_preset === 'full') {
                return <>Agents start with full decision-tree policies. The optimizer will refine payment strategies, bank actions, and parameters over multiple rounds.</>;
              }
              if (allSame) {
                return <>All agents start with <span className="font-mono text-slate-400">fraction = {fracs[0].f.toFixed(3)}</span> (commit {(fracs[0].f * 100).toFixed(0)}% of their pool). The optimizer will learn to reduce this over multiple rounds.</>;
              }
              return <>Agents start with custom fractions: {fracs.map((x, i) => <span key={x.aid}>{i > 0 && ', '}<span className="font-mono text-slate-400">{x.aid}={(x.f as number).toFixed(2)}</span></span>)}. The optimizer will refine these over multiple rounds.</>;
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
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4" data-tour="round-timeline">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">Round Timeline</h3>
              <div className="flex gap-1 flex-wrap">
                {gameState.days.map((d, i) => (
                  <button
                    key={i}
                    onClick={() => setSelectedDay(i)}
                    title={d.optimized ? `Round ${i + 1} — optimized` : `Round ${i + 1}`}
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
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4" data-tour="replay">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-slate-300">🔁 Tick Replay</h3>
                {!replayData || replayData.dayNum !== (selectedDay ?? gameState.days.length - 1) ? (
                  <button
                    onClick={() => handleReplay(selectedDay ?? gameState.days.length - 1)}
                    className="px-3 py-1 rounded bg-slate-700 hover:bg-slate-600 text-xs"
                  >
                    Load Round {(selectedDay ?? gameState.days.length - 1) + 1} Replay
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
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4" data-tour="day-costs">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">
                Round {day.day + 1} Results{' '}
                <span className="text-xs text-slate-500 font-normal ml-1">seed={day.seed}</span>
              </h3>
              {/* Settlement Rate Banner */}
              {(() => {
                const agentArrivals: Record<string, number> = {};
                const agentSettled: Record<string, number> = {};
                let totalArrivals = 0;
                let totalSettled = 0;
                for (const e of day.events) {
                  const t = String(e.event_type ?? '');
                  const rec = e as Record<string, unknown>;
                  if (t === 'Arrival') {
                    const sender = String(rec.sender_id ?? '');
                    if (sender) {
                      agentArrivals[sender] = (agentArrivals[sender] ?? 0) + 1;
                    }
                    totalArrivals++;
                  } else if (t === 'RtgsImmediateSettlement' || t === 'Queue2LiquidityRelease') {
                    // These events use "sender" not "sender_id"
                    const sender = String(rec.sender ?? '');
                    if (sender) {
                      agentSettled[sender] = (agentSettled[sender] ?? 0) + 1;
                    }
                    totalSettled++;
                  } else if (t === 'LsmBilateralOffset') {
                    // Both agents settle — agent_a and agent_b
                    for (const k of ['agent_a', 'agent_b']) {
                      const a = String(rec[k] ?? '');
                      if (a) agentSettled[a] = (agentSettled[a] ?? 0) + 1;
                    }
                    totalSettled += 2;
                  } else if (t === 'LsmCycleSettlement') {
                    const agents = rec.agents as string[] | undefined;
                    if (agents) {
                      for (const a of agents) {
                        agentSettled[a] = (agentSettled[a] ?? 0) + 1;
                      }
                      totalSettled += agents.length;
                    }
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
                    const rec = e as Record<string, unknown>;
                    const t = String(rec.event_type ?? '');
                    if (t === 'Arrival' && String(rec.sender_id ?? '') === aid) agentArr++;
                    else if ((t === 'RtgsImmediateSettlement' || t === 'Queue2LiquidityRelease') && String(rec.sender ?? '') === aid) agentStl++;
                    else if (t === 'LsmBilateralOffset' && (String(rec.agent_a ?? '') === aid || String(rec.agent_b ?? '') === aid)) agentStl++;
                    else if (t === 'LsmCycleSettlement' && (rec.agents as string[] | undefined)?.includes(aid)) agentStl++;
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
                          {gameState.constraint_preset !== 'full' && (
                            <span className="text-xs text-slate-400">
                              fraction={fraction.toFixed(3)}
                            </span>
                          )}
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
                            <div className="text-slate-500">Penalty<InfoTip text="Flat fee for each payment that missed its deadline or remained unsettled at end of round." /></div>
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
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4" data-tour="balance-chart">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">Round {day.day + 1} Balances</h3>
              <MiniBalanceChart balanceHistory={day.balance_history} agentIds={gameState.agent_ids} />
            </div>
          )}
        </div>

        {/* Right: Policy evolution */}
        <div className="space-y-4">
          {/* Fraction evolution chart — only show in simple mode */}
          {gameState.days.length > 0 && gameState.constraint_preset !== 'full' && (
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

          {/* Policy changes summary — show in full mode */}
          {gameState.days.length > 0 && gameState.constraint_preset === 'full' && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">📊 Policy Evolution</h3>
              <div className="space-y-3">
                {gameState.agent_ids.map(aid => {
                  const history = gameState.reasoning_history[aid] || [];
                  const latest = history[history.length - 1];
                  if (!latest) return null;
                  return (
                    <div key={aid} className="border-l-2 border-slate-600 pl-3">
                      <div className="text-xs font-medium text-sky-400 mb-1">{aid}</div>
                      <PolicyDiffView oldPolicy={latest.old_policy} newPolicy={latest.new_policy} compact />
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Cost evolution chart */}
          {gameState.days.length > 0 && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4" data-tour="cost-evolution">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">Cost Evolution</h3>
              <EvolutionChart
                data={gameState.cost_history}
                agentIds={gameState.agent_ids}
                yLabel="Cost"
                format={(v) => Math.round(v).toLocaleString()}
              />
            </div>
          )}

          {/* Policy Evolution — fraction chart only in simple mode */}
          {gameState.days.length > 0 && gameState.constraint_preset !== 'full' && (
            <PolicyEvolutionPanel
              gameId={gameId}
              agentIds={gameState.agent_ids}
              currentDay={gameState.current_day}
            />
          )}

          {/* Day-specific reasoning */}
          {gameState.reasoning_history && Object.keys(gameState.reasoning_history).length > 0 && (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4" data-tour="reasoning">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">
                🧠 {selectedDay !== null && selectedDay < gameState.days.length - 1
                  ? `Round ${selectedDay + 1} Reasoning`
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
                        {latest.mock && <span className="text-[10px] text-slate-600 bg-slate-800 px-1 rounded" title={latest.fallback_reason ? `LLM failed: ${latest.fallback_reason}` : "Using mock reasoning (no API call)"}>{latest.fallback_reason ? '⚠ fallback' : 'sim'}</span>}
                        {latest.accepted
                          ? <span className="text-green-400 text-[10px] font-medium">✓ ACCEPTED</span>
                          : <span className="text-red-400 text-[10px] font-medium">✗ REJECTED</span>
                        }
                        {gameState.constraint_preset !== 'full' && latest.old_fraction != null && latest.new_fraction != null && (
                          <span className="text-[10px] text-slate-500 font-mono">
                            {latest.old_fraction.toFixed(3)} → {latest.new_fraction.toFixed(3)}
                          </span>
                        )}
                        {gameState.constraint_preset === 'full' && latest.new_policy && (
                          <PolicyChangeSummary oldPolicy={latest.old_policy} newPolicy={latest.new_policy} />
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

                      {/* Metadata bar: model, latency, tokens */}
                      {(latest.latency_seconds || latest.usage || latest.model) && (
                        <div className="flex flex-wrap gap-2 mt-1.5 text-[10px] text-slate-600 font-mono">
                          {latest.model && <span>{latest.model.split(':').pop()}</span>}
                          {latest.latency_seconds != null && <span>{latest.latency_seconds}s</span>}
                          {latest.usage && (
                            <>
                              <span>{latest.usage.input_tokens.toLocaleString()}→{latest.usage.output_tokens.toLocaleString()} tok</span>
                              {latest.usage.thinking_tokens > 0 && (
                                <span>🧠 {latest.usage.thinking_tokens.toLocaleString()} thinking</span>
                              )}
                            </>
                          )}
                        </div>
                      )}

                      {/* Expandable full AI response */}
                      <ReasoningExplorer result={latest} />

                      {gameState.constraint_preset === 'full' && latest.new_policy && latest.old_policy && (
                        <div className="mt-2 pt-2 border-t border-slate-700/50">
                          <PolicyDiffView oldPolicy={latest.old_policy} newPolicy={latest.new_policy} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Policy history (all iterations) */}
          {gameState.reasoning_history && gameState.agent_ids.some(aid => (gameState.reasoning_history[aid] ?? []).length > 0) && (
            <PolicyHistoryPanel agentIds={gameState.agent_ids} reasoningHistory={gameState.reasoning_history} fractionHistory={gameState.fraction_history} constraintPreset={gameState.constraint_preset} />
          )}

          {/* Policies for selected day */}
          <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4" data-tour="policy-display">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">
              📋 {selectedDay !== null && selectedDay < gameState.days.length - 1
                ? `Round ${selectedDay + 1} Policies`
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

      {/* Payment Trace / Events toggle */}
      {day && (
        <div className="flex gap-2 mb-0">
          <button
            onClick={() => setShowPaymentTrace(false)}
            className={`px-3 py-1.5 rounded-t-lg text-xs font-medium transition-all ${
              !showPaymentTrace ? 'bg-slate-800 text-white border border-b-0 border-slate-700' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            📊 Event Summary
          </button>
          <button
            onClick={() => setShowPaymentTrace(true)}
            className={`px-3 py-1.5 rounded-t-lg text-xs font-medium transition-all ${
              showPaymentTrace ? 'bg-slate-800 text-white border border-b-0 border-slate-700' : 'text-slate-500 hover:text-slate-300'
            }`}
            data-tour="payment-trace"
          >
            📋 Payment Trace
          </button>
        </div>
      )}

      {day && !showPaymentTrace && day.events.length > 0 && (
        <EventSummary day={day} />
      )}

      {day && showPaymentTrace && (
        <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">
            📋 Payment Lifecycle — Day {day.day + 1}
          </h3>
          <PaymentTraceView gameId={gameId} dayNum={day.day} />
        </div>
      )}

      {/* Notes panel */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700" data-tour="notes">
        <button
          onClick={() => setNotesOpen(!notesOpen)}
          className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-slate-300 hover:text-white transition-colors"
        >
          <span>📝 Notes {notes && <span className="text-xs text-slate-500 font-normal ml-1">({notes.length} chars)</span>}</span>
          <span className="text-slate-500">{notesOpen ? '▲' : '▼'}</span>
        </button>
        {notesOpen && (
          <div className="px-4 pb-4">
            <textarea
              value={notes}
              onChange={e => updateNotes(e.target.value)}
              placeholder="Jot observations about this experiment… (auto-saved to browser, included in JSON export)"
              className="w-full h-32 bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 placeholder-slate-600 resize-y focus:outline-none focus:border-sky-500"
            />
          </div>
        )}
      </div>

      {/* Tour overlay */}
      {tour.state.active && tour.currentStep && (
        <TourOverlay
          step={tour.state.step}
          currentStep={tour.currentStep}
          waitingForRound={tour.state.waitingForRound}
          waitingForAuto={tour.state.waitingForAuto}
          onNext={tour.next}
          onBack={tour.back}
          onSkip={tour.skip}
        />
      )}
      {tour.state.showCompletion && (
        <TourCompletionNote onDismiss={tour.dismissCompletion} />
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
          Round {day.day + 1} Events ({day.events.length})
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

function PolicyHistoryPanel({ agentIds, reasoningHistory, fractionHistory, constraintPreset }: {
  agentIds: string[];
  reasoningHistory: Record<string, GameOptimizationResult[]>;
  fractionHistory: Record<string, number[]>;
  constraintPreset?: string;
}) {
  const [selectedAgent, setSelectedAgent] = useState(agentIds[0] ?? '');
  const [selectedRound, setSelectedRound] = useState<number | null>(null);

  const history = reasoningHistory[selectedAgent] ?? [];
  const fractions = fractionHistory[selectedAgent] ?? [];
  const selected = selectedRound !== null ? history[selectedRound] : null;

  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-300">📊 Policy History</h3>
        <div className="flex items-center gap-2">
          {agentIds.map((aid, i) => (
            <button
              key={aid}
              onClick={() => { setSelectedAgent(aid); setSelectedRound(null); }}
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
        </div>
      </div>

      {/* Round pills — clickable iteration selector */}
      <div className="flex items-center gap-1 flex-wrap mb-2">
        {history.map((r, i) => {
          const isSelected = selectedRound === i;
          const fraction = constraintPreset !== 'full' && fractions[i + 1] != null
            ? fractions[i + 1].toFixed(3) : null;
          return (
            <button
              key={i}
              onClick={() => setSelectedRound(isSelected ? null : i)}
              className={`group flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-mono transition-all border ${
                isSelected
                  ? 'bg-slate-700 border-slate-500 text-white'
                  : 'bg-slate-900/50 border-slate-700/50 text-slate-500 hover:text-slate-300 hover:border-slate-600'
              }`}
              title={r.reasoning}
            >
              <span className="text-slate-600 group-hover:text-slate-400">R{i + 1}</span>
              <span className={r.accepted ? 'text-green-400' : 'text-red-400'}>
                {r.accepted ? '✓' : '✗'}
              </span>
              {fraction && <span className={isSelected ? 'text-slate-300' : 'text-slate-600'}>{fraction}</span>}
              {r.mock && !r.fallback_reason && <span className="text-slate-700">sim</span>}
              {r.fallback_reason && <span className="text-amber-600">⚠</span>}
            </button>
          );
        })}
      </div>

      {/* Fraction trajectory (always visible, compact) */}
      {constraintPreset !== 'full' && fractions.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap text-[10px] font-mono text-slate-500 mb-2">
          {fractions.map((f, i) => (
            <span key={i} className="flex items-center gap-0.5">
              {i > 0 && <span className="text-slate-700">→</span>}
              <span className={`${
                selectedRound !== null && i === selectedRound + 1
                  ? 'text-white font-bold'
                  : i === fractions.length - 1
                    ? 'text-slate-300'
                    : 'text-slate-500'
              }`}>
                {f.toFixed(3)}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* Selected round detail */}
      {selected && (
        <div className={`bg-slate-900/50 rounded-lg p-3 border-l-2 ${
          selected.accepted ? 'border-green-500' : 'border-red-500'
        }`}>
          <div className="flex items-center gap-2 text-[10px] mb-1">
            <span className="text-slate-400 font-medium">Round {selectedRound! + 1}</span>
            <span className={selected.accepted ? 'text-green-400 font-medium' : 'text-red-400 font-medium'}>
              {selected.accepted ? '✓ ACCEPTED' : '✗ REJECTED'}
            </span>
            {constraintPreset !== 'full' && selected.old_fraction != null && (
              <span className="font-mono text-slate-400">
                {selected.old_fraction.toFixed(3)} → {selected.new_fraction?.toFixed(3) ?? selected.old_fraction.toFixed(3)}
              </span>
            )}
            {constraintPreset === 'full' && (
              <PolicyChangeSummary oldPolicy={selected.old_policy} newPolicy={selected.new_policy} />
            )}
            {selected.mock && <span className={`bg-slate-800 px-1 rounded ${selected.fallback_reason ? 'text-amber-500' : 'text-slate-600'}`}>{selected.fallback_reason ? '⚠ fallback' : 'sim'}</span>}
          </div>

          {selected.bootstrap && (
            <div className="flex gap-3 text-[10px] text-slate-500 mb-1 font-mono">
              <span>Δ={selected.bootstrap.delta_sum.toLocaleString()}</span>
              <span>CV={selected.bootstrap.cv.toFixed(2)}</span>
              <span>CI=[{selected.bootstrap.ci_lower.toLocaleString()},{selected.bootstrap.ci_upper.toLocaleString()}]</span>
            </div>
          )}

          {selected.rejection_reason && (
            <div className="text-[10px] text-red-400/80 mb-1">{selected.rejection_reason}</div>
          )}

          <p className="text-xs text-slate-400 leading-relaxed mb-1">{selected.reasoning}</p>

          {/* Token stats */}
          {(selected.latency_seconds || selected.usage) && (
            <div className="flex flex-wrap gap-2 text-[10px] text-slate-600 font-mono mb-1">
              {selected.latency_seconds != null && <span>⏱ {selected.latency_seconds.toFixed(1)}s</span>}
              {selected.usage && (
                <>
                  <span>📥 {selected.usage.input_tokens.toLocaleString()}</span>
                  <span>📤 {selected.usage.output_tokens.toLocaleString()}</span>
                  {selected.usage.thinking_tokens > 0 && <span>🧠 {selected.usage.thinking_tokens.toLocaleString()}</span>}
                </>
              )}
            </div>
          )}

          <ReasoningExplorer result={selected} compact />
        </div>
      )}

      {/* No round selected hint */}
      {!selected && history.length > 0 && (
        <div className="text-[10px] text-slate-600 text-center py-2">
          Click a round above to explore reasoning
        </div>
      )}
    </div>
  );
}

// Shared tooltip hook for SVG charts
function useChartTooltip() {
  const [tooltip, setTooltip] = useState<{ x: number; y: number; content: React.ReactNode } | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const showTooltip = useCallback((e: React.MouseEvent, content: React.ReactNode) => {
    const rect = (e.currentTarget as Element).closest('.chart-container')?.getBoundingClientRect();
    if (!rect) return;
    setTooltip({ x: e.clientX - rect.left + 12, y: e.clientY - rect.top - 8, content });
  }, []);

  const hideTooltip = useCallback(() => setTooltip(null), []);

  return { tooltip, showTooltip, hideTooltip, containerRef };
}

function ChartTooltip({ tooltip }: { tooltip: { x: number; y: number; content: React.ReactNode } | null }) {
  if (!tooltip) return null;
  return (
    <div
      className="absolute pointer-events-none z-50 px-2.5 py-1.5 rounded-lg bg-slate-800 border border-slate-600 text-white text-xs shadow-xl whitespace-nowrap"
      style={{ left: tooltip.x, top: tooltip.y, transform: 'translateY(-100%)' }}
    >
      {tooltip.content}
    </div>
  );
}

// Simple SVG line chart for evolution data
function EvolutionChart({ data, agentIds, yLabel, format }: {
  data: Record<string, number[]>;
  agentIds: string[];
  yLabel?: string;
  format: (v: number) => string;
}) {
  const { tooltip, showTooltip, hideTooltip } = useChartTooltip();
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
    <div className="relative chart-container">
      <ChartTooltip tooltip={tooltip} />
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
                <circle
                  key={i}
                  cx={toX(i)}
                  cy={toY(v)}
                  r={3}
                  fill={AGENT_COLORS[ci % AGENT_COLORS.length]}
                  className="cursor-pointer"
                  onMouseMove={(e) => showTooltip(e, (
                    <div>
                      <div className="font-semibold" style={{ color: AGENT_COLORS[ci % AGENT_COLORS.length] }}>{aid}</div>
                      <div>Round {i + 1}: <span className="font-mono">{format(v)}</span></div>
                      {yLabel && <div className="text-slate-400 text-[10px]">{yLabel}</div>}
                    </div>
                  ))}
                  onMouseLeave={hideTooltip}
                />
              ))}
              {/* Larger invisible hit targets */}
              {vals.map((v, i) => (
                <circle
                  key={`hit-${i}`}
                  cx={toX(i)}
                  cy={toY(v)}
                  r={8}
                  fill="transparent"
                  className="cursor-pointer"
                  onMouseMove={(e) => showTooltip(e, (
                    <div>
                      <div className="font-semibold" style={{ color: AGENT_COLORS[ci % AGENT_COLORS.length] }}>{aid}</div>
                      <div>Round {i + 1}: <span className="font-mono">{format(v)}</span></div>
                      {yLabel && <div className="text-slate-400 text-[10px]">{yLabel}</div>}
                    </div>
                  ))}
                  onMouseLeave={hideTooltip}
                />
              ))}
              <text x={toX(vals.length - 1) + 4} y={toY(vals[vals.length - 1]) + 3}
                className="text-[7px]" fill={AGENT_COLORS[ci % AGENT_COLORS.length]}>{aid}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function MiniBalanceChart({ balanceHistory, agentIds }: {
  balanceHistory: Record<string, number[]>;
  agentIds: string[];
}) {
  const { tooltip, showTooltip, hideTooltip } = useChartTooltip();
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

  // For vertical hover line — find nearest tick column on mouse move over the chart area
  const [hoverInfo, setHoverInfo] = useState<{ tickIdx: number; svgX: number } | null>(null);

  const handleChartMouseMove = useCallback((e: React.MouseEvent<SVGRectElement>) => {
    const svg = (e.currentTarget as Element).closest('svg');
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const mouseX = (e.clientX - rect.left) / rect.width * w;
    // Find nearest tick
    let nearest = 0;
    let minDist = Infinity;
    for (let i = 0; i < numTicks; i++) {
      const dist = Math.abs(toX(i) - mouseX);
      if (dist < minDist) { minDist = dist; nearest = i; }
    }
    setHoverInfo({ tickIdx: nearest, svgX: toX(nearest) });

    // Build tooltip content
    const content = (
      <div>
        <div className="font-semibold text-slate-300 mb-1">Tick {nearest + 1}</div>
        {agentIds.map((aid, ci) => {
          const vals = balanceHistory[aid] ?? [];
          const val = vals[nearest];
          if (val === undefined) return null;
          return (
            <div key={aid} className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: AGENT_COLORS[ci % AGENT_COLORS.length] }} />
              <span style={{ color: AGENT_COLORS[ci % AGENT_COLORS.length] }}>{aid}:</span>
              <span className="font-mono">{fmtDollar(val)}</span>
            </div>
          );
        })}
      </div>
    );
    showTooltip(e, content);
  }, [numTicks, agentIds, balanceHistory, showTooltip, fmtDollar, toX, w]);

  const handleChartMouseLeave = useCallback(() => {
    setHoverInfo(null);
    hideTooltip();
  }, [hideTooltip]);

  return (
    <div className="relative chart-container">
      <ChartTooltip tooltip={tooltip} />
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
        {/* Hover vertical line */}
        {hoverInfo && (
          <line x1={hoverInfo.svgX} y1={pad.t} x2={hoverInfo.svgX} y2={pad.t + plotH} stroke="#64748b" strokeWidth={0.5} strokeDasharray="3,3" />
        )}
        {/* Lines */}
        {agentIds.map((aid, ci) => {
          const vals = balanceHistory[aid] ?? [];
          if (vals.length < 1) return null;
          const points = vals.map((v, i) => `${toX(i)},${toY(v)}`).join(' ');
          return <polyline key={aid} points={points} fill="none" stroke={AGENT_COLORS[ci % AGENT_COLORS.length]} strokeWidth={1.5} />;
        })}
        {/* Hover dots */}
        {hoverInfo && agentIds.map((aid, ci) => {
          const vals = balanceHistory[aid] ?? [];
          const val = vals[hoverInfo.tickIdx];
          if (val === undefined) return null;
          return (
            <circle key={aid} cx={hoverInfo.svgX} cy={toY(val)} r={3} fill={AGENT_COLORS[ci % AGENT_COLORS.length]} stroke="#1e293b" strokeWidth={1} />
          );
        })}
        {/* Invisible hover rect over entire plot area */}
        <rect
          x={pad.l} y={pad.t} width={plotW} height={plotH}
          fill="transparent"
          className="cursor-crosshair"
          onMouseMove={handleChartMouseMove}
          onMouseLeave={handleChartMouseLeave}
        />
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
