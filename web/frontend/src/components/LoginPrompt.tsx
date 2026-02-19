import { useAuthInfo } from '../AuthInfoContext';

interface LoginPromptProps {
  reason?: string;
  inline?: boolean;
}

export function LoginPrompt({ reason = 'You need to sign in to access this feature.', inline = false }: LoginPromptProps) {
  const { onSignIn } = useAuthInfo();

  const content = (
    <div className="text-center space-y-4">
      <div className="text-3xl">🔒</div>
      <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Sign in required</h3>
      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{reason}</p>
      <button
        onClick={onSignIn}
        className="px-6 py-3 rounded-lg font-medium transition-colors flex items-center gap-3 mx-auto"
        style={{ backgroundColor: 'var(--btn-primary-bg)', color: '#fff', border: '1px solid var(--border-color)' }}
      >
        <svg className="w-5 h-5" viewBox="0 0 24 24">
          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
        </svg>
        Sign in with Google
      </button>
    </div>
  );

  if (inline) {
    return (
      <div className="rounded-xl border p-6" style={{ borderColor: 'var(--border-color)', backgroundColor: 'var(--bg-surface)' }}>
        {content}
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-[50vh]">
      <div className="rounded-xl border p-8 max-w-md w-full" style={{ borderColor: 'var(--border-color)', backgroundColor: 'var(--bg-surface)' }}>
        {content}
      </div>
    </div>
  );
}
