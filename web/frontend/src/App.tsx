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

  useEffect(() => {
    if (loading || !user) {
      setIsAdmin(false);
      return;
    }
    checkAdmin()
      .then((res) => setIsAdmin(res.is_admin))
      .catch(() => setIsAdmin(false));
  }, [user, loading]);

  // Render immediately — don't gate on auth loading.
  // Guest users see the landing page right away.
  // Auth state updates reactively once Firebase resolves.
  const isGuest = loading || !user;

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
