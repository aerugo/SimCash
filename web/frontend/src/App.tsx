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

  if (loading || !ready) {
    // Only show the splash when the backend is genuinely unreachable (cold start).
    // Once backend responds ('ready'), Firebase Auth may still be initializing —
    // show nothing for that brief period instead of a misleading splash.
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
            <div className="text-xs max-w-xs mx-auto" style={{ color: 'var(--text-muted)' }}>
              First load takes ~15 seconds while the Rust engine initialises
            </div>
          </div>
        </div>
      );
    }
    // Backend is reachable but auth still resolving — blank screen, no flash
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
