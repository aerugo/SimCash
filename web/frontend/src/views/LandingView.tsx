import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';

const FEATURES = [
  {
    icon: '📚',
    title: 'Explore Scenarios',
    desc: 'Browse crisis simulations, LSM tests, paper experiments, and more',
  },
  {
    icon: '🧠',
    title: 'Policy Library',
    desc: '30+ built-in strategies — from simple FIFO to adaptive decision trees',
  },
  {
    icon: '✏️',
    title: 'Build Your Own',
    desc: 'Write custom YAML scenarios with live validation and launch them',
  },
  {
    icon: '📖',
    title: 'Documentation',
    desc: 'Learn about RTGS, LSM, game theory, and the SimCash engine',
  },
];

const STEPS = [
  { num: '1', label: 'Pick a scenario', desc: 'Choose a payment network: number of banks, tick count, cost structure, LSM rules, and scheduled events.' },
  { num: '2', label: 'Watch agents learn', desc: 'Each round, the engine runs policies for all ticks, costs are tallied, and AI agents propose improved strategies.' },
  { num: '3', label: 'Analyze strategies', desc: 'Inspect decision trees, compare cost breakdowns, trace individual payments, and export data for further analysis.' },
];

export function LandingView() {
  const { signIn } = useAuth();
  useTheme(); // apply light mode

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--bg-base)', color: 'var(--text-primary)' }}>
      {/* Hero */}
      <div className="max-w-4xl mx-auto px-6 pt-24 pb-16 text-center">
        <h1 className="text-4xl sm:text-5xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
          SimCash
        </h1>
        <p className="text-xl sm:text-2xl font-light mb-3 italic" style={{ color: 'var(--accent)' }}>
          Can AI agents learn to coordinate in payment systems?
        </p>
        <p className="max-w-2xl mx-auto mb-10 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          Banks in real-time gross settlement systems face a fundamental tension:
          holding liquidity is expensive, but delaying payments is worse — and if every bank waits
          for incoming funds before releasing outgoing ones, the whole system gridlocks.
          Here, AI agents independently build decision-tree policies to navigate this coordination problem,
          and we watch whether they find equilibrium.
        </p>
        <button
          onClick={signIn}
          className="inline-flex items-center gap-3 px-8 py-4 rounded-xl font-semibold text-lg transition-colors shadow-lg cursor-pointer"
          style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path fill="#fff" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fillOpacity=".7" />
            <path fill="#fff" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fillOpacity=".85" />
            <path fill="#fff" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fillOpacity=".6" />
            <path fill="#fff" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fillOpacity=".75" />
          </svg>
          Sign In with Google
        </button>
      </div>

      {/* Feature cards */}
      <div className="max-w-5xl mx-auto px-6 pb-16">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-xl p-5" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
              <div className="text-2xl mb-2">{f.icon}</div>
              <h3 className="font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>{f.title}</h3>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* How it works */}
      <div className="max-w-3xl mx-auto px-6 pb-16">
        <h2 className="text-2xl font-bold text-center mb-8" style={{ color: 'var(--text-primary)' }}>How It Works</h2>
        <div className="flex flex-col sm:flex-row gap-6 sm:gap-4">
          {STEPS.map((s, i) => (
            <div key={s.num} className="flex-1 text-center">
              <div
                className="w-10 h-10 rounded-full font-bold text-lg flex items-center justify-center mx-auto mb-3"
                style={{ backgroundColor: 'var(--bg-well)', border: '1px solid var(--border)', color: 'var(--accent)' }}
              >
                {s.num}
              </div>
              <h3 className="font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>{s.label}</h3>
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{s.desc}</p>
              {i < STEPS.length - 1 && (
                <div className="hidden sm:block text-2xl mt-2" style={{ color: 'var(--border)' }}>→</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="max-w-3xl mx-auto px-6 pb-20 text-center">
        <div className="pt-10 space-y-3" style={{ borderTop: '1px solid var(--border)' }}>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            Built by <strong>Hugi Aegisberg</strong> · Licensed under{' '}
            <a href="https://opensource.org/licenses/MIT" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-accent)' }}>MIT</a>
          </p>
          <p className="text-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>
            Methodology builds on the work of{' '}
            <a href="https://www.bankofcanada.ca/2025/11/staff-working-paper-2025-35/" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-accent)' }}>
              Castro et al. (2025)
            </a>
            {' '}· Source code on{' '}
            <a href="https://github.com/aerugo/SimCash" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-accent)' }}>
              GitHub
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
