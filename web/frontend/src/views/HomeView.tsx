import { Link, useNavigate } from 'react-router-dom';
import { HowItWorks } from '../components/HowItWorks';
import { useAuthInfo } from '../AuthInfoContext';

export function HomeView() {
  const { isGuest, onSignIn } = useAuthInfo();
  const navigate = useNavigate();

  return (
    <div className="max-w-4xl mx-auto">
      {/* Alpha disclaimer */}
      <div className="mb-6 rounded-lg px-4 py-3 text-center text-sm" style={{ backgroundColor: 'var(--bg-surface, rgba(255,255,255,0.05))', border: '1px solid var(--border-color, rgba(255,255,255,0.1))', color: 'var(--text-muted, #94a3b8)' }}>
        🚧 <strong style={{ color: 'var(--text-secondary, #cbd5e1)' }}>Early Alpha</strong> — SimCash is under active development. Some features may be incomplete or behave unexpectedly.
      </div>

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

      {/* Tutorial Card */}
      <div className="bg-gradient-to-r from-sky-500/10 to-violet-500/10 border border-sky-500/30 rounded-xl p-6 text-center mb-8">
        <h3 className="text-lg font-semibold text-white mb-2">🎓 Guided Tour</h3>
        <p className="text-sm text-slate-300 max-w-lg mx-auto mb-4">
          Walk through a real completed experiment in 5 minutes. See how two AI agents independently optimized
          payment strategies, evolved decision trees, and reduced costs by 60%.
        </p>
        <button
          onClick={() => {
            localStorage.removeItem('simcash_tour_done');
            navigate('/experiment/9af6fa02?tour=1');
          }}
          className="px-8 py-4 rounded-xl bg-gradient-to-r from-sky-500 to-violet-500 font-bold text-lg text-white hover:from-sky-400 hover:to-violet-400 transition-all shadow-lg shadow-sky-500/25 cursor-pointer"
        >
          ▶ Start Tutorial
        </button>
        <p className="text-xs text-slate-500 mt-3">Real experiment · 24 interactive steps · No setup needed</p>
      </div>

      {/* Why SimCash — Research Motivations */}
      <div className="mb-8 space-y-4 max-w-3xl mx-auto text-sm" style={{ color: 'var(--text-secondary)' }}>
        <h3 className="text-lg font-semibold text-center" style={{ color: 'var(--text-primary)' }}>Why SimCash?</h3>

        <div>
          <h4 className="font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Auditable agentic systems</h4>
          <p>
            As AI agents take on increasingly consequential decision-making roles — from portfolio management
            to infrastructure operations — a central challenge emerges: how do you audit a system whose
            reasoning is a neural network forward pass? SimCash explores what agentic systems can look like
            when auditability is a first-class design constraint. Rather than letting an LLM make
            transaction-level decisions directly, agents optimise a structured decision tree — a JSON policy
            with explicit conditions, thresholds, and actions that the simulation engine executes
            deterministically. Every decision the system makes can be traced to a specific node in the tree,
            and every change the AI proposes is captured as a versioned diff between policy documents.
            This architecture demonstrates how the generative power of hard-to-audit foundation models can
            be channelled into producing explainable decisions that follow a consistent, systematic framework —
            separating the <em>creativity</em> of policy design (where LLMs excel) from the <em>execution</em> of
            policy logic (where determinism and traceability matter).
          </p>
        </div>

        <div>
          <h4 className="font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Statistical guardrails for AI governance</h4>
          <p>
            When an AI system proposes a change — a new trading strategy, a revised operating procedure, an
            updated decision policy — how do you decide whether to accept it? Naive before/after comparisons
            are confounded by stochastic variation: a policy might look better simply because it was tested on
            a favourable random draw. SimCash addresses this with bootstrap paired evaluation: each candidate
            policy is run alongside the incumbent on the <em>same</em> set of stochastic samples, and
            acceptance requires statistically demonstrated improvement. The AI proposes; the statistical
            framework disposes. This provides a concrete, working example of how quantitative guardrails can
            govern AI-driven decisions in any domain — not by constraining what the AI can suggest, but by
            rigorously validating whether its suggestions actually improve outcomes.
          </p>
        </div>

        <div>
          <h4 className="font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Building on recent research</h4>
          <p>
            SimCash sits at the intersection of two active research frontiers: AI in payment systems and
            AI agents in economic research. It builds directly on{' '}
            <a href="https://www.bankofcanada.ca/2025/11/staff-working-paper-2025-35/" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-accent)' }}>
              Castro et al. (2025)
            </a>, who demonstrated that reinforcement learning agents can learn near-optimal liquidity
            management strategies in RTGS environments, replicating their experimental scenarios while
            replacing neural network policy gradients with LLM-based natural language reasoning. It extends
            the work of{' '}
            <a href="https://www.bis.org/publ/work1310.htm" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-accent)' }}>
              Desai &amp; Aldasoro (2025, BIS Working Paper No. 1310)
            </a>, who explored how generative AI could be applied to intraday cash management in wholesale
            payment systems — a question SimCash makes interactive and experimentally reproducible.
            It also draws on the framework proposed by{' '}
            <a href="https://www.aeaweb.org/content/file?id=23290" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-accent)' }}>
              Korinek (2025)
            </a>{' '}
            for deploying AI agents in economic research — using LLMs not as black-box oracles but as
            autonomous optimisers with structured reasoning, tool use, and iterative refinement. SimCash
            operationalises this vision: each agent is an autonomous reasoner that analyses simulation
            results, formulates hypotheses about cost drivers, and proposes structural policy changes —
            the kind of multi-step analytical workflow Korinek argues LLM agents are uniquely suited for.
          </p>
        </div>

        <div>
          <h4 className="font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Open-weight models for regulated environments</h4>
          <p>
            SimCash currently runs on{' '}
            <a href="https://bigmodel.cn/" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-accent)' }}>
              GLM-4.7
            </a>, an open-weight model served via Google Vertex AI. This is a deliberate choice.
            In any realistic future where AI agents operate within payment systems, those agents will almost
            certainly run on-premise — inside tightly regulated institutions that cannot route sensitive
            transaction data through third-party APIs. By demonstrating that an open-weight model already
            achieves strong results on this coordination task, SimCash provides evidence that the capability
            threshold for agentic cash management is within reach of models that banks and central banks
            can deploy on their own infrastructure, under their own governance frameworks. The reasoning
            capabilities needed to analyse payment flows, identify cost drivers, and propose structural
            policy improvements do not require the largest proprietary frontier models — they require a
            model that is good enough, auditable, and deployable where the data lives.
          </p>
        </div>
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
          Built by <a href="https://www.linkedin.com/in/hugi/" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-accent)' }}><strong>Hugi Aegisberg</strong></a> · Licensed under{' '}
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
