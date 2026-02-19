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
        // Access denied or error — still let them in as non-admin
        setIsAdmin(false);
      })
      .finally(() => setReady(true));
  }, [user, loading]);

  if (loading || !ready) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center">
        <div className="text-slate-400 text-lg">Loading...</div>
      </div>
    );
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
