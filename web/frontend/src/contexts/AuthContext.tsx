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
    let devResolved = false;

    // Register auth state listener IMMEDIATELY — not gated behind backend fetch.
    // Otherwise, if the user completes signInWithPopup before the backend responds,
    // onAuthStateChanged fires with no listener registered → sign-in silently lost.
    const authTimeout = setTimeout(() => {
      if (!cancelled && !devResolved) {
        setUser(null);
        setLoading(false);
      }
    }, 5000);

    const unsub = onAuthStateChanged(auth, (u) => {
      if (cancelled || devResolved) return;
      clearTimeout(authTimeout);
      setUser(u);
      setLoading(false);
    });

    // Also try to complete any pending redirect
    handleRedirectResult().catch(() => {});

    // Check backend for dev mode / auth-disabled
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
            devResolved = true;
            clearTimeout(authTimeout);
            setDevMode(true);
            setUser(DEV_USER);
            setLoading(false);
          }
        })
        .catch(() => {
          if (cancelled) return;
          if (attempt < 10) {
            const delay = Math.min(2000 * attempt, 5000);
            setTimeout(tryConnect, delay);
          } else {
            setBackendStatus('ready');
          }
        });
    };

    tryConnect();

    return () => {
      cancelled = true;
      clearTimeout(authTimeout);
      unsub();
    };
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
