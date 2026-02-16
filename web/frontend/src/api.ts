import type { CreateSimResponse, Preset, SimulationState, TickResult } from './types';

const BASE = '/api';

export async function getPresets(): Promise<Preset[]> {
  const res = await fetch(`${BASE}/presets`);
  const data = await res.json();
  return data.presets;
}

export async function createSimulation(preset?: string): Promise<CreateSimResponse> {
  const body = preset ? { preset } : {};
  const res = await fetch(`${BASE}/simulations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
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

export function connectWebSocket(simId: string): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return new WebSocket(`${protocol}//${window.location.host}/ws/simulations/${simId}`);
}
