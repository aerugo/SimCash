import { useState, useEffect, useCallback } from 'react';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { AuthProvider } from './contexts/AuthContext';
import { useAuth } from './hooks/useAuth';
import { AuthInfoContext } from './AuthInfoContext';
import { checkAdmin, setImpersonateUid } from './api';

function AppContent() {
  const { user, loading, signOut: handleAuthSignOut } = useAuth();
  const [isAdmin, setIsAdmin] = useState(false);
  const [impersonatingUid, setImpersonatingUid] = useState<string | null>(null);
  const [impersonatingEmail, setImpersonatingEmail] = useState<string | null>(null);

  useEffect(() => {
    if (loading || !user) {
      setIsAdmin(false);
      return;
    }
    checkAdmin()
      .then((res) => setIsAdmin(res.is_admin))
      .catch(() => setIsAdmin(false));
  }, [user, loading]);

  // Sync impersonation state with api.ts header injection
  useEffect(() => {
    setImpersonateUid(impersonatingUid);
  }, [impersonatingUid]);

  const setImpersonating = useCallback((uid: string | null, email: string | null) => {
    setImpersonatingUid(uid);
    setImpersonatingEmail(email);
  }, []);

  const isGuest = loading || !user;

  const handleSignIn = async () => {
    window.location.href = '/login';
  };

  return (
    <AuthInfoContext.Provider value={{
      isAdmin,
      userEmail: user?.email ?? '',
      isGuest,
      onSignOut: handleAuthSignOut,
      onSignIn: handleSignIn,
      impersonatingUid,
      impersonatingEmail,
      setImpersonating,
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
