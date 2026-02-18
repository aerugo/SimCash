import { createContext, useEffect, useState, type ReactNode } from 'react';
import { onAuthStateChanged, type User } from 'firebase/auth';
import { auth, signInWithGoogle, signOut, getIdToken } from '../firebase';

export interface AuthContextValue {
  user: User | null;
  loading: boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  getToken: () => Promise<string | null>;
}

export const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  signIn: async () => {},
  signOut: async () => {},
  getToken: async () => null,
});

// Minimal fake user for dev mode (when backend has SIMCASH_AUTH_DISABLED=true)
const DEV_USER = {
  uid: 'dev-user',
  email: 'dev@localhost',
  displayName: 'Dev User',
  emailVerified: true,
} as unknown as User;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [devMode, setDevMode] = useState(false);

  useEffect(() => {
    // Check for dev_token in URL params
    const urlParams = new URLSearchParams(window.location.search);
    const devToken = urlParams.get('dev_token');

    // Check if backend auth is disabled (dev mode) or dev_token provided
    fetch('/api/auth-mode')
      .then(r => r.json())
      .then(data => {
        if (data.auth_disabled || (data.dev_token_enabled && devToken)) {
          // Store dev token for API calls
          if (devToken) {
            sessionStorage.setItem('simcash_dev_token', devToken);
          }
          setDevMode(true);
          setUser(DEV_USER);
          setLoading(false);
          return;
        }
        // Normal Firebase auth
        const unsub = onAuthStateChanged(auth, (u) => {
          setUser(u);
          setLoading(false);
        });
        return unsub;
      })
      .catch(() => {
        // Backend unreachable — fall through to Firebase
        const unsub = onAuthStateChanged(auth, (u) => {
          setUser(u);
          setLoading(false);
        });
        return unsub;
      });
  }, []);

  const handleSignIn = async () => {
    await signInWithGoogle();
  };

  const handleSignOut = async () => {
    await signOut();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        signIn: handleSignIn,
        signOut: handleSignOut,
        getToken: devMode ? (async () => sessionStorage.getItem('simcash_dev_token') || 'dev-token') : getIdToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
