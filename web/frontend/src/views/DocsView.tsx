import { useState } from 'react';

type DocSection = 'overview' | 'how-it-works' | 'cost-model' | 'policy-optimization' | 'experiments' | 'game-theory' | 'architecture' | 'blog-convergence' | 'blog-coordination' | 'blog-bootstrap' | 'references';

interface NavItem {
  id: DocSection;
  label: string;
  icon: string;
  group: 'guide' | 'blog' | 'reference';
}

const NAV: NavItem[] = [
  // Guides
  { id: 'overview', label: 'Overview', icon: '📖', group: 'guide' },
  { id: 'how-it-works', label: 'How the Simulator Works', icon: '⚙️', group: 'guide' },
  { id: 'cost-model', label: 'The Cost Model', icon: '💰', group: 'guide' },
  { id: 'policy-optimization', label: 'AI Policy Optimization', icon: '🤖', group: 'guide' },
  { id: 'experiments', label: 'Experiments', icon: '🧪', group: 'guide' },
  { id: 'game-theory', label: 'Game Theory Primer', icon: '♟️', group: 'guide' },
  { id: 'architecture', label: 'Technical Architecture', icon: '🏗️', group: 'guide' },
  // Blog
  { id: 'blog-convergence', label: 'Do LLM Agents Converge?', icon: '📝', group: 'blog' },
  { id: 'blog-coordination', label: 'Coordination Failures', icon: '📝', group: 'blog' },
  { id: 'blog-bootstrap', label: 'Bootstrap Evaluation', icon: '📝', group: 'blog' },
  // Reference
  { id: 'references', label: 'References & Reading', icon: '📚', group: 'reference' },
];

