import { useState, useEffect, useCallback } from 'react';
import { fetchUsers, inviteUser, revokeUser, type AdminUser } from '../api';

export function AdminDashboard({ onClose }: { onClose: () => void }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviting, setInviting] = useState(false);
  const [confirmRevoke, setConfirmRevoke] = useState<string | null>(null);

  const loadUsers = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchUsers();
      setUsers(data);
      setError('');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  const handleInvite = async () => {
    if (!inviteEmail.trim()) return;
    setInviting(true);
    try {
      await inviteUser(inviteEmail.trim());
      setInviteEmail('');
      await loadUsers();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to invite user');
    } finally {
      setInviting(false);
    }
  };

  const handleRevoke = async (email: string) => {
    try {
      await revokeUser(email);
      setConfirmRevoke(null);
      await loadUsers();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to revoke user');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-2xl w-full max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <h2 className="text-lg font-semibold text-slate-100">👑 Admin Dashboard</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200 text-xl">✕</button>
        </div>

        {/* Invite form */}
        <div className="p-4 border-b border-slate-700">
          <div className="flex gap-2">
            <input
              type="email"
              placeholder="Email to invite"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleInvite()}
              className="flex-1 px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-sky-500"
            />
            <button
              onClick={handleInvite}
              disabled={inviting || !inviteEmail.trim()}
              className="px-4 py-2 bg-sky-600 hover:bg-sky-500 rounded-lg text-white text-sm font-medium disabled:opacity-50"
            >
              {inviting ? 'Inviting…' : 'Invite'}
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="px-4 pt-3">
            <p className="text-red-400 text-xs">{error}</p>
          </div>
        )}

        {/* Users table */}
        <div className="flex-1 overflow-auto p-4">
          {loading ? (
            <p className="text-slate-400 text-sm">Loading…</p>
          ) : users.length === 0 ? (
            <p className="text-slate-500 text-sm">No users yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 text-xs uppercase border-b border-slate-700">
                  <th className="text-left py-2 px-2">Email</th>
                  <th className="text-left py-2 px-2">Status</th>
                  <th className="text-left py-2 px-2">Method</th>
                  <th className="text-left py-2 px-2">Last Login</th>
                  <th className="text-left py-2 px-2">Invited By</th>
                  <th className="text-right py-2 px-2"></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.email} className="border-b border-slate-800 hover:bg-slate-800/50">
                    <td className="py-2 px-2 text-slate-200 font-mono text-xs">{u.email}</td>
                    <td className="py-2 px-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        u.status === 'active' ? 'bg-green-900/40 text-green-400' : 'bg-yellow-900/40 text-yellow-400'
                      }`}>
                        {u.status || 'unknown'}
                      </span>
                    </td>
                    <td className="py-2 px-2 text-slate-400 text-xs">{u.sign_in_method || '—'}</td>
                    <td className="py-2 px-2 text-slate-400 text-xs">
                      {u.last_login ? new Date(u.last_login).toLocaleDateString() : '—'}
                    </td>
                    <td className="py-2 px-2 text-slate-400 text-xs">{u.invited_by || '—'}</td>
                    <td className="py-2 px-2 text-right">
                      {confirmRevoke === u.email ? (
                        <span className="space-x-2">
                          <button onClick={() => handleRevoke(u.email)} className="text-red-400 hover:text-red-300 text-xs font-medium">Confirm</button>
                          <button onClick={() => setConfirmRevoke(null)} className="text-slate-500 hover:text-slate-300 text-xs">Cancel</button>
                        </span>
                      ) : (
                        <button onClick={() => setConfirmRevoke(u.email)} className="text-slate-500 hover:text-red-400 text-xs">Revoke</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
