import type { CreateSimResponse, Preset, SimulationState, TickResult, SavedScenario, ScenarioConfig, CompareResult, AgentReasoning } from './types';
import type { GameState, ScenarioPackEntry, GameScenario, GameSetupConfig } from './types';
import { getIdToken } from './firebase';

const BASE = '/api';

/** Authenticated fetch wrapper — auto-includes Bearer token for /api/games/* */
async function authFetch(url: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  // Add auth token for game endpoints
  if (url.includes('/games')) {
    const token = await getIdToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }
  return fetch(url, { ...init, headers });
}

export async function getPresets(): Promise<Preset[]> {
  const res = await fetch(`${BASE}/presets`);
  const data = await res.json();
  return data.presets;
}

export async function createSimulation(presetOrConfig?: string | ScenarioConfig): Promise<CreateSimResponse> {
  const body = typeof presetOrConfig === 'string' ? { preset: presetOrConfig } : (presetOrConfig ?? {});
  const res = await fetch(`${BASE}/simulations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getSimulation(simId: string): Promise<SimulationState> {
  const res = await fetch(`${BASE}/simulations/${simId}`);
  return res.json();
}

export async function tickSimulation(simId: string): Promise<TickResult> {
  const res = await fetch(`${BASE}/simulations/${simId}/tick`, { method: 'POST' });
  return res.json();
}

export async function runSimulation(simId: string): Promise<{ ticks: TickResult[]; final_state: SimulationState }> {
  const res = await fetch(`${BASE}/simulations/${simId}/run`, { method: 'POST' });
  return res.json();
}

export async function getSimConfig(simId: string): Promise<{ raw_config: Record<string, unknown>; ffi_config: Record<string, unknown> }> {
  const res = await fetch(`${BASE}/simulations/${simId}/config`);
  return res.json();
}

export async function exportSimulation(simId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE}/simulations/${simId}/export`);
  return res.json();
}

export async function getReplayTick(simId: string, tick: number): Promise<TickResult> {
  const res = await fetch(`${BASE}/simulations/${simId}/replay/${tick}`);
  return res.json();
}

export async function getReplayInfo(simId: string): Promise<{ total_recorded_ticks: number; is_complete: boolean }> {
  const res = await fetch(`${BASE}/simulations/${simId}/replay`);
  return res.json();
}

export async function getSimEvents(simId: string): Promise<{ events: Record<string, unknown>[]; total: number }> {
  const res = await fetch(`${BASE}/simulations/${simId}/events`);
  return res.json();
}

export async function compareRuns(runs: { scenario: ScenarioConfig; policy_id?: string }[]): Promise<{ results: CompareResult[] }> {
  const res = await fetch(`${BASE}/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ runs }),
  });
  return res.json();
}

// Scenario Library
export async function listScenarios(): Promise<SavedScenario[]> {
  const res = await fetch(`${BASE}/scenarios`);
  const data = await res.json();
  return data.scenarios;
}

export async function saveScenario(scenario: { name: string; description: string; config: ScenarioConfig }): Promise<SavedScenario> {
  const res = await fetch(`${BASE}/scenarios`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(scenario),
  });
  return res.json();
}

export async function deleteScenario(id: string): Promise<void> {
  await fetch(`${BASE}/scenarios/${id}`, { method: 'DELETE' });
}

export async function getReasoning(simId: string): Promise<Record<string, AgentReasoning[]>> {
  const res = await fetch(`${BASE}/simulations/${simId}/reasoning`);
  const data = await res.json();
  return data.reasoning;
}

export function connectWebSocket(simId: string): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return new WebSocket(`${protocol}//${window.location.host}/ws/simulations/${simId}`);
}

// ---- Multi-Day Game API ----

export async function getScenarioPack(): Promise<ScenarioPackEntry[]> {
  const res = await fetch(`${BASE}/scenario-pack`);
  const data = await res.json();
  return data.scenarios;
}

export async function getGameScenarios(): Promise<GameScenario[]> {
  const res = await authFetch(`${BASE}/games/scenarios`);
  const data = await res.json();
  return data.scenarios;
}

export async function createGame(config: GameSetupConfig): Promise<{ game_id: string; game: GameState }> {
  const res = await authFetch(`${BASE}/games`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getGame(gameId: string): Promise<GameState> {
  const res = await authFetch(`${BASE}/games/${gameId}`);
  return res.json();
}

export async function stepGame(gameId: string): Promise<{ day: Record<string, unknown>; reasoning: Record<string, unknown>; game: GameState }> {
  const res = await authFetch(`${BASE}/games/${gameId}/step`, { method: 'POST' });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function autoRunGame(gameId: string): Promise<{ days: unknown[]; game: GameState }> {
  const res = await authFetch(`${BASE}/games/${gameId}/auto`, { method: 'POST' });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getGameDayReplay(gameId: string, dayNum: number): Promise<{
  day: number;
  seed: number;
  num_ticks: number;
  ticks: { tick: number; events: Record<string, unknown>[]; balances: Record<string, number> }[];
  policies: Record<string, { initial_liquidity_fraction: number }>;
  final_costs: Record<string, { liquidity_cost: number; delay_cost: number; penalty_cost: number; total: number }>;
}> {
  const res = await authFetch(`${BASE}/games/${gameId}/days/${dayNum}/replay`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function connectGameWebSocket(gameId: string): Promise<WebSocket> {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const token = await getIdToken();
  const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
  return new WebSocket(`${protocol}//${window.location.host}/ws/games/${gameId}${tokenParam}`);
}
