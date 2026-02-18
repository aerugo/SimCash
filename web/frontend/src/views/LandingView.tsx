import { useAuth } from '../hooks/useAuth';

const FEATURES = [
  { icon: '📅', title: 'Multi-Day Optimization', desc: 'AI agents learn liquidity strategies across multi-day settlement horizons with realistic carry-over dynamics.' },
  { icon: '🌳', title: 'Real Decision Trees', desc: 'Agents produce interpretable policy trees — not black-box weights — so you can trace every decision.' },
  { icon: '📊', title: 'Bootstrap Evaluation', desc: 'Statistically rigorous policy scoring with bootstrap confidence intervals over thousands of replications.' },
  { icon: '📚', title: 'Scenario Library', desc: 'Pre-built scenarios from the research literature, plus a visual editor for designing your own.' },
];

const STEPS = [
  { num: '1', label: 'Pick a scenario', desc: 'Choose from the library or design a custom payment network.' },
  { num: '2', label: 'Watch AI agents learn', desc: 'Agents explore strategies in real time, building decision trees.' },
  { num: '3', label: 'Analyze results', desc: 'Compare policies, inspect agent reasoning, and export findings.' },
];

export function LandingView() {
  const { signIn } = useAuth();

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100">
      {/* Hero */}
      <div className="max-w-4xl mx-auto px-6 pt-24 pb-16 text-center">
        <div className="text-6xl mb-6">💰</div>
        <h1 className="text-4xl sm:text-5xl font-bold mb-4 bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">
          SimCash
        </h1>
        <p className="text-xl sm:text-2xl text-slate-300 font-light mb-3">
          AI Agents Learn to Play the Liquidity Game
        </p>
        <p className="text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
          An interactive research platform for studying how AI agents learn coordination strategies
          in RTGS and LSM payment systems — where timing, liquidity, and strategic patience all matter.
        </p>
        <button
          onClick={signIn}
          className="inline-flex items-center gap-3 px-8 py-4 bg-sky-600 hover:bg-sky-500 rounded-xl text-white font-semibold text-lg transition-colors shadow-lg shadow-sky-600/20"
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

      {/* Features */}
      <div className="max-w-5xl mx-auto px-6 pb-16">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {FEATURES.map((f) => (
            <div key={f.title} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-6">
              <div className="text-2xl mb-3">{f.icon}</div>
              <h3 className="text-lg font-semibold text-slate-100 mb-2">{f.title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* How it works */}
      <div className="max-w-3xl mx-auto px-6 pb-16">
        <h2 className="text-2xl font-bold text-center text-slate-200 mb-8">How It Works</h2>
        <div className="flex flex-col sm:flex-row gap-6 sm:gap-4">
          {STEPS.map((s, i) => (
            <div key={s.num} className="flex-1 text-center">
              <div className="w-10 h-10 rounded-full bg-sky-600/20 border border-sky-500/30 text-sky-400 font-bold text-lg flex items-center justify-center mx-auto mb-3">
                {s.num}
              </div>
              <h3 className="font-semibold text-slate-200 mb-1">{s.label}</h3>
              <p className="text-sm text-slate-400">{s.desc}</p>
              {i < STEPS.length - 1 && (
                <div className="hidden sm:block text-slate-600 text-2xl mt-2">→</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Built on */}
      <div className="max-w-3xl mx-auto px-6 pb-20 text-center">
        <div className="border-t border-slate-800 pt-10">
          <p className="text-slate-500 text-sm leading-relaxed">
            Built on a <span className="text-emerald-400/80">Rust</span> simulation engine
            · Powered by <span className="text-cyan-400/80">Vertex AI</span>
            · Based on <span className="text-slate-400">Castro et al. (2025)</span> research on RTGS/LSM coordination games
          </p>
        </div>
      </div>
    </div>
  );
}
