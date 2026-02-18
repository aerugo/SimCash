import { useState, useEffect } from 'react';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { AuthProvider } from './contexts/AuthContext';
import { useAuth } from './hooks/useAuth';
import { LoginPage } from './components/LoginPage';
import { LandingView } from './views/LandingView';
import { AuthInfoContext } from './AuthInfoContext';
import { checkAdmin } from './api';

function AppContent() {
  const { user, loading, signOut: handleAuthSignOut } = useAuth();
  const [accessDenied, setAccessDenied] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminChecked, setAdminChecked] = useState(false);

  useEffect(() => {
    if (!user) {
      setAccessDenied(false);
      setIsAdmin(false);
      setAdminChecked(false);
      return;
    }
    checkAdmin()
      .then((res) => {
        setIsAdmin(res.is_admin);
        setAdminChecked(true);
      })
      .catch((err) => {
        if (err instanceof Error && err.message.includes('403')) {
          setAccessDenied(true);
        }
        setAdminChecked(true);
      });
  }, [user]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center">
        <div className="text-slate-400 text-lg">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return <LandingView />;
  }

  if (accessDenied) {
    return <LoginPage accessDenied={accessDenied} />;
  }

  if (!adminChecked) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center">
        <div className="text-slate-400 text-lg">Loading...</div>
      </div>
    );
  }

  return (
    <AuthInfoContext.Provider value={{ isAdmin, userEmail: user.email ?? '', onSignOut: handleAuthSignOut }}>
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
