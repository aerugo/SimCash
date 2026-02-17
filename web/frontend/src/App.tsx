import { useState, useCallback, useRef, useEffect } from 'react';
import type { SimulationState, TickResult, SimEvent, Preset, TabId, ScenarioConfig, AgentReasoning, GameState, GameSetupConfig } from './types';
import { createSimulation, getPresets, connectWebSocket, createGame } from './api';
import { ToastContainer, toast } from './components/Toast';
import { HomeView } from './views/HomeView';
import { DashboardView } from './views/DashboardView';
import { EventsView } from './views/EventsView';
import { ConfigView } from './views/ConfigView';
import { ReplayView } from './views/ReplayView';
import { AnalysisView } from './views/AnalysisView';
import { LibraryView } from './views/LibraryView';
import { AgentsView } from './views/AgentsView';
import { GameView } from './views/GameView';

const TABS: { id: TabId; label: string; icon: string; requiresSim?: boolean; requiresGame?: boolean }[] = [
  { id: 'home', label: 'Setup', icon: '🏠' },
  { id: 'game', label: 'Game', icon: '🎮', requiresGame: true },
  { id: 'dashboard', label: 'Dashboard', icon: '📊', requiresSim: true },
  { id: 'agents', label: 'Agents', icon: '🧠', requiresSim: true },
  { id: 'events', label: 'Events', icon: '📋', requiresSim: true },
  { id: 'config', label: 'Config', icon: '⚙️', requiresSim: true },
  { id: 'replay', label: 'Replay', icon: '🔄', requiresSim: true },
  { id: 'analysis', label: 'Analysis', icon: '📈', requiresSim: true },
  { id: 'library', label: 'Library', icon: '🎮' },
];