export function DocsView() {
  const [section, setSection] = useState<DocSection>('overview');

  const groups: { key: string; label: string; items: NavItem[] }[] = [
    { key: 'guide', label: 'Guides', items: NAV.filter(n => n.group === 'guide') },
    { key: 'blog', label: 'Blog Posts', items: NAV.filter(n => n.group === 'blog') },
    { key: 'reference', label: 'Reference', items: NAV.filter(n => n.group === 'reference') },
  ];

  return (
    <div className="flex gap-6 max-w-6xl mx-auto">
      {/* Sidebar */}
      <nav className="w-56 shrink-0 hidden md:block">
        <div className="sticky top-24 space-y-5">
          {groups.map(g => (
            <div key={g.key}>
              <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">{g.label}</h4>
              <div className="space-y-0.5">
                {g.items.map(item => (
                  <button
                    key={item.id}
                    onClick={() => setSection(item.id)}
                    className={`w-full text-left px-3 py-1.5 rounded-lg text-sm transition-colors ${
                      section === item.id
                        ? 'bg-sky-500/10 text-sky-400'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                    }`}
                  >
                    <span className="mr-2">{item.icon}</span>
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </nav>

      {/* Mobile nav */}
      <div className="md:hidden w-full mb-4">
        <select
          value={section}
          onChange={e => setSection(e.target.value as DocSection)}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200"
        >
          {NAV.map(n => (
            <option key={n.id} value={n.id}>{n.icon} {n.label}</option>
          ))}
        </select>
      </div>

      {/* Content */}
      <article className="flex-1 min-w-0">
        <div className="prose prose-invert prose-sm max-w-none">
          {section === 'overview' && <Overview />}
          {section === 'how-it-works' && <HowItWorks />}
          {section === 'cost-model' && <CostModel />}
          {section === 'policy-optimization' && <PolicyOptimization />}
          {section === 'experiments' && <Experiments />}
          {section === 'game-theory' && <GameTheory />}
          {section === 'architecture' && <Architecture />}
          {section === 'blog-convergence' && <BlogConvergence />}
          {section === 'blog-coordination' && <BlogCoordination />}
          {section === 'blog-bootstrap' && <BlogBootstrap />}
          {section === 'references' && <References />}
        </div>
      </article>
    </div>
  );
}

/* ─── Guide Pages ─── */

function Overview() {
  return (
    <DocPage title="Overview" subtitle="What is SimCash and why does it exist?">
      <p>
        SimCash is an interactive research sandbox for exploring how AI agents learn to manage
        liquidity in payment systems. It models the fundamental coordination problem that banks
        face every day: <strong>how much cash should you keep ready?</strong>
      </p>

      <h3>The Problem</h3>
      <p>
        In a Real-Time Gross Settlement (RTGS) system, banks settle payments individually in real
        time. Each bank must decide how much liquidity to commit at the start of each day. This
        creates a strategic tradeoff:
      </p>
      <ul>
        <li><strong>Too much liquidity</strong> → expensive (opportunity cost of idle capital)</li>
        <li><strong>Too little liquidity</strong> → payments queue up, delays accumulate, deadlines are missed</li>
      </ul>
      <p>
        What makes this interesting is that each bank's optimal strategy depends on what other
        banks do. If your counterparty commits lots of liquidity, their payments to you settle
        quickly, giving you incoming cash to fund your own outgoing payments. This is a
        <em>coordination game</em>.
      </p>

      <h3>The Experiment</h3>
      <p>
        We let AI agents (powered by GPT-5.2) play this game repeatedly. Each day, the Rust
        simulation engine runs the payment system with the agents' current policies. At the end
        of each day, each agent independently analyzes its own results — costs incurred, payments
        settled, delays suffered — and proposes an improved policy for the next day.
      </p>
      <p>
        Over many days, we watch whether these independently-optimizing agents converge to stable
        strategies, and whether those strategies resemble the game-theoretic equilibria predicted
        by economic theory.
      </p>

      <h3>Key Insight</h3>
      <Callout type="insight">
        <strong>Stability does not imply optimality.</strong> In our experiments, LLM agents
        reliably converge to <em>stable</em> policy profiles, but these aren't always
        Pareto-efficient. In deterministic scenarios, we observe <em>coordination failures</em>
        where one agent free-rides on the other's liquidity — the free-rider benefits while
        the exploited bank is worse off, and the system as a whole is less efficient than it
        could be. Stochastic environments with statistical evaluation produce more symmetric,
        near-optimal outcomes.
      </Callout>

      <h3>Context</h3>
      <p>
        SimCash was created by Hugi Aegisberg as a research tool for studying multi-agent
        coordination in payment systems. It implements and extends the experimental scenarios
        from the BIS Working Paper No. 1310, <em>"AI agents for cash management in payment
        systems"</em> (2025), which demonstrated that general-purpose LLMs can replicate key
        cash management practices even without domain-specific training.
      </p>
      <p>
        Where the BIS paper tested a single LLM agent's ability to make prudent liquidity
        decisions, SimCash asks the next question: what happens when <em>multiple</em> AI agents
        interact strategically? The answer involves coordination games, free-riding, and the
        surprising role of statistical evaluation in promoting cooperation.
      </p>
      <p>
        The simulation engine is built in Rust for speed and determinism, with a Python
        orchestration layer using PyO3 FFI. This work sits at the intersection of AI agents
        for economic research (Korinek, 2025) and computational game theory.
      </p>
    </DocPage>
  );
}

function HowItWorks() {
  return (
    <DocPage title="How the Simulator Works" subtitle="Ticks, queues, and settlement mechanics">
      <h3>Discrete-Time Simulation</h3>
      <p>
        Time in SimCash proceeds in <strong>ticks</strong> — atomic time units within a simulated
        trading day. A typical scenario has 12 ticks per day, representing the business hours of
        a payment system.
      </p>

      <h3>Payment Lifecycle</h3>
      <p>At each tick, the engine processes payments through these steps:</p>
      <ol>
        <li><strong>Arrivals</strong> — New payments arrive (stochastically or from a fixed schedule)</li>
        <li><strong>Policy Execution</strong> — Each bank's policy tree decides: Release or Hold each queued payment</li>
        <li><strong>Settlement</strong> — Released payments attempt RTGS settlement (requires sufficient balance)</li>
        <li><strong>Cost Accrual</strong> — Liquidity costs tick, delay costs accumulate on unsettled payments</li>
        <li><strong>End-of-Day</strong> — At the last tick, deadline penalties apply to unsettled payments</li>
      </ol>

      <h3>Two-Queue Architecture</h3>
      <p>
        The engine uses a two-queue design inspired by TARGET2:
      </p>
      <ul>
        <li><strong>Internal Queue (Q1)</strong> — Bank-controlled strategic queue. The policy tree decides what to release.</li>
        <li><strong>RTGS Queue (Q2)</strong> — Central system queue. Payments released from Q1 attempt immediate gross settlement.</li>
      </ul>

      <h3>Liquidity-Saving Mechanisms (LSM)</h3>
      <p>
        Optionally, the engine supports T2-compliant LSM features:
      </p>
      <ul>
        <li><strong>Bilateral Offsetting</strong> — Netted settlement when two banks owe each other</li>
        <li><strong>Multilateral Cycle Detection</strong> — Settles circular payment chains simultaneously</li>
      </ul>
      <p className="text-slate-500 text-xs">
        LSM features are available but not used in the current paper experiments.
      </p>

      <h3>Determinism</h3>
      <Callout type="info">
        SimCash is fully deterministic. Given the same seed and configuration, it produces
        byte-identical output. All randomness flows through a seeded xorshift64* RNG, and all
        money is represented as 64-bit integers (cents) — never floating point.
      </Callout>
    </DocPage>
  );
}

function CostModel() {
  return (
    <DocPage title="The Cost Model" subtitle="How banks are penalized — and why it matters">
      <p>
        The cost model creates the incentive structure that drives strategic behavior. It consists
        of three primary costs, ordered by severity:
      </p>

      <h3>1. Liquidity Cost (r<sub>c</sub>)</h3>
      <p>
        Proportional to committed funds per tick. Measured in basis points (bps). This represents
        the opportunity cost of holding reserves in the settlement account rather than investing
        them elsewhere.
      </p>
      <CodeBlock>{`cost = committed_balance × (bps / 10000) per tick`}</CodeBlock>
      <p>Default: 83 bps/tick. The cheapest cost — you always prefer committing liquidity over the alternatives.</p>

      <h3>2. Delay Cost (r<sub>d</sub>)</h3>
      <p>
        Charged per cent of unsettled payment per tick. Represents the cost of failing to
        settle a payment on time — client dissatisfaction, SLA penalties, reputational damage.
      </p>
      <CodeBlock>{`cost = unsettled_amount × rate per tick`}</CodeBlock>
      <p>Default: 0.2 per cent per tick. More expensive than liquidity cost.</p>

      <h3>3. Deadline Penalty (r<sub>b</sub>)</h3>
      <p>
        A flat fee for each payment that misses its individual deadline (each payment has
        a specific tick by which it should settle). This is the most expensive per-event cost,
        representing regulatory penalties or failed obligations.
      </p>
      <CodeBlock>{`cost = penalty_amount per unsettled payment`}</CodeBlock>
      <p>Default: $500 (50,000 cents) per payment. By far the most expensive.</p>

      <h3>The Ordering Constraint</h3>
      <Callout type="important">
        <strong>r<sub>c</sub> &lt; r<sub>d</sub> &lt; r<sub>b</sub></strong> — This constraint
        ensures rational behavior. Banks should always prefer committing liquidity (cheapest) over
        delaying payments (medium) over missing deadlines entirely (most expensive). If this ordering
        is violated, the incentives break down and optimal behavior becomes degenerate.
      </Callout>

      <h3>End-of-Day Penalty</h3>
      <p>
        A separate large penalty for any payment still unsettled when the day ends. Default: $1,000
        (100,000 cents). This creates a hard deadline for all payments.
      </p>

      <h3>Total Cost</h3>
      <p>
        Each agent's total cost is the sum across all ticks. The AI optimizer aims to minimize
        this total by choosing the right <code>initial_liquidity_fraction</code> — the fraction
        of the bank's liquidity pool to commit at the start of each day.
      </p>
    </DocPage>
  );
}

function PolicyOptimization() {
  return (
    <DocPage title="AI Policy Optimization" subtitle="How LLMs learn to be cash managers">
      <h3>The Multi-Day Loop</h3>
      <p>
        Each "game" runs for multiple simulated trading days. The optimization loop is:
      </p>
      <ol>
        <li>Day starts → banks commit liquidity according to their current policy</li>
        <li>Rust engine runs the full day (all ticks) with stochastic payment arrivals</li>
        <li>Day ends → costs tallied, events collected per agent</li>
        <li>AI analyzes each agent's results independently (information isolation)</li>
        <li>AI proposes improved policy (new <code>initial_liquidity_fraction</code> + decision tree)</li>
        <li>Optional: bootstrap evaluation compares new vs old policy statistically</li>
        <li>If accepted, next day uses new policy; if rejected, keeps old policy</li>
      </ol>

      <h3>Information Isolation</h3>
      <p>
        This is critical: each agent sees <strong>only its own</strong> costs, events, and
        transaction history. No counterparty balances, policies, or cost breakdowns. The only
        signal about other agents comes from incoming payment timing — just like in real RTGS
        systems where participants see settlement messages but not others' internal positions.
      </p>
      <Callout type="important">
        Crucially, agents are <strong>not told the environment is stationary</strong>. They don't
        know that iterations use the same payment parameters (or identical schedules in deterministic
        scenarios). Any regularity must be inferred from observed data. This is a realistic
        constraint — real cash managers don't have perfect knowledge of the data-generating process.
      </Callout>

      <h3>The Prompt</h3>
      <p>
        The PolicyOptimizer builds a 50,000+ token prompt containing:
      </p>
      <ul>
        <li>Current performance metrics and cost breakdown</li>
        <li>Verbose simulation output from best and worst performing seeds</li>
        <li>Full iteration history with acceptance status</li>
        <li>Parameter trajectories across iterations</li>
        <li>Optimization guidance based on cost analysis</li>
        <li>Policy schema (valid JSON structure)</li>
      </ul>

      <h3>Policy Format</h3>
      <p>
        The LLM outputs a JSON policy with two key components:
      </p>
      <CodeBlock>{`{
  "version": "2.0",
  "policy_id": "optimized_v5",
  "parameters": {
    "initial_liquidity_fraction": 0.085
  },
  "payment_tree": {
    "type": "condition", "field": "ticks_to_deadline",
    "operator": "<=", "value": 2,
    "true_branch": {"type": "action", "action": "Release"},
    "false_branch": {"type": "action", "action": "Hold"}
  },
  "bank_tree": {
    "type": "action", "action": "NoAction"
  }
}`}</CodeBlock>

      <h3>Constraint Validation</h3>
      <p>
        Every LLM output is validated against scenario constraints (parameter ranges, allowed
        fields, valid actions). Invalid policies trigger retry with error feedback — up to 3
        attempts before falling back to the current policy.
      </p>
    </DocPage>
  );
}

function Experiments() {
  return (
    <DocPage title="Experiments" subtitle="Replicating Castro et al. (2025)">
      <p>
        SimCash implements three canonical scenarios from Castro et al. (2025), each designed to
        test different aspects of multi-agent coordination:
      </p>

      <h3>Experiment 1: Asymmetric Equilibrium</h3>
      <table className="w-full text-sm">
        <tbody>
          <tr><td className="text-slate-400 pr-4">Ticks</td><td>2 per day</td></tr>
          <tr><td className="text-slate-400 pr-4">Payments</td><td>Asymmetric — A sends 15% at tick 1; B sends 15% at tick 0, 5% at tick 1</td></tr>
          <tr><td className="text-slate-400 pr-4">Mode</td><td>Deterministic-temporal</td></tr>
          <tr><td className="text-slate-400 pr-4">Expected</td><td>Asymmetric: A≈0%, B≈20%</td></tr>
          <tr><td className="text-slate-400 pr-4">Result</td><td>A=0.1%, B=17% — matches prediction ✓</td></tr>
        </tbody>
      </table>
      <p>
        Bank A free-rides on Bank B's liquidity provision. B must commit reserves to settle
        payments to A, which then gives A incoming liquidity to fund its own obligations.
      </p>

      <h3>Experiment 2: Stochastic Coordination</h3>
      <table className="w-full text-sm">
        <tbody>
          <tr><td className="text-slate-400 pr-4">Ticks</td><td>12 per day</td></tr>
          <tr><td className="text-slate-400 pr-4">Payments</td><td>Poisson arrivals (λ=2/tick), LogNormal amounts (μ=$100, σ=$50)</td></tr>
          <tr><td className="text-slate-400 pr-4">Mode</td><td>Bootstrap (50 paired samples)</td></tr>
          <tr><td className="text-slate-400 pr-4">Expected</td><td>Both agents 10–30%</td></tr>
          <tr><td className="text-slate-400 pr-4">Result</td><td>A≈5.7–8.5%, B≈5.8–6.3% across 3 passes (near-symmetric, lower than predicted)</td></tr>
        </tbody>
      </table>
      <p>
        The flagship experiment. Stochastic arrivals create genuine uncertainty, and bootstrap
        evaluation ensures statistical rigor in policy comparison.
      </p>

      <h3>Experiment 3: Symmetric Coordination</h3>
      <table className="w-full text-sm">
        <tbody>
          <tr><td className="text-slate-400 pr-4">Ticks</td><td>3 per day</td></tr>
          <tr><td className="text-slate-400 pr-4">Payments</td><td>Symmetric — both banks send 20% at ticks 0 and 1</td></tr>
          <tr><td className="text-slate-400 pr-4">Mode</td><td>Deterministic-temporal</td></tr>
          <tr><td className="text-slate-400 pr-4">Expected</td><td>Symmetric ≈20%</td></tr>
          <tr><td className="text-slate-400 pr-4">Result</td><td>Coordination failures in all 3 passes — one agent free-rides (1–10%) while the other overcommits (29–30%), but both end up worse off than the 50% baseline</td></tr>
        </tbody>
      </table>

      <Callout type="insight">
        The divergence between Experiments 2 and 3 is revealing: stochastic environments with
        statistical evaluation produce better coordination than deterministic environments.
        Bootstrap evaluation acts as a kind of "hedge" against greedy exploitation.
      </Callout>

      <h3>Methodology Differences from Castro et al.</h3>
      <ul>
        <li><strong>Optimization</strong>: Castro uses REINFORCE (neural network policy gradient); we use LLM reasoning</li>
        <li><strong>Action space</strong>: Castro discretizes to 21 values; LLM proposes continuous values in [0,1]</li>
        <li><strong>Convergence</strong>: Castro monitors training loss; we use explicit policy stability or multi-criteria statistical convergence</li>
        <li><strong>Agent dynamics</strong>: Castro trains simultaneously; we optimize sequentially within iterations</li>
      </ul>
    </DocPage>
  );
}

function GameTheory() {
  return (
    <DocPage title="Game Theory Primer" subtitle="Nash equilibria, coordination, and free-riding">
      <h3>The Coordination Game</h3>
      <p>
        RTGS liquidity management is a <strong>coordination game</strong>. Each bank's optimal
        strategy depends on what other banks do. Unlike zero-sum games, there are mutual gains
        from coordination — if all banks commit appropriate liquidity, everyone benefits from
        faster settlement and lower delay costs.
      </p>

      <h3>Nash Equilibrium</h3>
      <p>
        A Nash equilibrium is a strategy profile where no player can improve their outcome by
        unilaterally changing their strategy. In payment systems, this means: given what every
        other bank is doing, each bank's liquidity allocation is already optimal for them.
      </p>
      <p>
        Castro et al. (2025) characterize the equilibria for several stylized scenarios. Our
        experiments test whether LLM agents can <em>discover</em> these equilibria through
        independent optimization without any explicit game-theoretic reasoning.
      </p>

      <h3>Free-Riding</h3>
      <p>
        A persistent phenomenon in our experiments: when one bank commits lots of liquidity, its
        payments to counterparties settle quickly, giving those counterparties incoming cash. The
        counterparties can then get away with committing less of their own liquidity — they're
        "free-riding" on the generous bank's reserves.
      </p>

      <h3>Pareto Efficiency</h3>
      <p>
        A stable outcome isn't necessarily a <em>good</em> outcome. A Pareto-efficient allocation
        means no one can be made better off without making someone worse off. Our coordination
        failures in Experiment 3 show agents converging to Pareto-<em>dominated</em> outcomes —
        both agents could be better off, but neither has an individual incentive to change.
      </p>

      <h3>Stochastic Environments Help</h3>
      <Callout type="insight">
        Stochastic payment arrivals + bootstrap evaluation seem to discourage free-riding.
        The statistical evaluation introduces a form of "noise" that makes greedy exploitation
        harder to sustain, pushing agents toward more symmetric, cooperative allocations.
      </Callout>

      <h3>AI Agents as Game Players</h3>
      <p>
        SimCash's agents follow what Korinek (2025) describes as the core agent loop:
        {' '}<strong>Think → Act → Observe → Respond</strong>. Each iteration, the LLM reasons
        about its cost history (Think), proposes a new policy (Act), the simulation runs (Observe),
        and results feed back into the next iteration (Respond). Unlike traditional game-theoretic
        agents with explicit utility maximization, these agents reason in natural language —
        making them both more flexible and more prone to the kinds of bounded rationality
        that produce coordination failures.
      </p>
    </DocPage>
  );
}

function Architecture() {
  return (
    <DocPage title="Technical Architecture" subtitle="Rust, Python, and the FFI boundary">
      <h3>Stack Overview</h3>
      <CodeBlock>{`┌─────────────────────────────────────────────┐
│  Web Frontend (React + TypeScript + Vite)   │
│  • Interactive UI, WebSocket streaming      │
└──────────────────┬──────────────────────────┘
                   │ HTTP/WS
┌──────────────────▼──────────────────────────┐
│  Web Backend (FastAPI)                      │
│  • Game orchestration, LLM calls            │
│  • PolicyOptimizer, bootstrap evaluation    │
└──────────────────┬──────────────────────────┘
                   │ PyO3 FFI
┌──────────────────▼──────────────────────────┐
│  Rust Simulation Engine                     │
│  • Tick loop, RTGS settlement, LSM          │
│  • Deterministic RNG, i64 arithmetic        │
└─────────────────────────────────────────────┘`}</CodeBlock>

      <h3>Design Principles</h3>
      <ul>
        <li><strong>Rust owns state; Python orchestrates.</strong> The simulation engine is a Rust library compiled as a Python extension via PyO3.</li>
        <li><strong>FFI boundary is minimal.</strong> Only primitives cross the boundary. Policies enter as JSON strings, results come back as dicts.</li>
        <li><strong>Money is i64.</strong> All monetary values are 64-bit integers representing cents. No floating-point arithmetic, no rounding errors.</li>
        <li><strong>Determinism is sacred.</strong> Same seed = identical output, always. The RNG is xorshift64*, and seeds are persisted after each use.</li>
        <li><strong>Replay identity.</strong> Running a simulation and replaying from checkpoint produce byte-identical output.</li>
      </ul>

      <h3>Policy Pipeline</h3>
      <p>How an LLM decision becomes a simulated outcome:</p>
      <ol>
        <li>LLM generates JSON policy (via PolicyOptimizer)</li>
        <li>ConstraintValidator checks against scenario constraints</li>
        <li>Extract <code>initial_liquidity_fraction</code> → set on agent config</li>
        <li>Wrap policy tree → <code>{`{"type": "InlineJson", "json_string": "..."}`}</code></li>
        <li><code>SimulationConfig.from_dict()</code> → <code>to_ffi_dict()</code></li>
        <li><code>Orchestrator.new(ffi_config)</code> → run ticks</li>
      </ol>

      <h3>LLM Configuration</h3>
      <p>
        The paper experiments used GPT-5.2 with reasoning effort <code>high</code>,
        temperature 0.5, and up to 50 iterations per experiment pass. Each experiment
        was run 3 times (independent passes) to assess reproducibility. The web sandbox
        defaults to mock mode for zero-cost exploration, with optional real LLM mode
        using the same model configuration.
      </p>

      <h3>Performance</h3>
      <p>
        The Rust engine achieves 1,000+ ticks/second and has been tested at 200+ agents.
        A typical 12-tick scenario with 2 banks runs in under 1ms. Bootstrap evaluation
        (50 samples × 2 policies) completes in ~100ms.
      </p>
    </DocPage>
  );
}

/* ─── Blog Posts ─── */

function BlogConvergence() {
  return (
    <DocPage title="Do LLM Agents Converge?" subtitle="Watching AI discover stable payment strategies" isBlog date="2026-02-17">
      <p className="text-slate-400 italic">
        Coming soon — this post will analyze convergence behavior across all three experiments,
        comparing LLM agent trajectories with the theoretical equilibria from Castro et al. (2025).
      </p>

      <h3>Topics to Cover</h3>
      <ul>
        <li>Convergence speed: Experiments 1 and 3 converge in 7–12 iterations; Experiment 2 hits the 50-iteration budget</li>
        <li>The role of evaluation mode: deterministic-temporal vs bootstrap</li>
        <li>Does GPT-5.2's reasoning effort matter? Comparing <code>high</code> vs <code>low</code></li>
        <li>Reproducibility: 3 independent passes per experiment</li>
        <li>Comparison with Castro's REINFORCE training curves</li>
      </ul>
    </DocPage>
  );
}

function BlogCoordination() {
  return (
    <DocPage title="Coordination Failures in Symmetric Games" subtitle="When stable isn't optimal" isBlog date="2026-02-17">
      <p className="text-slate-400 italic">
        Coming soon — this post will explore the coordination failures observed in Experiment 3,
        where agents converge to Pareto-dominated outcomes despite having symmetric positions.
      </p>

      <h3>Topics to Cover</h3>
      <ul>
        <li>What makes a coordination failure? Defining Pareto dominance in this context</li>
        <li>The "early mover" effect: which agent becomes the free-rider is determined by early aggressive moves</li>
        <li>Why stochastic environments produce better coordination than deterministic ones</li>
        <li>Implications for real RTGS systems: does this match observed bank behavior?</li>
        <li>Can prompt engineering prevent coordination failures?</li>
      </ul>
    </DocPage>
  );
}

function BlogBootstrap() {
  return (
    <DocPage title="Bootstrap Evaluation: Why and How" subtitle="Statistical rigor in policy comparison" isBlog date="2026-02-17">
      <p className="text-slate-400 italic">
        Coming soon — this post will explain the bootstrap paired comparison methodology,
        the 3-agent sandbox design, and why it matters for getting good results.
      </p>

      <h3>Topics to Cover</h3>
      <ul>
        <li>The problem: single-simulation comparison is unreliable under stochastic arrivals</li>
        <li>Paired comparison: evaluate both policies on the same N samples to eliminate noise</li>
        <li>The 3-agent sandbox (SOURCE → AGENT → SINK): why isolation helps</li>
        <li>Settlement timing as a sufficient statistic for the liquidity environment</li>
        <li>Risk-adjusted acceptance: mean improvement + CI doesn't cross zero + CV &lt; 0.5</li>
        <li>Known limitations: bootstrap variance can overestimate sensitivity to timing</li>
        <li>Alternatives: block bootstrap, day-level bootstrap, held-out seed evaluation</li>
      </ul>
    </DocPage>
  );
}

/* ─── Reference ─── */

function References() {
  return (
    <DocPage title="References & Reading" subtitle="Papers, documentation, and further resources">
      <h3>Primary References</h3>
      <ul className="space-y-3">
        <li>
          <strong>Castro et al. (2025)</strong>.{' '}
          <em>"AI agents for cash management in payment systems."</em>{' '}
          BIS Working Paper No. 1310.{' '}
          <a href="https://www.bis.org/publ/work1310.pdf" target="_blank" rel="noopener" className="text-sky-400 hover:underline">
            PDF ↗
          </a>
          <p className="text-sm text-slate-500 mt-1">
            The foundational paper. Tests whether gen AI can perform intraday liquidity management
            in a wholesale payment system. SimCash replicates and extends their experiments.
          </p>
        </li>
        <li>
          <strong>Korinek, A. (2025)</strong>.{' '}
          <em>"AI Agents for Economic Research."</em>{' '}
          August 2025 update to <em>"Generative AI for Economic Research"</em> (JEL, 2023).{' '}
          <a href="https://www.aeaweb.org/content/file?id=23290" target="_blank" rel="noopener" className="text-sky-400 hover:underline">
            PDF ↗
          </a>
          <p className="text-sm text-slate-500 mt-1">
            Demystifies AI agents for economists — covering autonomous LLM systems with planning, tool use,
            and multi-step task execution. Shows how to build research agents using "vibe coding" and
            frameworks like LangGraph. Directly relevant to SimCash's approach of using LLM agents as
            autonomous policy optimizers.
          </p>
        </li>
      </ul>

      <h3>Background Reading</h3>
      <ul className="space-y-3">
        <li>
          <strong>ECB TARGET Services</strong>.{' '}
          <em>T2 (formerly TARGET2) RTGS System.</em>
          <p className="text-sm text-slate-500 mt-1">
            The real-world system that SimCash's settlement mechanics are modeled on.
            T2 is the Eurosystem's RTGS system for large-value euro payments.
            SimCash implements T2-compliant liquidity-saving mechanisms.
          </p>
        </li>
        <li>
          <strong>Liquidity-Saving Mechanisms (LSM)</strong>.
          <p className="text-sm text-slate-500 mt-1">
            Bilateral offsetting and multilateral cycle detection — the algorithms that let
            banks settle with less liquidity by netting mutual obligations.
          </p>
        </li>
      </ul>

      <h3>SimCash Documentation</h3>
      <ul className="space-y-2">
        <li>
          <a href="https://github.com/aerugo/SimCash" target="_blank" rel="noopener" className="text-sky-400 hover:underline">
            GitHub Repository ↗
          </a>{' '}
          — Source code, README, and development guidelines
        </li>
        <li>
          <a href="https://github.com/aerugo/SimCash/tree/main/docs/reference" target="_blank" rel="noopener" className="text-sky-400 hover:underline">
            Reference Documentation ↗
          </a>{' '}
          — 80+ pages covering CLI, experiments, AI cash management, policy DSL
        </li>
        <li>
          <a href="https://github.com/aerugo/SimCash/blob/main/docs/game_concept_doc.md" target="_blank" rel="noopener" className="text-sky-400 hover:underline">
            Game Concept Document ↗
          </a>{' '}
          — The "why" behind the simulation
        </li>
      </ul>

      <h3>Key Concepts Glossary</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700">
            <th className="text-left py-2 text-slate-300">Term</th>
            <th className="text-left py-2 text-slate-300">Definition</th>
          </tr>
        </thead>
        <tbody className="text-slate-400">
          <tr className="border-b border-slate-800"><td className="py-2 pr-4 font-mono text-sky-400">RTGS</td><td>Real-Time Gross Settlement — each payment settles individually in real time</td></tr>
          <tr className="border-b border-slate-800"><td className="py-2 pr-4 font-mono text-sky-400">LSM</td><td>Liquidity-Saving Mechanism — bilateral/multilateral netting to reduce liquidity needs</td></tr>
          <tr className="border-b border-slate-800"><td className="py-2 pr-4 font-mono text-sky-400">initial_liquidity_fraction</td><td>The key parameter: what fraction of the pool to commit (0.0–1.0)</td></tr>
          <tr className="border-b border-slate-800"><td className="py-2 pr-4 font-mono text-sky-400">Bootstrap</td><td>Statistical resampling to compare policies across multiple samples</td></tr>
          <tr className="border-b border-slate-800"><td className="py-2 pr-4 font-mono text-sky-400">Paired comparison</td><td>Evaluating both policies on identical samples to cancel noise</td></tr>
          <tr className="border-b border-slate-800"><td className="py-2 pr-4 font-mono text-sky-400">Nash equilibrium</td><td>Strategy profile where no player gains from unilateral deviation</td></tr>
          <tr className="border-b border-slate-800"><td className="py-2 pr-4 font-mono text-sky-400">Pareto efficiency</td><td>No player can be made better off without making another worse off</td></tr>
          <tr><td className="py-2 pr-4 font-mono text-sky-400">Free-riding</td><td>Exploiting others' liquidity commitment while minimizing your own</td></tr>
        </tbody>
      </table>
    </DocPage>
  );
}

/* ─── Shared Components ─── */

function DocPage({ title, subtitle, isBlog, date, children }: {
  title: string;
  subtitle: string;
  isBlog?: boolean;
  date?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      {isBlog && (
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs bg-violet-500/20 text-violet-400 px-2 py-0.5 rounded-full">Blog</span>
          {date && <span className="text-xs text-slate-500">{date}</span>}
        </div>
      )}
      <h1 className="text-2xl font-bold text-slate-100 mb-1">{title}</h1>
      <p className="text-slate-400 mb-6">{subtitle}</p>
      <div className="space-y-4 text-slate-300 leading-relaxed [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:text-slate-200 [&_h3]:mt-8 [&_h3]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:space-y-1 [&_li]:text-slate-300 [&_a]:text-sky-400 [&_a]:hover:underline [&_code]:text-sky-400 [&_code]:bg-slate-800 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_table]:border-collapse [&_table]:w-full [&_td]:py-1.5 [&_td]:pr-4 [&_td]:text-sm">
        {children}
      </div>
    </div>
  );
}

function Callout({ type, children }: { type: 'info' | 'important' | 'insight'; children: React.ReactNode }) {
  const styles = {
    info: 'border-sky-500/30 bg-sky-500/5',
    important: 'border-amber-500/30 bg-amber-500/5',
    insight: 'border-violet-500/30 bg-violet-500/5',
  };
  const icons = { info: 'ℹ️', important: '⚠️', insight: '💡' };

  return (
    <div className={`border-l-4 rounded-r-lg p-4 my-4 text-sm ${styles[type]}`}>
      <span className="mr-2">{icons[type]}</span>
      {children}
    </div>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="bg-slate-900 border border-slate-700 rounded-lg p-4 text-xs font-mono text-slate-300 overflow-x-auto my-4 whitespace-pre">
      {children}
    </pre>
  );
}
