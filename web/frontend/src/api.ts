import type { CreateSimResponse, Preset, SimulationState, TickResult, SavedScenario, ScenarioConfig, CompareResult, AgentReasoning } from './types';
import type { GameState, ScenarioPackEntry, GameScenario, GameSetupConfig, LibraryScenario, LibraryScenarioDetail, LibraryPolicy, LibraryPolicyDetail, PolicyHistoryResponse, PolicyDiffResponse, PaymentTraceResponse } from './types';
import { getIdToken } from './firebase';

/** API base URL — relative in same-origin deploy (Cloud Run), absolute for Firebase Hosting */
export const API_ORIGIN = import.meta.env.VITE_API_ORIGIN || '';
const BASE = `${API_ORIGIN}/api`;

/** Authenticated fetch wrapper — auto-includes Bearer token for protected endpoints */
export async function authFetch(url: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  // Dev token takes priority (staging bypass)
  const devToken = sessionStorage.getItem('simcash_dev_token');
  const token = devToken || await getIdToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  return fetch(url, { ...init, headers, credentials: 'include' });
}

// ---- Admin API ----

export interface AdminUser {
  email: string;
  status?: string;
  sign_in_method?: string;
  last_login?: string;
  invited_by?: string;
  invited_at?: string;
}

export async function checkAdmin(): Promise<{ email: string; is_admin: boolean }> {
  const res = await authFetch(`${BASE}/admin/me`);
  if (res.status === 403) return { email: '', is_admin: false };
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchUsers(): Promise<AdminUser[]> {
  const res = await authFetch(`${BASE}/admin/users`);
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.users;
}

export async function inviteUser(email: string): Promise<void> {
  const res = await authFetch(`${BASE}/admin/invite`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function revokeUser(email: string): Promise<void> {
  const res = await authFetch(`${BASE}/admin/users/${encodeURIComponent(email)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(await res.text());
}

// ---- Platform Settings (Model Selection) ----

export interface ModelOption {
  id: string;
  label: string;
  provider: string;
  active: boolean;
}

export interface PlatformSettings {
  optimization_model: string;
  model_settings: Record<string, unknown>;
  available_models: { id: string; label: string; provider: string }[];
  updated_by: string;
  updated_at: string;
}

export async function fetchModels(): Promise<ModelOption[]> {
  const res = await authFetch(`${BASE}/settings/models`);
  const data = await res.json();
  return data.models;
}

export async function fetchSettings(): Promise<PlatformSettings> {
  const res = await authFetch(`${BASE}/settings`);
  const data = await res.json();
  return data;
}

export async function updateSettings(updates: { optimization_model?: string; model_settings?: Record<string, unknown> }): Promise<PlatformSettings> {
  const res = await authFetch(`${BASE}/settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getPresets(): Promise<Preset[]> {
  const res = await authFetch(`${BASE}/presets`);
  const data = await res.json();
  return data.presets;
}

export async function createSimulation(presetOrConfig?: string | ScenarioConfig): Promise<CreateSimResponse> {
  const body = typeof presetOrConfig === 'string' ? { preset: presetOrConfig } : (presetOrConfig ?? {});
  const res = await authFetch(`${BASE}/simulations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getSimulation(simId: string): Promise<SimulationState> {
  const res = await authFetch(`${BASE}/simulations/${simId}`);
  return res.json();
}

export async function tickSimulation(simId: string): Promise<TickResult> {
  const res = await authFetch(`${BASE}/simulations/${simId}/tick`, { method: 'POST' });
  return res.json();
}

export async function runSimulation(simId: string): Promise<{ ticks: TickResult[]; final_state: SimulationState }> {
  const res = await authFetch(`${BASE}/simulations/${simId}/run`, { method: 'POST' });
  return res.json();
}

export async function getSimConfig(simId: string): Promise<{ raw_config: Record<string, unknown>; ffi_config: Record<string, unknown> }> {
  const res = await authFetch(`${BASE}/simulations/${simId}/config`);
  return res.json();
}

export async function exportSimulation(simId: string): Promise<Record<string, unknown>> {
  const res = await authFetch(`${BASE}/simulations/${simId}/export`);
  return res.json();
}

export async function getReplayTick(simId: string, tick: number): Promise<TickResult> {
  const res = await authFetch(`${BASE}/simulations/${simId}/replay/${tick}`);
  return res.json();
}

export async function getReplayInfo(simId: string): Promise<{ total_recorded_ticks: number; is_complete: boolean }> {
  const res = await authFetch(`${BASE}/simulations/${simId}/replay`);
  return res.json();
}

export async function getSimEvents(simId: string): Promise<{ events: Record<string, unknown>[]; total: number }> {
  const res = await authFetch(`${BASE}/simulations/${simId}/events`);
  return res.json();
}

export async function compareRuns(runs: { scenario: ScenarioConfig; policy_id?: string }[]): Promise<{ results: CompareResult[] }> {
  const res = await authFetch(`${BASE}/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ runs }),
  });
  return res.json();
}

// Scenario Library
export async function listScenarios(): Promise<SavedScenario[]> {
  const res = await authFetch(`${BASE}/scenarios`);
  const data = await res.json();
  return data.scenarios;
}

export async function saveScenario(scenario: { name: string; description: string; config: ScenarioConfig }): Promise<SavedScenario> {
  const res = await authFetch(`${BASE}/scenarios`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(scenario),
  });
  return res.json();
}

export async function deleteScenario(id: string): Promise<void> {
  await authFetch(`${BASE}/scenarios/${id}`, { method: 'DELETE' });
}

export async function getReasoning(simId: string): Promise<Record<string, AgentReasoning[]>> {
  const res = await authFetch(`${BASE}/simulations/${simId}/reasoning`);
  const data = await res.json();
  return data.reasoning;
}

export function connectWebSocket(simId: string): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return new WebSocket(`${protocol}//${window.location.host}/ws/simulations/${simId}`);
}