function App() {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [tab, setTab] = useState<TabId>('home');
  const [simId, setSimId] = useState<string | null>(null);
  const [state, setState] = useState<SimulationState | null>(null);
  const [events, setEvents] = useState<SimEvent[]>([]);
  const [reasoning, setReasoning] = useState<Record<string, AgentReasoning[]>>({});
  const [isRunning, setIsRunning] = useState(false);
  const [speed, setSpeed] = useState(500);
  const wsRef = useRef<WebSocket | null>(null);
  const [gameId, setGameId] = useState<string | null>(null);
  const [gameState, setGameState] = useState<GameState | null>(null);

  useEffect(() => {
    getPresets().then(setPresets);
  }, []);

  const handleLaunch = useCallback(async (configOrPreset: ScenarioConfig | string) => {
    try {
      const res = await createSimulation(configOrPreset);
      setSimId(res.sim_id);
      setEvents([]);
      setReasoning({});
      setIsRunning(false);
      setTab('dashboard');
      toast(`Simulation ${res.sim_id} created`, 'success');

      const ws = connectWebSocket(res.sim_id);
      wsRef.current = ws;

      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'state' || msg.type === 'paused' || msg.type === 'complete') {
          setState(msg.data);
          if (msg.type === 'complete') {
            setIsRunning(false);
            toast('Simulation complete!', 'success');
          }
        } else if (msg.type === 'tick') {
          const tick = msg.data as TickResult;
          setState(prev => prev ? {
            ...prev,
            current_tick: tick.tick + 1,
            is_complete: tick.is_complete,
            agents: tick.agents,
            balance_history: tick.balance_history,
            cost_history: tick.cost_history,
          } : prev);
          setEvents(prev => [...prev, ...tick.events]);
          // Capture reasoning data
          const tickReasoning = (msg.data as Record<string, unknown>).reasoning as Record<string, AgentReasoning> | undefined;
          if (tickReasoning) {
            setReasoning(prev => {
              const next = { ...prev };
              for (const [aid, trace] of Object.entries(tickReasoning)) {
                if (!next[aid]) next[aid] = [];
                next[aid] = [...next[aid], trace];
              }
              return next;
            });
          }
          if (tick.is_complete) {
            setIsRunning(false);
            toast('Simulation complete!', 'success');
          }
        }
      };

      ws.onclose = () => setIsRunning(false);
      ws.onerror = () => toast('WebSocket error', 'error');
    } catch (e) {
      toast(`Failed to create simulation: ${e}`, 'error');
    }
  }, []);

  const handleTick = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ action: 'tick' }));
  }, []);

  const handleRun = useCallback(() => {
    setIsRunning(true);
    wsRef.current?.send(JSON.stringify({ action: 'run', speed_ms: speed }));
  }, [speed]);

  const handlePause = useCallback(() => {
    setIsRunning(false);
    wsRef.current?.send(JSON.stringify({ action: 'pause' }));
  }, []);

  const handleReset = useCallback(() => {
    wsRef.current?.close();
    setSimId(null);
    setState(null);
    setEvents([]);
    setReasoning({});
    setIsRunning(false);
    setGameId(null);
    setGameState(null);
    setTab('home');
  }, []);

  const handleGameLaunch = useCallback(async (config: GameSetupConfig) => {
    try {
      const res = await createGame(config);
      setGameId(res.game_id);
      setGameState(res.game);
      setTab('game');
      toast(`Game ${res.game_id} created`, 'success');
    } catch (e) {
      toast(`Failed to create game: ${e}`, 'error');
    }
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;
      if (e.code === 'Space') {
        e.preventDefault();
        if (isRunning) handlePause();
        else if (state && !state.is_complete) handleRun();
      } else if (e.code === 'ArrowRight' && !isRunning && state && !state.is_complete) {
        e.preventDefault();
        handleTick();
      } else if (e.code === 'KeyR' && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        handleReset();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isRunning, state, handleRun, handlePause, handleTick, handleReset]);

  const visibleTabs = TABS.filter(t => {
    if (t.requiresSim && !simId) return false;
    if (t.requiresGame && !gameId) return false;
    return true;
  });

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-700 bg-[#0f172a]/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="text-2xl font-bold bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">
              💰 SimCash
            </div>
            <span className="text-xs text-slate-500 hidden sm:inline">Interactive Payment Simulator</span>
          </div>
          {simId && state && (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <span className="font-mono bg-slate-800 px-2 py-1 rounded text-xs">{simId}</span>
              <span className="text-xs">
                Tick {state.current_tick}/{state.total_ticks}
                {state.is_complete && <span className="ml-1 text-green-400">✓</span>}
              </span>
            </div>
          )}
        </div>

        {/* Tab bar */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex gap-1 overflow-x-auto pb-0 -mb-px">
            {visibleTabs.map(t => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`px-3 py-2 text-xs sm:text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                  tab === t.id
                    ? 'border-sky-400 text-sky-400'
                    : 'border-transparent text-slate-500 hover:text-slate-300'
                }`}
              >
                <span className="mr-1">{t.icon}</span>
                <span className="hidden sm:inline">{t.label}</span>
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {tab === 'home' && (
          <HomeView presets={presets} onLaunch={handleLaunch} onGameLaunch={handleGameLaunch} />
        )}

        {tab === 'game' && gameId && gameState && (
          <GameView
            gameId={gameId}
            gameState={gameState}
            onUpdate={setGameState}
            onReset={handleReset}
          />
        )}

        {tab === 'dashboard' && state && (
          <DashboardView
            state={state}
            events={events}
            isRunning={isRunning}
            speed={speed}
            onTick={handleTick}
            onRun={handleRun}
            onPause={handlePause}
            onReset={handleReset}
            onSpeedChange={setSpeed}
            reasoning={reasoning}
            onNavigateToAgents={() => setTab('agents')}
          />
        )}

        {tab === 'agents' && (
          <AgentsView reasoning={reasoning} />
        )}

        {tab === 'events' && (
          <EventsView events={events} />
        )}

        {tab === 'config' && simId && (
          <ConfigView simId={simId} />
        )}

        {tab === 'replay' && simId && state && (
          <ReplayView simId={simId} state={state} />
        )}

        {tab === 'analysis' && simId && state && (
          <AnalysisView state={state} events={events} simId={simId} />
        )}

        {tab === 'library' && (
          <LibraryView onLaunch={(config) => handleLaunch(config)} />
        )}
      </main>

      {/* Keyboard hint */}
      <div className="fixed bottom-4 left-4 text-[10px] text-slate-600 hidden lg:block">
        Space: play/pause · →: step · R: reset
      </div>

      <ToastContainer />
    </div>
  );
}

export default App;
