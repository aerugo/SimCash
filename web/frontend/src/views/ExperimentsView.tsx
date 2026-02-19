import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { authFetch } from '../api';

interface GameSummary {
  game_id: string;
  scenario_id: string;
  status: string;
  current_day: number;
  max_days: number;
  use_llm: boolean;
  simulated_ai: boolean;
  agent_count: number;
  created_at: string;
  updated_at: string;
}

export default function ExperimentsView() {
  const navigate = useNavigate();
  const [games, setGames] = useState<GameSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'running' | 'complete'>('all');

  const refresh = useCallback(async () => {
    try {
      const res = await authFetch('/api/games');
      if (res.ok) {
        const data = await res.json();
        setGames(data.games || []);
      }
    } catch (e) {
      console.error('Failed to load experiments', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleDelete = async (gameId: string) => {
    if (!confirm('Delete this experiment? This cannot be undone.')) return;
    await authFetch(`/api/games/${gameId}`, { method: 'DELETE' });
    setGames(g => g.filter(x => x.game_id !== gameId));
  };

  const filtered = games.filter(g => {
    if (filter === 'running') return g.status !== 'complete';
    if (filter === 'complete') return g.status === 'complete';
    return true;
  });

  const formatDate = (iso: string) => {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return iso; }
  };

  const statusBadge = (status: string) => {
    const styles: Record<string, { bg: string; text: string; label: string }> = {
      created: { bg: 'var(--bg-inset)', text: 'var(--text-muted)', label: 'Created' },
      running: { bg: 'var(--color-warning)', text: '#fff', label: 'Running' },
      paused: { bg: 'var(--text-accent)', text: '#fff', label: 'Paused' },
      complete: { bg: 'var(--color-success)', text: '#fff', label: 'Complete' },
    };
    const s = styles[status] || styles.created;
    return (
      <span className="text-[11px] px-2 py-0.5 rounded-full font-medium"
        style={{ background: s.bg, color: s.text }}>
        {s.label}
      </span>
    );
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
          📋 My Experiments
        </h2>
        <button
          onClick={() => navigate('/library/scenarios')}
          className="text-sm px-4 py-2 rounded-lg font-medium"
          style={{ background: 'var(--btn-primary-bg)', color: '#fff' }}
        >
          + New Experiment
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 mb-4">
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
            {f} {f === 'all' ? `(${games.length})` : `(${games.filter(g => f === 'running' ? g.status !== 'complete' : g.status === 'complete').length})`}
          </button>
        ))}
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
                    {g.scenario_id || 'Custom Scenario'}
                  </span>
                  {statusBadge(g.status)}
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
                </div>
                <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                  {g.game_id}
                </span>
              </div>

              <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--text-secondary)' }}>
                <span>Round {g.current_day}/{g.max_days}</span>
                <span>{g.agent_count} {g.agent_count === 1 ? 'bank' : 'banks'}</span>
                <span>{formatDate(g.updated_at || g.created_at)}</span>

                {/* Progress bar */}
                <div className="flex-1 max-w-32">
                  <div className="h-1.5 rounded-full" style={{ background: 'var(--bg-inset)' }}>
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${g.max_days > 0 ? (g.current_day / g.max_days) * 100 : 0}%`,
                        background: g.status === 'complete' ? 'var(--color-success)' : 'var(--text-accent)',
                      }}
                    />
                  </div>
                </div>

                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(g.game_id); }}
                  className="text-xs px-2 py-1 rounded opacity-50 hover:opacity-100 transition-opacity"
                  style={{ color: 'var(--color-danger)' }}
                >
                  🗑
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
