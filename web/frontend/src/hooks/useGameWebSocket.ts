import { useEffect, useRef, useState, useCallback } from 'react';
import type { GameState, DayResult } from '../types';
import { getIdToken } from '../firebase';

export type WSMessageType =
  | 'game_state'
  | 'simulation_running'
  | 'day_complete'
  | 'optimization_start'
  | 'optimization_chunk'
  | 'optimization_complete'
  | 'game_complete'
  | 'error';

export interface WSMessage {
  type: WSMessageType;
  data?: unknown;
  day?: number;
  agent_id?: string;
  message?: string;
  text?: string;
}

export type GamePhase = 'idle' | 'simulating' | 'optimizing' | 'complete';

export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';

interface UseGameWebSocketReturn {
  gameState: GameState | null;
  connected: boolean;
  connectionStatus: ConnectionStatus;
  reconnectAttempt: number;
  phase: GamePhase;
  optimizingAgent: string | null;
  simulatingDay: number | null;
  lastDay: DayResult | null;
  streamingText: Record<string, string>;
  step: () => void;
  rerun: (day?: number) => void;
  autoRun: (speedMs?: number) => void;
  stop: () => void;
}

const MAX_RETRIES = 10;
const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;

export function useGameWebSocket(gameId: string, initialState: GameState): UseGameWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const retryCountRef = useRef(0);
  const backoffMsRef = useRef(INITIAL_BACKOFF_MS);
  const [gameState, setGameState] = useState<GameState | null>(initialState);
  const [connected, setConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [phase, setPhase] = useState<GamePhase>('idle');
  const [optimizingAgent, setOptimizingAgent] = useState<string | null>(null);
  const [simulatingDay, setSimulatingDay] = useState<number | null>(null);
  const [lastDay, setLastDay] = useState<DayResult | null>(null);
  const [streamingText, setStreamingText] = useState<Record<string, string>>({});

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
        if (msg.agent_id) {
          setStreamingText(prev => ({ ...prev, [msg.agent_id!]: '' }));
        }
        break;

      case 'optimization_chunk':
        if (msg.agent_id && msg.text) {
          setStreamingText(prev => ({
            ...prev,
            [msg.agent_id!]: (prev[msg.agent_id!] ?? '') + msg.text!,
          }));
        }
        break;

      case 'optimization_complete':
        if (msg.agent_id) {
          setStreamingText(prev => ({ ...prev, [msg.agent_id!]: '' }));
        }
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

  const connect = useCallback(async () => {
    if (!mountedRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const devToken = sessionStorage.getItem('simcash_dev_token');
    const token = devToken ? null : await getIdToken();
    const params = new URLSearchParams();
    if (token) params.set('token', token);
    if (devToken) params.set('dev_token', devToken);
    const paramStr = params.toString() ? `?${params.toString()}` : '';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/games/${gameId}${paramStr}`);
    wsRef.current = ws;

    ws.onopen = () => {
      if (mountedRef.current) {
        setConnected(true);
        setConnectionStatus('connected');
        // Reset backoff on successful connection
        retryCountRef.current = 0;
        backoffMsRef.current = INITIAL_BACKOFF_MS;
        setReconnectAttempt(0);
      }
    };

    ws.onclose = () => {
      if (mountedRef.current) {
        setConnected(false);

        if (retryCountRef.current >= MAX_RETRIES) {
          setConnectionStatus('disconnected');
          return;
        }

        setConnectionStatus('reconnecting');
        retryCountRef.current += 1;
        setReconnectAttempt(retryCountRef.current);

        const delay = backoffMsRef.current;
        backoffMsRef.current = Math.min(backoffMsRef.current * 2, MAX_BACKOFF_MS);

        reconnectTimer.current = setTimeout(() => connect(), delay);
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
  const rerun = useCallback((day?: number) => send('rerun', day != null ? { day } : undefined), [send]);
  const autoRun = useCallback((speedMs = 1000) => send('auto', { speed_ms: speedMs }), [send]);
  const stop = useCallback(() => send('stop'), [send]);

  return { gameState, connected, connectionStatus, reconnectAttempt, phase, optimizingAgent, simulatingDay, lastDay, streamingText, step, rerun, autoRun, stop };
}
