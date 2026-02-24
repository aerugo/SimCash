import { useState, useEffect, useCallback } from 'react';
import { authFetch, API_ORIGIN } from '../api';

interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string | null;
  last_used_at: string | null;
}

const BASE = `${API_ORIGIN}/api/v1`;

export default function ApiKeysView() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyRaw, setNewKeyRaw] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const fetchKeys = useCallback(async () => {
    try {
      const res = await authFetch(`${BASE}/keys`);
      if (!res.ok) throw new Error('Failed to fetch keys');
      const data = await res.json();
      setKeys(data.keys);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchKeys(); }, [fetchKeys]);

  const handleCreate = async () => {
    if (!newKeyName.trim()) return;
    setError(null);
    try {
      const res = await authFetch(`${BASE}/keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newKeyName.trim() }),
      });
      if (!res.ok) throw new Error('Failed to create key');
      const data = await res.json();
      setNewKeyRaw(data.key);
      setNewKeyName('');
      fetchKeys();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleRevoke = async (keyId: string) => {
    if (!confirm('Revoke this API key? This cannot be undone.')) return;
    try {
      const res = await authFetch(`${BASE}/keys/${keyId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to revoke key');
      fetchKeys();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleCopy = () => {
    if (newKeyRaw) {
      navigator.clipboard.writeText(newKeyRaw);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      <h1 className="text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>API Keys</h1>
      <p className="mb-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
        Create API keys to access SimCash programmatically via the <code>/api/v1/</code> endpoints.
      </p>

      {error && (
        <div className="mb-4 p-3 rounded text-sm" style={{ backgroundColor: 'var(--color-error-bg, #fef2f2)', color: 'var(--color-error, #dc2626)' }}>
          {error}
        </div>
      )}

      {/* New key creation */}
      <div className="mb-6 p-4 rounded-lg" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)' }}>
        <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Create New Key</h2>
        <div className="flex gap-2">
          <input
            type="text"
            value={newKeyName}
            onChange={e => setNewKeyName(e.target.value)}
            placeholder="Key name (e.g. 'My Script')"
            className="flex-1 px-3 py-2 rounded text-sm"
            style={{ backgroundColor: 'var(--bg-base)', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
          />
          <button
            onClick={handleCreate}
            disabled={!newKeyName.trim()}
            className="px-4 py-2 rounded text-sm font-medium"
            style={{ backgroundColor: 'var(--text-accent)', color: 'white', opacity: newKeyName.trim() ? 1 : 0.5 }}
          >
            Create
          </button>
        </div>
      </div>

      {/* Show newly created key */}
      {newKeyRaw && (
        <div className="mb-6 p-4 rounded-lg" style={{ backgroundColor: 'var(--color-success-bg, #f0fdf4)', border: '1px solid var(--color-success, #22c55e)' }}>
          <p className="text-sm font-semibold mb-2" style={{ color: 'var(--color-success, #22c55e)' }}>
            ✅ Key created! Copy it now — it won't be shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs p-2 rounded break-all" style={{ backgroundColor: 'var(--bg-base)', color: 'var(--text-primary)' }}>
              {newKeyRaw}
            </code>
            <button onClick={handleCopy} className="px-3 py-1 rounded text-xs font-medium" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)' }}>
              {copied ? '✓ Copied' : 'Copy'}
            </button>
          </div>
          <button onClick={() => setNewKeyRaw(null)} className="mt-2 text-xs underline" style={{ color: 'var(--text-muted)' }}>
            Dismiss
          </button>
        </div>
      )}

      {/* Key list */}
      {loading ? (
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading...</p>
      ) : keys.length === 0 ? (
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No API keys yet.</p>
      ) : (
        <div className="space-y-2">
          {keys.map(k => (
            <div key={k.id} className="flex items-center justify-between p-3 rounded-lg" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)' }}>
              <div>
                <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{k.name}</span>
                <span className="ml-3 text-xs font-mono" style={{ color: 'var(--text-muted)' }}>{k.prefix}</span>
                {k.created_at && (
                  <span className="ml-3 text-xs" style={{ color: 'var(--text-muted)' }}>
                    Created {new Date(k.created_at).toLocaleDateString()}
                  </span>
                )}
              </div>
              <button
                onClick={() => handleRevoke(k.id)}
                className="px-3 py-1 rounded text-xs"
                style={{ color: 'var(--color-error, #dc2626)' }}
              >
                Revoke
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Usage example */}
      <div className="mt-8 p-4 rounded-lg" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)' }}>
        <h2 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>Usage</h2>
        <pre className="text-xs overflow-x-auto p-3 rounded" style={{ backgroundColor: 'var(--bg-base)', color: 'var(--text-secondary)' }}>{`curl -H "Authorization: Bearer sk_live_..." \\
  ${window.location.origin}/api/v1/scenarios`}</pre>
      </div>
    </div>
  );
}
