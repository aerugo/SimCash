import { useState, useEffect, useCallback, useRef, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { authFetch, publicFetch, API_ORIGIN } from '../api';
import { AuthInfoContext } from '../AuthInfoContext';

interface GameSummary {
  game_id: string;
  scenario_id?: string;
  scenario_name: string;
  status: string;
  display_status: string;
  current_round: number;
  rounds: number;
  current_day: number;
  use_llm: boolean;
  simulated_ai: boolean;
  agent_count: number;
  created_at: string;
  updated_at: string;
  last_activity_at: string;
  has_active_ws: boolean;
  quality?: string;
  stalled?: boolean;
  stall_reason?: string;
  optimization_model?: string;
  prompt_profile?: string;
  final_cost?: number;
  final_settlement_rate?: number;
}

function timeAgo(iso: string): string {
  if (!iso) return '';
  try {
    const ms = Date.now() - new Date(iso).getTime();
    if (ms < 0) return 'just now';
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    return `${d}d ago`;
  } catch { return ''; }
}

export default function ExperimentsView() {
  const navigate = useNavigate();
  const { isGuest } = useContext(AuthInfoContext);
  const [games, setGames] = useState<GameSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'running' | 'complete'>('all');
  const [sortAsc, setSortAsc] = useState(false); // false = newest first
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      // Authenticated users see their own experiments; guests see public list
      const url = isGuest ? `${API_ORIGIN}/api/games/public` : `${API_ORIGIN}/api/games`;
      const fetcher = isGuest ? publicFetch : authFetch;
      const res = await fetcher(url);
      if (res.ok) {
        const data = await res.json();
        setGames(data.games || []);
      }
    } catch (e) {
      console.error('Failed to load experiments', e);
    } finally {
      setLoading(false);
    }
  }, [isGuest]);

  useEffect(() => {
    refresh();
    // Auto-refresh every 15s
    intervalRef.current = setInterval(refresh, 15000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [refresh]);

  const handleDelete = async (gameId: string) => {
    if (!confirm('Delete this experiment? This cannot be undone.')) return;
    await authFetch(`${API_ORIGIN}/api/games/${gameId}`, { method: 'DELETE' });
    setGames(g => g.filter(x => x.game_id !== gameId));
  };

  const filtered = games
    .filter(g => {
      const ds = g.display_status || g.status;
      if (filter === 'running') return ds !== 'complete';
      if (filter === 'complete') return ds === 'complete';
      return true;
    })
    .sort((a, b) => {
      const ta = new Date(a.created_at || 0).getTime();
      const tb = new Date(b.created_at || 0).getTime();
      return sortAsc ? ta - tb : tb - ta;
    });

  const formatDate = (iso: string) => {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return iso; }
  };

  const statusBadge = (g: GameSummary) => {
    const ds = g.display_status || g.status;
    const styles: Record<string, { bg: string; text: string; label: string; pulse?: boolean }> = {
      created: { bg: 'var(--bg-inset)', text: 'var(--text-muted)', label: 'Created' },
      running: { bg: 'var(--color-success)', text: '#fff', label: 'Running', pulse: true },
      stalled: { bg: 'var(--color-warning)', text: '#fff', label: 'Stalled' },
      paused: { bg: 'var(--bg-inset)', text: 'var(--text-secondary)', label: 'Paused' },
      complete: { bg: 'var(--color-success)', text: '#fff', label: 'Complete' },
    };
    // Override for degraded complete
    if (ds === 'complete' && g.quality === 'degraded') {
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] px-2 py-0.5 rounded-full font-medium"
          style={{ background: 'var(--color-warning)', color: '#fff' }}>
          Complete ⚠️
        </span>
      );
    }
    // Override for stalled
    if (ds === 'stalled' || g.stalled) {
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] px-2 py-0.5 rounded-full font-medium"
          style={{ background: 'var(--color-warning)', color: '#fff' }}>
          Stalled ⚠️
        </span>
      );
    }
    const s = styles[ds] || styles.created;
    const activity = g.last_activity_at || g.updated_at;
    const ago = ds !== 'complete' && ds !== 'created' ? timeAgo(activity) : '';
    return (
      <span className="inline-flex items-center gap-1.5 text-[11px] px-2 py-0.5 rounded-full font-medium"
        style={{ background: s.bg, color: s.text }}>
        {s.pulse && (
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ background: '#fff' }} />
            <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: '#fff' }} />
          </span>
        )}
        {s.label}
        {ago && <span className="opacity-75 text-[10px]">· {ago}</span>}
      </span>
    );
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
          📋 {isGuest ? 'Public Experiments' : 'My Experiments'}
        </h2>
        <button
          onClick={() => navigate('/library/scenarios')}
          className="text-sm px-4 py-2 rounded-lg font-medium"
          style={{ background: 'var(--btn-primary-bg)', color: '#fff' }}
        >
          + New Experiment
        </button>
      </div>

      {/* Filter tabs + sort */}
      <div className="flex items-center gap-2 mb-4">
        {(['all', 'running', 'complete'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className="text-xs px-3 py-1.5 rounded-md font-medium transition-all capitalize"
            style={{
              background: filter === f ? 'var(--btn-primary-bg)' : 'var(--bg-inset)',
              color: filter === f ? '#fff' : 'var(--text-muted)',
              border: `1px solid ${filter === f ? 'var(--btn-primary-bg)' : 'var(--border-color)'}`,
            }}
          >
            {f} {f === 'all' ? `(${games.length})` : `(${games.filter(g => {
              const ds = g.display_status || g.status;
              return f === 'running' ? ds !== 'complete' : ds === 'complete';
            }).length})`}
          </button>
        ))}
        <div className="flex-1" />
        <button
          onClick={() => setSortAsc(v => !v)}
          className="text-xs px-3 py-1.5 rounded-md font-medium transition-all"
          style={{ background: 'var(--bg-inset)', color: 'var(--text-muted)', border: '1px solid var(--border-color)' }}
          title={sortAsc ? 'Oldest first' : 'Newest first'}
        >
          {sortAsc ? '↑ Oldest' : '↓ Newest'}
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12" style={{ color: 'var(--text-muted)' }}>Loading...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-3">🧪</div>
          <p className="text-sm mb-4" style={{ color: 'var(--text-muted)' }}>
            {games.length === 0 ? 'No experiments yet. Run one from the Scenario Library!' : 'No experiments match this filter.'}
          </p>
          {games.length === 0 && (
            <button
              onClick={() => navigate('/library/scenarios')}
              className="text-sm px-4 py-2 rounded-lg font-medium"
              style={{ background: 'var(--btn-primary-bg)', color: '#fff' }}
            >
              Browse Scenarios
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(g => (
            <div
              key={g.game_id}
              className="rounded-xl p-4 cursor-pointer transition-all hover:opacity-90"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)' }}
              onClick={() => navigate(`/experiment/${g.game_id}`)}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {g.scenario_id ? (
                      <a
                        href={`/library/scenarios/${g.scenario_id}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          e.preventDefault();
                          navigate(`/library/scenarios/${g.scenario_id}`);
                        }}
                        className="hover:underline"
                        style={{ color: 'var(--text-accent)' }}
                      >
                        {g.scenario_name || g.scenario_id || 'Scenario'}
                      </a>
                    ) : (
                      g.scenario_name || 'Custom Scenario'
                    )}
                  </span>
                  {statusBadge(g)}
                  {g.use_llm && !g.simulated_ai && (
                    <span className="text-[11px] px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-inset)', color: 'var(--text-accent)' }}>
                      🧠 AI
                    </span>
                  )}
                  {g.simulated_ai && (
                    <span className="text-[11px] px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-inset)', color: 'var(--text-muted)' }}>
                      sim
                    </span>
                  )}
                  {g.optimization_model && (
                    <span className="text-[11px] px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-inset)', color: 'var(--text-accent)' }}>
                      🧠 {g.optimization_model.split(':').pop()}
                    </span>
                  )}
                  {g.prompt_profile && (
                    <span className="text-[11px] px-1.5 py-0.5 rounded font-mono" style={{ background: 'var(--bg-inset)', color: 'var(--text-muted)' }}>
                      {g.prompt_profile}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {g.final_cost != null && (g.display_status || g.status) === 'complete' && (
                    <span className="text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                      cost: {Math.round(g.final_cost).toLocaleString()}
                    </span>
                  )}
                  {g.final_settlement_rate != null && (g.display_status || g.status) === 'complete' && (
                    <span className="text-[11px] font-mono" style={{ color: g.final_settlement_rate >= 99 ? 'var(--color-success)' : 'var(--text-secondary)' }}>
                      SR: {g.final_settlement_rate}%
                    </span>
                  )}
                  <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                    {g.game_id}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--text-secondary)' }}>
                <span>Round {g.current_round ?? g.current_day}/{g.rounds ?? g.current_day}</span>
                <span>{g.agent_count} {g.agent_count === 1 ? 'bank' : 'banks'}</span>
                <span>{formatDate(g.updated_at || g.created_at)}</span>

                {/* Progress bar */}
                <div className="flex-1 max-w-32">
                  <div className="h-1.5 rounded-full" style={{ background: 'var(--bg-inset)' }}>
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${Math.min(100, (g.rounds ?? 0) > 0 ? ((g.current_round ?? g.current_day) / (g.rounds ?? 1)) * 100 : 0)}%`,
                        background: (g.display_status || g.status) === 'complete' ? 'var(--color-success)' : 'var(--text-accent)',
                      }}
                    />
                  </div>
                </div>

                {!isGuest && (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(g.game_id); }}
                    className="text-xs px-2 py-1 rounded opacity-50 hover:opacity-100 transition-opacity"
                    style={{ color: 'var(--color-danger)' }}
                  >
                    🗑
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
