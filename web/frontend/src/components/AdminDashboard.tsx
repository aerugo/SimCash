import { useState, useEffect, useCallback } from 'react';
import { fetchUsers, inviteUser, revokeUser, fetchModels, updateSettings, fetchAdminLibrary, toggleLibraryVisibility, fetchCollections, adminCreateCollection, adminUpdateCollectionScenarios, type AdminUser, type ModelOption, type AdminLibrary, type Collection } from '../api';

const PROVIDER_COLORS: Record<string, string> = {
  'google-vertex': 'bg-blue-900/40 text-blue-400',
  'openai': 'bg-green-900/40 text-green-400',
  'anthropic': 'bg-amber-900/40 text-amber-400',
};

export function AdminDashboard({ onClose }: { onClose?: () => void } = {}) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviting, setInviting] = useState(false);
  const [confirmRevoke, setConfirmRevoke] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<'users' | 'model' | 'library'>('users');

  // Model selection state
  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [modelSaving, setModelSaving] = useState(false);
  const [modelSuccess, setModelSuccess] = useState('');

  // Library curation state
  const [library, setLibrary] = useState<AdminLibrary | null>(null);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [librarySearch, setLibrarySearch] = useState('');
  const [togglingId, setTogglingId] = useState<string | null>(null);

  // Collection management state
  const [collections, setCollections] = useState<Collection[]>([]);
  const [editingCollection, setEditingCollection] = useState<string | null>(null);
  const [editScenarioIds, setEditScenarioIds] = useState<string[]>([]);
  const [showNewCollection, setShowNewCollection] = useState(false);
  const [newCollName, setNewCollName] = useState('');
  const [newCollIcon, setNewCollIcon] = useState('📁');
  const [newCollDesc, setNewCollDesc] = useState('');
  const [collSaving, setCollSaving] = useState(false);

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

  const loadModels = useCallback(async () => {
    try {
      setModelsLoading(true);
      const data = await fetchModels();
      setModels(data);
    } catch {
      // Non-critical — models section just won't show
    } finally {
      setModelsLoading(false);
    }
  }, []);

  const loadLibrary = useCallback(async () => {
    try {
      setLibraryLoading(true);
      const data = await fetchAdminLibrary();
      setLibrary(data);
    } catch {
      // Non-critical
    } finally {
      setLibraryLoading(false);
    }
  }, []);

  const loadCollections = useCallback(async () => {
    try {
      const data = await fetchCollections();
      setCollections(data);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadUsers(); loadModels(); }, [loadUsers, loadModels]);
  useEffect(() => {
    if (activeTab === 'library') {
      if (!library) loadLibrary();
      loadCollections();
    }
  }, [activeTab, library, loadLibrary, loadCollections]);

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

  const handleModelChange = async (modelId: string) => {
    setModelSaving(true);
    setModelSuccess('');
    try {
      await updateSettings({ optimization_model: modelId });
      await loadModels();
      setModelSuccess('Model updated');
      setTimeout(() => setModelSuccess(''), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update model');
    } finally {
      setModelSaving(false);
    }
  };

  const activeModel = models.find(m => m.active);

  const handleToggleVisibility = async (itemType: 'scenario' | 'policy', itemId: string, currentVisible: boolean) => {
    setTogglingId(itemId);
    try {
      await toggleLibraryVisibility(itemType, itemId, !currentVisible);
      await loadLibrary();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to toggle visibility');
    } finally {
      setTogglingId(null);
    }
  };

  const librarySearchLower = librarySearch.toLowerCase();
  const filteredScenarios = library?.scenarios.filter(s => s.name.toLowerCase().includes(librarySearchLower)) ?? [];
  const filteredPolicies = library?.policies.filter(p => p.name.toLowerCase().includes(librarySearchLower)) ?? [];
  const scenarioVisibleCount = library?.scenarios.filter(s => s.visible).length ?? 0;
  const scenarioArchivedCount = library?.scenarios.filter(s => !s.visible).length ?? 0;
  const policyVisibleCount = library?.policies.filter(p => p.visible).length ?? 0;
  const policyArchivedCount = library?.policies.filter(p => !p.visible).length ?? 0;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-2xl w-full max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <h2 className="text-lg font-semibold text-slate-100">👑 Admin Dashboard</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200 text-xl">✕</button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-700">
          {([
            { id: 'users' as const, label: '👥 Users' },
            { id: 'model' as const, label: '🧠 Model' },
            { id: 'library' as const, label: '📚 Library' },
          ]).map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-sky-400 border-b-2 border-sky-400'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-auto">
          {/* Error */}
          {error && (
            <div className="px-4 pt-3">
              <p className="text-red-400 text-xs">{error}</p>
            </div>
          )}

          {/* Model Tab */}
          {activeTab === 'model' && (
            <div className="p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">🧠 Optimization Model</h3>
              {modelsLoading ? (
                <p className="text-slate-500 text-xs">Loading models…</p>
              ) : (
                <div className="space-y-2">
                  {models.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => handleModelChange(m.id)}
                      disabled={modelSaving || m.active}
                      className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg border transition-colors text-left ${
                        m.active
                          ? 'border-sky-500 bg-sky-900/20'
                          : 'border-slate-700 hover:border-slate-500 bg-slate-800/50'
                      } ${modelSaving ? 'opacity-50' : ''}`}
                    >
                      <div className="flex items-center gap-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-mono ${PROVIDER_COLORS[m.provider] || 'bg-slate-700 text-slate-300'}`}>
                          {m.provider}
                        </span>
                        <span className={`text-sm ${m.active ? 'text-sky-300 font-medium' : 'text-slate-300'}`}>
                          {m.label}
                        </span>
                      </div>
                      {m.active && <span className="text-sky-400 text-xs font-medium">Active ✓</span>}
                    </button>
                  ))}
                  {modelSuccess && (
                    <p className="text-green-400 text-xs mt-1">✓ {modelSuccess}</p>
                  )}
                  {activeModel && (
                    <p className="text-slate-500 text-xs mt-1">
                      Next optimization will use <span className="text-slate-300">{activeModel.label}</span>
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Users Tab */}
          {activeTab === 'users' && (
            <>
              <div className="p-4 border-b border-slate-700">
                <h3 className="text-sm font-semibold text-slate-300 mb-3">👥 User Management</h3>
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

              <div className="p-4">
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
            </>
          )}

          {/* Library Tab */}
          {activeTab === 'library' && (
            <div className="p-4">
              <div className="mb-4">
                <input
                  type="text"
                  placeholder="Search scenarios and policies…"
                  value={librarySearch}
                  onChange={(e) => setLibrarySearch(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-sky-500"
                />
              </div>

              {libraryLoading ? (
                <p className="text-slate-500 text-xs">Loading library…</p>
              ) : !library ? (
                <p className="text-slate-500 text-xs">Failed to load library data.</p>
              ) : (
                <>
                  {/* Collections */}
                  <div className="mb-6">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-semibold text-slate-300">🏷️ Collections</h3>
                      <button
                        onClick={() => setShowNewCollection(!showNewCollection)}
                        className="text-xs text-sky-400 hover:text-sky-300"
                      >
                        {showNewCollection ? '✕ Cancel' : '+ New Collection'}
                      </button>
                    </div>

                    {showNewCollection && (
                      <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 mb-3 space-y-2">
                        <div className="flex gap-2">
                          <input
                            value={newCollIcon}
                            onChange={e => setNewCollIcon(e.target.value)}
                            className="w-12 px-2 py-1 bg-slate-900 border border-slate-700 rounded text-sm text-center"
                            placeholder="📁"
                          />
                          <input
                            value={newCollName}
                            onChange={e => setNewCollName(e.target.value)}
                            className="flex-1 px-2 py-1 bg-slate-900 border border-slate-700 rounded text-sm text-slate-200"
                            placeholder="Collection name"
                          />
                        </div>
                        <input
                          value={newCollDesc}
                          onChange={e => setNewCollDesc(e.target.value)}
                          className="w-full px-2 py-1 bg-slate-900 border border-slate-700 rounded text-sm text-slate-200"
                          placeholder="Description (optional)"
                        />
                        <button
                          disabled={!newCollName.trim() || collSaving}
                          onClick={async () => {
                            setCollSaving(true);
                            try {
                              const id = newCollName.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_');
                              await adminCreateCollection({ id, name: newCollName.trim(), icon: newCollIcon, description: newCollDesc });
                              setShowNewCollection(false);
                              setNewCollName(''); setNewCollIcon('📁'); setNewCollDesc('');
                              await loadCollections();
                            } catch (e) {
                              alert(e instanceof Error ? e.message : 'Failed to create collection');
                            } finally { setCollSaving(false); }
                          }}
                          className="px-3 py-1 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 rounded text-xs text-white"
                        >
                          Create
                        </button>
                      </div>
                    )}

                    <div className="space-y-2">
                      {collections.map(coll => (
                        <div key={coll.id} className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-medium text-slate-200">
                              {coll.icon} {coll.name}
                              <span className="text-xs text-slate-500 ml-2">
                                {coll.scenario_ids
                                  ? coll.scenario_ids.length
                                  : '?'} scenarios
                              </span>
                            </span>
                            <div className="flex gap-2">
                              {editingCollection === coll.id ? (
                                <button
                                  disabled={collSaving}
                                  onClick={async () => {
                                    setCollSaving(true);
                                    try {
                                      await adminUpdateCollectionScenarios(coll.id, editScenarioIds);
                                      setEditingCollection(null);
                                      await loadCollections();
                                    } catch (e) {
                                      alert(e instanceof Error ? e.message : 'Failed');
                                    } finally { setCollSaving(false); }
                                  }}
                                  className="text-xs text-green-400 hover:text-green-300"
                                >Save</button>
                              ) : (
                                <button
                                  onClick={() => {
                                    setEditingCollection(coll.id);
                                    setEditScenarioIds(
                                      coll.scenario_ids || []
                                    );
                                  }}
                                  className="text-xs text-sky-400 hover:text-sky-300"
                                >Edit</button>
                              )}
                              {editingCollection === coll.id && (
                                <button onClick={() => setEditingCollection(null)} className="text-xs text-slate-500 hover:text-slate-300">Cancel</button>
                              )}
                            </div>
                          </div>

                          {editingCollection === coll.id && library && (
                            <div className="mt-2 max-h-48 overflow-y-auto space-y-1">
                              {library.scenarios.map(s => (
                                <label key={s.id} className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer hover:text-slate-100">
                                  <input
                                    type="checkbox"
                                    checked={editScenarioIds.includes(s.id)}
                                    onChange={e => {
                                      if (e.target.checked) {
                                        setEditScenarioIds([...editScenarioIds, s.id]);
                                      } else {
                                        setEditScenarioIds(editScenarioIds.filter(x => x !== s.id));
                                      }
                                    }}
                                    className="accent-sky-500"
                                  />
                                  {s.name}
                                </label>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Scenarios */}
                  <div className="mb-6">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-semibold text-slate-300">📚 Scenarios</h3>
                      <span className="text-xs text-slate-500">
                        {scenarioVisibleCount} visible / {scenarioArchivedCount} archived
                      </span>
                    </div>
                    <div className="space-y-1">
                      {filteredScenarios.map(s => (
                        <div key={s.id} className="flex items-center justify-between px-3 py-2 rounded-lg bg-slate-800/50 border border-slate-700">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="text-sm text-slate-200 truncate">{s.name}</span>
                            {s.collections && s.collections.map(col => (
                              <span key={col} className="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300 whitespace-nowrap">
                                {col}
                              </span>
                            ))}
                          </div>
                          <button
                            onClick={() => handleToggleVisibility('scenario', s.id, s.visible)}
                            disabled={togglingId === s.id}
                            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors flex-shrink-0 ${
                              s.visible ? 'bg-green-600' : 'bg-slate-700'
                            } ${togglingId === s.id ? 'opacity-50' : ''}`}
                          >
                            <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                              s.visible ? 'translate-x-4.5' : 'translate-x-0.5'
                            }`} />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Policies */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-semibold text-slate-300">🧠 Policies</h3>
                      <span className="text-xs text-slate-500">
                        {policyVisibleCount} visible / {policyArchivedCount} archived
                      </span>
                    </div>
                    <div className="space-y-1">
                      {filteredPolicies.map(p => (
                        <div key={p.id} className="flex items-center justify-between px-3 py-2 rounded-lg bg-slate-800/50 border border-slate-700">
                          <span className="text-sm text-slate-200 truncate">{p.name}</span>
                          <button
                            onClick={() => handleToggleVisibility('policy', p.id, p.visible)}
                            disabled={togglingId === p.id}
                            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors flex-shrink-0 ${
                              p.visible ? 'bg-green-600' : 'bg-slate-700'
                            } ${togglingId === p.id ? 'opacity-50' : ''}`}
                          >
                            <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                              p.visible ? 'translate-x-4.5' : 'translate-x-0.5'
                            }`} />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
