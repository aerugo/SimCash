import { useState, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import { sendMagicLink, isEmailSignInLink, completeMagicLinkSignIn } from '../firebase';

export function LoginPage({ accessDenied }: { accessDenied?: boolean }) {
  const { signIn, loading } = useAuth();
  const [email, setEmail] = useState('');
  const [magicLinkSent, setMagicLinkSent] = useState(false);
  const [magicLinkLoading, setMagicLinkLoading] = useState(false);
  const [error, setError] = useState('');
  const [completingSignIn, setCompletingSignIn] = useState(false);

  // Handle magic link callback on page load
  useEffect(() => {
    if (isEmailSignInLink(window.location.href)) {
      setCompletingSignIn(true);
      completeMagicLinkSignIn(window.location.href)
        .then(() => {
          // Clear the URL params
          window.history.replaceState(null, '', window.location.pathname);
        })
        .catch((err) => {
          setError(err.message || 'Failed to complete sign-in.');
        })
        .finally(() => setCompletingSignIn(false));
    }
  }, []);

  const handleSendMagicLink = async () => {
    if (!email.trim()) return;
    setMagicLinkLoading(true);
    setError('');
    try {
      await sendMagicLink(email.trim());
      setMagicLinkSent(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to send magic link.');
    } finally {
      setMagicLinkLoading(false);
    }
  };

  if (completingSignIn) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center">
        <div className="text-slate-400 text-lg">Completing sign-in…</div>
      </div>
    );
  }

  if (accessDenied) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center">
        <div className="text-center space-y-6">
          <div className="text-5xl font-bold bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent mb-2">
            💰 SimCash
          </div>
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-6 max-w-md">
            <p className="text-red-300 font-medium">Access Denied</p>
            <p className="text-slate-400 text-sm mt-2">
              You don't have access to SimCash. Contact an admin to get invited.
            </p>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors underline"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0f172a] flex items-center justify-center">
      <div className="text-center space-y-8 w-full max-w-sm px-4">
        <div>
          <div className="text-5xl font-bold bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent mb-2">
            💰 SimCash
          </div>
          <p className="text-slate-400 text-sm">Interactive Payment Simulator</p>
        </div>

        <button
          onClick={signIn}
          disabled={loading}
          className="px-6 py-3 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded-lg text-slate-100 font-medium transition-colors flex items-center gap-3 mx-auto disabled:opacity-50"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          Sign in with Google
        </button>

        <div className="flex items-center gap-3">
          <div className="flex-1 border-t border-slate-700" />
          <span className="text-slate-500 text-xs">or</span>
          <div className="flex-1 border-t border-slate-700" />
        </div>

        {magicLinkSent ? (
          <div className="bg-green-900/30 border border-green-700 rounded-lg p-4">
            <p className="text-green-300 text-sm font-medium">Check your email</p>
            <p className="text-slate-400 text-xs mt-1">
              We sent a sign-in link to <strong className="text-slate-300">{email}</strong>
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <input
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMagicLink()}
              className="w-full px-4 py-3 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-sky-500 transition-colors"
            />
            <button
              onClick={handleSendMagicLink}
              disabled={magicLinkLoading || !email.trim()}
              className="w-full px-4 py-3 bg-sky-600 hover:bg-sky-500 rounded-lg text-white font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {magicLinkLoading ? 'Sending…' : 'Send magic link'}
            </button>
          </div>
        )}

        {error && (
          <p className="text-red-400 text-xs">{error}</p>
        )}

        <p className="text-slate-600 text-xs">Access restricted to authorized users</p>
      </div>
    </div>
  );
}
