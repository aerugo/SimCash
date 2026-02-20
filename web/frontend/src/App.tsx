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
    // Never show a splash screen — just a blank page with matching background.
    // The landing page / login page will appear once auth resolves (typically <1s warm, ~15s cold).
    return <div className="min-h-screen" style={{ backgroundColor: 'var(--bg-base)' }} />;
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
