import { useEffect, useRef, useState, useCallback } from 'react';
import type { GameState, DayResult } from '../types';

export type WSMessageType =
  | 'game_state'
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

interface UseGameWebSocketReturn {
  gameState: GameState | null;
  connected: boolean;
  optimizingAgent: string | null;
  lastDay: DayResult | null;
  step: () => void;
  autoRun: (speedMs?: number) => void;
  stop: () => void;
}

export function useGameWebSocket(gameId: string, initialState: GameState): UseGameWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [gameState, setGameState] = useState<GameState | null>(initialState);
  const [connected, setConnected] = useState(false);
  const [optimizingAgent, setOptimizingAgent] = useState<string | null>(null);
  const [lastDay, setLastDay] = useState<DayResult | null>(null);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/games/${gameId}`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);

    ws.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data);

      switch (msg.type) {
        case 'game_state':
          setGameState(msg.data as GameState);
          setOptimizingAgent(null);
          break;

        case 'day_complete':
          setLastDay(msg.data as DayResult);
          break;

        case 'optimization_start':
          setOptimizingAgent(msg.agent_id ?? null);
          break;

        case 'optimization_complete':
          // Could accumulate reasoning here if needed
          break;

        case 'game_complete':
          setGameState(msg.data as GameState);
          setOptimizingAgent(null);
          break;

        case 'error':
          console.error('WS error:', msg.message);
          break;
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [gameId]);

  const send = useCallback((action: string, extra?: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, ...extra }));
    }
  }, []);

  const step = useCallback(() => send('step'), [send]);
  const autoRun = useCallback((speedMs = 1000) => send('auto', { speed_ms: speedMs }), [send]);
  const stop = useCallback(() => send('stop'), [send]);

  return { gameState, connected, optimizingAgent, lastDay, step, autoRun, stop };
}
