import { createContext, useEffect, useState, type ReactNode } from 'react';
import { onAuthStateChanged, type User } from 'firebase/auth';
import { auth, signInWithGoogle, signOut, getIdToken, handleRedirectResult } from '../firebase';

const API_ORIGIN = import.meta.env.VITE_API_ORIGIN || '';

export type BackendStatus = 'connecting' | 'ready' | 'cold-start';

export interface AuthContextValue {
  user: User | null;
  loading: boolean;
  backendStatus: BackendStatus;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  getToken: () => Promise<string | null>;
}

export const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  backendStatus: 'connecting',
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
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('connecting');

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const devToken = urlParams.get('dev_token') || sessionStorage.getItem('simcash_dev_token');

    let cancelled = false;
    let attempt = 0;

    const tryConnect = () => {
      attempt++;
      if (attempt > 1) setBackendStatus('cold-start');

      fetch(`${API_ORIGIN}/api/auth-mode`)
        .then(r => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
        .then(data => {
          if (cancelled) return;
          setBackendStatus('ready');
          if (data.auth_disabled || (data.dev_token_enabled && devToken)) {
            if (devToken) {
              sessionStorage.setItem('simcash_dev_token', devToken);
            }
            setDevMode(true);
            setUser(DEV_USER);
            setLoading(false);
            return;
          }
          handleRedirectResult().catch(() => {});
          // Timeout: if Firebase Auth doesn't resolve in 3s, assume no user
          const authTimeout = setTimeout(() => {
            if (!cancelled) {
              setUser(null);
              setLoading(false);
            }
          }, 3000);
          const unsub = onAuthStateChanged(auth, (u) => {
            clearTimeout(authTimeout);
            if (!cancelled) {
              setUser(u);
              setLoading(false);
            }
          });
          return unsub;
        })
        .catch(() => {
          if (cancelled) return;
          // Backend not ready — retry with backoff (cold start takes ~20s)
          if (attempt < 10) {
            const delay = Math.min(2000 * attempt, 5000);
            setTimeout(tryConnect, delay);
          } else {
            // Give up after ~30s, fall through to Firebase auth
            setBackendStatus('ready');
            handleRedirectResult().catch(() => {});
            const authTimeout2 = setTimeout(() => {
              if (!cancelled) { setUser(null); setLoading(false); }
            }, 3000);
            const unsub = onAuthStateChanged(auth, (u) => {
              clearTimeout(authTimeout2);
              if (!cancelled) {
                setUser(u);
                setLoading(false);
              }
            });
            return unsub;
          }
        });
    };

    tryConnect();

    // Safety net: never stay in loading state for more than 10s
    const safetyTimeout = setTimeout(() => {
      if (!cancelled) setLoading(false);
    }, 10000);

    return () => { cancelled = true; clearTimeout(safetyTimeout); };
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
        backendStatus,
        signIn: handleSignIn,
        signOut: handleSignOut,
        getToken: devMode ? (async () => sessionStorage.getItem('simcash_dev_token') || 'dev-token') : getIdToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
