import { Link, useNavigate } from 'react-router-dom';
import type { GameSetupConfig } from '../types';
import { HowItWorks } from '../components/HowItWorks';
import { useGameContext } from '../GameContext';
import { useAuthInfo } from '../AuthInfoContext';

export function HomeView() {
  const { handleGameLaunch } = useGameContext();
  const { isGuest, onSignIn } = useAuthInfo();
  const navigate = useNavigate();
  const onGameLaunch = async (config: GameSetupConfig, tour = false) => {
    const gid = await handleGameLaunch(config);
    if (gid) navigate(`/experiment/${gid}${tour ? '?tour=1' : ''}`);
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold mb-1">Payment System Simulator</h2>
        <p className="text-lg text-violet-300/90 italic mb-3">Can AI agents learn to coordinate in payment systems?</p>
        <p className="text-slate-400 max-w-2xl mx-auto">
          Banks in real-time gross settlement systems face a fundamental tension:
          holding liquidity is expensive, but delaying payments is worse — and if every bank waits
          for incoming funds before releasing outgoing ones, the whole system gridlocks.
          Here, AI agents independently build decision-tree policies to navigate this coordination problem,
          and we watch whether they find equilibrium.
        </p>
      </div>

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Link
          to="/library/scenarios"
          className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 text-left hover:border-sky-500/50 transition-colors group"
        >
          <div className="text-2xl mb-2">📚</div>
          <h3 className="font-semibold text-slate-100 group-hover:text-sky-300 transition-colors mb-1">Explore Scenarios</h3>
          <p className="text-xs text-slate-400">Browse crisis simulations, LSM tests, paper experiments, and more</p>
        </Link>
        <Link
          to="/library/policies"
          className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 text-left hover:border-violet-500/50 transition-colors group"
        >
          <div className="text-2xl mb-2">🧠</div>
          <h3 className="font-semibold text-slate-100 group-hover:text-violet-300 transition-colors mb-1">Policy Library</h3>
          <p className="text-xs text-slate-400">30+ built-in strategies — from simple FIFO to adaptive decision trees</p>
        </Link>
        <Link
          to="/create"
          className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 text-left hover:border-amber-500/50 transition-colors group"
        >
          <div className="text-2xl mb-2">✏️</div>
          <h3 className="font-semibold text-slate-100 group-hover:text-amber-300 transition-colors mb-1">Build Your Own</h3>
          <p className="text-xs text-slate-400">Write custom YAML scenarios with live validation and launch them</p>
        </Link>
        <Link
          to="/docs"
          className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 text-left hover:border-emerald-500/50 transition-colors group"
        >
          <div className="text-2xl mb-2">📖</div>
          <h3 className="font-semibold text-slate-100 group-hover:text-emerald-300 transition-colors mb-1">Documentation</h3>
          <p className="text-xs text-slate-400">Learn about RTGS, LSM, game theory, and the SimCash engine</p>
        </Link>
      </div>

      {/* Quick Tutorial Card */}
      <div className="bg-gradient-to-r from-violet-500/10 to-pink-500/10 border border-violet-500/30 rounded-xl p-6 text-center mb-8">
        <h3 className="text-lg font-semibold text-white mb-2">Quick Tutorial</h3>
        <p className="text-sm text-slate-300 max-w-lg mx-auto mb-4">
          Run a demo experiment in one click with simulated AI responses — results appear instantly.
          Real experiments use an LLM for optimization, where each round waits for the AI to analyze
          results and propose an improved policy (typically 10–40 seconds per optimization).
        </p>
        <button
          onClick={() => {
            onGameLaunch({
              scenario_id: '2bank_12tick',
              use_llm: true,
              simulated_ai: true,
              max_days: 5,
              num_eval_samples: 1,
              optimization_interval: 1,
              constraint_preset: 'full',
            }, true);
          }}
          className="px-8 py-4 rounded-xl bg-gradient-to-r from-violet-500 to-pink-500 font-bold text-lg text-white hover:from-violet-400 hover:to-pink-400 transition-all shadow-lg shadow-violet-500/25 cursor-pointer"
        >
          ▶ Launch Tutorial
        </button>
        <p className="text-xs text-slate-500 mt-3">2 Banks · Simulated AI · 5 rounds · No API cost</p>
      </div>

      {isGuest && (
        <div className="bg-slate-800/30 border border-slate-700 rounded-xl p-4 text-center mb-8">
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            <button onClick={onSignIn} className="font-medium underline" style={{ color: 'var(--text-accent)' }}>Sign in</button>
            {' '}to save experiments and use real AI optimization
          </p>
        </div>
      )}

      <HowItWorks defaultOpen={true} />

      {/* Credits */}
      <div className="mt-12 mb-4 text-center" style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1.5rem' }}>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Built by <strong>Hugi Aegisberg</strong> · Licensed under{' '}
          <a href="https://opensource.org/licenses/MIT" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-accent)' }}>MIT</a>
        </p>
        <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
          Source code on{' '}
          <a href="https://github.com/aerugo/SimCash" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-accent)' }}>GitHub</a>
        </p>
      </div>
    </div>
  );
}
