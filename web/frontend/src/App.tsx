import { useState, useEffect } from 'react';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { AuthProvider } from './contexts/AuthContext';
import { useAuth } from './hooks/useAuth';
import { AuthInfoContext } from './AuthInfoContext';
import { checkAdmin } from './api';

function AppContent() {
  const { user, loading, signIn, signOut: handleAuthSignOut } = useAuth();
  const [isAdmin, setIsAdmin] = useState(false);
  const [ready, setReady] = useState(false);
  const [showSplash, setShowSplash] = useState(false);

  // Only show the cold-start splash after 2s of waiting — avoids flash on warm reloads
  useEffect(() => {
    if (!loading && ready) return;
    const timer = setTimeout(() => setShowSplash(true), 2000);
    return () => clearTimeout(timer);
  }, [loading, ready]);

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
    if (showSplash) {
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
    // Still loading but under 2s — show nothing (no flash)
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
