import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { GameOptimizationResult, GameState } from '../types';
import { useGameWebSocket } from '../hooks/useGameWebSocket';
import { getGameDayReplay, downloadGameExport } from '../api';
import { PolicyEvolutionPanel } from '../components/PolicyEvolutionPanel';
import { PolicyDiffView, PolicyChangeSummary } from '../components/PolicyDiffView';
import { ReasoningExplorer } from '../components/ReasoningExplorer';
import { InfoTip } from '../components/Tooltip';
import { PaymentTraceView } from '../components/PaymentTraceView';
import { useGameContext } from '../GameContext';
import { PolicyViewerModal } from '../components/PolicyViewerModal';
import { useTour } from '../hooks/useTour';
import { TourOverlay, TourCompletionNote } from '../components/TourOverlay';
import { ActivityFeed, useActivityLog } from '../components/ActivityFeed';
import { PromptExplorer } from '../components/PromptExplorer';
import type { WSMessage } from '../hooks/useGameWebSocket';

import { getAgentColor as _getAgentColorUtil } from '../utils';

/** Theme-aware agent color array — reads from CSS vars */
function getAgentColorArray(): string[] {
  const s = getComputedStyle(document.documentElement);
  return [
    s.getPropertyValue('--agent-1').trim() || '#4A6FA5',
    s.getPropertyValue('--agent-2').trim() || '#7A6B98',
    s.getPropertyValue('--agent-3').trim() || '#3D7A55',
    s.getPropertyValue('--agent-4').trim() || '#B8854A',
    s.getPropertyValue('--agent-5').trim() || '#A06070',
    s.getPropertyValue('--agent-1').trim() || '#4A6FA5',
    s.getPropertyValue('--agent-2').trim() || '#7A6B98',
    s.getPropertyValue('--agent-3').trim() || '#3D7A55',
  ];
}
const AGENT_COLORS = new Proxy([] as string[], {
  get(_target, prop) {
    if (prop === 'length') return 8;
    if (typeof prop === 'string' && !isNaN(Number(prop))) return getAgentColorArray()[Number(prop) % 8];
    if (prop === Symbol.iterator) return function* () { const a = getAgentColorArray(); for (const c of a) yield c; };
    return ([] as unknown as Record<string | symbol, unknown>)[prop];
  },
});

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
  // Only use context state if it matches the current game (avoids stale state from previous game)
  const useContextState = contextGameState && contextGameId === gameId;
  const relevantContextState = useContextState ? contextGameState : null;
  const [fetchedState, setFetchedState] = useState<GameState | null>(null);
  const [fetchRetrying, setFetchRetrying] = useState(false);
  const [fetchLoading, setFetchLoading] = useState(false);
  const fetchRetryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initialState = relevantContextState ?? fetchedState;

  // Reset fetched state when gameId changes (navigating between experiments)
  useEffect(() => {
    setFetchedState(null);
    setFetchRetrying(false);
    setFetchLoading(false);
  }, [gameId]);
  const onReset = () => { handleReset(); nav('/'); };

  // Fetch game from API if not in context (e.g. direct navigation or from experiments list)
  // Auto-retries every 5s on 404 (backend may be restarting / loading checkpoint)
  useEffect(() => {
    if (relevantContextState || !gameId || fetchedState) return;
    let cancelled = false;
    setFetchLoading(true);

    const attempt = () => {
      import('../api').then(({ getGame }) => getGame(gameId))
        .then(state => {
          if (cancelled) return;
          setFetchedState(state);
          setFetchLoading(false);
          setFetchRetrying(false);
        })
        .catch(() => {
          if (cancelled) return;
          setFetchRetrying(true);
          fetchRetryRef.current = setTimeout(attempt, 5000);
        });
    };
    attempt();

    return () => {
      cancelled = true;
      if (fetchRetryRef.current) clearTimeout(fetchRetryRef.current);
    };
  }, [gameId, relevantContextState, fetchedState]);

  // ALL hooks must be called before any conditional returns (React rules of hooks)
  const { gameState: wsState, connected, connectionStatus, reconnectAttempt, phase, optimizingAgent: _optimizingAgent, optimizingAgents, simulatingDay, streamingText, step, rerun, autoRun, stop, onRawMessage } = useGameWebSocket(gameId, initialState);
  void _optimizingAgent; // kept for API compat

  // Stall detection: track time since last WS message
  const lastWsMsgRef = useRef<number>(Date.now());
  const [stalled, setStalled] = useState(false);

  useEffect(() => {
    return onRawMessage(() => {
      lastWsMsgRef.current = Date.now();
      setStalled(false);
    });
  }, [onRawMessage]);

  // Check for stall every 10s during auto-run
  useEffect(() => {
    const id = setInterval(() => {
      if (phase !== 'idle' && connectionStatus === 'connected') {
        const age = Date.now() - lastWsMsgRef.current;
        if (age > 60_000) setStalled(true);
      } else {
        setStalled(false);
      }
    }, 10_000);
    return () => clearInterval(id);
  }, [phase, connectionStatus]);

  // Activity feed
  const actLog = useActivityLog();
  const simStartTimeRef = useRef<number>(0);
  const simEventIdRef = useRef<number | null>(null);

  useEffect(() => {
    return onRawMessage((msg: WSMessage) => {
      const d = msg.data as Record<string, unknown> | undefined;
      switch (msg.type) {
        case 'simulation_running':
          simStartTimeRef.current = Date.now();
          simEventIdRef.current = actLog.push(
            'simulation_running',
            `Simulating day ${((msg.day as number) ?? 0) + 1}...`,
            'info',
            true,
          );
          break;
        case 'simulation_progress':
          // Update the active simulation event with elapsed time
          break;
        case 'day_complete': {
          if (simEventIdRef.current) actLog.deactivate(simEventIdRef.current);
          const elapsed = Math.round((Date.now() - simStartTimeRef.current) / 1000);
          const totalCost = d?.total_cost as number | undefined;
          actLog.push(
            'simulation_complete',
            `Day complete in ${elapsed}s` + (totalCost != null ? ` — total cost: ${Math.round(totalCost).toLocaleString()}` : ''),
            'success',
          );
          break;
        }
        case 'optimization_start':
          actLog.push('agent_thinking', `${msg.agent_id}: analyzing results...`, 'info', true);
          break;
        case 'optimization_complete': {
          const result = d as Record<string, unknown> | undefined;
          const accepted = result?.accepted;
          const oldFrac = result?.old_fraction as number | undefined;
          const newFrac = result?.new_fraction as number | undefined;
          const fallback = result?.fallback_reason as string | undefined;
          let detail = '';
          if (fallback) {
            detail = ` (fallback: ${fallback.slice(0, 60)})`;
          } else if (accepted && oldFrac != null && newFrac != null) {
            detail = ` (fraction ${oldFrac.toFixed(3)} → ${newFrac.toFixed(3)})`;
          } else if (!accepted) {
            const reason = result?.rejection_reason as string | undefined;
            detail = reason ? ` (rejected: ${reason.slice(0, 60)})` : ' (rejected)';
          }
          actLog.push(
            'agent_done',
            `${msg.agent_id}: policy ${accepted ? 'updated' : 'rejected'}${detail}`,
            fallback ? 'warning' : accepted ? 'success' : 'info',
          );
          break;
        }
        case 'agent_retry':
          actLog.push('agent_retry', `${msg.agent_id}: retrying (${msg.reason ?? 'rate limit'})...`, 'warning');
          break;
        case 'agent_fallback':
          actLog.push('agent_fallback', `${msg.agent_id}: ${msg.message ?? 'LLM failed'}`, 'error');
          break;
        case 'agent_error':
          actLog.push('error', `❌ ${msg.agent_id}: ${msg.message ?? 'LLM optimization failed'}`, 'error');
          break;
        case 'experiment_error':
          actLog.push('error', `🛑 ${msg.message ?? 'Experiment stopped due to LLM failure'}`, 'error');
          setExperimentError(msg.message ?? 'Experiment stopped due to LLM failure');
          break;
        case 'game_complete':
          actLog.push('experiment_complete', `All days complete!`, 'success');
          break;
        case 'error':
          // Suppress "Game not found" — backend is restarting, WS will auto-reconnect
          if (msg.message && /game not found/i.test(msg.message)) break;
          actLog.push('error', msg.message ?? 'Unknown error', 'error');
          break;
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onRawMessage]);

  // Log connection status changes to activity feed
  const prevConnStatus = useRef<string>(connectionStatus);
  useEffect(() => {
    if (prevConnStatus.current === connectionStatus) return;
    const prev = prevConnStatus.current;
    prevConnStatus.current = connectionStatus;
    if (connectionStatus === 'connected' && prev === 'reconnecting') {
      actLog.push('connection', '🔄 Reconnected to server', 'success');
    } else if (connectionStatus === 'disconnected') {
      actLog.push('connection', '🔴 Connection lost — experiment paused', 'error');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionStatus]);

  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const [autoRunning, setAutoRunning] = useState(false);
  const [experimentError, setExperimentError] = useState<string | null>(null);
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

  // Old conditional returns removed — now handled after all hooks below

  const SPEED_MS: Record<typeof speed, number> = { fast: 0, normal: 3000, slow: 8000 };

  const gameState = wsState ?? initialState;

  const tour = useTour(gameState?.days?.length ?? 0, autoRunning);

  // Sync state up to parent — use ref to avoid dependency on onUpdate
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;
  useEffect(() => {
    if (wsState) onUpdateRef.current(wsState);
  }, [wsState]);

  // Auto-select latest day when new days arrive
  const daysLength = gameState?.days?.length ?? 0;
  useEffect(() => {
    if (daysLength > 0) {
      setSelectedDay(daysLength - 1);
    }
  }, [daysLength]);

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
    setExperimentError(null);
    setAutoRunning(true);
    autoRun(SPEED_MS[speed]);
  };

  // Stop auto-run when game completes
  const isComplete = gameState?.is_complete ?? false;
  useEffect(() => {
    if (isComplete && autoRunning) setAutoRunning(false);
  }, [isComplete, autoRunning]);

  // Conditional returns AFTER all hooks
  if (fetchLoading) {
    return (
      <div className="text-center py-20">
        <div className="text-4xl mb-4 animate-spin">⏳</div>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          {fetchRetrying
            ? 'Server restarting — reloading from checkpoint…'
            : `Loading experiment ${gameId}…`}
        </p>
      </div>
    );
  }

  if (!gameState) {
    return (
      <div className="text-center py-20">
        <div className="text-4xl mb-4">🔍</div>
        <h2 className="text-xl font-semibold mb-2">Experiment Not Found</h2>
        <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>No active experiment for ID: {gameId}</p>
        <button onClick={() => nav('/')} className="px-4 py-2 rounded-lg text-sm font-medium" style={{ backgroundColor: 'var(--bg-accent)', color: 'white' }}>← Back to Home</button>
      </div>
    );
  }

  const day = selectedDay !== null && selectedDay < gameState.days.length
    ? gameState.days[selectedDay] : gameState.days[gameState.days.length - 1] ?? null;

  return (
    <div className="space-y-6">
      {/* Top Bar */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2" data-tour="top-bar">
          <span className="relative flex h-2.5 w-2.5 mt-1" title={connectionStatus}>
            {connectionStatus === 'connected' ? (
              <span className="inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
            ) : connectionStatus === 'reconnecting' ? (<>
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500" />
            </>) : (
              <span className="inline-flex rounded-full h-2.5 w-2.5 bg-red-500" />
            )}
          </span>
          <h2 className="text-xl sm:text-2xl font-bold">{gameState.scenario_name || 'Policy Experiment'}</h2>
          <span className="text-base sm:text-lg font-mono text-sky-400">
            {gameState.optimization_schedule === 'every_scenario_day' && gameState.scenario_num_days
              ? (() => {
                  const displayDay = gameState.is_complete
                    ? gameState.current_day  // show last completed day
                    : gameState.current_day + 1;  // show next day to simulate
                  const scenDay = ((displayDay - 1) % gameState.scenario_num_days) + 1;
                  const round = Math.floor((displayDay - 1) / gameState.scenario_num_days) + 1;
                  return `Day ${scenDay}/${gameState.scenario_num_days} · Cycle ${round}`;
                })()
              : `Day ${gameState.current_day}/${gameState.max_days}`
            }
          </span>
          {gameState.is_complete && (
            <span className="px-2 py-1 rounded bg-green-500/20 text-green-400 text-xs font-medium">COMPLETE</span>
          )}
          {gameState.use_llm && (
            <span className="px-2 py-1 rounded bg-violet-500/20 text-violet-400 text-xs font-medium">
              🧠 {gameState.optimization_model ? gameState.optimization_model.split(':').pop() : 'glm-4.7-maas'}
            </span>
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
        {/* Stall warning */}
        {stalled && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-amber-500/10 border border-amber-500/30 text-amber-400">
            <span>⚠️ No response from server for 60s — simulation may have stalled.</span>
            <button
              onClick={() => { setStalled(false); window.location.reload(); }}
              className="px-2 py-0.5 rounded bg-amber-500/20 hover:bg-amber-500/30 text-xs font-medium"
            >
              Reload
            </button>
          </div>
        )}
        {/* Action buttons — wrap on mobile */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => { setExperimentError(null); step(); }}
            disabled={!connected || autoRunning || gameState.is_complete}
            className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-sm font-medium text-white"
            data-tour="next-btn"
          >
            ▶ Next
          </button>
          <button
            onClick={() => rerun()}
            disabled={!connected || autoRunning || gameState.days.length === 0}
            title="Re-run the last day with the same seed (deterministic replay)"
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

      {/* Activity Feed */}
      <ActivityFeed events={actLog.events} />

      {/* Fatal experiment error banner */}
      {experimentError && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm" style={{ color: 'var(--color-danger)' }}>
          🛑 <strong>Experiment stopped</strong> — {experimentError}
          <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            The experiment was halted because the AI model could not respond after all retries.
            You can try restarting with ▶ Next or ⏩ Auto.
          </div>
        </div>
      )}

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
            ⏳ Pausing between days... ({speed === 'normal' ? '3s' : '8s'})
          </span>
        </div>
      )}

      {phase === 'simulating' && (
        <SimulatingBanner day={(simulatingDay ?? 0) + 1} />
      )}
      {phase === 'optimizing' && optimizingAgents.size > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 px-1">
            <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>🔒 Independent Optimization</span>
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>— each agent sees only its own costs and events, never other agents' strategies</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[...optimizingAgents].map((aid) => (
              <div key={aid} className="rounded-xl p-3" style={{
                background: 'var(--bg-card)',
                border: `1px solid ${AGENT_COLORS[gameState.agent_ids.indexOf(aid) % AGENT_COLORS.length]}33`,
              }}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: AGENT_COLORS[gameState.agent_ids.indexOf(aid) % AGENT_COLORS.length] }} />
                  <span className="text-sm font-medium" style={{ color: AGENT_COLORS[gameState.agent_ids.indexOf(aid) % AGENT_COLORS.length] }}>{aid}</span>
                  <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-secondary)', color: 'var(--text-muted)' }}>🔒 isolated</span>
                  <span className="inline-block w-2 h-2 rounded-full bg-violet-400 animate-pulse ml-auto" />
                </div>
                {streamingText[aid] ? (
                  <div className="max-h-28 overflow-y-auto">
                    <pre className="text-xs whitespace-pre-wrap font-mono leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                      {streamingText[aid]}
                      <span className="inline-block w-1.5 h-3.5 bg-violet-400 animate-pulse ml-0.5 align-text-bottom" />
                    </pre>
                  </div>
                ) : (
                  <div className="text-xs animate-pulse" style={{ color: 'var(--text-muted)' }}>Waiting for response...</div>
                )}
              </div>
            ))}
          </div>
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
            <h3 className="text-lg font-semibold text-green-400 mb-3">Experiment Complete — {gameState.max_days} Days</h3>
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
            Click <strong>▶ Next Day</strong> to simulate the first day. Each day, banks process payments using their current liquidity policy.
            After each day, the AI optimizer analyzes costs and proposes improved policies — watching for the sweet spot between
            holding too much liquidity (wasted capital) and too little (missed deadlines).
          </p>
          <p className="text-xs text-slate-500 mt-3">
            {(() => {
              const fracs = Object.entries(gameState.current_policies).map(([aid, p]) => ({ aid, f: (p.parameters?.initial_liquidity_fraction as number) ?? 1 }));
              const allSame = fracs.length > 0 && fracs.every(x => x.f === fracs[0].f);
              if (gameState.constraint_preset === 'full') {
                return <>Agents start with full decision-tree policies. The optimizer will refine payment strategies, bank actions, and parameters over multiple days.</>;
              }
              if (allSame) {
                return <>All agents start with <span className="font-mono text-slate-400">fraction = {fracs[0].f.toFixed(3)}</span> (commit {(fracs[0].f * 100).toFixed(0)}% of their pool). The optimizer will learn to reduce this over multiple days.</>;
              }
              return <>Agents start with custom fractions: {fracs.map((x, i) => <span key={x.aid}>{i > 0 && ', '}<span className="font-mono text-slate-400">{x.aid}={(x.f as number).toFixed(2)}</span></span>)}. The optimizer will refine these over multiple days.</>;
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
                    {d.optimized && !d.optimization_failed && <span className="absolute -top-1 -right-1 text-[8px]">🧠</span>}
                    {d.optimization_failed && <span className="absolute -top-1 -right-1 text-[8px]">⚠️</span>}
                  </button>
                ))}
              </div>
              <div className="text-[10px] mt-1.5" style={{ color: 'var(--text-muted, #94a3b8)' }}>
                🧠 optimized · ⚠️ optimization failed
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
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4" data-tour="day-costs">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">
                Day {day.day + 1} Results{' '}
                <span className="text-xs text-slate-500 font-normal ml-1">seed={day.seed}</span>
              </h3>
              {/* Settlement Rate Banner */}
              {(() => {
                // Use server-provided event_summary when available (WS summary mode),
                // fall back to client-side event iteration for full data
                const serverSummary = (day as unknown as Record<string, unknown>).event_summary as Record<string, { arrivals: number; settled: number }> | undefined;
                const agentArrivals: Record<string, number> = {};
                const agentSettled: Record<string, number> = {};
                let totalArrivals = (day as unknown as Record<string, unknown>).total_arrivals as number | undefined ?? 0;
                let totalSettled = (day as unknown as Record<string, unknown>).total_settled as number | undefined ?? 0;
                if (serverSummary) {
                  for (const [aid, stats] of Object.entries(serverSummary)) {
                    agentArrivals[aid] = stats.arrivals;
                    agentSettled[aid] = stats.settled;
                  }
                } else if (day.events && day.events.length > 0) {
                  totalArrivals = 0;
                  totalSettled = 0;
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
                      const sender = String(rec.sender ?? '');
                      if (sender) {
                        agentSettled[sender] = (agentSettled[sender] ?? 0) + 1;
                      }
                      totalSettled++;
                    } else if (t === 'LsmBilateralOffset') {
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
                  // Per-agent settlement rate — prefer server summary
                  const srvSum = (day as unknown as Record<string, unknown>).event_summary as Record<string, { arrivals: number; settled: number }> | undefined;
                  let agentArr = srvSum?.[aid]?.arrivals ?? 0;
                  let agentStl = srvSum?.[aid]?.settled ?? 0;
                  if (!srvSum && day.events?.length > 0) {
                    agentArr = 0;
                    agentStl = 0;
                    for (const e of day.events) {
                      const rec = e as Record<string, unknown>;
                      const t = String(rec.event_type ?? '');
                      if (t === 'Arrival' && String(rec.sender_id ?? '') === aid) agentArr++;
                      else if ((t === 'RtgsImmediateSettlement' || t === 'Queue2LiquidityRelease') && String(rec.sender ?? '') === aid) agentStl++;
                      else if (t === 'LsmBilateralOffset' && (String(rec.agent_a ?? '') === aid || String(rec.agent_b ?? '') === aid)) agentStl++;
                      else if (t === 'LsmCycleSettlement' && (rec.agents as string[] | undefined)?.includes(aid)) agentStl++;
                    }
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
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4" data-tour="balance-chart">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">Day {day.day + 1} Balances</h3>
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
            <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)' }} data-tour="reasoning">
              <div className="flex items-center gap-3 mb-4">
                <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                  🧠 {selectedDay !== null && selectedDay < gameState.days.length - 1
                    ? `Day ${selectedDay + 1} Reasoning`
                    : 'Latest Reasoning'}
                </h3>
                <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--bg-secondary)', color: 'var(--text-muted)' }} title="Each agent optimizes independently using only its own performance data — no visibility into other agents' policies, costs, or strategies. This mirrors real-world banking where institutions make decisions with private information only.">🔒 information-isolated</span>
              </div>
              <div className="space-y-4">
                {gameState.agent_ids.map((aid, i) => {
                  const history = gameState.reasoning_history[aid] ?? [];
                  if (history.length === 0) return null;
                  const targetDay = selectedDay ?? gameState.days.length - 1;
                  const exactMatch = history.find((r: GameOptimizationResult & { day_num?: number }) => r.day_num === targetDay);
                  const latest = exactMatch ?? history[history.length - 1];
                  if (selectedDay !== null && !exactMatch) {
                    return (
                      <div key={aid} className="rounded-lg p-3" style={{ background: 'var(--bg-inset)', border: '1px solid var(--border-color)' }}>
                        <span className="font-mono text-sm" style={{ color: AGENT_COLORS[i % AGENT_COLORS.length] }}>{aid}</span>
                        <span className="text-xs ml-2" style={{ color: 'var(--text-muted)' }}>No optimization ran on this day.</span>
                      </div>
                    );
                  }
                  return (
                    <AgentReasoningCard
                      key={aid}
                      aid={aid}
                      result={latest}
                      colorIdx={i}
                      constraintPreset={gameState.constraint_preset}
                    />
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
                      fraction = {(pol?.initial_liquidity_fraction ?? (pol as any)?.parameters?.initial_liquidity_fraction ?? 1.0).toFixed(3)}
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

      {day && !showPaymentTrace && (
        <EventSummary day={day} gameId={gameId} />
      )}

      {day && showPaymentTrace && (
        <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">
            📋 Payment Lifecycle — Day {day.day + 1}
          </h3>
          <PaymentTraceView gameId={gameId} dayNum={day.day} />
        </div>
      )}

      {/* Prompt Explorer */}
      {gameState.use_llm && gameState.days.length > 0 && (
        <PromptExplorerSection gameId={gameId} agentIds={gameState.agent_ids} />
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

function SimulatingBanner({ day }: { day: number }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    setElapsed(0);
    const t = setInterval(() => setElapsed(s => s + 1), 1000);
    return () => clearInterval(t);
  }, [day]);
  return (
    <div className="bg-sky-500/10 border border-sky-500/30 rounded-xl p-3 text-center animate-pulse">
      <span className="text-sm">⚙️ Simulating Day {day}… ({elapsed}s elapsed)</span>
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

function EventSummary({ day, gameId }: { day: { day: number; events: Record<string, unknown>[] }; gameId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [loadedEvents, setLoadedEvents] = useState<Record<string, unknown>[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Use loaded events if available, otherwise fall back to day.events
  const events = (day.events && day.events.length > 0) ? day.events : loadedEvents ?? [];
  const needsLazyLoad = !day.events || day.events.length === 0;

  // Fetch events from replay API when expanded and events aren't available
  const handleExpand = async () => {
    const next = !expanded;
    setExpanded(next);
    if (next && needsLazyLoad && !loadedEvents && !loading) {
      setLoading(true);
      setError(null);
      try {
        const replay = await getGameDayReplay(gameId, day.day);
        const allEvents = replay.ticks.flatMap(t => t.events);
        setLoadedEvents(allEvents);
      } catch (err) {
        setError(String(err));
      } finally {
        setLoading(false);
      }
    }
  };

  // Count events by type
  const counts: Record<string, number> = {};
  for (const e of events) {
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
          Day {day.day + 1} Events {events.length > 0 ? `(${events.length})` : needsLazyLoad ? '(click to load)' : '(0)'}
        </h3>
        <button
          onClick={handleExpand}
          className="text-xs text-slate-500 hover:text-slate-300"
        >
          {expanded ? '▲ Collapse' : '▼ Show details'}
        </button>
      </div>
      {summaryEntries.length > 0 && (
        <div className="text-xs text-slate-500 flex flex-wrap gap-x-3 gap-y-1">
          {summaryEntries.map(([type, count], i) => (
            <span key={i}>{count} {type}{EVENT_TOOLTIPS[type] && <InfoTip text={EVENT_TOOLTIPS[type]} />}</span>
          ))}
        </div>
      )}
      {expanded && loading && (
        <div className="mt-3 text-xs text-slate-500 border-t border-slate-700 pt-3">Loading events...</div>
      )}
      {expanded && error && (
        <div className="mt-3 text-xs text-red-400 border-t border-slate-700 pt-3">Failed to load events: {error}</div>
      )}
      {expanded && !loading && events.length > 0 && (
        <div className="mt-3 max-h-48 overflow-y-auto text-xs font-mono text-slate-400 space-y-0.5 border-t border-slate-700 pt-3">
          {events.slice(0, 200).map((e, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-slate-600 w-6">{String(e.tick)}</span>
              <span className="text-sky-400">{String(e.event_type)}</span>
              {'sender_id' in e && 'receiver_id' in e && <span>{String(e.sender_id)}→{String(e.receiver_id)}</span>}
              {'agent_id' in e && !('sender_id' in e) && <span>{String(e.agent_id)}</span>}
              {'amount' in e && <span className="text-emerald-400">${(Number(e.amount)/100).toLocaleString()}</span>}
            </div>
          ))}
          {events.length > 200 && (
            <div className="text-slate-600">... and {events.length - 200} more</div>
          )}
        </div>
      )}
      {expanded && !loading && events.length === 0 && !error && (
        <div className="mt-3 text-xs text-slate-600 border-t border-slate-700 pt-3">No events available</div>
      )}
    </div>
  );
}

// ── Shared reasoning card for a single agent result ─────────────────

function AgentReasoningCard({ aid, result, colorIdx, constraintPreset }: {
  aid: string;
  result: GameOptimizationResult;
  colorIdx: number;
  constraintPreset?: string;
}) {
  const [policyModal, setPolicyModal] = useState<{ policy: import('../types').PolicyJson; rejected?: boolean; rejectionReason?: string; bootstrap?: import('../types').BootstrapResult } | null>(null);
  const bs = result.bootstrap;
  return (
    <div className="rounded-lg p-4 border-l-3"
      style={{
        background: 'var(--bg-inset)',
        borderLeft: `3px solid ${result.accepted ? 'var(--color-success)' : 'var(--color-danger)'}`,
      }}>
      {/* Header: agent name + status */}
      <div className="flex items-center gap-2 mb-2">
        <span className="font-mono text-sm font-semibold" style={{ color: AGENT_COLORS[colorIdx % AGENT_COLORS.length] }}>
          {aid}
        </span>
        {result.mock && (
          <span className="text-[11px] px-1.5 py-0.5 rounded"
            style={{ background: 'var(--bg-well, var(--bg-surface))', color: 'var(--text-muted)' }}
            title={result.fallback_reason ? `LLM failed: ${result.fallback_reason}` : 'Simulated AI'}>
            {result.fallback_reason ? '⚠ fallback' : 'sim'}
          </span>
        )}
        <span className="text-xs font-medium" style={{ color: result.accepted ? 'var(--color-success)' : 'var(--color-danger)' }}>
          {result.accepted ? '✓ Accepted' : '✗ Rejected'}
        </span>
        {constraintPreset !== 'full' && result.old_fraction != null && result.new_fraction != null && (
          <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
            {result.old_fraction.toFixed(3)} → {result.new_fraction.toFixed(3)}
          </span>
        )}
        {constraintPreset === 'full' && result.new_policy && (
          <PolicyChangeSummary oldPolicy={result.old_policy} newPolicy={result.new_policy} />
        )}
      </div>

      {/* Summary text */}
      <p className="text-xs leading-relaxed mb-2" style={{ color: 'var(--text-secondary)' }}>
        {result.reasoning}
      </p>

      {/* Bootstrap stats — clean horizontal layout */}
      {bs && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs font-mono mb-2" style={{ color: 'var(--text-muted)' }}>
          <span>Δ {bs.delta_sum.toLocaleString()}<InfoTip text="Cost change (negative = improvement)" /></span>
          <span>CV {bs.cv.toFixed(2)}<InfoTip text="Coefficient of variation — lower = more reliable" /></span>
          <span>CI [{bs.ci_lower.toLocaleString()}, {bs.ci_upper.toLocaleString()}]<InfoTip text="95% confidence interval" /></span>
          <span>n={bs.num_samples}<InfoTip text="Bootstrap samples" /></span>
        </div>
      )}

      {!result.accepted && result.rejection_reason && (
        <p className="text-xs mb-2" style={{ color: 'var(--color-danger)' }}>
          {result.rejection_reason}
        </p>
      )}

      {/* Metadata: model · latency · tokens */}
      {(result.latency_seconds || result.usage || result.model) && (
        <div className="flex flex-wrap gap-3 text-[11px] font-mono mb-2" style={{ color: 'var(--text-muted)' }}>
          {result.model && <span>{result.model.split(':').pop()}</span>}
          {result.latency_seconds != null && <span>{result.latency_seconds.toFixed(1)}s</span>}
          {result.usage && (
            <>
              <span>{result.usage.input_tokens.toLocaleString()} in</span>
              <span>{result.usage.output_tokens.toLocaleString()} out</span>
              {result.usage.thinking_tokens > 0 && (
                <span>{result.usage.thinking_tokens.toLocaleString()} thinking</span>
              )}
            </>
          )}
        </div>
      )}

      {/* Expandable sections */}
      <ReasoningExplorer result={result} />

      {constraintPreset === 'full' && result.new_policy && result.old_policy && (
        <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border-color)' }}>
          <PolicyDiffView oldPolicy={result.old_policy} newPolicy={result.new_policy} />
        </div>
      )}

      {/* View Policy buttons */}
      <div className="flex flex-wrap gap-2 mt-2">
        {(result.accepted ? result.new_policy : result.old_policy) && (
          <button
            onClick={() => setPolicyModal({
              policy: (result.accepted ? result.new_policy : result.old_policy)!,
            })}
            className="text-[11px] px-2 py-1 rounded"
            style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)', cursor: 'pointer' }}
          >
            🔍 View Policy
          </button>
        )}
        {!result.accepted && (result.rejected_policy || result.new_policy) && (
          <button
            onClick={() => setPolicyModal({
              policy: (result.rejected_policy || result.new_policy)!,
              rejected: true,
              rejectionReason: result.rejection_reason,
              bootstrap: result.bootstrap,
            })}
            className="text-[11px] px-2 py-1 rounded"
            style={{ background: 'rgba(239,68,68,0.1)', color: 'var(--color-danger)', border: '1px solid rgba(239,68,68,0.3)', cursor: 'pointer' }}
          >
            🚫 View Rejected Policy
          </button>
        )}
      </div>

      {policyModal && (
        <PolicyViewerModal
          policy={policyModal.policy}
          onClose={() => setPolicyModal(null)}
          title={`${aid} — ${policyModal.rejected ? 'Rejected' : 'Active'} Policy`}
          rejected={policyModal.rejected}
          rejectionReason={policyModal.rejectionReason}
          bootstrap={policyModal.bootstrap}
        />
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
    <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>📊 Policy History</h3>
        <div className="flex items-center gap-1 flex-wrap">
          {agentIds.map((aid, i) => (
            <button
              key={aid}
              onClick={() => { setSelectedAgent(aid); setSelectedRound(null); }}
              className="px-2.5 py-1 rounded-md text-xs font-mono transition-all"
              style={selectedAgent === aid
                ? { backgroundColor: AGENT_COLORS[i % AGENT_COLORS.length] + '20', color: AGENT_COLORS[i % AGENT_COLORS.length], border: `1px solid ${AGENT_COLORS[i % AGENT_COLORS.length]}40` }
                : { color: 'var(--text-muted)', border: '1px solid transparent' }
              }
            >
              {aid}
            </button>
          ))}
        </div>
      </div>

      {/* Round pills */}
      <div className="flex items-center gap-1.5 flex-wrap mb-3">
        {history.map((r, i) => {
          const isSelected = selectedRound === i;
          return (
            <button
              key={i}
              onClick={() => setSelectedRound(isSelected ? null : i)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono transition-all"
              style={{
                background: isSelected ? 'var(--btn-primary-bg)' : 'var(--bg-inset)',
                color: isSelected ? '#fff' : 'var(--text-muted)',
                border: `1px solid ${isSelected ? 'var(--btn-primary-bg)' : 'var(--border-color)'}`,
              }}
              title={r.reasoning}
            >
              <span>D{r.day_num != null ? r.day_num + 1 : i + 1}</span>
              {r.failed ? (
                <span style={{ color: isSelected ? '#fff' : 'var(--text-muted)' }}>⚠</span>
              ) : (
                <span style={{ color: isSelected ? '#fff' : r.accepted ? 'var(--color-success)' : 'var(--color-danger)' }}>
                  {r.accepted ? '✓' : '✗'}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Fraction trajectory */}
      {constraintPreset !== 'full' && fractions.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap text-xs font-mono mb-3" style={{ color: 'var(--text-muted)' }}>
          {fractions.map((f, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && <span style={{ color: 'var(--border-color)' }}>→</span>}
              <span style={{
                color: selectedRound !== null && i === selectedRound + 1
                  ? 'var(--text-primary)'
                  : i === fractions.length - 1
                    ? 'var(--text-secondary)'
                    : 'var(--text-muted)',
                fontWeight: selectedRound !== null && i === selectedRound + 1 ? 600 : 400,
              }}>
                {f.toFixed(3)}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* Selected round detail */}
      {selected && (
        <AgentReasoningCard
          aid={selectedAgent}
          result={selected}
          colorIdx={agentIds.indexOf(selectedAgent)}
          constraintPreset={constraintPreset}
        />
      )}

      {!selected && history.length > 0 && (
        <div className="text-xs text-center py-3" style={{ color: 'var(--text-muted)' }}>
          Select a day to explore reasoning
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
      className="absolute pointer-events-none z-50 px-2.5 py-1.5 rounded-lg text-xs shadow-xl whitespace-nowrap"
      style={{ background: 'var(--tooltip-bg)', border: '1px solid var(--border-color)', color: 'var(--text-primary)', left: tooltip.x, top: tooltip.y, transform: 'translateY(-100%)' }}
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
                      <div>Day {i + 1}: <span className="font-mono">{format(v)}</span></div>
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
                      <div>Day {i + 1}: <span className="font-mono">{format(v)}</span></div>
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
        <line x1={pad.l} y1={pad.t} x2={pad.l + plotW} y2={pad.t} stroke="var(--border-color)" strokeWidth={0.5} />
        <line x1={pad.l} y1={toY(midVal)} x2={pad.l + plotW} y2={toY(midVal)} stroke="var(--border-color)" strokeWidth={0.5} strokeDasharray="4,4" />
        <line x1={pad.l} y1={pad.t + plotH} x2={pad.l + plotW} y2={pad.t + plotH} stroke="var(--border-color)" strokeWidth={0.5} />
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
          <line x1={hoverInfo.svgX} y1={pad.t} x2={hoverInfo.svgX} y2={pad.t + plotH} stroke="var(--text-muted)" strokeWidth={0.5} strokeDasharray="3,3" />
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
            <circle key={aid} cx={hoverInfo.svgX} cy={toY(val)} r={3} fill={AGENT_COLORS[ci % AGENT_COLORS.length]} stroke="var(--bg-surface)" strokeWidth={1} />
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

function PromptExplorerSection({ gameId, agentIds }: { gameId: string; agentIds: string[] }) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-slate-300 hover:text-white transition-colors"
      >
        <span>🔍 Prompt Explorer</span>
        <span className="text-slate-500">{isOpen ? '▲' : '▼'}</span>
      </button>
      {isOpen && (
        <div className="px-4 pb-4">
          <PromptExplorer gameId={gameId} agentIds={agentIds} />
        </div>
      )}
    </div>
  );
}
