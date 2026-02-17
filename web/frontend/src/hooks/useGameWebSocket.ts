import { useEffect, useRef, useState, useCallback } from 'react';
import type { GameState, DayResult } from '../types';

export type WSMessageType =
  | 'game_state'
  | 'simulation_running'
  | 'day_complete'
  | 'optimization_start'
  | 'optimization_complete'
  | 'game_complete'
  | 'error';

export interface WSMessage {
  type: WSMessageType;
  data?: unknown;
  day?: number;
  agent_id?: string;
  message?: string;
}

export type GamePhase = 'idle' | 'simulating' | 'optimizing' | 'complete';

interface UseGameWebSocketReturn {
  gameState: GameState | null;
  connected: boolean;
  phase: GamePhase;
  optimizingAgent: string | null;
  simulatingDay: number | null;
  lastDay: DayResult | null;
  step: () => void;
  autoRun: (speedMs?: number) => void;
  stop: () => void;
}

export function useGameWebSocket(gameId: string, initialState: GameState): UseGameWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const [gameState, setGameState] = useState<GameState | null>(initialState);
  const [connected, setConnected] = useState(false);
  const [phase, setPhase] = useState<GamePhase>('idle');
  const [optimizingAgent, setOptimizingAgent] = useState<string | null>(null);
  const [simulatingDay, setSimulatingDay] = useState<number | null>(null);
  const [lastDay, setLastDay] = useState<DayResult | null>(null);

  const handleMessage = useCallback((event: MessageEvent) => {
    const msg: WSMessage = JSON.parse(event.data);

    switch (msg.type) {
      case 'game_state':
        setGameState(msg.data as GameState);
        setOptimizingAgent(null);
        setPhase('idle');
        break;

      case 'simulation_running':
        setPhase('simulating');
        setSimulatingDay(msg.day ?? null);
        break;

      case 'day_complete':
        setLastDay(msg.data as DayResult);
        setPhase('idle');
        break;

      case 'optimization_start':
        setPhase('optimizing');
        setOptimizingAgent(msg.agent_id ?? null);
        break;

      case 'optimization_complete':
        break;

      case 'game_complete':
        setGameState(msg.data as GameState);
        setOptimizingAgent(null);
        setPhase('complete');
        break;

      case 'error':
        console.error('WS error:', msg.message);
        break;
    }
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/games/${gameId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      if (mountedRef.current) setConnected(true);
    };

    ws.onclose = () => {
      if (mountedRef.current) {
        setConnected(false);
        // Auto-reconnect after 1s
        reconnectTimer.current = setTimeout(() => connect(), 1000);
      }
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = handleMessage;
  }, [gameId, handleMessage]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on intentional close
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const send = useCallback((action: string, extra?: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, ...extra }));
    }
  }, []);

  const step = useCallback(() => send('step'), [send]);
  const autoRun = useCallback((speedMs = 1000) => send('auto', { speed_ms: speedMs }), [send]);
  const stop = useCallback(() => send('stop'), [send]);

  return { gameState, connected, phase, optimizingAgent, simulatingDay, lastDay, step, autoRun, stop };
}
