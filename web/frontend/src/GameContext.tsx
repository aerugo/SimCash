import { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import type { SimulationState, TickResult, SimEvent, Preset, ScenarioConfig, AgentReasoning, GameState, GameSetupConfig } from './types';
import { createSimulation, getPresets, connectWebSocket, createGame } from './api';
import { toast } from './components/Toast';
import type { ScenarioEditorState } from './views/ScenarioEditorView';

export interface GameContextValue {
  // Presets
  presets: Preset[];
  // Simulation state
  simId: string | null;
  state: SimulationState | null;
  events: SimEvent[];
  reasoning: Record<string, AgentReasoning[]>;
  isRunning: boolean;
  speed: number;
  setSpeed: (s: number) => void;
  // Game state
  gameId: string | null;
  gameState: GameState | null;
  setGameState: (s: GameState) => void;
  // Actions
  handleLaunch: (configOrPreset: ScenarioConfig | string) => Promise<void>;
  handleTick: () => void;
  handleRun: () => void;
  handlePause: () => void;
  handleReset: () => void;
  handleGameLaunch: (config: GameSetupConfig) => Promise<string | null>;
  // Admin
  isAdmin: boolean;
  userEmail: string;
  onSignOut: () => void;
  // Editor state persistence
  scenarioEditorState: ScenarioEditorState | undefined;
  setScenarioEditorState: (s: ScenarioEditorState | undefined) => void;
  policyEditorJsonText: string | undefined;
  setPolicyEditorJsonText: (s: string | undefined) => void;
}

const GameContext = createContext<GameContextValue | null>(null);

export function useGameContext() {
  const ctx = useContext(GameContext);
  if (!ctx) throw new Error('useGameContext must be used within GameProvider');
  return ctx;
}

interface GameProviderProps {
  children: React.ReactNode;
  isAdmin: boolean;
  userEmail: string;
  onSignOut: () => void;
}

export function GameProvider({ children, isAdmin, userEmail, onSignOut }: GameProviderProps) {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [simId, setSimId] = useState<string | null>(null);
  const [state, setState] = useState<SimulationState | null>(null);
  const [events, setEvents] = useState<SimEvent[]>([]);
  const [reasoning, setReasoning] = useState<Record<string, AgentReasoning[]>>({});
  const [isRunning, setIsRunning] = useState(false);
  const [speed, setSpeed] = useState(500);
  const wsRef = useRef<WebSocket | null>(null);
  const [gameId, setGameId] = useState<string | null>(null);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [scenarioEditorState, setScenarioEditorState] = useState<ScenarioEditorState | undefined>(undefined);
  const [policyEditorJsonText, setPolicyEditorJsonText] = useState<string | undefined>(undefined);

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
  }, []);

  const handleGameLaunch = useCallback(async (config: GameSetupConfig): Promise<string | null> => {
    try {
      const res = await createGame(config);
      setGameId(res.game_id);
      setGameState(res.game);
      toast(`Game ${res.game_id} created`, 'success');
      return res.game_id;
    } catch (e) {
      let msg = String(e);
      try {
        const parsed = JSON.parse(msg.replace(/^Error:\s*/, ''));
        if (parsed.detail) msg = parsed.detail;
      } catch { /* not JSON, use as-is */ }
      toast(msg, 'error');
      return null;
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

  const value: GameContextValue = {
    presets, simId, state, events, reasoning, isRunning, speed, setSpeed,
    gameId, gameState, setGameState,
    handleLaunch, handleTick, handleRun, handlePause, handleReset, handleGameLaunch,
    isAdmin, userEmail, onSignOut,
    scenarioEditorState, setScenarioEditorState,
    policyEditorJsonText, setPolicyEditorJsonText,
  };

  return <GameContext.Provider value={value}>{children}</GameContext.Provider>;
}
