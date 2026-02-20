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
  /** First agent currently optimizing (for backwards compat display). */
  optimizingAgent: string | null;
  /** All agents currently optimizing (parallel mode). */
  optimizingAgents: Set<string>;
  simulatingDay: number | null;
  lastDay: DayResult | null;
  streamingText: Record<string, string>;
  step: () => void;
  rerun: (day?: number) => void;
  autoRun: (speedMs?: number) => void;
  stop: () => void;
}

const MAX_RETRIES = 10;
const INITIAL_BACKOFF_MS = 2000;
const MAX_BACKOFF_MS = 30000;

export function useGameWebSocket(gameId: string, initialState: GameState | null): UseGameWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const retryCountRef = useRef(0);
  const backoffMsRef = useRef(INITIAL_BACKOFF_MS);
  const pendingQueue = useRef<string[]>([]);
  const autoRunState = useRef<{ active: boolean; speedMs: number }>({ active: false, speedMs: 1000 });
  const [gameState, setGameState] = useState<GameState | null>(initialState);
  const [connected, setConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [phase, setPhase] = useState<GamePhase>('idle');
  const [optimizingAgent, setOptimizingAgent] = useState<string | null>(null);
  const [optimizingAgents, setOptimizingAgents] = useState<Set<string>>(new Set());
  const [simulatingDay, setSimulatingDay] = useState<number | null>(null);
  const [lastDay, setLastDay] = useState<DayResult | null>(null);
  const [streamingText, setStreamingText] = useState<Record<string, string>>({});

  const handleMessage = useCallback((event: MessageEvent) => {
    const msg: WSMessage = JSON.parse(event.data);

    switch (msg.type) {
      case 'game_state':
        setGameState(msg.data as GameState);
        setOptimizingAgent(null);
        setOptimizingAgents(new Set());
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
        if (msg.agent_id) {
          setOptimizingAgent(prev => prev ?? msg.agent_id!); // keep first if already set
          setOptimizingAgents(prev => new Set([...prev, msg.agent_id!]));
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
          setOptimizingAgents(prev => {
            const next = new Set(prev);
            next.delete(msg.agent_id!);
            // If no more agents optimizing, clear the singular field too
            if (next.size === 0) {
              setOptimizingAgent(null);
            } else {
              // Update singular to show one of the remaining agents
              setOptimizingAgent([...next][0]);
            }
            return next;
          });
        }
        break;

      case 'game_complete':
        setGameState(msg.data as GameState);
        setOptimizingAgent(null);
        setOptimizingAgents(new Set());
        setPhase('complete');
        autoRunState.current.active = false;
        break;

      case 'error':
        console.error('WS error:', msg.message);
        break;
    }
  }, []);

  const initialStateRef = useRef(initialState);
  initialStateRef.current = initialState;

  const connect = useCallback(async () => {
    if (!mountedRef.current) return;
    if (!gameId || !initialStateRef.current) return;  // Don't connect without a game
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return;

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
        // Flush any actions queued while connecting
        while (pendingQueue.current.length > 0) {
          const msg = pendingQueue.current.shift()!;
          ws.send(msg);
        }
        // Re-send auto-run command on reconnect if it was active
        if (autoRunState.current.active) {
          ws.send(JSON.stringify({ action: 'auto', speed_ms: autoRunState.current.speedMs }));
        }
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
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
    const msg = JSON.stringify({ action, ...extra });
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(msg);
    } else {
      // Queue for delivery once connected
      pendingQueue.current.push(msg);
    }
  }, []);

  const step = useCallback(() => send('step'), [send]);
  const rerun = useCallback((day?: number) => send('rerun', day != null ? { day } : undefined), [send]);
  const autoRun = useCallback((speedMs = 1000) => {
    autoRunState.current = { active: true, speedMs };
    send('auto', { speed_ms: speedMs });
  }, [send]);
  const stop = useCallback(() => {
    autoRunState.current.active = false;
    send('stop');
  }, [send]);

  return { gameState, connected, connectionStatus, reconnectAttempt, phase, optimizingAgent, optimizingAgents, simulatingDay, lastDay, streamingText, step, rerun, autoRun, stop };
}
