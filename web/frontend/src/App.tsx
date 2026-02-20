import { useState, useEffect } from 'react';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { AuthProvider } from './contexts/AuthContext';
import { useAuth } from './hooks/useAuth';
import { AuthInfoContext } from './AuthInfoContext';
import { checkAdmin } from './api';

function AppContent() {
  const { user, loading, backendStatus, signIn, signOut: handleAuthSignOut } = useAuth();
  const [isAdmin, setIsAdmin] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      setIsAdmin(false);
      setReady(true);
      return;
    }
    checkAdmin()
      .then((res) => {
        setIsAdmin(res.is_admin);
      })
      .catch(() => {
        setIsAdmin(false);
      })
      .finally(() => setReady(true));
  }, [user, loading]);

  // Only show loading screen on genuine cold starts (backend not yet responding).
  // For warm starts, auth + admin check resolve within a frame — skip the splash.
  if (loading || !ready) {
    if (backendStatus === 'cold-start') {
      return (
        <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--bg-base)', color: 'var(--text-primary)' }}>
          <div className="text-center space-y-6">
            <div className="text-4xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              SimCash
            </div>
            <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Interactive Payment Simulator
            </div>
            <div className="flex items-center justify-center gap-3">
              <div className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: 'var(--text-accent)' }} />
              <div className="text-base" style={{ color: 'var(--text-secondary)' }}>
                Starting simulation engine...
              </div>
            </div>
            <div className="text-xs max-w-xs mx-auto" style={{ color: 'var(--text-tertiary, var(--text-secondary))' }}>
              First load takes ~15 seconds while the Rust engine initialises
            </div>
          </div>
        </div>
      );
    }
    // Warm start: render nothing for the brief moment while auth resolves
    return null;
  }

  const isGuest = !user;

  return (
    <AuthInfoContext.Provider value={{
      isAdmin,
      userEmail: user?.email ?? '',
      isGuest,
      onSignOut: handleAuthSignOut,
      onSignIn: signIn,
    }}>
      <RouterProvider router={router} />
    </AuthInfoContext.Provider>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
