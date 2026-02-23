import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { signInWithPassword } from '../firebase';

const page = "min-h-screen flex items-center justify-center";
const pageStyle: React.CSSProperties = { backgroundColor: 'var(--bg-base)', color: 'var(--text-primary)' };

export function LoginPage({ accessDenied }: { accessDenied?: boolean }) {
  const { user, signIn, loading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [error, setError] = useState('');

  // Redirect to home if already authenticated
  useEffect(() => {
    if (user && !loading) navigate('/', { replace: true });
  }, [user, loading, navigate]);

  const handlePasswordLogin = async () => {
    if (!email.trim() || !password.trim()) return;
    setPasswordLoading(true);
    setError('');
    try {
      await signInWithPassword(email.trim(), password);
    } catch (err: unknown) {
      const code = (err as { code?: string }).code;
      if (code === 'auth/wrong-password' || code === 'auth/invalid-credential') {
        setError('Incorrect email or password.');
      } else if (code === 'auth/user-not-found') {
        setError('No account found with this email.');
      } else if (code === 'auth/too-many-requests') {
        setError('Too many attempts. Try again later.');
      } else {
        setError(err instanceof Error ? err.message : 'Sign-in failed.');
      }
    } finally {
      setPasswordLoading(false);
    }
  };

  if (accessDenied) {
    return (
      <div className={page} style={pageStyle}>
        <div className="text-center space-y-6">
          <div className="text-5xl font-bold mb-2" style={{ color: 'var(--text-accent)' }}>
            💰 SimCash
          </div>
          <div className="rounded-lg p-6 max-w-md" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)' }}>
            <p className="font-medium" style={{ color: 'var(--color-danger, #ef4444)' }}>Access Denied</p>
            <p className="text-sm mt-2" style={{ color: 'var(--text-secondary)' }}>
              You don't have access to SimCash. Contact an admin to get invited.
            </p>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="text-xs underline transition-colors"
            style={{ color: 'var(--text-muted)' }}
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={page} style={pageStyle}>
      <div className="text-center space-y-8 w-full max-w-sm px-4">
        <div>
          <div className="text-5xl font-bold mb-2" style={{ color: 'var(--text-accent)' }}>
            💰 SimCash
          </div>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Interactive Payment Simulator</p>
        </div>

        {/* Email + Password form */}
        <div className="space-y-3">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && document.getElementById('pw-input')?.focus()}
            className="w-full px-4 py-3 rounded-lg text-sm focus:outline-none transition-colors"
            style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
          />
          <input
            id="pw-input"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handlePasswordLogin()}
            className="w-full px-4 py-3 rounded-lg text-sm focus:outline-none transition-colors"
            style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
          />
          <button
            onClick={handlePasswordLogin}
            disabled={passwordLoading || !email.trim() || !password.trim()}
            className="w-full px-4 py-3 rounded-lg text-white font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ backgroundColor: 'var(--text-accent)' }}
          >
            {passwordLoading ? 'Signing in…' : 'Sign In'}
          </button>
        </div>

        {error && (
          <p className="text-xs" style={{ color: 'var(--color-danger, #ef4444)' }}>{error}</p>
        )}

        <div className="flex items-center gap-3">
          <div className="flex-1" style={{ borderTop: '1px solid var(--border-color)' }} />
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>or</span>
          <div className="flex-1" style={{ borderTop: '1px solid var(--border-color)' }} />
        </div>

        <button
          onClick={signIn}
          className="px-6 py-3 rounded-lg font-medium transition-colors flex items-center gap-3 mx-auto"
          style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          Sign in with Google
        </button>

        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Access restricted to authorized users</p>
      </div>
    </div>
  );
}