// ---- Multi-Day Game API ----

export async function getScenarioPack(): Promise<ScenarioPackEntry[]> {
  const res = await authFetch(`${BASE}/scenario-pack`);
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
  if (!res.ok) throw new Error(`Game not found: ${res.status}`);
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

// ---- Scenario Library API ----

export async function getScenarioLibrary(includeArchived?: boolean): Promise<LibraryScenario[]> {
  const qs = includeArchived ? '?include_archived=true' : '';
  const res = await authFetch(`${BASE}/scenarios/library${qs}`);
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.scenarios;
}

export async function getScenarioLibraryDetail(scenarioId: string): Promise<LibraryScenarioDetail> {
  const res = await authFetch(`${BASE}/scenarios/library/${scenarioId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ---- Policy Library API ----

export async function getPolicyLibrary(includeArchived?: boolean): Promise<LibraryPolicy[]> {
  const qs = includeArchived ? '?include_archived=true' : '';
  const res = await authFetch(`${BASE}/policies/library${qs}`);
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.policies;
}

export async function getPolicyLibraryDetail(policyId: string): Promise<LibraryPolicyDetail> {
  const res = await authFetch(`${BASE}/policies/library/${policyId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ---- Policy Evolution API ----

export async function getPolicyHistory(gameId: string): Promise<PolicyHistoryResponse> {
  const res = await authFetch(`${BASE}/games/${gameId}/policy-history`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getPolicyDiff(gameId: string, day1: number, day2: number, agent: string): Promise<PolicyDiffResponse> {
  const res = await authFetch(`${BASE}/games/${gameId}/policy-diff?day1=${day1}&day2=${day2}&agent=${encodeURIComponent(agent)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ---- Payment Trace API ----

export async function getPaymentTraces(gameId: string, dayNum: number): Promise<PaymentTraceResponse> {
  const res = await authFetch(`${BASE}/games/${gameId}/days/${dayNum}/payments`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ---- Collections API ----

export interface Collection {
  id: string;
  name: string;
  icon: string;
  description: string;
  scenario_ids: string[];
  scenario_count: number;
}

export interface CollectionDetail {
  id: string;
  name: string;
  icon: string;
  description: string;
  scenarios: LibraryScenario[];
}

export async function fetchCollections(): Promise<Collection[]> {
  const res = await authFetch(`${BASE}/collections`);
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.collections ?? data;
}

export async function fetchCollectionDetail(id: string): Promise<CollectionDetail> {
  const res = await authFetch(`${BASE}/collections/${id}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ---- Admin Library API ----

export interface AdminLibraryItem {
  id: string;
  name: string;
  visible: boolean;
  collections?: string[];
}

export interface AdminLibrary {
  scenarios: AdminLibraryItem[];
  policies: AdminLibraryItem[];
}

export async function fetchAdminLibrary(): Promise<AdminLibrary> {
  const res = await authFetch(`${BASE}/admin/library`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function toggleLibraryVisibility(
  itemType: 'scenario' | 'policy',
  itemId: string,
  visible: boolean,
): Promise<{ ok: boolean }> {
  const typePlural = itemType === 'scenario' ? 'scenarios' : 'policies';
  const res = await authFetch(`${BASE}/admin/library/${typePlural}/${itemId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ visible }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function adminCreateCollection(data: {
  id: string; name: string; icon?: string; description?: string; scenario_ids?: string[];
}): Promise<Collection> {
  const res = await authFetch(`${BASE}/admin/collections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function adminUpdateCollectionScenarios(
  collectionId: string, scenarioIds: string[],
): Promise<Collection> {
  const res = await authFetch(`${BASE}/admin/collections/${collectionId}/scenarios`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario_ids: scenarioIds }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function adminDeleteCollection(collectionId: string): Promise<void> {
  const res = await authFetch(`${BASE}/admin/collections/${collectionId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(await res.text());
}

export function getGameExportUrl(gameId: string, format: 'csv' | 'json'): string {
  return `${BASE}/games/${gameId}/export?format=${format}`;
}

export async function downloadGameExport(gameId: string, format: 'csv' | 'json'): Promise<void> {
  const res = await authFetch(getGameExportUrl(gameId, format));
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `game_${gameId}.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function connectGameWebSocket(gameId: string): Promise<WebSocket> {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const token = await getIdToken();
  const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
  return new WebSocket(`${protocol}//${window.location.host}/ws/games/${gameId}${tokenParam}`);
}
